import json
import os
import subprocess
import sys
import time
from pathlib import Path

import pytest

from matchlens.domain import AnalysisRequest, ClipRequest, MatchCreate, now, uid
from matchlens.exports import clip, report, source_parts
from matchlens.media import probe, register_import, run_media, sha256
from matchlens.pipeline import analyze
from matchlens.review import snapshot


@pytest.fixture
def video_match(store):
    match_id = store.create(MatchCreate(title="Media fixture", profile="synthetic"))["id"]
    staged = store.path(match_id, "temporary/input.mp4")
    run_media(
        [
            store.settings.ffmpeg,
            "-v",
            "error",
            "-y",
            "-f",
            "lavfi",
            "-i",
            "testsrc2=size=320x180:rate=30",
            "-f",
            "lavfi",
            "-i",
            "sine=frequency=440:sample_rate=48000",
            "-t",
            "6",
            "-c:v",
            "libx264",
            "-threads",
            "2",
            "-pix_fmt",
            "yuv420p",
            "-c:a",
            "aac",
            str(staged),
        ]
    )
    source = register_import(store, match_id, staged, "fixture.mp4")
    return match_id, source


def make_job(store, mid, source, cancel=False, job_id=None):
    job = {
        "id": job_id or uid(),
        "kind": "analysis",
        "status": "running",
        "created": now(),
        "heartbeat": now(),
        "cancel": cancel,
        "progress": 0,
        "config": AnalysisRequest(source_id=source["id"], detector="synthetic", sample_fps=5).model_dump(),
    }
    store.put_job(mid, job)
    return job


def test_original_resume_and_export(store, video_match):
    mid, source = video_match
    original = store.path(mid, source["path"])
    checksum = sha256(original)
    job = make_job(store, mid, source, cancel=True)
    analyze(store, mid, job)
    saved = store.job(mid, job["id"])
    assert saved["status"] == "paused"
    assert saved["checkpoint"]["frames"] == 10
    first = store.frames(mid)
    saved.update(status="running", cancel=False)
    store.put_job(mid, saved)
    analyze(store, mid, saved)
    frames = store.frames(mid)
    assert len(frames) == 30
    assert frames[:10] == first
    uninterrupted = make_job(store, mid, source)
    analyze(store, mid, uninterrupted)
    assert store.active_runs(mid)[source["id"]] == saved["id"]
    store.activate(mid, source["id"], uninterrupted["id"])
    baseline = store.frames(mid)

    def normalize(rows):
        return [
            {**f, "run_id": "run", "tracks": [{**t, "id": t["id"].split("-")[-1]} for t in f["tracks"]]}
            for f in rows
        ]

    assert normalize(frames) == normalize(baseline)
    assert sha256(original) == checksum
    export_job = {
        "id": uid(),
        "config": ClipRequest(start=1, end=3, title="Exact clip").model_dump(),
        "snapshot": snapshot(store, mid),
    }
    artifact = clip(store, mid, export_job)
    exported = store.path(mid, artifact["files"]["highlight.mp4"])
    assert probe(exported, store.settings)["duration"] == pytest.approx(2, abs=1 / 30 + 0.005)
    result = report(store, mid)
    contents = json.loads(store.path(mid, result["files"]["match.json"]).read_text())
    assert contents["match"]["revision"] == result["revision"]
    assert "No media was uploaded" in store.path(mid, result["files"]["report.html"]).read_text()
    assert sha256(original) == checksum


def test_corrupt_source_is_rejected_without_modification(store, match):
    staged = store.path(match, "temporary/corrupt.mp4")
    staged.write_bytes(b"not a movie")
    with pytest.raises(ValueError):
        register_import(store, match, staged, "corrupt.mp4")
    assert staged.read_bytes() == b"not a movie"


def test_clip_cannot_hide_gap():
    source = {"segments": [{"path": "a", "start": 0, "end": 5}, {"path": "b", "start": 8, "end": 10}]}
    with pytest.raises(ValueError, match="gap"):
        source_parts(source, 2, 9)
    assert source_parts(source, 1, 4) == [("a", 1, 4)]


def test_resume_rejects_changed_provenance(store, video_match):
    mid, source = video_match
    job = make_job(store, mid, source, cancel=True)
    analyze(store, mid, job)
    saved = store.job(mid, job["id"])
    saved["provenance"]["pipeline"] = "different"
    with pytest.raises(ValueError, match="changed since checkpoint"):
        analyze(store, mid, saved)


def test_report_is_pinned_and_jobs_do_not_embed_snapshots(store, match):
    from matchlens.domain import Correction
    from matchlens.review import correct

    pinned = snapshot(store, match)
    store.put_job(
        match, {"id": uid(), "kind": "report", "status": "queued", "config": {}, "snapshot": pinned}
    )
    correct(
        store,
        match,
        Correction(
            revision=0,
            operation="event",
            payload={"kind": "goal", "start": 3, "team": "home", "status": "confirmed"},
        ),
    )
    assert snapshot(store, match)["statistics"]["score"]["home"] == 1
    assert "snapshot" not in snapshot(store, match)["jobs"][0]
    artifact = report(store, match, pinned)
    result = json.loads(store.path(match, artifact["files"]["match.json"]).read_text())
    assert result["statistics"]["score"]["home"] == 0
    assert artifact["revision"] == 0


def test_portrait_rotation_decoder(store, video_match):
    from matchlens.decoder import buffered_frames

    mid, source = video_match
    rotated = store.path(mid, "temporary/rotated.mp4")
    run_media(
        [
            store.settings.ffmpeg,
            "-v",
            "error",
            "-y",
            "-display_rotation:v:0",
            "90",
            "-i",
            str(store.path(mid, source["path"])),
            "-c",
            "copy",
            str(rotated),
        ]
    )
    assert abs(probe(rotated, store.settings)["rotation"]) == 90
    stream = buffered_frames(rotated, 1)
    try:
        _, frame, _, _ = next(stream)
        assert frame.shape[:2] == (320, 180)
    finally:
        stream.close()


def test_phone_spool_produces_decodable_segments(store, match):
    from fastapi.testclient import TestClient

    from matchlens.jobs import Supervisor
    from matchlens.phone import create_pair, receiver_app

    input_path = store.path(match, "temporary/phone.webm")
    run_media(
        [
            store.settings.ffmpeg,
            "-v",
            "error",
            "-y",
            "-f",
            "lavfi",
            "-i",
            "testsrc2=size=320x180:rate=15",
            "-t",
            "6",
            "-c:v",
            "libvpx",
            "-threads",
            "2",
            "-deadline",
            "realtime",
            str(input_path),
        ]
    )
    data = input_path.read_bytes()
    pairing = create_pair(store, Supervisor(store), match)
    with TestClient(receiver_app(store.settings)) as client:
        headers = {"x-pair-secret": pairing["secret"]}
        for sequence, start in enumerate(range(0, len(data), 16384)):
            assert (
                client.post(
                    f"/ingest/{pairing['pair_id']}/{sequence}",
                    headers=headers,
                    content=data[start : start + 16384],
                ).status_code
                == 200
            )
        assert client.post(f"/finish/{pairing['pair_id']}", headers=headers).status_code == 200
    env = {**os.environ, "PYTHONPATH": str(Path(__file__).resolve().parents[1] / "src")}
    subprocess.run(
        [sys.executable, "-m", "matchlens.worker", str(store.settings.data_dir), match, pairing["job_id"]],
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        timeout=30,
        check=True,
    )
    job = store.job(match, pairing["job_id"])
    assert job["status"] == "complete", job.get("error")
    source = store.source(match, job["config"]["source_id"])
    assert source["duration"] == pytest.approx(6, abs=0.2)
    assert len(source["segments"]) >= 3
    for segment in source["segments"]:
        assert probe(store.path(match, segment["path"]), store.settings)["duration"] > 0
    assert store.path(match, job["config"]["spool"]).read_bytes() == data


def test_recording_survives_analysis_failure(store, match):
    source = {
        "id": uid(),
        "kind": "test",
        "duration": 0,
        "status": "recording",
        "segments": [],
        "name": "test",
        "offset": 0,
    }
    store.put_source(match, source)
    capture_id = uid()
    store.put_job(
        match,
        {
            "id": capture_id,
            "kind": "capture",
            "status": "running",
            "created": now(),
            "heartbeat": now(),
            "cancel": False,
            "config": {"kind": "test", "source_id": source["id"]},
        },
    )
    env = {**os.environ, "PYTHONPATH": str(Path(__file__).resolve().parents[1] / "src")}
    proc = subprocess.Popen(
        [sys.executable, "-m", "matchlens.worker", str(store.settings.data_dir), match, capture_id],
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        deadline = time.monotonic() + 20
        while time.monotonic() < deadline and len(store.source(match, source["id"]).get("segments", [])) < 1:
            if proc.poll() is not None:
                pytest.fail(store.job(match, capture_id).get("error", "Capture exited"))
            time.sleep(0.2)
        before = len(store.source(match, source["id"])["segments"])
        assert before >= 1
        failed = make_job(store, match, source)
        failed["config"]["detector"] = "missing-model"
        store.put_job(match, failed)
        # Run a real failed analysis worker while the independent recorder continues.
        result = subprocess.run(
            [sys.executable, "-m", "matchlens.worker", str(store.settings.data_dir), match, failed["id"]],
            env=env,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=15,
        )
        assert result.returncode == 0
        assert store.job(match, failed["id"])["status"] == "failed"
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline and len(store.source(match, source["id"])["segments"]) <= before:
            time.sleep(0.2)
        assert len(store.source(match, source["id"])["segments"]) > before
        job = store.job(match, capture_id)
        job["cancel"] = True
        store.put_job(match, job)
        proc.wait(timeout=15)
        segments = store.source(match, source["id"])["segments"]
        assert store.job(match, capture_id)["status"] == "complete"
        for segment in segments:
            meta = probe(store.path(match, segment["path"]), store.settings)
            assert meta["duration"] > 0
            assert meta["has_audio"]
        for a, b in zip(segments, segments[1:]):
            assert abs(b["start"] - a["end"]) < 0.1
    finally:
        if proc.poll() is None:
            import psutil

            children = psutil.Process(proc.pid).children(recursive=True)
            for child in children:
                child.terminate()
            proc.terminate()
            proc.wait(timeout=5)


def test_reviewed_cuts_and_replays_are_snapshotted_in_analysis(store, video_match):
    mid, source = video_match
    job = make_job(store, mid, source)
    job["config"]["reviewed_intervals"] = [
        {"kind": "camera_cut", "start": 1, "end": 1.1},
        {"kind": "replay", "start": 2, "end": 3},
    ]
    analyze(store, mid, job)
    frames = store.frames(mid)
    cut = next(f for f in frames if abs(f["time"] - 1) < 0.01)
    assert cut["scene_cut"] and cut["last_cut"] == pytest.approx(1)
    excluded = [f for f in frames if 2 <= f["time"] < 3]
    assert excluded and all(f["reviewed_excluded"] and f["tracks"] == [] for f in excluded)
    assert job["provenance"]["reviewed_intervals"] == job["config"]["reviewed_intervals"]


def test_vfr_uses_media_pts_and_preserves_skipped_timestamps(store, match):
    from matchlens.decoder import buffered_frames

    staged = store.path(match, "temporary/vfr.mp4")
    run_media(
        [
            store.settings.ffmpeg,
            "-v",
            "error",
            "-y",
            "-f",
            "lavfi",
            "-i",
            "testsrc2=size=320x180:rate=30:duration=2",
            "-vf",
            "select='if(lt(t,1),not(mod(n,2)),not(mod(n,5)))'",
            "-fps_mode",
            "vfr",
            "-c:v",
            "libx264",
            "-threads",
            "2",
            str(staged),
        ]
    )
    rows = list(buffered_frames(staged, 30))
    times = [r[0] for r in rows]
    assert len(rows) == 21
    assert times[1] - times[0] == pytest.approx(2 / 30, abs=0.001)
    assert times[-1] - times[-2] == pytest.approx(5 / 30, abs=0.001)
    assert all(
        t == pytest.approx(pts * float(__import__("fractions").Fraction(tb))) for t, _, pts, tb in rows
    )


def test_analysis_queue_bounds_high_resolution_payload(store, match):
    from matchlens.decoder import buffered_frames

    staged = store.path(match, "temporary/4k.mp4")
    run_media(
        [
            store.settings.ffmpeg,
            "-v",
            "error",
            "-y",
            "-f",
            "lavfi",
            "-i",
            "color=c=green:size=3840x2160:rate=1:duration=1",
            "-c:v",
            "libx264",
            "-threads",
            "2",
            str(staged),
        ]
    )
    before = sha256(staged)
    rows = list(buffered_frames(staged, 1))
    assert rows[0][1].shape == (1440, 2560, 3)
    assert probe(staged, store.settings)["width"] == 3840
    assert sha256(staged) == before


def test_truncated_copy_rejected_without_touching_original(store, video_match):
    mid, source = video_match
    original = store.path(mid, source["path"])
    checksum = sha256(original)
    copied = store.path(mid, "temporary/truncated.mp4")
    copied.write_bytes(original.read_bytes()[: original.stat().st_size // 2])
    with pytest.raises(ValueError):
        register_import(store, mid, copied, "truncated.mp4")
    assert sha256(original) == checksum

from __future__ import annotations

import json
import time

import cv2
import numpy as np
import psutil

from .decoder import buffered_frames
from .domain import now
from .live import live_policy
from .media import quality, sha256
from .profiles import profile_id
from .sports import SoccerCandidates
from .storage import Store, encode
from .television import MovementGuard, original_box, rectify
from .tracking import Tracker
from .vision import detector_for


def analyze(store: Store, match_id: str, job: dict):
    config = job["config"]
    source = store.source(match_id, config["source_id"])
    detector = detector_for(config["detector"], store.settings, config.get("provider", "cpu"))
    checkpoint = job.get("checkpoint", {})
    television = config.get("television")
    guard = None
    tv_invalid = checkpoint.get("tv_invalid", False)
    if television:
        reference_path = store.path(match_id, television["reference"])
        if sha256(reference_path) != television["reference_sha256"]:
            raise ValueError("Television reference frame changed; start a new reviewed setup")
        guard = MovementGuard(cv2.imread(str(reference_path)), television)
        guard.invalid = tv_invalid
    tracker = Tracker(job["id"][:8], checkpoint.get("tracker"))
    candidates = SoccerCandidates(checkpoint.get("events"))
    last = checkpoint.get("time", -1.0)
    frames_count = checkpoint.get("frames", 0)
    requested_fps = config["sample_fps"]
    fps = checkpoint.get("fps", requested_fps)
    processed_segments = set(checkpoint.get("segments", []))
    skipped = list(checkpoint.get("skipped", []))
    visualizations = checkpoint.get("visualizations", True)
    last_cut = checkpoint.get("last_cut", -1.0)
    started, accumulated = time.monotonic(), checkpoint.get("wall_seconds", 0.0)
    previous_thumb = np.array(checkpoint["thumbnail"]) if checkpoint.get("thumbnail") is not None else None
    batch, proposals = [], []
    run_id = job["id"]
    model_path = store.settings.data_dir / (
        "models/yolox_s.onnx" if config["detector"] == "yolox_s" else "models/yolox_tiny.onnx"
    )
    provenance = {
        "detector": detector.name,
        "model_sha256": sha256(model_path) if config["detector"] in ("yolox", "yolox_s") else None,
        "source_sha256": source.get("sha256"),
        "pipeline": "0.2.0",
        "sampling_fps": requested_fps,
        "accuracy": "unvalidated",
        "runtime": config.get("provider", "cpu"),
        "registered_providers": detector.session.get_providers() if hasattr(detector, "session") else [],
        "television": television,
        "setup_revision": config.get("setup_revision"),
        "source_id": source["id"],
        "source_profile": profile_id(source, store.get(match_id)["profile"]),
    }
    if checkpoint and job.get("provenance") and job["provenance"] != provenance:
        raise ValueError("Source/model/pipeline changed since checkpoint; start a new analysis run")
    if checkpoint and source.get("path") and source.get("sha256"):
        if sha256(store.path(match_id, source["path"])) != source["sha256"]:
            raise ValueError("Original media changed since import; resume refused")
    job["provenance"] = provenance
    # First analysis may be selected; subsequent runs require explicit version selection.
    if source["id"] not in store.active_runs(match_id):
        store.activate(match_id, source["id"], run_id)

    def flush():
        nonlocal batch, proposals
        elapsed = accumulated + time.monotonic() - started
        job["checkpoint"] = {
            "time": last,
            "frames": frames_count,
            "tracker": tracker.state,
            "events": candidates.state,
            "segments": sorted(processed_segments),
            "skipped": skipped,
            "fps": fps,
            "wall_seconds": elapsed,
            "last_cut": last_cut,
            "tv_invalid": tv_invalid,
            "visualizations": visualizations,
            "thumbnail": previous_thumb.tolist() if previous_thumb is not None else None,
        }
        job.update(
            heartbeat=now(),
            progress=min(1.0, max(0.0, last) / max(source.get("duration", 1), 1)),
            metrics={
                "processed_frames": frames_count,
                "wall_seconds": elapsed,
                "processed_fps": frames_count / max(elapsed, 0.001),
                "sample_fps": fps,
                "rss_mb": psutil.Process().memory_info().rss / 1024**2,
                "analysis_delay": max(0, source.get("duration", 0) - max(0, last))
                if config["live"]
                else None,
                "skipped_intervals": skipped,
                "visualizations": visualizations,
                "analysis_state": "reduced" if fps < requested_fps else "normal",
            },
        )
        with store.db(match_id) as db:
            db.execute("BEGIN IMMEDIATE")
            for frame in batch:
                db.execute(
                    "INSERT OR REPLACE INTO frames VALUES(?,?,?,?)",
                    (run_id, frame["time"], source["id"], encode(frame)),
                )
            for event in proposals:
                db.execute(
                    "INSERT OR REPLACE INTO proposals VALUES(?,?,?)", (event["id"], run_id, encode(event))
                )
            current = db.execute("SELECT data FROM jobs WHERE id=?", (run_id,)).fetchone()
            if current and json.loads(current[0]).get("cancel"):
                job["cancel"] = True
            db.execute("UPDATE jobs SET data=?,status=? WHERE id=?", (encode(job), job["status"], run_id))
        batch, proposals = [], []

    while True:
        source = store.source(match_id, source["id"])
        segments = source.get("segments", [])
        if not segments and source.get("path"):
            segments = [
                {
                    "path": source["path"],
                    "start": source.get("offset", 0),
                    "end": source.get("offset", 0) + source["duration"],
                    "id": source["id"],
                }
            ]
        pending = [s for s in segments if s["id"] not in processed_segments]
        if config["live"] and source.get("status") == "recording" and pending:
            newest = pending[-1]["end"]
            lag = newest - max(last, pending[0]["start"])
            policy = live_policy(lag, fps)
            fps, visualizations = policy.sample_fps, policy.visualizations
            if policy.recording_only:
                skipped.append([pending[0]["start"], pending[-1]["end"]])
                job.update(
                    status="paused",
                    error="Recording-only mode: analysis delay exceeded 60 s at minimum sampling. Run an offline pass after capture.",
                )
                flush()
                return
            if policy.skip_stale and len(pending) > 2:
                discarded = pending[:-2]
                skipped.append([discarded[0]["start"], discarded[-1]["end"]])
                processed_segments.update(s["id"] for s in discarded)
                pending = pending[-2:]
                tracker.reset()
        for segment in pending:
            offset = segment["start"]
            after = last - offset if last >= offset else -1
            for t, image, pts, timebase in buffered_frames(store.path(match_id, segment["path"]), fps, after):
                timestamp = offset + t
                if timestamp <= last + 1e-6:
                    continue
                thumb = cv2.resize(cv2.cvtColor(image, cv2.COLOR_BGR2GRAY), (64, 36))
                flags = quality(image)
                cut = (
                    previous_thumb is not None
                    and float(np.mean(np.abs(thumb.astype(float) - previous_thumb))) > 45
                )
                if cut:
                    tracker.reset()
                    last_cut = timestamp
                    flags.append("Camera movement/cut: identities reset; review calibration validity")
                previous_thumb = thumb.astype(float)
                analysis_image = image
                allow_detection = True
                if guard and timestamp >= television["start"]:
                    movement = guard.check(image)
                    if movement == "moved":
                        if not tv_invalid:
                            tracker.reset()
                            last_cut = timestamp
                        tv_invalid = True
                        allow_detection = False
                        flags.append(
                            "Television/phone moved: rectification invalid; recording continues. Mark corners and start a new run."
                        )
                    elif movement == "obscured":
                        allow_detection = False
                        flags.append(
                            "Television surroundings obscured or alignment uncertain: inference withheld"
                        )
                    elif movement == "unavailable":
                        flags.append(
                            "Television movement check unavailable: insufficient static surroundings; verify alignment manually"
                        )
                    analysis_image = rectify(image, television)
                detections = detector.detect(analysis_image) if allow_detection else []
                if guard and timestamp >= television["start"]:
                    for detection in detections:
                        detection.box = original_box(detection.box, television, image.shape)

                tracks = tracker.update(detections, timestamp)
                frame = {
                    "schema": 1,
                    "run_id": run_id,
                    "source_id": source["id"],
                    "time": timestamp,
                    "source_pts": pts,
                    "time_base": timebase,
                    "tracks": tracks,
                    "warnings": flags,
                    "sample_interval": 1 / fps,
                    "scene_cut": cut,
                    "last_cut": last_cut,
                    "television_valid": not tv_invalid if television else None,
                    "analysis_coordinate_space": "displayed_original_normalized",
                    "width": image.shape[1],
                    "height": image.shape[0],
                }
                batch.append(frame)
                if config["experimental_events"]:
                    proposals.extend(candidates.update(tracks, timestamp, source["id"], run_id))
                last, frames_count = timestamp, frames_count + 1
                if len(batch) >= 10:
                    flush()
                    if job.get("cancel"):
                        job["status"] = "paused"
                        flush()
                        return
            processed_segments.add(segment["id"])
            flush()
        if not config["live"] or source.get("status") != "recording":
            break
        flush()
        if job.get("cancel"):
            job["status"] = "paused"
            flush()
            return
        time.sleep(0.5)
    job.update(status="complete", progress=1.0, finished=now())
    flush()

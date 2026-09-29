"""Sustained generated capture/analysis in a disposable library. No hardware claim."""

import argparse
import json
import shutil
import tempfile
import time
from pathlib import Path

import psutil

from matchlens.config import Settings
from matchlens.domain import AnalysisRequest, MatchCreate
from matchlens.jobs import Supervisor
from matchlens.media import probe, run_media, sha256
from matchlens.storage import Store, atomic_json


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--seconds", type=int, default=7200)
    parser.add_argument("--model", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.seconds < 30 or args.seconds > 7200:
        parser.error("Use 30–7200 seconds; shortened runs do not qualify the 120-minute gate")
    with tempfile.TemporaryDirectory(prefix="matchlens-soak-") as directory:
        settings = Settings.load(directory)
        store = Store(settings)
        shutil.copyfile(args.model, settings.data_dir / "models/yolox_tiny.onnx")
        info = store.create(MatchCreate(title="Synthetic recording soak", profile="synthetic"))
        mid = info["id"]
        source = {
            "id": "soak-source",
            "kind": "test",
            "profile": "synthetic",
            "duration": 0,
            "offset": 0,
            "status": "recording",
            "segments": [],
            "name": "Generated testsrc2 + sine",
        }
        store.put_source(mid, source)
        supervisor = Supervisor(store)
        capture = supervisor.enqueue(mid, "capture", {"source_id": source["id"], "kind": "test"})
        analysis = supervisor.enqueue(
            mid, "analysis", AnalysisRequest(source_id=source["id"], detector="yolox", live=True).model_dump()
        )
        supervisor.start()
        start = time.monotonic()
        measurements = []
        injected = False
        segments_before_crash = None
        try:
            while time.monotonic() - start < args.seconds:
                jobs = store.jobs(mid)
                capt = store.job(mid, capture["id"])
                an = store.job(mid, analysis["id"])
                source = store.source(mid, source["id"])
                if capt["status"] == "failed":
                    raise AssertionError(capt.get("error"))
                processes = []
                for j in jobs:
                    if j.get("pid") and psutil.pid_exists(j["pid"]):
                        try:
                            process = psutil.Process(j["pid"])
                            processes += [process, *process.children(recursive=True)]
                        except psutil.NoSuchProcess:
                            pass
                rss = 0
                for process in processes:
                    try:
                        rss += process.memory_info().rss
                    except psutil.NoSuchProcess:
                        pass
                measurements.append(
                    {
                        "elapsed": time.monotonic() - start,
                        "segments": len(source["segments"]),
                        "recorded_seconds": source.get("duration", 0),
                        "bytes": source.get("bytes", 0),
                        "total_worker_rss_mb": rss / 1024**2,
                        "analysis_delay": an.get("metrics", {}).get("analysis_delay"),
                        "analysis_state": an["status"],
                    }
                )
                if not injected and time.monotonic() - start > args.seconds / 2 and an.get("pid"):
                    psutil.Process(an["pid"]).kill()
                    segments_before_crash = len(source["segments"])
                    injected = True
                time.sleep(1)
            supervisor.cancel(mid, capture["id"])
            deadline = time.monotonic() + 20
            while time.monotonic() < deadline and store.job(mid, capture["id"])["status"] not in (
                "complete",
                "failed",
            ):
                time.sleep(0.2)
            source = store.source(mid, source["id"])
            assert injected and source["segments"] and len(source["segments"]) > segments_before_crash
            assert store.job(mid, capture["id"])["status"] == "complete"
            gaps = []
            for a, b in zip(source["segments"], source["segments"][1:]):
                if abs(b["start"] - a["end"]) > 0.1:
                    gaps.append([a["end"], b["start"]])
            hashes = []
            for segment in source["segments"]:
                path = store.path(mid, segment["path"])
                meta = probe(path, settings)
                assert meta["has_audio"], "Generated audio must survive capture normalization"
                run_media([settings.ffmpeg, "-v", "error", "-i", str(path), "-f", "null", "-"], 30)
                hashes.append(
                    {
                        "id": segment["id"],
                        "sha256": sha256(path),
                        "duration": meta["duration"],
                        "has_audio": meta["has_audio"],
                    }
                )
            result = {
                "schema": "matchlens-soak-1",
                "source_profile": "synthetic",
                "fixture": "FFmpeg testsrc2 + sine, real-time recording; actual YOLOX CPU worker",
                "requested_seconds": args.seconds,
                "recorded_seconds": source["duration"],
                "analysis_crash_injected": injected,
                "segments_before_crash": segments_before_crash,
                "segments_after_crash": len(source["segments"]),
                "media_gaps": gaps,
                "all_segments_decoded": True,
                "segments": hashes,
                "measurements": measurements,
                "hardware_capture": "not evaluated",
                "soccer_accuracy": "not evaluated",
                "full_120_minute_gate": args.seconds == 7200,
            }
            atomic_json(args.output, result)
            print(
                json.dumps(
                    {k: v for k, v in result.items() if k not in ("measurements", "segments")}, indent=2
                )
            )
        finally:
            supervisor.stop_match(mid)
            supervisor.close()


if __name__ == "__main__":
    main()

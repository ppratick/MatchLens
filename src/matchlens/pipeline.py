from __future__ import annotations

import json
import time

import cv2
import numpy as np
import psutil

from .decoder import buffered_frames
from .domain import now
from .media import quality, sha256
from .sports import SoccerCandidates
from .storage import Store, encode
from .tracking import Tracker
from .vision import detector_for


def analyze(store: Store, match_id: str, job: dict):
    config = job["config"]
    source = store.source(match_id, config["source_id"])
    detector = detector_for(config["detector"], store.settings)
    checkpoint = job.get("checkpoint", {})
    tracker = Tracker(job["id"][:8], checkpoint.get("tracker"))
    candidates = SoccerCandidates(checkpoint.get("events"))
    last = checkpoint.get("time", -1.0)
    frames_count = checkpoint.get("frames", 0)
    requested_fps = config["sample_fps"]
    fps = checkpoint.get("fps", requested_fps)
    processed_segments = set(checkpoint.get("segments", []))
    skipped = list(checkpoint.get("skipped", []))
    last_cut = checkpoint.get("last_cut", -1.0)
    started, accumulated = time.monotonic(), checkpoint.get("wall_seconds", 0.0)
    previous_thumb = np.array(checkpoint["thumbnail"]) if checkpoint.get("thumbnail") is not None else None
    batch, proposals = [], []
    run_id = job["id"]
    model_path = store.settings.data_dir / "models/yolox_tiny.onnx"
    provenance = {
        "detector": detector.name,
        "model_sha256": sha256(model_path) if config["detector"] == "yolox" else None,
        "source_sha256": source.get("sha256"),
        "pipeline": "0.1.0",
        "sampling_fps": requested_fps,
        "accuracy": "unvalidated",
        "runtime": "CPU",
        "source_id": source["id"],
    }
    if checkpoint and job.get("provenance") and job["provenance"] != provenance:
        raise ValueError("Source/model/pipeline changed since checkpoint; start a new analysis run")
    if checkpoint and source.get("path") and source.get("sha256"):
        if sha256(store.path(match_id, source["path"])) != source["sha256"]:
            raise ValueError("Original media changed since import; resume refused")
    job["provenance"] = provenance
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
            if newest - max(last, pending[0]["start"]) > 12 and len(pending) > 2:
                discarded = pending[:-2]
                skipped.append([discarded[0]["start"], discarded[-1]["end"]])
                processed_segments.update(s["id"] for s in discarded)
                pending = pending[-2:]
                fps = max(2.0, fps / 2)
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
                detections = detector.detect(image)
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

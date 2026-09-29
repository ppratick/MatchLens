from __future__ import annotations

import json
import platform
import time
from pathlib import Path

import numpy as np
import psutil
from scipy.optimize import linear_sum_assignment

from .decoder import buffered_frames
from .media import probe, sha256
from .tracking import Tracker, iou
from .vision import detector_for


def match_boxes(predicted, truth, threshold=0.5):
    if not predicted or not truth:
        return []
    scores = np.array(
        [
            [
                iou(p["box"], g["box"]) if p.get("kind", "person") == g.get("kind", "person") else 0
                for g in truth
            ]
            for p in predicted
        ]
    )
    # Maximize valid match count first, then overlap; subthreshold edges cannot steal matches.
    costs = np.where(scores >= threshold, -1 - scores * 0.001, 0)
    rows, cols = linear_sum_assignment(costs)
    return [(int(r), int(c)) for r, c in zip(rows, cols) if scores[r, c] >= threshold]


def detection_metrics(predicted_frames: list[dict], annotations: list[dict], tolerance=0.1):
    tp = fp = fn = 0
    switches, visible_minutes = 0, 0.0
    last_identity, pair_counts = {}, {}
    track_truth, track_pred = 0, 0
    for annotation in annotations:
        closest = min(predicted_frames, key=lambda f: abs(f["time"] - annotation["time"]), default=None)
        predicted = (
            closest["tracks"] if closest and abs(closest["time"] - annotation["time"]) <= tolerance else []
        )
        truth = annotation["objects"]
        matches = match_boxes(predicted, truth)
        tp += len(matches)
        fp += len(predicted) - len(matches)
        fn += len(truth) - len(matches)
        track_truth += sum("id" in g for g in truth)
        track_pred += len(predicted)
        for pi, gi in matches:
            if "id" not in truth[gi]:
                continue
            gid, pid = str(truth[gi]["id"]), predicted[pi]["id"]
            pair_counts[(gid, pid)] = pair_counts.get((gid, pid), 0) + 1
            if gid in last_identity and last_identity[gid] != pid:
                switches += 1
            last_identity[gid] = pid
        visible_minutes += annotation.get("sample_interval", 0.2) * len(truth) / 60
    gids, pids = sorted({g for g, _ in pair_counts}), sorted({p for _, p in pair_counts})
    idtp = 0
    if gids and pids:
        matrix = np.array([[pair_counts.get((g, p), 0) for p in pids] for g in gids])
        rows, cols = linear_sum_assignment(-matrix)
        idtp = int(matrix[rows, cols].sum())
    precision, recall = tp / (tp + fp) if tp + fp else None, tp / (tp + fn) if tp + fn else None
    return {
        "iou_threshold": 0.5,
        "tp": tp,
        "fp": fp,
        "fn": fn,
        "precision": precision,
        "recall": recall,
        "idf1": 2 * idtp / (track_truth + track_pred) if track_truth + track_pred else None,
        "identity_switches": switches,
        "switches_per_visible_player_minute": switches / visible_minutes if visible_minutes else None,
        "annotations": len(annotations),
        "note": "Sampled-frame metrics. Use TrackEval for official HOTA/benchmark-comparable IDF1; no AP claim from one confidence threshold.",
    }


def event_metrics(predicted, truth, tolerance=2):
    results = {}
    for kind in sorted({e["kind"] for e in predicted + truth}):
        p, g = [e for e in predicted if e["kind"] == kind], [e for e in truth if e["kind"] == kind]
        matched, errors = 0, []
        if p and g:
            distances = np.array([[abs(a["start"] - b["start"]) for b in g] for a in p])
            costs = np.where(distances <= tolerance, -1 - (tolerance - distances) * 0.001, 0)
            rows, cols = linear_sum_assignment(costs)
            errors = [float(distances[r, c]) for r, c in zip(rows, cols) if distances[r, c] <= tolerance]
            matched = len(errors)
        results[kind] = {
            "precision": matched / len(p) if p else None,
            "recall": matched / len(g) if g else None,
            "true_positives": matched,
            "false_positives": len(p) - matched,
            "false_negatives": len(g) - matched,
            "mean_time_error": float(np.mean(errors)) if errors else None,
            "tolerance_seconds": tolerance,
        }
    return results


def benchmark_video(settings, path: Path, fps: float, detector_name: str, annotations=None):
    if not 0.5 <= fps <= 30:
        raise ValueError("Benchmark fps must be between 0.5 and 30")
    metadata = probe(path, settings)
    detector = detector_for(detector_name, settings)
    tracker = Tracker("benchmark")
    frames, stage_ms = [], []
    start, peak = time.monotonic(), 0
    for t, image, _, _ in buffered_frames(path, fps):
        before = time.monotonic()
        detections = detector.detect(image)
        tracks = tracker.update(detections, t)
        stage_ms.append((time.monotonic() - before) * 1000)
        frames.append({"time": t, "tracks": tracks})
        peak = max(peak, psutil.Process().memory_info().rss)
    wall = time.monotonic() - start
    result = {
        "schema": "matchlens-benchmark-1",
        "video_sha256": sha256(path),
        "video": metadata,
        "hardware": platform.platform(),
        "detector": detector.name,
        "requested_sample_fps": fps,
        "processed_frames": len(frames),
        "wall_seconds": wall,
        "processed_fps": len(frames) / max(wall, 0.001),
        "media_seconds_per_wall_second": metadata["duration"] / max(wall, 0.001),
        "peak_worker_rss_mb": peak / 1024**2,
        "inference_tracking_ms": {f"p{p}": float(np.percentile(stage_ms, p)) for p in (50, 95, 99)}
        if stage_ms
        else {},
        "accuracy": "not evaluated — annotations not supplied",
        "recording_drops": "not measured by this offline benchmark",
    }
    if annotations:
        labels = json.loads(Path(annotations).read_text())
        if labels.get("video_sha256") != result["video_sha256"]:
            raise ValueError("Annotation checksum does not match video")
        result["accuracy"] = detection_metrics(frames, labels["frames"], tolerance=0.5 / fps)
    return result

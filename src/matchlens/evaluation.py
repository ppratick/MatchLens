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


def class_metrics(predictions, labels, kind, tolerance, max_area=None):
    tp = fp = fn = 0
    for frame in labels:
        if not frame.get("observable", True):
            continue
        closest = min(predictions, key=lambda f: abs(f["time"] - frame["time"]), default=None)
        objects = (
            closest.get("detections", closest["tracks"])
            if closest and abs(closest["time"] - frame["time"]) <= tolerance
            else []
        )

        def selected(o):
            box = o["box"]
            return o.get("kind", "person") == kind and (
                max_area is None or (box[2] - box[0]) * (box[3] - box[1]) <= max_area
            )

        p = [o for o in objects if o.get("kind", "person") == kind]
        g = [o for o in frame["objects"] if selected(o)]
        if max_area is not None:
            # Size bins apply to truth, not predicted boxes. A slightly oversized
            # prediction can still correctly localize a small ball at IoU >= .5.
            larger = [o for o in frame["objects"] if o.get("kind", "person") == kind and not selected(o)]
            ignored = {pi for pi, _ in match_boxes(p, larger)}
            p = [o for pi, o in enumerate(p) if pi not in ignored]
        count = len(match_boxes(p, g))
        tp += count
        fp += len(p) - count
        fn += len(g) - count
    return {
        "tp": tp,
        "fp": fp,
        "fn": fn,
        "precision": tp / (tp + fp) if tp + fp else None,
        "recall": tp / (tp + fn) if tp + fn else None,
        "truth_count": tp + fn,
        "iou_threshold": 0.5,
    }


def team_metrics(predictions, labels, tolerance):
    pairs, unknown, total = {}, 0, 0
    for frame in labels:
        if not frame.get("observable", True):
            continue
        nearest = min(predictions, key=lambda f: abs(f["time"] - frame["time"]), default=None)
        tracks = nearest["tracks"] if nearest and abs(nearest["time"] - frame["time"]) <= tolerance else []
        for pi, gi in match_boxes(tracks, frame["objects"]):
            truth = frame["objects"][gi]
            if truth.get("team") not in ("home", "away") or truth.get("kind", "person") != "person":
                continue
            hint = tracks[pi].get("team_hint", "unknown")
            total += 1
            if hint == "unknown":
                unknown += 1
            else:
                pairs[(hint, truth["team"])] = pairs.get((hint, truth["team"]), 0) + 1
    clusters = sorted({c for c, t in pairs})
    matrix = np.array([[pairs.get((c, t), 0) for t in ("home", "away")] for c in clusters])
    correct = 0
    if matrix.size:
        rows, cols = linear_sum_assignment(-matrix)
        correct = int(matrix[rows, cols].sum())
    return {
        "matched_labeled_players": total,
        "unknown": unknown,
        "assignment_coverage": (total - unknown) / total if total else None,
        "best_permutation_cluster_agreement": correct / (total - unknown) if total > unknown else None,
        "named_team_accuracy": None,
        "note": "Best permutation is an optimistic clustering diagnostic, not held-out named-team accuracy. Named teams require a frozen reviewed kit mapping.",
    }


def benchmark_video(
    settings,
    path: Path,
    fps: float,
    detector_name: str,
    annotations=None,
    provider="cpu",
    profile="broadcast",
):
    import tempfile

    from .profiles import PROFILES
    from .vision import YOLOX

    if not 0.5 <= fps <= 30 or profile not in PROFILES:
        raise ValueError("Declare a source profile and benchmark fps between 0.5 and 30")
    metadata = probe(path, settings)
    checksum = sha256(path)
    labels = json.loads(Path(annotations).read_text()) if annotations else None
    if labels:
        if labels.get("source_sha256", labels.get("video_sha256")) != checksum:
            raise ValueError("Annotation checksum does not match video")
        if labels.get("source_profile") != profile or labels.get("source_offset", 0) != 0:
            raise ValueError("Benchmark labels must match this source profile and file-relative timeline")
    with tempfile.TemporaryDirectory(prefix="matchlens-profile-") as directory:
        start = time.monotonic()
        detector = detector_for(detector_name, settings, provider, Path(directory) / "runtime")
        initialization = time.monotonic() - start
        samples = buffered_frames(path, fps)
        try:
            first = next(samples)
        finally:
            samples.close()
        warmup_start = time.monotonic()
        detector.detect(first[1])
        first_inference = time.monotonic() - warmup_start
        for _ in range(3):
            detector.detect(first[1])
        warmup = time.monotonic() - warmup_start
        parity = {"status": "not applicable"}
        model_file = settings.data_dir / (
            "models/yolox_s.onnx" if detector_name == "yolox_s" else "models/yolox_tiny.onnx"
        )
        if provider == "coreml" and hasattr(detector, "raw"):
            cpu = YOLOX(model_file)
            expected, actual = cpu.raw(first[1]), detector.raw(first[1])
            parity = {
                "status": "compared",
                "raw_allclose": bool(np.allclose(expected, actual, rtol=1e-3, atol=1e-3)),
                "max_absolute_difference": float(np.max(np.abs(expected - actual))),
                "rtol": 0.001,
                "atol": 0.001,
                "frames": 1,
                "note": "One real decoded fixture frame; not a full-corpus numerical/accuracy qualification",
            }
            del cpu
        parity_seconds = time.monotonic() - start - initialization - warmup
        tracker = Tracker("benchmark")
        frames, stage_ms = [], []
        start, peak = time.monotonic(), 0
        count = 0
        for t, image, _, _ in buffered_frames(path, fps):
            before = time.monotonic()
            detections = detector.detect(image)
            tracks = tracker.update(detections, t)
            stage_ms.append((time.monotonic() - before) * 1000)
            # Retain only labeled samples; unlabeled long benchmarks stay bounded.
            if labels and any(abs(t - f["time"]) <= 0.5 / fps for f in labels["frames"]):
                frames.append(
                    {"time": t, "tracks": tracks, "detections": [d.model_dump() for d in detections]}
                )
            count += 1
            peak = max(peak, psutil.Process().memory_info().rss)
        wall = time.monotonic() - start
        result = {
            "schema": "matchlens-benchmark-2",
            "source_profile": profile,
            "video_sha256": checksum,
            "video": metadata,
            "hardware": platform.platform(),
            "detector": detector.name,
            "provider": provider,
            "registered_providers": detector.session.get_providers() if hasattr(detector, "session") else [],
            "model_bytes": model_file.stat().st_size if detector_name in ("yolox", "yolox_s") else 0,
            "model_sha256": sha256(model_file) if detector_name in ("yolox", "yolox_s") else None,
            "requested_sample_fps": fps,
            "initialization_seconds": initialization,
            "first_inference_seconds": first_inference,
            "warmup_seconds": warmup,
            "processed_frames": count,
            "wall_seconds": wall,
            "total_seconds_including_init_warmup": initialization + warmup + wall,
            "parity_and_fixture_setup_seconds": parity_seconds,
            "processed_fps": count / max(wall, 0.001),
            "media_seconds_per_wall_second": metadata["duration"] / max(wall, 0.001),
            "peak_worker_rss_mb": peak / 1024**2,
            "inference_tracking_ms": {f"p{p}": float(np.percentile(stage_ms, p)) for p in (50, 95, 99)}
            if stage_ms
            else {},
            "accuracy": "not evaluated — annotations not supplied",
            "recording_drops": "not measured by offline benchmark",
            "live_delay": "not measured by offline benchmark",
            "output_parity": parity,
        }
        if hasattr(detector, "session"):
            result["graph_placement"] = profile_placement(detector.session.end_profiling())
        if labels:
            observable = [f for f in labels["frames"] if f.get("observable", True)]
            result["accuracy"] = {
                "players": class_metrics(frames, observable, "person", 0.5 / fps),
                "ball": class_metrics(frames, observable, "ball", 0.5 / fps),
                "small_ball": class_metrics(
                    frames,
                    observable,
                    "ball",
                    0.5 / fps,
                    max_area=32**2 / (metadata["width"] * metadata["height"]),
                ),
                "tracking": detection_metrics(
                    [{**f, "tracks": [t for t in f["tracks"] if t["kind"] == "person"]} for f in frames],
                    [
                        {**f, "objects": [o for o in f["objects"] if o.get("kind", "person") == "person"]}
                        for f in observable
                    ],
                    tolerance=0.5 / fps,
                ),
                "team": team_metrics(frames, observable, 0.5 / fps),
                "labeled_frames": len(observable),
                "unobservable_frames": len(labels["frames"]) - len(observable),
            }
        return result


def profile_placement(path):
    counts, durations = {}, {}
    for event in json.loads(Path(path).read_text()):
        provider = event.get("args", {}).get("provider")
        if event.get("cat") == "Node" and provider:
            counts[provider] = counts.get(provider, 0) + 1
            durations[provider] = durations.get(provider, 0) + event.get("dur", 0)
    return {
        "executed_node_calls": counts,
        "kernel_microseconds": durations,
        "note": "ORT runtime kernel trace. Registered providers alone do not establish graph placement.",
    }


def compare_providers(
    settings,
    path: Path,
    fps=5,
    annotations=None,
    profile="broadcast",
    detectors=("yolox", "hog", "yolox_s"),
    providers=("cpu", "coreml"),
):
    """Run each configuration in a fresh process, avoiding memory/provider interference."""
    import os
    import subprocess
    import sys
    import tempfile

    from .storage import atomic_json

    results = []
    with tempfile.TemporaryDirectory(prefix="matchlens-bench-") as directory:
        for detector in detectors:
            for provider in providers if detector != "hog" else ("cpu",):
                output = Path(directory) / f"{detector}-{provider}.json"
                command = [
                    sys.executable,
                    "-m",
                    "matchlens.benchmark_worker",
                    str(settings.data_dir),
                    str(path.resolve()),
                    str(output),
                    str(fps),
                    detector,
                    provider,
                    profile,
                ]
                if annotations:
                    command += [str(Path(annotations).resolve())]
                process = subprocess.run(
                    command,
                    capture_output=True,
                    timeout=max(300, probe(path, settings)["duration"] * 20),
                    env={**os.environ, "PYTHONPATH": str(Path(__file__).resolve().parents[1])},
                )
                if output.exists():
                    results.append(json.loads(output.read_text()))
                else:
                    results.append(
                        {
                            "detector": detector,
                            "provider": provider,
                            "status": "failed",
                            "error": process.stderr.decode(errors="replace")[-2000:],
                        }
                    )
        result = {
            "schema": "matchlens-comparison-1",
            "source_profile": profile,
            "video_sha256": sha256(path),
            "results": results,
            "default_provider": "cpu",
            "accuracy_gate": "No profile is qualified without held-out manual labels",
            "live_delay": "Offline throughput does not measure live latency",
        }
        atomic_json(Path(directory) / "comparison.json", result)
        return result

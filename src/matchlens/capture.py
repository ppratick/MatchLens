from __future__ import annotations

import csv
import json
import os
import re
import signal
import subprocess
import sys
import threading
import time
from urllib.parse import urlparse

from .domain import now
from .media import probe, sha256
from .storage import Store, atomic_json


def capture(store: Store, match_id: str, job: dict):
    config, source = job["config"], store.source(match_id, job["config"]["source_id"])
    root = store.path(match_id, f"original/{source['id']}")
    root.mkdir(exist_ok=True)
    started = time.monotonic()
    source.update(status="recording", segments=[], gaps=[])
    store.put_source(match_id, source)
    args = [store.settings.ffmpeg, "-v", "warning", "-y", "-nostdin"]
    kind = config["kind"]
    if kind == "test":
        args += [
            "-re",
            "-f",
            "lavfi",
            "-i",
            "testsrc2=size=640x360:rate=30",
            "-f",
            "lavfi",
            "-i",
            "sine=frequency=440:sample_rate=48000",
        ]
    elif kind in ("screen", "camera"):
        if sys.platform != "darwin":
            raise ValueError(
                "Built-in device capture currently supports macOS; use file or stream ingestion on this OS"
            )
        device = config["device"]
        if not re.fullmatch(r"[0-9]+:(?:none|[0-9]+)", device):
            raise ValueError("Use an AVFoundation index such as 1:none")
        args += ["-f", "avfoundation", "-framerate", str(config["fps"]), "-i", device]
    elif kind == "stream":
        address = config["address"]
        parsed = urlparse(address)
        if parsed.scheme not in ("rtsp", "rtmp", "srt", "udp", "tcp", "http", "https") or not parsed.hostname:
            raise ValueError("Use an explicit RTSP/RTMP/SRT/UDP/TCP/HTTP stream URL")
        if parsed.scheme == "rtsp":
            args += ["-rtsp_transport", "tcp"]
        args += ["-rw_timeout", "10000000", "-i", address]
    elif kind == "phone":
        args += ["-probesize", "65536", "-analyzeduration", "1000000", "-i", "pipe:0"]
    else:
        raise ValueError("Unsupported capture source")
    listing = root / "segments.csv"
    args += [
        "-map",
        "0:v:0",
        "-map",
        "1:a:0" if kind == "test" else "0:a?",
        "-c:v",
        "libx264",
        "-preset",
        "ultrafast",
        "-threads",
        "2",
        "-crf",
        "20",
        "-pix_fmt",
        "yuv420p",
        "-force_key_frames",
        "expr:gte(t,n_forced*2)",
        "-c:a",
        "aac",
        "-f",
        "segment",
        "-segment_time",
        "2",
        "-reset_timestamps",
        "1",
        "-segment_list",
        str(listing),
        "-segment_list_type",
        "csv",
        str(root / "segment-%06d.mp4"),
    ]
    log = store.path(match_id, f"logs/{job['id']}-ffmpeg.log")
    stop = threading.Event()
    phone_done = threading.Event()
    with log.open("wb") as errors:
        proc = subprocess.Popen(
            args,
            stdin=subprocess.PIPE if kind == "phone" else subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=errors,
        )
        job["recorder_pid"] = proc.pid
        store.put_job(match_id, job)
        feed_thread = None
        if kind == "phone":
            spool = store.path(match_id, config["spool"])

            def feed():
                cursor = 0
                try:
                    while not stop.is_set():
                        pair_path = store.settings.data_dir / "pairing" / f"{config['pair_id']}.json"
                        committed = (
                            json.loads(pair_path.read_text()).get("bytes", 0) if pair_path.exists() else 0
                        )
                        if spool.exists() and committed > cursor:
                            with spool.open("rb") as file:
                                file.seek(cursor)
                                chunk = file.read(min(256 * 1024, committed - cursor))
                            if chunk:
                                proc.stdin.write(chunk)
                                proc.stdin.flush()
                                cursor += len(chunk)
                                continue
                        if spool.with_name(spool.name + ".finished").exists() and cursor >= committed:
                            phone_done.set()
                            break
                        time.sleep(0.1)
                except (BrokenPipeError, OSError):
                    pass
                finally:
                    try:
                        proc.stdin.close()
                    except OSError:
                        pass

            feed_thread = threading.Thread(target=feed, daemon=True)
            feed_thread.start()

        def commit_segments():
            if not listing.exists():
                return
            existing = {s["path"] for s in source["segments"]}
            for row in csv.reader(listing.read_text().splitlines()):
                if len(row) != 3:
                    continue
                segment = root / row[0]
                if not segment.exists():
                    continue
                relative = str(segment.relative_to(store.settings.match_dir(match_id)))
                if relative in existing:
                    continue
                try:
                    a, b = float(row[1]), float(row[2])
                    if b <= a:
                        continue
                    # Only FFmpeg's closed, listed segments are published.
                    with segment.open("rb") as handle:
                        os.fsync(handle.fileno())
                    meta = probe(segment, store.settings)
                except (ValueError, subprocess.TimeoutExpired):
                    continue
                source["segments"].append(
                    {"id": segment.stem, "path": relative, "start": a, "end": b, "sha256": sha256(segment)}
                )
                source.update(
                    duration=b,
                    width=meta["width"],
                    height=meta["height"],
                    fps=meta["fps"],
                    codec=meta["codec"],
                    has_audio=meta["has_audio"],
                )
            if kind == "phone":
                pair_path = store.settings.data_dir / "pairing" / f"{config['pair_id']}.json"
                pairing = json.loads(pair_path.read_text()) if pair_path.exists() else {}
                source["sender_health"] = pairing.get("health_events", [])
                source["gaps"] = [
                    {
                        **e,
                        "reason": "Sender pause/suspension: wall-time gap; precise media boundary unavailable",
                    }
                    for e in source["sender_health"]
                    if e["state"] != "resumed"
                ]
                source["received_bytes"] = pairing.get("bytes", 0)
                source["last_received"] = pairing.get("last_received")
            source["bytes"] = sum(store.path(match_id, s["path"]).stat().st_size for s in source["segments"])
            atomic_json(root / "manifest.json", source)
            store.put_source(match_id, source)

        try:
            while proc.poll() is None:
                commit_segments()
                current = store.job(match_id, job["id"])
                if current.get("cancel"):
                    job["cancel"] = True
                    break
                store.settings.require_space()
                job.update(
                    heartbeat=now(),
                    progress=0,
                    metrics={
                        "recorded_seconds": source["duration"],
                        "wall_seconds": time.monotonic() - started,
                        "bytes": source.get("bytes", 0),
                        "segments": len(source["segments"]),
                    },
                )
                store.put_job(match_id, job)
                time.sleep(0.5)
        finally:
            stop.set()
            if proc.poll() is None:
                proc.send_signal(signal.SIGINT)
                try:
                    proc.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    proc.kill()
                    proc.wait()
            if feed_thread:
                feed_thread.join(timeout=2)
            commit_segments()
            source["status"] = "ready" if source["segments"] else "failed"
            if not job.get("cancel") and not phone_done.is_set():
                source["gaps"].append(
                    {
                        "after": source["duration"],
                        "reason": "Input ended or recorder stopped. Reconnect as another source with an explicit time offset.",
                    }
                )
            atomic_json(root / "manifest.json", source)
            store.put_source(match_id, source)
    if not source["segments"]:
        raise ValueError(
            log.read_text(errors="replace")[-1500:]
            or "Capture produced no video; check source and permissions"
        )
    job.update(status="complete", finished=now(), progress=1)
    store.put_job(match_id, job)

from __future__ import annotations

import hashlib
import json
import math
import subprocess
from pathlib import Path

from .config import Settings
from .domain import uid
from .storage import Store


def run_media(args: list[str], timeout: float = 120) -> subprocess.CompletedProcess:
    result = subprocess.run(args, capture_output=True, timeout=timeout)
    if result.returncode:
        raise ValueError(result.stderr.decode(errors="replace")[-1800:] or "Media operation failed")
    return result


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as src:
        for chunk in iter(lambda: src.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def probe(path: Path, settings: Settings) -> dict:
    data = json.loads(
        run_media(
            [
                settings.ffprobe,
                "-v",
                "error",
                "-protocol_whitelist",
                "file,pipe",
                "-show_format",
                "-show_streams",
                "-of",
                "json",
                str(path),
            ],
            30,
        ).stdout
    )
    video = next((s for s in data.get("streams", []) if s["codec_type"] == "video"), None)
    if not video:
        raise ValueError("No decodable video stream found")
    duration = float(data.get("format", {}).get("duration", video.get("duration", 0)) or 0)
    if not math.isfinite(duration) or duration <= 0:
        raise ValueError("Video duration is missing or invalid; finalize the recording before import")
    rotation = next((s.get("rotation", 0) for s in video.get("side_data_list", []) if "rotation" in s), 0)
    numerator, denominator = video.get("avg_frame_rate", "0/1").split("/")
    fps = float(numerator) / float(denominator) if float(denominator) else 0
    return {
        "duration": duration,
        "width": int(video["width"]),
        "height": int(video["height"]),
        "codec": video["codec_name"],
        "fps": fps,
        "time_base": video.get("time_base"),
        "rotation": rotation,
        "bytes": path.stat().st_size,
        "has_audio": any(s["codec_type"] == "audio" for s in data["streams"]),
    }


def register_import(store: Store, match_id: str, staged: Path, filename: str) -> dict:
    info = probe(staged, store.settings)
    source_id = uid()
    suffix = Path(filename).suffix.lower()
    if suffix not in (".mp4", ".mov", ".mkv", ".webm", ".avi", ".m4v", ".ts"):
        suffix = ".mkv"
    relative = f"original/{source_id}{suffix}"
    destination = store.path(match_id, relative)
    staged.replace(destination)
    source = {
        **info,
        "id": source_id,
        "name": Path(filename).name[:200],
        "kind": "file",
        "profile": "synthetic"
        if store.get(match_id)["profile"] == "synthetic"
        else {"screen": "screen", "phone_tv": "phone_tv"}.get(store.get(match_id)["profile"], "broadcast"),
        "offset": 0,
        "path": relative,
        "sha256": sha256(destination),
        "status": "ready",
        "gaps": [],
    }
    store.put_source(match_id, source)
    try:
        poster = store.path(match_id, f"thumbnails/{source_id}.jpg")
        run_media(
            [
                store.settings.ffmpeg,
                "-v",
                "error",
                "-y",
                "-i",
                str(destination),
                "-frames:v",
                "1",
                "-vf",
                "scale=640:-2",
                str(poster),
            ],
            30,
        )
        source["poster"] = str(poster.relative_to(store.settings.match_dir(match_id)))
        store.put_source(match_id, source)
    except (ValueError, subprocess.TimeoutExpired):
        pass
    return source


def sampled_frames(path: Path, fps: float, after: float = -1, stop=None):
    """Bounded caller-driven decode; timestamps come from PTS, never frame count."""
    import av

    with av.open(str(path), options={"protocol_whitelist": "file,pipe"}) as container:
        stream = container.streams.video[0]
        stream.thread_count = 2
        origin = float(stream.start_time * stream.time_base) if stream.start_time is not None else 0.0
        if after > 0:
            container.seek(int((after + origin) / stream.time_base), stream=stream, backward=True)
        next_sample = max(0.0, after + 1 / fps if after >= 0 else 0.0)
        for frame in container.decode(stream):
            if stop is not None and stop.is_set():
                return
            if frame.pts is None:
                continue
            t = float(frame.pts * frame.time_base) - origin
            if t <= after + 1e-6 or t + 1e-5 < next_sample:
                continue
            next_sample = t + 1 / fps
            import numpy as np

            pts, timebase = frame.pts, str(frame.time_base)
            rotation = int(round(frame.rotation / 90)) % 4
            if frame.width * frame.height > 40_000_000:
                raise ValueError(
                    "Frame exceeds supported analysis dimensions; original media remains preserved"
                )
            # Bound queued RGB payloads even for high-resolution originals.
            # Normalized coordinates remain in the displayed-original space.
            scale = min(1.0, 2560 / max(frame.width, frame.height))
            if scale < 1:
                frame = frame.reformat(
                    width=max(1, round(frame.width * scale)), height=max(1, round(frame.height * scale))
                )
            image = frame.to_ndarray(format="bgr24")
            if rotation:
                image = np.ascontiguousarray(np.rot90(image, k=rotation))
            yield t, image, pts, timebase


def quality(image) -> list[str]:
    import cv2

    gray = cv2.cvtColor(cv2.resize(image, (320, 180)), cv2.COLOR_BGR2GRAY)
    result = []
    if gray.mean() < 45:
        result.append("Low light: detections may be unreliable")
    if cv2.Laplacian(gray, cv2.CV_64F).var() < 20:
        result.append("Blur or low detail: small players and ball may be missed")
    return result


def make_proxy(store: Store, match_id: str, source: dict) -> Path:
    dest = store.path(match_id, f"proxies/{source['id']}.mp4")
    if dest.exists():
        return dest
    partial = dest.with_suffix(".partial.mp4")
    run_media(
        [
            store.settings.ffmpeg,
            "-v",
            "error",
            "-y",
            "-i",
            str(store.path(match_id, source["path"])),
            "-map",
            "0:v:0",
            "-map",
            "0:a?",
            "-vf",
            "scale='min(1280,iw)':-2",
            "-c:v",
            "libx264",
            "-threads",
            "2",
            "-preset",
            "veryfast",
            "-crf",
            "24",
            "-pix_fmt",
            "yuv420p",
            "-c:a",
            "aac",
            "-movflags",
            "+faststart",
            str(partial),
        ],
        max(120, source["duration"] * 3),
    )
    probe(partial, store.settings)
    partial.replace(dest)
    source["proxy"] = str(dest.relative_to(store.settings.match_dir(match_id)))
    store.put_source(match_id, source)
    return dest

from __future__ import annotations

import math
import subprocess

import cv2
import numpy as np

from .domain import AnalysisRequest, Correction, Event, now, uid
from .media import register_import
from .review import correct
from .storage import Store


def generate(store: Store, match_id: str):
    """A labeled engineering fixture. Not a real match or an accuracy benchmark."""
    output = store.path(match_id, "temporary/synthetic.mp4")
    width, height, fps, duration = 960, 540, 30, 20
    proc = subprocess.Popen(
        [
            store.settings.ffmpeg,
            "-v",
            "error",
            "-y",
            "-f",
            "rawvideo",
            "-pix_fmt",
            "bgr24",
            "-s",
            f"{width}x{height}",
            "-r",
            str(fps),
            "-i",
            "pipe:0",
            "-an",
            "-c:v",
            "libx264",
            "-threads",
            "2",
            "-preset",
            "veryfast",
            "-pix_fmt",
            "yuv420p",
            "-movflags",
            "+faststart",
            str(output),
        ],
        stdin=subprocess.PIPE,
    )
    try:
        for index in range(duration * fps):
            t = index / fps
            image = np.full((height, width, 3), (40, 87, 61), np.uint8)
            for x in range(60, 900, 84):
                if (x // 84) % 2 == 0:
                    cv2.rectangle(image, (x, 60), (x + 84, 480), (45, 95, 65), -1)
            white = (184, 211, 193)
            cv2.rectangle(image, (60, 60), (900, 480), white, 2)
            cv2.line(image, (480, 60), (480, 480), white, 2)
            cv2.circle(image, (480, 270), 63, white, 2)
            for x1, x2 in ((60, 185), (775, 900)):
                cv2.rectangle(image, (x1, 160), (x2, 380), white, 2)
            for team in range(2):
                color = (57, 104, 239) if team == 0 else (229, 132, 68)
                for player in range(7):
                    x = int(220 + team * 400 + 75 * math.sin(t * 0.12 + player))
                    y = int(100 + player * 52 + 12 * math.sin(t * 0.35 + player * 2))
                    cv2.ellipse(image, (x + 4, y + 7), (14, 7), 0, 0, 360, (26, 58, 38), -1)
                    cv2.rectangle(image, (x - 7, y - 14), (x + 7, y + 9), color, -1)
                    cv2.circle(image, (x, y - 17), 5, (146, 177, 207), -1)
            ball = (int(470 + 220 * math.sin(t * 0.3)), int(270 + 110 * math.sin(t * 0.5)))
            cv2.circle(image, ball, 4, (245, 245, 245), -1)
            cv2.rectangle(image, (0, 0), (960, 36), (20, 31, 25), -1)
            cv2.putText(
                image,
                f"SYNTHETIC DEMO  |  NOT REAL MATCH DATA        {t:05.2f}s",
                (24, 25),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.55,
                white,
                1,
            )
            proc.stdin.write(image.tobytes())
    finally:
        proc.stdin.close()
        if proc.wait(timeout=60):
            raise ValueError("Demo encoder failed")
    source = register_import(store, match_id, output, "Synthetic training fixture.mp4")
    for kind, start, end, team, note in (
        ("pass", 2, None, "home", "Scripted completed pass"),
        ("pass", 4, None, "home", "Scripted completed pass"),
        ("turnover", 6, None, "away", "Scripted change of control"),
        ("goal", 12, None, "away", "Scripted goal label, not visual detection"),
        ("possession", 0, 6, "home", "Scripted control interval"),
        ("possession", 6, 12, "away", "Scripted control interval"),
    ):
        event = Event(
            kind=kind, start=start, end=end, team=team, note=note, origin="synthetic", source_id=source["id"]
        )
        revision = store.review(match_id)[0]
        correct(store, match_id, Correction(revision=revision, operation="event", payload=event.model_dump()))
    correct(
        store,
        match_id,
        Correction(
            revision=store.review(match_id)[0],
            operation="exclude",
            payload={
                "start": 12,
                "end": 15,
                "reason": "Scripted dead-ball interval",
                "exclude_events": False,
            },
        ),
    )
    # Boundary goal remains a countable event; exclusion applies to time intervals rather than that label.
    correct(
        store,
        match_id,
        Correction(
            revision=store.review(match_id)[0],
            operation="calibration",
            payload={
                "source_id": source["id"],
                "image": [
                    [60 / 960, 60 / 540],
                    [900 / 960, 60 / 540],
                    [900 / 960, 480 / 540],
                    [60 / 960, 480 / 540],
                ],
                "field": [[0, 0], [1, 0], [1, 1], [0, 1]],
                "dimensions_measured": False,
            },
        ),
    )
    config = AnalysisRequest(source_id=source["id"], detector="synthetic", sample_fps=5).model_dump()
    store.put_job(
        match_id,
        {
            "id": uid(),
            "kind": "analysis",
            "config": config,
            "status": "queued",
            "created": now(),
            "heartbeat": now(),
            "cancel": False,
            "progress": 0,
            "error": None,
        },
    )
    return source

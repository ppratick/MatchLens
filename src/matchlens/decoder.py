"""Isolated PyAV decoder. Never imports OpenCV's separate FFmpeg libraries."""

from __future__ import annotations

import multiprocessing
import queue
from pathlib import Path


def decode_process(path: str, fps: float, after: float, items, stop):
    from .media import sampled_frames

    def put(value):
        while not stop.is_set():
            try:
                items.put(value, timeout=0.2)
                return
            except queue.Full:
                continue

    try:
        for value in sampled_frames(Path(path), fps, after, stop):
            put(("frame", value))
        put(("done", None))
    except Exception as exc:
        put(("error", str(exc)))


def buffered_frames(path: Path, fps: float, after: float = -1):
    context = multiprocessing.get_context("spawn")
    items = context.Queue(maxsize=4)
    stop = context.Event()
    process = context.Process(target=decode_process, args=(str(path), fps, after, items, stop), daemon=True)
    process.start()
    try:
        while True:
            try:
                kind, value = items.get(timeout=2)
            except queue.Empty:
                if not process.is_alive():
                    raise ValueError(f"Decoder stopped unexpectedly (exit {process.exitcode})")
                continue
            if kind == "done":
                break
            if kind == "error":
                raise ValueError(value)
            yield value
    finally:
        stop.set()
        process.join(timeout=2)
        if process.is_alive():
            process.terminate()
            process.join(timeout=2)
        items.close()

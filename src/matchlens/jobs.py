from __future__ import annotations

import os
import subprocess
import sys
import threading
import time
from pathlib import Path

import psutil

from .domain import now, uid
from .storage import Store


def process_alive(job: dict) -> bool:
    pid = job.get("pid")
    if not pid:
        return False
    try:
        process = psutil.Process(pid)
        return (
            abs(process.create_time() - job.get("process_created", 0)) < 1
            and "matchlens.worker" in process.cmdline()
        )
    except (psutil.Error, OSError):
        return False


class Supervisor:
    def __init__(self, store: Store):
        self.store = store
        self.stop_event = threading.Event()
        self.thread = threading.Thread(target=self.loop, daemon=True)
        self.lock = threading.RLock()
        self.children = {}

    def start(self):
        self.thread.start()

    def enqueue(self, match_id: str, kind: str, config: dict, pinned_snapshot=None):
        job = {
            "id": uid(),
            "kind": kind,
            "config": config,
            "status": "queued",
            "created": now(),
            "progress": 0,
            "error": None,
            "heartbeat": now(),
            "cancel": False,
        }
        if pinned_snapshot:
            job["snapshot"] = pinned_snapshot
        self.store.put_job(match_id, job)
        return job

    def loop(self):
        while not self.stop_event.wait(0.4):
            try:
                self.tick()
            except Exception:
                import logging

                logging.exception("Scheduler tick failed")

    def tick(self):
        with self.lock:
            all_jobs = [(m["id"], j) for m in self.store.list() for j in self.store.jobs(m["id"])]
            busy = set()
            for match_id, job in all_jobs:
                if job["status"] == "running":
                    if process_alive(job):
                        busy.add(
                            "analysis"
                            if job["kind"] == "analysis"
                            else "capture"
                            if job["kind"] == "capture"
                            else "export"
                        )
                    elif now() - job.get("heartbeat", 0) > 3:
                        job.update(
                            status="paused" if job["kind"] == "analysis" else "failed",
                            error="Worker interrupted; analysis can resume from its last committed checkpoint",
                        )
                        self.store.put_job(match_id, job)
                        if job["kind"] == "capture":
                            source = self.store.source(match_id, job["config"]["source_id"])
                            source["status"] = "failed"
                            source.setdefault("gaps", []).append(
                                {
                                    "after": source.get("duration", 0),
                                    "reason": "Recorder interrupted; inspect uncommitted tail",
                                }
                            )
                            self.store.put_source(match_id, source)
            for match_id, job in reversed(all_jobs):
                if job["status"] != "queued":
                    continue
                slot = (
                    "analysis"
                    if job["kind"] == "analysis"
                    else "capture"
                    if job["kind"] == "capture"
                    else "export"
                )
                if slot in busy or (slot == "export" and "capture" in busy):
                    continue
                if job["kind"] == "clip":
                    source = self.store.source(match_id, job["config"].get("source_id"))
                    if source.get("status") == "recording":
                        continue
                job.update(status="running", heartbeat=now(), cancel=False)
                self.store.put_job(match_id, job)
                logfile = self.store.path(match_id, f"logs/{job['id']}.log")
                with logfile.open("ab") as log:
                    proc = subprocess.Popen(
                        [
                            sys.executable,
                            "-m",
                            "matchlens.worker",
                            str(self.store.settings.data_dir),
                            match_id,
                            job["id"],
                        ],
                        stdout=log,
                        stderr=log,
                        start_new_session=True,
                        env={
                            **os.environ,
                            "OMP_NUM_THREADS": "2",
                            "OPENBLAS_NUM_THREADS": "2",
                            "PYTHONPATH": str(Path(__file__).resolve().parents[1]),
                        },
                    )
                # Worker records its own identity before doing work; do not overwrite its progress here.
                self.children[job["id"]] = proc
                busy.add(slot)
            for key, proc in list(self.children.items()):
                if proc.poll() is not None:
                    del self.children[key]

    def cancel(self, match_id: str, job_id: str):
        job = self.store.job(match_id, job_id)
        job["cancel"] = True
        if job["status"] == "queued":
            job["status"] = "paused" if job["kind"] == "analysis" else "cancelled"
            if job["kind"] == "capture":
                source = self.store.source(match_id, job["config"]["source_id"])
                source["status"] = "cancelled"
                self.store.put_source(match_id, source)
        self.store.put_job(match_id, job)

    def resume(self, match_id: str, job_id: str):
        job = self.store.job(match_id, job_id)
        if job["kind"] != "analysis" or job["status"] not in ("paused", "failed") or process_alive(job):
            raise ValueError("Only interrupted analysis jobs can resume")
        job.update(status="queued", cancel=False, error=None)
        self.store.put_job(match_id, job)
        return job

    def stop_match(self, match_id: str):
        with self.lock:
            for job in self.store.jobs(match_id):
                if job["status"] in ("queued", "running"):
                    self.cancel(match_id, job["id"])
            deadline = time.monotonic() + 15
            while time.monotonic() < deadline:
                running = [j for j in self.store.jobs(match_id) if process_alive(j)]
                if not running:
                    return
                time.sleep(0.2)
            for job in running:
                if process_alive(job):
                    process = psutil.Process(job["pid"])
                    children = process.children(recursive=True)
                    for child in children:
                        child.terminate()
                    process.terminate()
                    _, alive = psutil.wait_procs(children + [process], timeout=3)
                    for p in alive:
                        p.kill()

    def close(self):
        self.stop_event.set()
        self.thread.join(timeout=3)
        # Recorder workers intentionally survive an application-server restart.
        # Explicit Stop recording / Delete match stops them; UI closure is not capture cancellation.

from __future__ import annotations

import os
import sys
import traceback

import psutil

from .config import Settings
from .domain import now
from .storage import Store


def main():
    data_dir, match_id, job_id = sys.argv[1:4]
    store = Store(Settings.load(data_dir))
    job = store.job(match_id, job_id)
    job.update(pid=os.getpid(), process_created=psutil.Process().create_time(), heartbeat=now())
    store.put_job(match_id, job)
    try:
        if job["kind"] == "analysis":
            from .pipeline import analyze

            analyze(store, match_id, job)
            return
        if job["kind"] == "capture":
            from .capture import capture

            capture(store, match_id, job)
            return
        if job["kind"] == "clip":
            from .exports import clip

            job["result"] = clip(store, match_id, job)
        elif job["kind"] == "report":
            from .exports import report

            job["result"] = report(store, match_id, job.get("snapshot"))
        elif job["kind"] == "proxy":
            from .media import make_proxy

            source = store.source(match_id, job["config"]["source_id"])
            make_proxy(store, match_id, source)
        elif job["kind"] == "demo":
            from .demo import generate

            job["result"] = generate(store, match_id)
        else:
            raise ValueError("Unknown job kind")
        job.update(status="complete", progress=1, finished=now())
        store.put_job(match_id, job)
    except BaseException as exc:
        traceback.print_exc()
        try:
            current = store.job(match_id, job_id)
            current.update(status="failed", error=str(exc)[:2000], finished=now())
            store.put_job(match_id, current)
            if current["kind"] == "capture":
                source = store.source(match_id, current["config"]["source_id"])
                source["status"] = "failed"
                source.setdefault("gaps", []).append(
                    {"after": source.get("duration", 0), "reason": "Capture worker failed"}
                )
                store.put_source(match_id, source)
        except Exception:
            traceback.print_exc()


if __name__ == "__main__":
    main()

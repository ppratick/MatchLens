from __future__ import annotations

import asyncio
import json
import os
import secrets
import shutil
import time
from contextlib import asynccontextmanager
from pathlib import Path
from urllib.parse import urlparse

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from filelock import FileLock
from pydantic import ValidationError

from .annotations import AnnotationBundle, export_annotations, import_annotations
from .config import Settings
from .domain import AnalysisRequest, CaptureRequest, ClipRequest, Correction, MatchCreate, uid
from .geometry import apply_review
from .jobs import Supervisor
from .media import register_import
from .review import correct, public_job, snapshot
from .storage import Store


def create_app(settings: Settings | None = None, testing=False):
    settings = settings or Settings.load()
    store = Store(settings)
    supervisor = Supervisor(store)
    token = secrets.token_urlsafe(32)
    lock = FileLock(str(settings.data_dir / "server.lock"))
    cache = {}

    @asynccontextmanager
    async def lifespan(app):
        if not testing:
            lock.acquire(timeout=0)
            supervisor.start()
        yield
        if not testing:
            supervisor.close()
            lock.release()

    app = FastAPI(title="MatchLens", version="0.1.0", lifespan=lifespan, docs_url=None, redoc_url=None)
    app.state.store, app.state.supervisor = store, supervisor

    @app.middleware("http")
    async def local_security(request: Request, call_next):
        hostname = request.url.hostname
        allowed = {"127.0.0.1", "localhost", "::1"} | ({"testserver"} if testing else set())
        if hostname not in allowed:
            return JSONResponse(
                {"detail": "Local interface only. Use the separate phone receiver for LAN ingestion."}, 403
            )
        origin = request.headers.get("origin")
        if origin:
            parsed = urlparse(origin)
            if parsed.hostname not in allowed or parsed.port not in (request.url.port, 5173):
                return JSONResponse({"detail": "Origin not allowed"}, 403)
        if request.headers.get("sec-fetch-site") == "cross-site":
            return JSONResponse({"detail": "Cross-site access refused"}, 403)
        if request.method not in ("GET", "HEAD", "OPTIONS"):
            if not secrets.compare_digest(request.headers.get("x-matchlens-token", ""), token):
                return JSONResponse({"detail": "Refresh the local interface to establish a session"}, 403)
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Cross-Origin-Resource-Policy"] = "same-origin"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; img-src 'self' data: blob:; media-src 'self' blob:; style-src 'self' 'unsafe-inline'; script-src 'self'; connect-src 'self'; frame-ancestors 'self'"
        )
        return response

    @app.exception_handler(ValueError)
    async def value_error(request, exc):
        return JSONResponse({"detail": str(exc)}, 400)

    @app.exception_handler(KeyError)
    async def not_found(request, exc):
        return JSONResponse({"detail": "Item not found"}, 404)

    @app.exception_handler(ValidationError)
    async def invalid(request, exc):
        return JSONResponse({"detail": str(exc)}, 422)

    @app.get("/api/session")
    def session():
        return {"token": token, "version": "0.1.0", "data_dir": str(settings.data_dir)}

    @app.get("/api/system")
    def system():
        import platform

        import onnxruntime
        import psutil

        return {
            "version": "0.1.0",
            "platform": platform.platform(),
            "data_dir": str(settings.data_dir),
            "disk_free": shutil.disk_usage(settings.data_dir).free,
            "memory_total": psutil.virtual_memory().total,
            "ffmpeg": shutil.which(settings.ffmpeg),
            "model_ready": (settings.data_dir / "models/yolox_tiny.onnx").exists(),
            "providers": onnxruntime.get_available_providers(),
            "offline": True,
            "capabilities": {
                "player_tracking": "baseline, unvalidated",
                "ball": "experimental",
                "goals_shots_passes_saves": "manual review",
                "distance_speed": "withheld",
                "live_phone": "optional HTTPS receiver",
                "multi_camera": "independent sources; manual offsets; no automatic fusion",
            },
        }

    @app.get("/api/event-definitions")
    def event_definitions():
        from .broadcast import event_catalog

        return event_catalog()

    @app.get("/api/profiles")
    def source_profiles():
        from .profiles import profiles

        return profiles()

    @app.get("/api/matches")
    def matches():
        return store.list()

    @app.post("/api/matches", status_code=201)
    def create(body: MatchCreate):
        return store.create(body)

    @app.post("/api/demo", status_code=201)
    def demo():
        info = store.create(
            MatchCreate(
                title="The training ground",
                home="Coral XI",
                away="Blue XI",
                profile="synthetic",
                date="Synthetic engineering fixture",
            )
        )
        supervisor.enqueue(info["id"], "demo", {})
        return info

    @app.get("/api/matches/{match_id}")
    def detail(match_id: str):
        revision = store.review(match_id)[0]
        jobs = store.jobs(match_id)
        key = (revision, tuple((j["id"], j["status"], j.get("heartbeat")) for j in jobs))
        previous = cache.get(match_id)
        if previous and previous[0] == key and time.monotonic() - previous[1] < 3:
            return previous[2]
        result = snapshot(store, match_id)
        cache[match_id] = key, time.monotonic(), result
        return result

    @app.delete("/api/matches/{match_id}")
    def delete(match_id: str):
        supervisor.stop_match(match_id)
        store.delete(match_id)
        cache.pop(match_id, None)
        return {
            "deleted": True,
            "scope": "All managed match data; external originals and exported copies are unchanged",
        }

    @app.post("/api/matches/{match_id}/video")
    async def upload(match_id: str, request: Request, filename: str = "recording.mp4"):
        store.get(match_id)
        settings.require_space(int(request.headers.get("content-length", 0)))
        staged = store.path(match_id, f"temporary/{uid()}.upload")
        try:
            with staged.open("wb") as file:
                total = 0
                async for chunk in request.stream():
                    total += len(chunk)
                    if total % (64 * 1024 * 1024) < len(chunk):
                        settings.require_space()
                    file.write(chunk)
                file.flush()
                os.fsync(file.fileno())
            source = await asyncio.to_thread(register_import, store, match_id, staged, filename)
            # Original remains authoritative. Proxy is a separate queued job for browser playback.
            if source["codec"] not in ("h264", "vp8", "vp9", "av1") or Path(filename).suffix.lower() not in (
                ".mp4",
                ".webm",
                ".m4v",
            ):
                supervisor.enqueue(match_id, "proxy", {"source_id": source["id"]})
            return source
        finally:
            staged.unlink(missing_ok=True)

    @app.post("/api/matches/{match_id}/analyze")
    def analyze(match_id: str, body: AnalysisRequest):
        source = store.source(match_id, body.source_id)
        if body.detector == "synthetic" and store.get(match_id)["profile"] != "synthetic":
            raise ValueError("Synthetic detector is restricted to synthetic fixtures")
        if (
            body.detector in ("yolox", "yolox_s")
            and not (
                settings.data_dir
                / ("models/yolox_s.onnx" if body.detector == "yolox_s" else "models/yolox_tiny.onnx")
            ).exists()
        ):
            raise ValueError("Install the local model with: matchlens model install")
        if any(
            j["kind"] == "analysis" and j["status"] in ("queued", "running") for j in store.jobs(match_id)
        ):
            raise ValueError("Pause the existing analysis first")
        config = body.model_dump()
        config["source_id"] = source["id"]
        revision, review = store.review(match_id)
        config["television"] = review.get("television", {}).get(source["id"])
        config["reviewed_intervals"] = (
            review.get("annotations", {}).get(source["id"], {}).get("intervals", [])
        )
        config["setup_revision"] = revision
        return supervisor.enqueue(match_id, "analysis", config)

    @app.post("/api/matches/{match_id}/runs/{run_id}/activate")
    def activate_run(match_id: str, run_id: str):
        job = store.job(match_id, run_id)
        if job["kind"] != "analysis" or job["status"] not in ("complete", "paused"):
            raise ValueError("Choose a completed or paused analysis run")
        store.activate(match_id, job["config"]["source_id"], run_id)
        cache.pop(match_id, None)
        return {"active_run": run_id}

    @app.post("/api/matches/{match_id}/sources/{source_id}/offset")
    def source_offset(match_id: str, source_id: str, body: dict):
        import math

        source = store.source(match_id, source_id)
        value = float(body["offset"])
        if not math.isfinite(value) or not 0 <= value < 1e6:
            raise ValueError("Offset must be nonnegative seconds")
        if source_id in store.active_runs(match_id) or source.get("status") == "recording":
            raise ValueError("Align a finalized source before running analysis")
        delta = value - source.get("offset", 0)
        for segment in source.get("segments", []):
            segment["start"] += delta
            segment["end"] += delta
        source["offset"] = value
        store.put_source(match_id, source)
        cache.pop(match_id, None)
        return source

    @app.post("/api/matches/{match_id}/jobs/{job_id}/{action}")
    def job_action(match_id: str, job_id: str, action: str):
        if action == "pause":
            supervisor.cancel(match_id, job_id)
            return {"status": "stopping"}
        if action == "resume":
            return supervisor.resume(match_id, job_id)
        raise ValueError("Unknown job action")

    @app.post("/api/matches/{match_id}/sources/{source_id}/television")
    def television_setup(match_id: str, source_id: str, body: dict):
        from .television import save_setup

        result = save_setup(store, match_id, source_id, body)
        cache.pop(match_id, None)
        return result

    @app.get("/api/annotation-schema")
    def annotation_schema():
        return AnnotationBundle.model_json_schema()

    @app.get("/api/matches/{match_id}/sources/{source_id}/annotations")
    def annotations_export(match_id: str, source_id: str):
        return export_annotations(store, match_id, source_id)

    @app.post("/api/matches/{match_id}/sources/{source_id}/annotations")
    def annotations_import(match_id: str, source_id: str, body: AnnotationBundle, revision: int):
        result = import_annotations(store, match_id, source_id, body, revision)
        cache.pop(match_id, None)
        return {"revision": result}

    @app.get("/api/matches/{match_id}/frames")
    def frames(match_id: str, at: float = 0, source_id: str | None = None):
        if not 0 <= at <= 1e8:
            raise ValueError("Invalid timestamp")
        _, state = store.review(match_id)
        rows = store.frames(match_id, max(0, at - 2), at + 0.05, source_id, 100)
        return [apply_review(f, state) for f in rows[-1:]]

    @app.post("/api/matches/{match_id}/corrections")
    def corrections(match_id: str, body: Correction):
        revision = correct(store, match_id, body)
        cache.pop(match_id, None)
        if (
            body.operation == "event"
            and body.payload.get("status") == "confirmed"
            and body.payload.get("kind") in ("goal", "shot", "save")
        ):
            event_id = body.payload["id"]
            request = ClipRequest(
                title=f"{body.payload['kind'].title()} · {body.payload['start']:.1f}s",
                event_ids=[event_id],
                source_id=body.payload.get("source_id"),
            )
            supervisor.enqueue(match_id, "clip", request.model_dump(), snapshot(store, match_id))
        return {"revision": revision}

    @app.post("/api/matches/{match_id}/history/{action}")
    def history(match_id: str, action: str, body: dict):
        if action not in ("undo", "redo"):
            raise ValueError("Unknown history action")
        revision = store.undo(match_id, int(body["revision"]), action == "redo")
        cache.pop(match_id, None)
        return {"revision": revision}

    @app.post("/api/matches/{match_id}/clips")
    def create_clip(match_id: str, body: ClipRequest):
        store.source(match_id, body.source_id)
        return supervisor.enqueue(match_id, "clip", body.model_dump(), snapshot(store, match_id))

    @app.post("/api/matches/{match_id}/report")
    def create_report(match_id: str):
        store.get(match_id)
        return supervisor.enqueue(match_id, "report", {}, snapshot(store, match_id))

    @app.post("/api/matches/{match_id}/capture")
    def create_capture(match_id: str, body: CaptureRequest):
        settings.require_space()
        source = {
            "id": uid(),
            "name": f"{body.kind.title()} recording",
            "kind": body.kind,
            "profile": "synthetic"
            if body.kind == "test"
            else "screen"
            if body.kind == "screen"
            else "broadcast",
            "offset": 0,
            "status": "recording",
            "duration": 0,
            "segments": [],
            "width": 1280,
            "height": 720,
        }
        store.put_source(match_id, source)
        config = body.model_dump()
        config["source_id"] = source["id"]
        job = supervisor.enqueue(match_id, "capture", config)
        if body.analyze:
            supervisor.enqueue(
                match_id,
                "analysis",
                AnalysisRequest(source_id=source["id"], detector=body.detector, live=True).model_dump(),
            )
        return job

    @app.post("/api/matches/{match_id}/screen-pair")
    def screen_pair(match_id: str):
        from .phone import create_pair

        settings.require_space()
        return create_pair(store, supervisor, match_id, purpose="screen")

    @app.post("/api/matches/{match_id}/pair")
    def pair(match_id: str):
        from .phone import create_pair

        return create_pair(store, supervisor, match_id)

    @app.get("/media/{match_id}/{source_id}")
    def video(match_id: str, source_id: str, segment: str | None = None):
        source = store.source(match_id, source_id)
        if segment:
            item = next((s for s in source.get("segments", []) if s["id"] == segment), None)
            if not item:
                raise HTTPException(404, "Segment not found")
            path = item["path"]
        else:
            path = source.get("proxy") or source.get("path")
        if not path:
            raise HTTPException(404, "Choose a committed recording segment")
        return FileResponse(store.path(match_id, path))

    @app.get("/api/matches/{match_id}/poster/{source_id}")
    def poster(match_id: str, source_id: str):
        source = store.source(match_id, source_id)
        if not source.get("poster"):
            raise HTTPException(404, "No poster")
        return FileResponse(store.path(match_id, source["poster"]), media_type="image/jpeg")

    @app.get("/api/matches/{match_id}/exports/{export_id}/{filename}")
    def export_file(match_id: str, export_id: str, filename: str):
        item = next((e for e in store.exports(match_id) if e["id"] == export_id), None)
        if not item or filename not in item["files"]:
            raise HTTPException(404, "Export not found")
        return FileResponse(
            store.path(match_id, item["files"][filename]),
            filename=None if filename.endswith(".html") else filename,
        )

    @app.get("/api/matches/{match_id}/updates")
    async def updates(match_id: str, request: Request):
        store.get(match_id)

        async def stream():
            while not await request.is_disconnected():
                yield (
                    "data: "
                    + json.dumps(
                        {
                            "jobs": [public_job(j) for j in store.jobs(match_id)],
                            "revision": store.review(match_id)[0],
                        }
                    )
                    + "\n\n"
                )
                await asyncio.sleep(1)

        return StreamingResponse(
            stream(), media_type="text/event-stream", headers={"Cache-Control": "no-cache"}
        )

    from .phone import receiver_app

    app.mount("/screen-ingest", receiver_app(settings, purpose="screen"))

    frontend = Path(__file__).resolve().parents[2] / "dist"
    if frontend.exists():
        app.mount("/", StaticFiles(directory=frontend, html=True), name="ui")
    else:

        @app.get("/")
        def no_ui():
            return {
                "message": "Run npm run build to build the MatchLens interface",
                "status": "backend ready",
            }

    return app

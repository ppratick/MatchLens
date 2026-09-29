from __future__ import annotations

import hashlib
import json
import os
import secrets
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse
from filelock import FileLock

from .domain import now, uid
from .storage import Store, atomic_json


def create_pair(store, supervisor, match_id, purpose="phone"):
    store.get(match_id)
    source_id, pair_id, secret = uid(), uid(), secrets.token_urlsafe(32)
    source = {
        "id": source_id,
        "name": "Mac screen recording" if purpose == "screen" else "Phone television recording",
        "kind": purpose,
        "profile": "screen" if purpose == "screen" else "phone_tv",
        "status": "recording",
        "offset": 0,
        "duration": 0,
        "segments": [],
        "width": 1280,
        "height": 720,
    }
    store.put_source(match_id, source)
    spool = f"original/{source_id}-received.bin"
    job = supervisor.enqueue(
        match_id, "capture", {"kind": "phone", "source_id": source_id, "spool": spool, "pair_id": pair_id}
    )
    pairing = {
        "id": pair_id,
        "purpose": purpose,
        "sender_epoch": None,
        "health_events": [],
        "match_id": match_id,
        "source_id": source_id,
        "job_id": job["id"],
        "spool": spool,
        "secret_hash": hashlib.sha256(secret.encode()).hexdigest(),
        "expires": now() + 4 * 3600,
        "next_sequence": 0,
        "bytes": 0,
        "last_digest": None,
        "finished": False,
    }
    root = store.settings.data_dir / "pairing"
    root.mkdir(exist_ok=True, mode=0o700)
    atomic_json(root / f"{pair_id}.json", pairing)
    return {
        "pair_id": pair_id,
        "secret": secret,
        "expires": pairing["expires"],
        "job_id": job["id"],
        "fragment": f"#{pair_id}:{secret}",
        "receiver_port": 8766,
        "instructions": "Start the separate HTTPS phone receiver, then open its LAN URL with this pairing fragment. Keep the phone awake.",
    }


def receiver_app(settings, purpose="phone"):
    store = Store(settings)
    app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)

    @app.exception_handler(ValueError)
    async def invalid(request, exc):
        from fastapi.responses import JSONResponse

        return JSONResponse({"detail": str(exc)}, 400)

    def authenticate(pair_id, request):
        if len(pair_id) != 32 or any(c not in "0123456789abcdef" for c in pair_id):
            raise HTTPException(404, "Pairing not found")
        path = settings.data_dir / "pairing" / f"{pair_id}.json"
        if not path.exists():
            raise HTTPException(404, "Pairing not found")
        pairing = json.loads(path.read_text())
        if pairing.get("purpose", "phone") != purpose:
            raise HTTPException(403, "Pairing belongs to another capture channel")
        given = hashlib.sha256(request.headers.get("x-pair-secret", "").encode()).hexdigest()
        if pairing["expires"] < now() or not secrets.compare_digest(given, pairing["secret_hash"]):
            raise HTTPException(403, "Pairing expired or invalid")
        store.get(pairing["match_id"])
        return path, pairing

    @app.middleware("http")
    async def headers(request, call_next):
        origin = request.headers.get("origin")
        if origin and origin.rstrip("/") != str(request.base_url).rstrip("/"):
            from fastapi.responses import JSONResponse

            return JSONResponse({"detail": "Cross-origin ingest refused"}, 403)
        response = await call_next(request)
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["X-Content-Type-Options"] = "nosniff"
        return response

    @app.get("/", response_class=HTMLResponse)
    def page():
        return (Path(__file__).parent / "sender/index.html").read_text()

    @app.get("/sender.js")
    def sender_script():
        return FileResponse(Path(__file__).parent / "sender/sender.js", media_type="text/javascript")

    @app.post("/television/{pair_id}")
    async def television(pair_id: str, request: Request):
        from .television import save_setup

        _, pairing = authenticate(pair_id, request)
        if purpose != "phone":
            raise HTTPException(403, "Television setup is for paired phone capture only")
        body = await request.json()
        body["revision"] = store.review(pairing["match_id"])[0]
        return save_setup(store, pairing["match_id"], pairing["source_id"], body)

    @app.post("/ingest/{pair_id}/{sequence}")
    async def ingest(pair_id: str, sequence: int, request: Request):
        path, pairing = authenticate(pair_id, request)
        if sequence < 0:
            raise HTTPException(400, "Invalid sequence")
        settings.require_space()
        sender_epoch = request.headers.get("x-sender-epoch")
        if sender_epoch and len(sender_epoch) > 100:
            raise HTTPException(400, "Invalid sender epoch")
        staged = settings.data_dir / "temporary" / f"{uid()}.chunk"
        digest = hashlib.sha256()
        size = 0
        try:
            with staged.open("wb") as out:
                async for chunk in request.stream():
                    size += len(chunk)
                    if size > 32 * 1024 * 1024:
                        raise HTTPException(413, "Chunk exceeds 32 MiB; lower capture bitrate")
                    out.write(chunk)
                    digest.update(chunk)
            with FileLock(str(path) + ".lock", timeout=5):
                pairing = json.loads(path.read_text())
                if pairing.get("sender_epoch") and sender_epoch != pairing["sender_epoch"]:
                    raise HTTPException(
                        409,
                        "Recorder epoch changed. Create a new pairing/source; never append a restarted recorder to this timeline.",
                    )
                if sequence == pairing["next_sequence"] - 1 and digest.hexdigest() == pairing["last_digest"]:
                    return {"next_sequence": pairing["next_sequence"], "duplicate": True}
                if sequence != pairing["next_sequence"] or pairing["finished"]:
                    raise HTTPException(409, f"Expected sequence {pairing['next_sequence']}")
                spool = store.path(pairing["match_id"], pairing["spool"])
                # Last committed byte offset makes a crash between append and metadata commit recoverable.
                with spool.open("r+b" if spool.exists() else "w+b") as out, staged.open("rb") as src:
                    out.truncate(pairing["bytes"])
                    out.seek(pairing["bytes"])
                    while chunk := src.read(256 * 1024):
                        out.write(chunk)
                    out.flush()
                    os.fsync(out.fileno())
                pairing.update(
                    sender_epoch=sender_epoch or pairing.get("sender_epoch"),
                    next_sequence=sequence + 1,
                    bytes=pairing["bytes"] + size,
                    last_digest=digest.hexdigest(),
                    last_received=now(),
                )
                atomic_json(path, pairing)
                return {"next_sequence": sequence + 1, "bytes": pairing["bytes"]}
        finally:
            staged.unlink(missing_ok=True)

    @app.get("/status/{pair_id}")
    def status(pair_id: str, request: Request):
        _, pairing = authenticate(pair_id, request)
        source = store.source(pairing["match_id"], pairing["source_id"])
        job = store.job(pairing["match_id"], pairing["job_id"])
        return {
            "next_sequence": pairing["next_sequence"],
            "bytes": pairing["bytes"],
            "sender_epoch": pairing.get("sender_epoch"),
            "finished": pairing["finished"],
            "recording_state": job["status"],
            "recorded_seconds": source.get("duration", 0),
            "segments": len(source.get("segments", [])),
            "last_received": pairing.get("last_received"),
            "error": job.get("error"),
            "source_id": pairing["source_id"],
        }

    @app.post("/health/{pair_id}")
    async def health(pair_id: str, request: Request):
        from typing import Literal

        from pydantic import Field

        from .domain import StrictModel

        class Health(StrictModel):
            state: Literal["paused", "resumed", "suspended", "track_ended"]
            elapsed_ms: float = Field(ge=0, le=24 * 3600 * 1000)

        path, pairing = authenticate(pair_id, request)
        body = Health.model_validate(await request.json()).model_dump()
        with FileLock(str(path) + ".lock", timeout=5):
            pairing = json.loads(path.read_text())
            if pairing["finished"]:
                raise HTTPException(409, "Recording finalized")
            if len(pairing.get("health_events", [])) >= 5000:
                raise HTTPException(413, "Too many discontinuities; finalize and create a new source")
            source = store.source(pairing["match_id"], pairing["source_id"])
            pairing.setdefault("health_events", []).append(
                {**body, "received": now(), "after": source.get("duration", 0), "position_known": False}
            )
            atomic_json(path, pairing)
        return {"saved": True}

    @app.post("/finish/{pair_id}")
    def finish(pair_id: str, request: Request):
        path, pairing = authenticate(pair_id, request)
        with FileLock(str(path) + ".lock", timeout=5):
            pairing = json.loads(path.read_text())
            pairing["finished"] = True
            atomic_json(path, pairing)
        # The capture worker drains the committed spool before finalizing.
        marker = store.path(pairing["match_id"], pairing["spool"] + ".finished")
        marker.touch()
        return {"finished": True}

    return app

from __future__ import annotations

import hashlib
import json
import os
import secrets

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse
from filelock import FileLock

from .domain import now, uid
from .storage import Store, atomic_json


def create_pair(store, supervisor, match_id):
    source_id, pair_id, secret = uid(), uid(), secrets.token_urlsafe(32)
    source = {
        "id": source_id,
        "name": "Phone stream",
        "kind": "phone",
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


def receiver_app(settings):
    store = Store(settings)
    app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)

    def authenticate(pair_id, request):
        if len(pair_id) != 32 or any(c not in "0123456789abcdef" for c in pair_id):
            raise HTTPException(404, "Pairing not found")
        path = settings.data_dir / "pairing" / f"{pair_id}.json"
        if not path.exists():
            raise HTTPException(404, "Pairing not found")
        pairing = json.loads(path.read_text())
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
        return PHONE_PAGE

    @app.post("/ingest/{pair_id}/{sequence}")
    async def ingest(pair_id: str, sequence: int, request: Request):
        path, pairing = authenticate(pair_id, request)
        if sequence < 0:
            raise HTTPException(400, "Invalid sequence")
        settings.require_space()
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
                    next_sequence=sequence + 1,
                    bytes=pairing["bytes"] + size,
                    last_digest=digest.hexdigest(),
                    last_received=now(),
                )
                atomic_json(path, pairing)
                return {"next_sequence": sequence + 1, "bytes": pairing["bytes"]}
        finally:
            staged.unlink(missing_ok=True)

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


PHONE_PAGE = r"""<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>MatchLens · Camera</title>
<style>body{margin:0;padding:28px;background:#101d1b;color:#eef2e9;font:16px system-ui}main{max-width:640px;margin:auto}h1{font-size:40px;letter-spacing:-2px}video{width:100%;border-radius:16px;background:#07100f}button{padding:14px 22px;background:#dbfa8d;border:0;border-radius:10px;font:inherit;margin:8px 8px 8px 0}p{line-height:1.6;color:#b6c6bc}#status{color:#dbfa8d}small{display:block;margin:20px 0}</style>
<main><small>MATCHLENS / LOCAL CAMERA</small><h1>Your sideline. Connected.</h1><p>Video goes directly to your computer over your local network. Keep this page open, your phone awake, and connect power for a full match.</p><video id="preview" autoplay muted playsinline></video><p id="status">Ready to connect</p><button id="start">Start camera</button><button id="stop" disabled>Finish recording</button><small>Network interruptions are retried in order. A full buffer pauses capture and creates a visible coverage gap. Phone lock/background capture is not guaranteed.</small></main>
<script>
const [pair,secret]=location.hash.slice(1).split(':');let recorder,stream,queue=[],sequence=0,sending=false,finishing=false,wake;const status=document.getElementById('status');
async function send(){if(sending)return;sending=true;try{while(queue.length){const blob=queue[0];try{const r=await fetch('/ingest/'+pair+'/'+sequence,{method:'POST',headers:{'x-pair-secret':secret},body:blob});if(!r.ok)throw Error(await r.text());queue.shift();sequence++;status.textContent='Recording · '+sequence+' chunks saved on computer';if(recorder.state==='paused'&&queue.length<3){recorder.resume();status.textContent+=' · resumed after network gap'}}catch(e){status.textContent='Connection interrupted · retrying. '+String(e).slice(0,90);await new Promise(r=>setTimeout(r,1500));if(finishing&&queue.length===0)break}}}finally{sending=false}if(finishing){await fetch('/finish/'+pair,{method:'POST',headers:{'x-pair-secret':secret}});status.textContent='Saved on your computer';stream.getTracks().forEach(t=>t.stop());wake?.release()}}
document.getElementById('start').onclick=async()=>{try{if(!pair||!secret)throw Error('Open the pairing link from MatchLens on your computer');stream=await navigator.mediaDevices.getUserMedia({video:{facingMode:{ideal:'environment'},width:{ideal:1280},height:{ideal:720},frameRate:{ideal:30}},audio:true});document.getElementById('preview').srcObject=stream;const mime=['video/webm;codecs=vp8,opus','video/mp4;codecs=avc1.42E01E,mp4a.40.2','video/mp4'].find(m=>MediaRecorder.isTypeSupported(m));recorder=new MediaRecorder(stream,{...(mime?{mimeType:mime}:{}),videoBitsPerSecond:4000000});recorder.ondataavailable=e=>{if(e.data.size){queue.push(e.data);if(queue.reduce((s,b)=>s+b.size,0)>24*1024*1024&&recorder.state==='recording'){recorder.pause();status.textContent='Network buffer full · capture paused, coverage gap begins'}send()}};recorder.onstop=()=>{finishing=true;send()};recorder.start(2000);document.getElementById('start').disabled=true;document.getElementById('stop').disabled=false;status.textContent='Recording locally to computer';try{wake=await navigator.wakeLock.request('screen')}catch{}}catch(e){status.textContent=String(e)}};
document.getElementById('stop').onclick=()=>{document.getElementById('stop').disabled=true;recorder.stop()};
</script></html>"""

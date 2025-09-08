from __future__ import annotations

"""Greenfield control-plane API (FastAPI) with WebSocket events.

Endpoints:
- GET /models/asr -> local ASR models discovered (faster-whisper CT2 dirs or names if cached)
- GET /models/mt  -> local MT models discovered in HF cache
- GET /languages/mt/{model_id} -> supported target languages
- POST /models/download -> trigger HF snapshot download, progress via WS on channel "_download"
- POST /sessions -> create a new session; returns {session_id}
- DELETE /sessions/{sid} -> stop session
- WS /events/{sid} -> multiplexed event stream for a session id (JSON messages)

All new code intentionally lives under greenfield/api/.
"""

import asyncio
import time
import os
import uuid
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from .model_discovery import list_asr_models, list_mt_models, mt_supported_languages
from .supervisor import SessionConfig, SessionManager
from .events import EventStamper


ALLOWED_ORIGINS = os.getenv("GF_ALLOWED_ORIGINS", "http://localhost:5173").split(",")
app = FastAPI(title="Greenfield API", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve outputs directory for easy linking from UI (hardened)
OUT_ROOT = Path(os.getenv("GF_OUT_DIR", "loquilex/out")).resolve()
OUT_ROOT.mkdir(parents=True, exist_ok=True)

def _safe_session_dir(sid: str) -> Path:
    if not re.fullmatch(r"[A-Za-z0-9_-]{6,64}", sid):
        raise HTTPException(status_code=400, detail="bad sid")
    p = (OUT_ROOT / sid).resolve()
    if not str(p).startswith(str(OUT_ROOT)):
        raise HTTPException(status_code=400, detail="invalid path")
    return p

app.mount("/out", StaticFiles(directory=str(OUT_ROOT), html=False), name="out")

# Global manager instance
MANAGER = SessionManager()

class CreateSessionReq(BaseModel):
    name: Optional[str] = Field(default=None)
    asr_model_id: str
    mt_enabled: bool = Field(default=True)
    mt_model_id: Optional[str] = Field(default=None)
    dest_lang: str = Field(default="zho_Hans")
    device: str = Field(default="auto")  # auto|cuda|cpu
    vad: bool = Field(default=True)
    beams: int = Field(default=1)
    pause_flush_sec: float = Field(default=0.7)
    segment_max_sec: float = Field(default=7.0)
    partial_word_cap: int = Field(default=10)
    save_audio: str = Field(default="off")  # off|wav|flac

class CreateSessionResp(BaseModel):
    session_id: str

# (Mounted above)

class DownloadReq(BaseModel):
    repo_id: str
    type: str = Field(description="asr|mt|other")


class DownloadCancelResp(BaseModel):
    cancelled: bool


class SelfTestReq(BaseModel):
    asr_model_id: str | None = None
    device: str = Field(default="auto")
    seconds: float = Field(default=1.5)

class SelfTestResp(BaseModel):
    ok: bool
    asr_load_ms: int
    rms_avg: float
    message: str
    effective_asr_model: Optional[str] = None
    effective_device: Optional[str] = None
    effective_compute: Optional[str] = None
    sample_rate: Optional[int] = None


# Simple profiles CRUD on disk under greenfield/ui/profiles
PROFILES_DIR = os.path.join("greenfield", "ui", "profiles")


@app.get("/profiles")
def get_profiles() -> List[str]:
    if not os.path.isdir(PROFILES_DIR):
        return []
    return sorted([p[:-5] for p in os.listdir(PROFILES_DIR) if p.endswith('.json')])


@app.get("/profiles/{name}")
def get_profile(name: str) -> Dict[str, Any]:
    safe = "".join(c for c in name if c.isalnum() or c in ("-", "_"))
    path = os.path.join(PROFILES_DIR, f"{safe}.json")
    if not os.path.isfile(path):
        raise HTTPException(status_code=404, detail="not found")
    import json as _json
    with open(path, "r", encoding="utf-8") as f:
        return _json.load(f)


@app.post("/profiles/{name}")
def save_profile(name: str, body: Dict[str, Any]) -> Dict[str, Any]:
    os.makedirs(PROFILES_DIR, exist_ok=True)
    safe = "".join(c for c in name if c.isalnum() or c in ("-", "_"))
    path = os.path.join(PROFILES_DIR, f"{safe}.json")
    import json as _json
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        _json.dump(body, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)
    return {"ok": True}


@app.delete("/profiles/{name}")
def delete_profile(name: str) -> Dict[str, Any]:
    safe = "".join(c for c in name if c.isalnum() or c in ("-", "_"))
    path = os.path.join(PROFILES_DIR, f"{safe}.json")
    if os.path.isfile(path):
        os.remove(path)
    return {"ok": True}


@app.get("/models/asr")
def get_asr_models() -> List[Dict[str, Any]]:
    return list_asr_models()


@app.get("/models/mt")
def get_mt_models() -> List[Dict[str, Any]]:
    return list_mt_models()


@app.get("/languages/mt/{model_id}")
def get_mt_langs(model_id: str) -> Dict[str, Any]:
    return {"model_id": model_id, "languages": mt_supported_languages(model_id)}


@app.post("/models/download")
async def post_download(req: DownloadReq) -> Dict[str, Any]:
    job_id = str(uuid.uuid4())
    # Use the manager's background downloader so progress can be broadcast on WS channel "_download"
    MANAGER.start_download_job(job_id, req.repo_id, req.type)
    return {"job_id": job_id, "status": "started"}


@app.delete("/models/download/{job_id}", response_model=DownloadCancelResp)
async def delete_download(job_id: str) -> DownloadCancelResp:
    ok = MANAGER.cancel_download(job_id)
    return DownloadCancelResp(cancelled=ok)


@app.post("/sessions", response_model=CreateSessionResp)
async def create_session(req: CreateSessionReq) -> CreateSessionResp:
    cfg = SessionConfig(
        name=req.name or "session",
        asr_model_id=req.asr_model_id,
        mt_enabled=req.mt_enabled,
        mt_model_id=req.mt_model_id,
        dest_lang=req.dest_lang,
        device=req.device,
        vad=req.vad,
        beams=req.beams,
        pause_flush_sec=req.pause_flush_sec,
        segment_max_sec=req.segment_max_sec,
        partial_word_cap=req.partial_word_cap,
        save_audio=req.save_audio,
    )
    try:
        sid = MANAGER.start_session(cfg)
        return CreateSessionResp(session_id=sid)
    except RuntimeError as e:
        msg = str(e)
        status = 409 if "GPU busy" in msg else 400
        detail = {"error": msg, "requested_device": req.device}
        raise HTTPException(status_code=status, detail=detail)


@app.post("/sessions/selftest", response_model=SelfTestResp)
async def post_selftest(req: SelfTestReq) -> SelfTestResp:
    # Minimal self-test: try to import WhisperEngine and warm up; capture a short mic window and compute RMS
    import numpy as np
    from greenfield.asr.whisper_engine import WhisperEngine
    from greenfield.audio.capture import capture_stream
    from .vu import rms_peak, EmaVu

    t0 = time.perf_counter()
    try:
        os.environ["GF_ASR_MODEL"] = req.asr_model_id or os.getenv("GF_ASR_MODEL", "small.en")
        os.environ["GF_DEVICE"] = req.device
        eng = WhisperEngine()
        eng.warmup()
        asr_ms = int((time.perf_counter() - t0) * 1000)
    except Exception as e:
        return SelfTestResp(ok=False, asr_load_ms=0, rms_avg=0.0, message=f"ASR load failed: {e}")

    ema = EmaVu(0.4)
    levels: list[float] = []
    stop_fn = None
    try:
        def cb(fr) -> None:
            r, p = rms_peak(fr.data)
            r2, _ = ema.update(r, p)
            levels.append(r2)
        stop_fn = capture_stream(cb)
        await asyncio.sleep(min(3.0, max(0.2, req.seconds)))
    except Exception as e:
        return SelfTestResp(ok=False, asr_load_ms=asr_ms, rms_avg=0.0, message=f"mic failed: {e}")
    finally:
        if stop_fn:
            try:
                stop_fn()
            except Exception:
                pass

    rms_avg = float(np.mean(levels)) if levels else 0.0
    ok = rms_avg > 1e-4
    # Effective runtime details
    try:
        from greenfield.config.defaults import ASR as _ASR
        sample_rate = _ASR.sample_rate
    except Exception:
        sample_rate = None
    return SelfTestResp(
        ok=ok,
        asr_load_ms=asr_ms,
        rms_avg=rms_avg,
        message="ok" if ok else "no mic signal detected",
        effective_asr_model=getattr(eng, "model_name", None),
        effective_device=getattr(eng, "device", None),
        effective_compute=getattr(eng, "dtype", None),
        sample_rate=sample_rate,
    )


@app.delete("/sessions/{sid}")
async def stop_session(sid: str) -> Dict[str, Any]:
    ok = MANAGER.stop_session(sid)
    if not ok:
        raise HTTPException(status_code=404, detail="session not found")
    return {"stopped": True}

@app.post("/sessions/{sid}/pause")
async def pause_session(sid: str) -> Dict[str, Any]:
    sess = MANAGER._sessions.get(sid)
    if not sess:
        raise HTTPException(status_code=404, detail="session not found")
    sess.pause()
    return {"ok": True}

@app.post("/sessions/{sid}/resume")
async def resume_session(sid: str) -> Dict[str, Any]:
    sess = MANAGER._sessions.get(sid)
    if not sess:
        raise HTTPException(status_code=404, detail="session not found")
    sess.resume()
    return {"ok": True}

@app.post("/sessions/{sid}/finalize")
async def finalize_session(sid: str) -> Dict[str, Any]:
    sess = MANAGER._sessions.get(sid)
    if not sess:
        raise HTTPException(status_code=404, detail="session not found")
    sess.finalize_now()
    return {"ok": True}

@app.get("/sessions/{sid}/snapshot")
async def get_snapshot(sid: str) -> Dict[str, Any]:
    sess = MANAGER._sessions.get(sid)
    if not sess:
        raise HTTPException(status_code=404, detail="session not found")
    return {
        "sid": sid,
        "cfg": sess.cfg.__dict__,
        "status": "running" if (sess.proc and sess.proc.poll() is None) else "stopped",
    }


@app.websocket("/events/{sid}")
async def ws_events(ws: WebSocket, sid: str) -> None:
    origin = ws.headers.get("origin", "")
    if origin not in ALLOWED_ORIGINS:
        raise WebSocketDisconnect(code=4403)
    await ws.accept()
    try:
        await MANAGER.register_ws(sid, ws)
        while True:
            try:
                await ws.receive_text()
            except Exception:
                await asyncio.sleep(10)
    except WebSocketDisconnect:
        pass
    finally:
        await MANAGER.unregister_ws(sid, ws)


def main() -> None:
    # Entry point for `python -m greenfield.api.server`
    import uvicorn

    port = int(os.getenv("GF_API_PORT", "8000"))
    uvicorn.run("greenfield.api.server:app", host="0.0.0.0", port=port, reload=False)


if __name__ == "__main__":
    main()

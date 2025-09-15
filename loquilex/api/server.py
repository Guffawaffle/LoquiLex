from __future__ import annotations

import asyncio
import logging
import os
import re
import time
import uuid
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from .model_discovery import list_asr_models, list_mt_models, mt_supported_languages
from .supervisor import SessionConfig, SessionManager, StreamingSession

logger = logging.getLogger(__name__)

"""LoquiLex control-plane API (FastAPI) with WebSocket events.

Endpoints:
- GET /models/asr -> local ASR models discovered (faster-whisper CT2 dirs or names if cached)
- GET /models/mt  -> local MT models discovered in HF cache
- GET /languages/mt/{model_id} -> supported target languages
- POST /models/download -> trigger HF snapshot download, progress via WS on channel "_download"
- POST /sessions -> create a new session; returns {session_id}
- DELETE /sessions/{sid} -> stop session
- WS /events/{sid} -> multiplexed event stream for a session id (JSON messages)

All new code intentionally lives under loquilex/api/.
"""

# Allow localhost and 127.0.0.1 by default for dev. Can be overridden via LLX_ALLOWED_ORIGINS.
ALLOWED_ORIGINS = os.getenv(
    "LLX_ALLOWED_ORIGINS",
    "http://localhost:5173,http://127.0.0.1:5173",
).split(",")

# Environment variables for server configuration
API_PORT = int(os.getenv("LX_API_PORT", "8000"))
UI_PORT = int(os.getenv("LX_UI_PORT", "5173"))
WS_PATH = os.getenv("LX_WS_PATH", "/ws")

app = FastAPI(title="LoquiLex API", version="0.1.0")

# CSP and security headers
@app.middleware("http")
async def security_headers(request: Request, call_next):
    response = await call_next(request)
    # Strict CSP for production with some dev allowances
    csp = (
        "default-src 'self'; "
        "script-src 'self'; "
        "style-src 'self' 'unsafe-inline'; "  # Allow inline styles for Vite CSS 
        "img-src 'self' blob:; "
        "font-src 'self'; "
        "connect-src 'self' ws://127.0.0.1:*; "
        "object-src 'none'; "
        "frame-ancestors 'none'; "
        "base-uri 'self';"
    )
    response.headers["Content-Security-Policy"] = csp
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Permissions-Policy"] = "microphone=()"
    return response

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve outputs directory for easy linking from UI (hardened)
OUT_ROOT = Path(os.getenv("LLX_OUT_DIR", "loquilex/out")).resolve()
OUT_ROOT.mkdir(parents=True, exist_ok=True)

# UI static files serving
UI_DIST_PATH = Path("ui/app/dist").resolve()

def _safe_session_dir(sid: str) -> Path:
    if not re.fullmatch(r"[A-Za-z0-9_-]{6,64}", sid):
        raise HTTPException(status_code=400, detail="bad sid")
    p = (OUT_ROOT / sid).resolve()
    if not str(p).startswith(str(OUT_ROOT)):
        raise HTTPException(status_code=400, detail="invalid path")
    return p

app.mount("/out", StaticFiles(directory=str(OUT_ROOT), html=False), name="out")

# Mount UI static files at root if they exist
if UI_DIST_PATH.exists() and UI_DIST_PATH.is_dir():
    # Mount assets directory for CSS/JS files
    assets_path = UI_DIST_PATH / "assets"
    if assets_path.exists():
        app.mount("/assets", StaticFiles(directory=str(assets_path)), name="assets")

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
    streaming_mode: bool = Field(default=False)  # Enable new streaming ASR pipeline


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


# Simple profiles CRUD on disk under loquilex/ui/profiles
PROFILES_DIR = os.path.join("loquilex", "ui", "profiles")


@app.get("/profiles")
def get_profiles() -> List[str]:
    if not os.path.isdir(PROFILES_DIR):
        return []
    return sorted([p[:-5] for p in os.listdir(PROFILES_DIR) if p.endswith(".json")])


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


@app.get("/healthz")
async def healthz() -> Dict[str, Any]:
    """Health endpoint for Electron readiness check."""
    return {"status": "ok", "timestamp": time.time()}


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
        streaming_mode=req.streaming_mode,
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

    from loquilex.asr.whisper_engine import WhisperEngine
    from loquilex.audio.capture import capture_stream

    from .vu import EmaVu, rms_peak

    t0 = time.perf_counter()
    try:
        os.environ["LX_ASR_MODEL"] = req.asr_model_id or os.getenv("LX_ASR_MODEL") or "small.en"
        os.environ["LX_DEVICE"] = req.device
        eng = WhisperEngine()
        eng.warmup()
        asr_ms = int((time.perf_counter() - t0) * 1000)
    except Exception as e:
        return SelfTestResp(ok=False, asr_load_ms=0, rms_avg=0.0, message=f"ASR load failed: {e}")

    ema = EmaVu(0.4)
    levels: list[float] = []
    stop_fn: Optional[Callable[[], None]] = None
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
        if stop_fn is not None:
            try:
                stop_fn()
            except Exception:
                pass

    rms_avg = float(np.mean(levels)) if levels else 0.0
    ok = rms_avg > 1e-4
    # Effective runtime details
    try:
        from loquilex.config.defaults import ASR as _ASR

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


@app.get("/sessions/{sid}/metrics")
async def get_session_metrics(sid: str) -> Dict[str, Any]:
    """Get performance metrics for a streaming session."""
    sess = MANAGER._sessions.get(sid)
    if not sess:
        raise HTTPException(status_code=404, detail="session not found")

    if isinstance(sess, StreamingSession):
        try:
            metrics = sess.get_metrics()
            if metrics is None:
                raise HTTPException(status_code=503, detail="metrics not available")
            return metrics
        except Exception:
            logger.exception("metrics error")
            raise HTTPException(status_code=500, detail="metrics error")
    else:
        raise HTTPException(
            status_code=400, detail="metrics not available for non-streaming session"
        )


@app.get("/sessions/{sid}/asr/snapshot")
async def get_asr_snapshot(sid: str) -> Dict[str, Any]:
    """Get ASR snapshot for reconnect scenarios (streaming sessions only)."""
    sess = MANAGER._sessions.get(sid)
    if not sess:
        raise HTTPException(status_code=404, detail="session not found")

    if isinstance(sess, StreamingSession):
        snapshot = sess.get_asr_snapshot()
        if snapshot is None:
            raise HTTPException(status_code=503, detail="ASR snapshot not available")
        return snapshot
    else:
        raise HTTPException(
            status_code=400, detail="snapshot not available for non-streaming session"
        )


@app.get("/sessions/{sid}/snapshot")
async def get_snapshot(sid: str) -> Dict[str, Any]:
    sess = MANAGER._sessions.get(sid)
    if not sess:
        raise HTTPException(status_code=404, detail="session not found")

    # Try to get ASR snapshot if session has streaming ASR
    asr_snapshot = None
    if hasattr(sess, "get_asr_snapshot"):
        try:
            asr_snapshot = sess.get_asr_snapshot()
        except Exception:
            pass  # ASR snapshot is optional

    # Try to get MT status if session supports it
    mt_status = None
    if hasattr(sess, "get_mt_status"):
        try:
            mt_status = sess.get_mt_status()
        except Exception:
            pass  # MT status is optional

    # Determine status correctly for both regular and streaming sessions
    if hasattr(sess, "_audio_thread") and sess._audio_thread is not None:
        # Streaming session - check audio thread
        status = "running" if sess._audio_thread.is_alive() else "stopped"
    else:
        # Regular session - check subprocess
        status = (
            "running"
            if (sess.proc and getattr(sess.proc, "poll", lambda: None)() is None)
            else "stopped"
        )

    base_snapshot = {
        "sid": sid,
        "cfg": sess.cfg.__dict__,
        "status": status,
    }

    if asr_snapshot:
        base_snapshot["asr"] = asr_snapshot

    if mt_status:
        base_snapshot["mt"] = mt_status

    return base_snapshot


@app.websocket(WS_PATH + "/{sid}")
async def ws_events(ws: WebSocket, sid: str) -> None:
    origin = ws.headers.get("origin", "")
    if origin not in ALLOWED_ORIGINS:
        raise WebSocketDisconnect(code=4403)
    await ws.accept()
    try:
        await MANAGER.register_ws(sid, ws)
        while True:
            try:
                # Receive and process messages through the protocol manager
                message = await ws.receive_text()
                await MANAGER.handle_ws_message(sid, ws, message)
            except WebSocketDisconnect:
                break
            except Exception as e:
                logger.exception(f"WebSocket message handling error: {e}")
                await asyncio.sleep(1)  # Brief pause before retry
    except WebSocketDisconnect:
        pass
    finally:
        await MANAGER.unregister_ws(sid, ws)


# SPA fallback route - must be last to catch all unmatched routes
@app.get("/{full_path:path}")
@app.head("/{full_path:path}")
async def spa_fallback(full_path: str) -> FileResponse:  # noqa: ARG001
    """Serve SPA index.html for all unknown routes (client-side routing)."""
    if UI_DIST_PATH.exists() and UI_DIST_PATH.is_dir():
        index_path = UI_DIST_PATH / "index.html"
        if index_path.exists():
            return FileResponse(str(index_path), media_type="text/html")
    # Fallback to 404 if no UI is built
    raise HTTPException(status_code=404, detail="Not found")


def main() -> None:
    # Entry point for `python -m loquilex.api.server`
    import uvicorn

    port = API_PORT
    uvicorn.run("loquilex.api.server:app", host="0.0.0.0", port=port, reload=False)


if __name__ == "__main__":
    main()

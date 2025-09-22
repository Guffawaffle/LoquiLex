from __future__ import annotations

import asyncio
import logging
import os
import re
import time
import uuid
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, model_validator

from .model_discovery import mt_supported_languages
from .supervisor import SessionConfig, SessionManager, StreamingSession
from ..config.model_defaults import get_model_defaults_manager
from ..indexing import get_model_indexer
from ..hardware import get_hardware_snapshot

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
# Optional dev-only alias to accept legacy /events path when explicitly allowed.
ALLOW_EVENTS_ALIAS = os.getenv("LX_WS_ALLOW_EVENTS_ALIAS", "0") == "1"
DEV_MODE = os.getenv("LX_DEV", "0") == "1"

# One-time flag for /events alias deprecation logging
_events_alias_warned = False

app = FastAPI(title="LoquiLex API", version="0.1.0")


# Hardware snapshot cache and configuration
# TTL for cached snapshot in seconds (default 30s) and timeout for probing (default 10s)
_HW_SNAPSHOT_TTL = float(os.getenv("LX_HW_SNAPSHOT_TTL_SEC", "30"))
_HW_SNAPSHOT_TIMEOUT = float(os.getenv("LX_HW_SNAPSHOT_TIMEOUT_SEC", "10"))
# Cache and lock (kept un-annotated to avoid complex serialization in typecheck)
_hw_snapshot_cache = None
_hw_snapshot_cache_ts = 0.0
_hw_snapshot_lock = None

# Admin token for protected endpoints (optional). When set, endpoints under
# `/admin/*` require a Bearer token in `Authorization` or `X-Admin-Token` header.
_ADMIN_TOKEN = os.getenv("LX_ADMIN_TOKEN")


# CSP and security headers
@app.middleware("http")
async def security_headers(request: Request, call_next):
    response = await call_next(request)
    # Production: strict CSP, no 'unsafe-inline'
    if DEV_MODE:
        csp = (
            "default-src 'self'; "
            "script-src 'self'; "
            "style-src 'self' 'unsafe-inline'; "
            "img-src 'self' blob:; "
            "font-src 'self'; "
            "connect-src 'self' ws: http://127.0.0.1:* http://localhost:*; "
            "object-src 'none'; "
            "frame-ancestors 'none'; "
            "base-uri 'self'"
        )
    else:
        csp = (
            "default-src 'self'; "
            "script-src 'self'; "
            "style-src 'self'; "
            "img-src 'self' blob:; "
            "font-src 'self'; "
            "connect-src 'self' ws://127.0.0.1:*; "
            "object-src 'none'; "
            "frame-ancestors 'none'; "
            "base-uri 'self'"
        )

    response.headers["Content-Security-Policy"] = csp
    response.headers["Permissions-Policy"] = "microphone=(self)"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["X-Content-Type-Options"] = "nosniff"
    return response


if DEV_MODE:
    # Enable CORS only in explicit dev mode to allow Vite HMR during development
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

# UI static files path (mounted later to avoid shadowing API routes)
UI_DIST_PATH = Path("ui/app/dist").resolve()


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

# Initialize model indexer and start background worker
MODEL_INDEXER = get_model_indexer()
MODEL_INDEXER.start_background_worker()


class CreateSessionReq(BaseModel):
    """Create session request model.

    📖 Contract: /docs/contracts/session-management.md
    """

    name: Optional[str] = Field(default=None)
    asr_model_id: str
    mt_enabled: bool = Field(default=False)
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

    # Validate MT settings: require model id only when enabled
    @model_validator(mode="before")
    @classmethod
    def _validate_mt(cls, values: Dict[str, Any]):
        # Mirror field default: treat missing as disabled to ease minimal payloads
        mt_enabled = values.get("mt_enabled", False)
        if mt_enabled and not values.get("mt_model_id"):
            raise ValueError("mt_model_id is required when mt_enabled=True")
        return values


class CreateSessionResp(BaseModel):
    session_id: str


# (Mounted above)


class DownloadReq(BaseModel):
    """Model download request.

    📖 Contract: /docs/contracts/downloads-api.md
    """

    repo_id: str
    type: str = Field(description="asr|mt|other")


class DownloadCancelResp(BaseModel):
    cancelled: bool


class SelfTestReq(BaseModel):
    """Device self-test request.

    📖 Contract: /docs/contracts/device-testing.md
    """

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


class UpdateDefaultsReq(BaseModel):
    """Request to update model defaults."""

    asr_model_id: Optional[str] = None
    asr_device: Optional[str] = None
    asr_compute_type: Optional[str] = None
    mt_model_id: Optional[str] = None
    mt_device: Optional[str] = None
    mt_compute_type: Optional[str] = None
    tts_model_id: Optional[str] = None
    tts_device: Optional[str] = None


class ModelDefaultsResp(BaseModel):
    """Model defaults response."""

    asr_model_id: str
    asr_device: str
    asr_compute_type: str
    mt_model_id: str
    mt_device: str
    mt_compute_type: str
    tts_model_id: str
    tts_device: str


# Simple profiles CRUD on disk under loquilex/ui/profiles
PROFILES_DIR = os.path.join("loquilex", "ui", "profiles")


@app.get("/sessions/{sid}/storage/stats")
async def get_session_storage_stats(sid: str) -> Dict[str, Any]:
    """Get session storage statistics."""
    sess = MANAGER._sessions.get(sid)
    if not sess:
        raise HTTPException(status_code=404, detail="session not found")

    if hasattr(sess, "state") and sess.state:
        stats = sess.state.get_session_storage_stats()
        if stats:
            return stats
        else:
            raise HTTPException(status_code=503, detail="session storage not available")
    else:
        raise HTTPException(status_code=400, detail="session does not support storage")


@app.get("/sessions/{sid}/storage/commits")
async def get_session_commits(
    sid: str,
    limit: Optional[int] = None,
    commit_type: Optional[str] = None,
    since_timestamp: Optional[float] = None,
) -> Dict[str, Any]:
    """Get session commits with optional filtering."""
    sess = MANAGER._sessions.get(sid)
    if not sess:
        raise HTTPException(status_code=404, detail="session not found")

    if hasattr(sess, "state") and sess.state and sess.state._session_storage:
        commits = sess.state._session_storage.get_commits(
            limit=limit, commit_type=commit_type, since_timestamp=since_timestamp
        )
        return {
            "session_id": sid,
            "commits": [
                {
                    "id": c.id,
                    "timestamp": c.timestamp,
                    "seq": c.seq,
                    "type": c.commit_type,
                    "data": c.data,
                }
                for c in commits
            ],
            "total_returned": len(commits),
        }
    else:
        raise HTTPException(status_code=400, detail="session does not support storage")


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
    """Get available ASR models (cached via indexer)."""
    indexer = get_model_indexer()
    return indexer.get_asr_models()


@app.get("/models/mt")
def get_mt_models() -> List[Dict[str, Any]]:
    """Get available MT models (cached via indexer)."""
    indexer = get_model_indexer()
    return indexer.get_mt_models()


@app.get("/languages/mt/{model_id}")
def get_mt_langs(model_id: str) -> Dict[str, Any]:
    return {"model_id": model_id, "languages": mt_supported_languages(model_id)}

@app.get("/settings/defaults", response_model=ModelDefaultsResp)
def get_model_defaults() -> ModelDefaultsResp:
    """Get current model defaults."""
    manager = get_model_defaults_manager()
    defaults = manager.get_defaults()
    return ModelDefaultsResp(**defaults.to_dict())


@app.post("/settings/defaults", response_model=ModelDefaultsResp)
def update_model_defaults(req: UpdateDefaultsReq) -> ModelDefaultsResp:
    """Update model defaults."""
    manager = get_model_defaults_manager()

    # Extract non-None values from request
    updates = {k: v for k, v in req.model_dump().items() if v is not None}

    # Update defaults
    defaults = manager.update_defaults(**updates)
    return ModelDefaultsResp(**defaults.to_dict())
@app.get("/hardware/snapshot")
async def get_hardware_snapshot_endpoint() -> Dict[str, Any]:
    """Get hardware system snapshot including GPU/CPU/Audio devices.

    The underlying `get_hardware_snapshot()` performs blocking operations
    (psutil, PyTorch CUDA queries, sounddevice probing). Run it in a thread
    pool via `asyncio.to_thread` to avoid blocking the ASGI event loop.
    """
    # Declare globals before use so static checkers know these are module-level
    global _hw_snapshot_cache, _hw_snapshot_cache_ts

    # Fast path: return cached snapshot when fresh
    now = time.time()
    if _hw_snapshot_cache is not None and (now - _hw_snapshot_cache_ts) < _HW_SNAPSHOT_TTL:
        return _hw_snapshot_cache

    # Ensure only one concurrent probe runs when cache is stale. Initialize
    # the lock lazily to avoid binding event-loop resources at import time.
    global _hw_snapshot_lock
    if _hw_snapshot_lock is None:
        _hw_snapshot_lock = asyncio.Lock()

    async with _hw_snapshot_lock:
        # Another coroutine might have populated the cache while we waited
        now = time.time()
        if _hw_snapshot_cache is not None and (now - _hw_snapshot_cache_ts) < _HW_SNAPSHOT_TTL:
            return _hw_snapshot_cache

        try:
            # Run blocking probe in thread pool with a timeout
            snapshot = await asyncio.wait_for(
                asyncio.to_thread(get_hardware_snapshot), timeout=_HW_SNAPSHOT_TIMEOUT
            )
            data = snapshot.to_dict()
            # Update cache
            _hw_snapshot_cache = data
            _hw_snapshot_cache_ts = time.time()
            return data
        except asyncio.TimeoutError:
            logger.error("Hardware snapshot timed out")
            raise HTTPException(status_code=504, detail="Hardware detection timed out")
        except Exception as e:
            logger.error(f"Hardware snapshot failed: {e}")
            raise HTTPException(status_code=500, detail=f"Hardware detection failed: {e}")


def _check_admin_auth(request: Request) -> None:
    """Validate admin token from `Authorization: Bearer <token>` or `X-Admin-Token`.

    Raises `HTTPException(status_code=403)` when token is configured but missing/invalid.
    If `_ADMIN_TOKEN` is not set, admin checks are a no-op (useful for dev).
    """
    if not _ADMIN_TOKEN:
        return

    # Try Authorization header first
    auth = request.headers.get("authorization") or request.headers.get("Authorization")
    token = None
    if auth and auth.lower().startswith("bearer "):
        token = auth.split(None, 1)[1].strip()

    # Fallback to explicit header
    if not token:
        token = request.headers.get("x-admin-token")

    if not token or token != _ADMIN_TOKEN:
        raise HTTPException(status_code=403, detail="admin auth required")


@app.post("/admin/cache/clear", summary="Clear in-memory caches", operation_id="admin_clear_cache")
async def admin_clear_cache(request: Request) -> Dict[str, Any]:
    """Admin-only endpoint to clear in-memory caches (hardware snapshot).

    Protected by `LX_ADMIN_TOKEN` when configured. Safe to call multiple times.
    Returns diagnostic info about previous cache state.
    """
    # Validate admin auth (no-op if `_ADMIN_TOKEN` unset)
    _check_admin_auth(request)

    # Use the same lock as snapshot endpoint if initialized to avoid racing probes.
    global _hw_snapshot_cache, _hw_snapshot_cache_ts, _hw_snapshot_lock
    # Capture prior cache diagnostics
    now = time.time()
    prior_present = _hw_snapshot_cache is not None
    prior_age = None
    if prior_present:
        prior_age = now - _hw_snapshot_cache_ts if _hw_snapshot_cache_ts else None

    if _hw_snapshot_lock is None:
        # Nothing in flight; just clear
        _hw_snapshot_cache = None
        _hw_snapshot_cache_ts = 0.0
        return {
            "ok": True,
            "cleared": True,
            "prior_cache_present": prior_present,
            "prior_cache_age_sec": prior_age,
            "admin_auth_required": bool(_ADMIN_TOKEN),
        }

    # Acquire lock to synchronize with any ongoing probes
    async with _hw_snapshot_lock:
        _hw_snapshot_cache = None
        _hw_snapshot_cache_ts = 0.0
        return {
            "ok": True,
            "cleared": True,
            "prior_cache_present": prior_present,
            "prior_cache_age_sec": prior_age,
            "admin_auth_required": bool(_ADMIN_TOKEN),
        }


@app.get("/healthz")
async def healthz() -> Dict[str, Any]:
    """Health endpoint for Electron readiness check."""
    return {"status": "ok", "timestamp": time.time()}


# Minimal API health endpoint used by external checks and tests
@app.get("/api/health")
async def api_health() -> Dict[str, Any]:
    return {"status": "ok"}


@app.head("/api/health")
async def api_health_head() -> Response:
    return Response(status_code=200)


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

    # Get session storage snapshot if available
    session_storage_snapshot = None
    if hasattr(sess, "state") and sess.state:
        try:
            session_storage_snapshot = sess.state.get_session_snapshot()
        except Exception:
            pass  # Session storage is optional

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

    if session_storage_snapshot:
        base_snapshot["session_storage"] = session_storage_snapshot

    return base_snapshot


@app.websocket(WS_PATH + "/{sid}")
async def ws_events(ws: WebSocket, sid: str) -> None:
    origin = ws.headers.get("origin", "")
    if DEV_MODE:
        if origin and origin not in ALLOWED_ORIGINS:
            raise WebSocketDisconnect(code=4403)
    else:
        # In prod, require same-origin or allow missing Origin (e.g., native/Electron)
        host = ws.headers.get("host", "")
        if origin:
            # Accept only if origin scheme+host matches ws host
            try:
                from urllib.parse import urlparse

                o = urlparse(origin)
                if host and o.netloc != host:
                    raise WebSocketDisconnect(code=4403)
            except Exception:
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


# Optional legacy alias for /events to ease dev migration. Only mounted when explicitly enabled.
if ALLOW_EVENTS_ALIAS and WS_PATH != "/events":
    _events_alias_warned = False

    @app.websocket("/events/{sid}")
    async def ws_events_alias(ws: WebSocket, sid: str) -> None:
        """Deprecated alias for backwards compatibility in dev only.

        Logs a one-time deprecation warning and otherwise behaves like the canonical handler.
        """
        global _events_alias_warned
        if not _events_alias_warned:
            logger.warning(
                "Deprecated: '/events' alias is enabled via LX_WS_ALLOW_EVENTS_ALIAS=1; set LX_WS_PATH to '/ws' and update clients to use VITE_WS_PATH"
            )
            _events_alias_warned = True

        origin = ws.headers.get("origin", "")
        if DEV_MODE:
            if origin and origin not in ALLOWED_ORIGINS:
                raise WebSocketDisconnect(code=4403)
        else:
            host = ws.headers.get("host", "")
            if origin:
                try:
                    from urllib.parse import urlparse

                    o = urlparse(origin)
                    if host and o.netloc != host:
                        raise WebSocketDisconnect(code=4403)
                except Exception:
                    raise WebSocketDisconnect(code=4403)

        await ws.accept()
        try:
            await MANAGER.register_ws(sid, ws)
            while True:
                try:
                    message = await ws.receive_text()
                    await MANAGER.handle_ws_message(sid, ws, message)
                except WebSocketDisconnect:
                    break
                except Exception as e:
                    logger.exception(f"WebSocket message handling error: {e}")
                    await asyncio.sleep(1)
        except WebSocketDisconnect:
            pass
        finally:
            await MANAGER.unregister_ws(sid, ws)


# Serve built assets under /assets if UI is present
if UI_DIST_PATH.exists() and UI_DIST_PATH.is_dir():
    assets_dir = UI_DIST_PATH / "assets"
    if assets_dir.exists() and assets_dir.is_dir():
        app.mount("/assets", StaticFiles(directory=str(assets_dir), html=False), name="assets")


# Root index route when UI is present
@app.get("/")
@app.head("/")
async def root_index() -> FileResponse:
    if UI_DIST_PATH.exists() and UI_DIST_PATH.is_dir():
        index_path = UI_DIST_PATH / "index.html"
        if index_path.exists():
            return FileResponse(str(index_path), media_type="text/html")
    raise HTTPException(status_code=404, detail="Not found")


# SPA fallback route - must be last to catch all unmatched routes
@app.get("/{full_path:path}")
@app.head("/{full_path:path}")
async def spa_fallback(full_path: str) -> FileResponse:  # noqa: ARG001
    """Serve SPA index.html for all unknown routes (client-side routing)."""
    # Guardrails: do not intercept API, WS, or asset paths
    if full_path.startswith(("api/", "ws/", "assets/")):
        raise HTTPException(status_code=404, detail="Not found")

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

from __future__ import annotations

import asyncio
import json
import logging
import os
import os.path
import re
import shutil
import time
import uuid
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, TYPE_CHECKING, TextIO, cast

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, model_validator

from .model_discovery import list_asr_models, list_mt_models, mt_supported_languages
from loquilex.hardware.detection import get_hardware_snapshot
from loquilex.config.model_defaults import get_model_defaults_manager
from loquilex.security import PathGuard, PathSecurityError
from .supervisor import SessionConfig, SessionManager, StreamingSession

if TYPE_CHECKING:  # pragma: no cover - type-only import
    from loquilex.security import CanonicalPath

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


# Global safety net: log exceptions, return generic 500 without internals
@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    logger.error(
        "Unhandled exception on %s: %s", getattr(request.url, "path", "?"), exc, exc_info=True
    )
    return JSONResponse(status_code=500, content={"detail": "Internal Server Error"})


# Admin token and simple in-process caches (overridable in tests)
_ADMIN_TOKEN: Optional[str] = os.getenv("LX_ADMIN_TOKEN")
_hw_snapshot_cache: Optional[Dict[str, Any]] = None
_hw_snapshot_cache_ts: Optional[float] = None


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


def _session_cp(sid: str) -> "CanonicalPath":
    """canonicalize_leaf → safe_join("sessions", sid)"""
    leaf = PATH_GUARD.canonicalize_leaf(sid)
    return PATH_GUARD.safe_join("sessions", leaf)


def _safe_session_dir(sid: str) -> Path:
    if not re.fullmatch(r"[A-Za-z0-9_-]{6,64}", sid):
        raise HTTPException(status_code=400, detail="bad sid")
    try:
        cp = _session_cp(sid)
        p = cp.as_path()
        # Ensure the directory itself exists (not just its parent)
        PATH_GUARD.ensure_dir(p)
        return p
    except PathSecurityError as exc:
        raise HTTPException(status_code=400, detail="invalid path") from exc


app.mount("/out", StaticFiles(directory=str(OUT_ROOT), html=False), name="out")

# Global manager instance
MANAGER = SessionManager()


# Allowed storage roots for path-based operations (named roots)
_env_allowed_roots = os.getenv("LX_ALLOWED_STORAGE_ROOTS")
if not _env_allowed_roots:  # Treat missing or empty as default '/tmp'
    _EXTRA_ALLOWED_ROOTS = ["/tmp"]
else:
    _EXTRA_ALLOWED_ROOTS = [p for p in _env_allowed_roots.split(":") if p]

_root_map: Dict[str, Path] = {
    # Canonical storage root for user-facing directories (CP-safe joins)
    "storage": OUT_ROOT,
    "sessions": OUT_ROOT,
    "exports": OUT_ROOT / "exports",
    "profiles": Path("loquilex/ui/profiles").resolve(),
}
for p in _EXTRA_ALLOWED_ROOTS:
    try:
        _root_map.setdefault("extra", Path(p).resolve())
    except Exception:
        pass

PATH_GUARD = PathGuard(_root_map, follow_symlinks=False)


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


class StorageInfoResp(BaseModel):
    """Storage information response model."""

    path: str
    total_bytes: int
    free_bytes: int
    used_bytes: int
    percent_used: float
    writable: bool


class BaseDirectoryReq(BaseModel):
    """Base directory selection request."""

    path: str


class BaseDirectoryResp(BaseModel):
    """Base directory selection response."""

    path: str
    valid: bool
    message: str


def _resolve_storage_dir(candidate: Optional[str]) -> Path:
    """Resolve a candidate path for storage/info and validation.

    Compatibility behavior retained for API stability:
    - None -> default OUT_ROOT
    - Absolute -> allowed only if inside any configured root
    - Relative single-segment leaf -> handled via CanonicalPath join on 'storage'
    - Other relative forms -> rejected
    """
    if candidate is None:
        return OUT_ROOT
    p = Path(candidate)
    if p.is_absolute():
        # Absolute: allow only when inside one of our roots, without resolving
        for base in _root_map.values():
            if PathGuard._is_within_root(base, p):
                return p
        raise PathSecurityError("path not permitted")
    # For relative inputs, only accept a single-segment leaf and map under 'storage'
    try:
        leaf = PATH_GUARD.canonicalize_leaf(candidate)
        cp = PATH_GUARD.safe_join("storage", leaf)
        # Return the underlying Path for existing call sites that expect Path
        return cp.as_path()
    except Exception as exc:
        raise PathSecurityError("invalid relative path") from exc


# Simple profiles CRUD on disk under loquilex/ui/profiles
PROFILES_DIR = Path("loquilex/ui/profiles")
PROFILES_ROOT = PROFILES_DIR.resolve()


def _profile_path(name: str, *, must_exist: bool = False, for_write: bool = False) -> Path:
    try:
        # Enforce profile filename policy via resolve on the 'profiles' root
        candidate = PATH_GUARD.resolve("profiles", f"{name}.json")
        if for_write:
            PATH_GUARD.ensure_dir(candidate.parent)
        if must_exist and not candidate.exists():
            raise HTTPException(status_code=404, detail="not found")
        return candidate
    except PathSecurityError as exc:
        raise HTTPException(status_code=400, detail="invalid profile name") from exc


def _profile_cp(name: str) -> "CanonicalPath":
    """
    Build a CanonicalPath for profile JSON under the 'profiles' root.
    Enforces single-segment leaf name and '.json' extension.
    """
    leaf = PATH_GUARD.canonicalize_leaf(name)
    return PATH_GUARD.safe_join("profiles", f"{leaf}.json")


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


@app.get("/storage/info")
async def get_storage_info(path: Optional[str] = None) -> StorageInfoResp:
    """Get storage information for a given path or current output directory.

    Uses CanonicalPath flow for relative single-segment inputs; keeps absolute/None behavior.
    """
    # Branch: relative single-segment -> CanonicalPath guarded flow
    if path is not None and not Path(path).is_absolute():
        try:
            leaf = PATH_GUARD.canonicalize_leaf(path)
            cp = PATH_GUARD.safe_join("storage", leaf)
            # Ensure the directory itself
            PATH_GUARD.ensure_dir(cp.as_path())
            stat = PATH_GUARD.disk_usage_cp(cp)
            total_bytes = stat.total
            free_bytes = stat.free
            used_bytes = total_bytes - free_bytes
            percent_used = (used_bytes / total_bytes * 100) if total_bytes > 0 else 0
            writable = os.access(os.fspath(cp), os.W_OK)
            return StorageInfoResp(
                path=str(cp),
                total_bytes=total_bytes,
                free_bytes=free_bytes,
                used_bytes=used_bytes,
                percent_used=percent_used,
                writable=writable,
            )
        except PathSecurityError as exc:
            raise HTTPException(status_code=400, detail="Cannot access path") from exc
        except Exception as exc:
            raise HTTPException(status_code=400, detail="Cannot access path") from exc

    # Fallback: None or absolute path -> guarded absolute handling
    try:
        target_path = _resolve_storage_dir(path)
        # Convert to CanonicalPath when absolute to reuse guarded sinks
        if isinstance(target_path, Path) and target_path.is_absolute():
            cp = PATH_GUARD.wrap_absolute(target_path)
            PATH_GUARD.ensure_dir(cp.as_path())
            stat = PATH_GUARD.disk_usage_cp(cp)
            total_bytes = stat.total
            free_bytes = stat.free
            used_bytes = total_bytes - free_bytes
            percent_used = (used_bytes / total_bytes * 100) if total_bytes > 0 else 0
            writable = os.access(os.fspath(cp), os.W_OK)
            return StorageInfoResp(
                path=str(cp),
                total_bytes=total_bytes,
                free_bytes=free_bytes,
                used_bytes=used_bytes,
                percent_used=percent_used,
                writable=writable,
            )
        else:
            # Non-absolute should already be handled above; fallback defensively
            PATH_GUARD.ensure_dir(target_path)
            stat = shutil.disk_usage(target_path)
            total_bytes = stat.total
            free_bytes = stat.free
            used_bytes = total_bytes - free_bytes
            percent_used = (used_bytes / total_bytes * 100) if total_bytes > 0 else 0
            writable = os.access(target_path, os.W_OK)
            return StorageInfoResp(
                path=str(target_path),
                total_bytes=total_bytes,
                free_bytes=free_bytes,
                used_bytes=used_bytes,
                percent_used=percent_used,
                writable=writable,
            )
    except PathSecurityError as exc:
        raise HTTPException(status_code=400, detail="Cannot access path") from exc
    except Exception as exc:
        raise HTTPException(status_code=400, detail="Cannot access path") from exc


@app.get("/hardware/snapshot")
def hardware_snapshot() -> Dict[str, Any]:
    """Return a cached hardware snapshot or compute a new one."""
    global _hw_snapshot_cache, _hw_snapshot_cache_ts
    now = time.time()
    try:
        if (
            _hw_snapshot_cache is not None
            and _hw_snapshot_cache_ts
            and (now - _hw_snapshot_cache_ts) < 10
        ):
            return _hw_snapshot_cache
        snap = get_hardware_snapshot()
        data = snap.to_dict()
        _hw_snapshot_cache = data
        _hw_snapshot_cache_ts = now
        return data
    except Exception as e:
        logger.exception("hardware snapshot failed: %s", e)
        return {
            "cpu": {
                "name": "error",
                "cores_physical": 0,
                "cores_logical": 0,
                "frequency_mhz": 0.0,
                "usage_percent": 0.0,
                "meets_threshold": False,
                "warnings": ["snapshot failed"],
            },
            "gpus": [
                {
                    "name": "unknown",
                    "memory_total_mb": 0,
                    "memory_free_mb": 0,
                    "memory_used_mb": 0,
                    "temperature_c": None,
                    "utilization_percent": None,
                    "cuda_available": False,
                    "meets_threshold": False,
                    "warnings": ["snapshot failed"],
                }
            ],
            "audio_devices": [],
            "memory_total_gb": 0.0,
            "memory_available_gb": 0.0,
            "platform_info": {},
            "overall_status": "unusable",
            "overall_score": 0,
            "warnings": ["snapshot failed"],
        }


@app.post("/admin/cache/clear")
async def admin_cache_clear(request: Request) -> Dict[str, Any]:
    """Clear in-process caches (hardware snapshot for now).

    Requires Authorization: Bearer <token> matching LX_ADMIN_TOKEN or _ADMIN_TOKEN.
    """
    global _hw_snapshot_cache, _hw_snapshot_cache_ts
    token = _ADMIN_TOKEN
    auth = request.headers.get("authorization", "")
    provided = None
    if auth.startswith("Bearer "):
        provided = auth[len("Bearer ") :].strip()
    if not token or provided != token:
        raise HTTPException(status_code=403, detail="forbidden")

    prior_present = _hw_snapshot_cache is not None
    _hw_snapshot_cache = None
    _hw_snapshot_cache_ts = None
    return {"ok": True, "cleared": True, "prior_cache_present": prior_present}


@app.post("/storage/base-directory")
async def set_base_directory(req: BaseDirectoryReq) -> BaseDirectoryResp:
    """Set and validate a new base directory for storage."""
    # Require absolute path input (UI contract)
    try:
        if not req.path or not Path(req.path).is_absolute():
            return BaseDirectoryResp(path=req.path, valid=False, message="Path must be absolute")
        target_path = _resolve_storage_dir(req.path)
        # target_path may be absolute (allowed) or a CanonicalPath.as_path return.
        # Ensure directory using guard; for absolute paths, guard verifies containment.
        PATH_GUARD.ensure_dir(target_path)
    except PathSecurityError as exc:
        detail = str(exc)
        message = f"Invalid path: {detail}"
        return BaseDirectoryResp(path=req.path, valid=False, message=message)
    except Exception as exc:
        return BaseDirectoryResp(path=req.path, valid=False, message=f"Invalid path: {exc}")

    try:
        # Check if writable
        if not os.access(target_path, os.W_OK):
            return BaseDirectoryResp(
                path=str(target_path), valid=False, message="Directory is not writable"
            )

        # Check disk space (warn if less than 1GB free) using guarded path
        cp = PATH_GUARD.wrap_absolute(target_path) if Path(target_path).is_absolute() else None
        if cp is not None:
            stat = PATH_GUARD.disk_usage_cp(cp)
        else:
            stat = shutil.disk_usage(target_path)
        if stat.free < 1024 * 1024 * 1024:  # 1GB
            return BaseDirectoryResp(
                path=str(target_path),
                valid=True,
                message=f"Warning: Only {stat.free // (1024*1024)} MB free space available",
            )

        return BaseDirectoryResp(
            path=str(target_path), valid=True, message="Directory is valid and writable"
        )
    except Exception as exc:
        return BaseDirectoryResp(path=str(target_path), valid=False, message=f"Invalid path: {exc}")


@app.get("/profiles")
def get_profiles() -> List[str]:
    if not PROFILES_ROOT.is_dir():
        return []
    return sorted([p.stem for p in PROFILES_ROOT.glob("*.json") if p.is_file()])


@app.get("/profiles/{name}")
def get_profile(name: str):
    cp = _profile_cp(name)                   # CanonicalPath
    with PATH_GUARD.open_read_cp(cp) as fh:  # guarded read
        data = json.load(fh)
    return JSONResponse(data)


@app.post("/profiles/{name}")
def save_profile(name: str, data: dict):
    cp = _profile_cp(name)
    PATH_GUARD.ensure_dir_cp(cp)
    # Guarded write; symlinks and traversal are blocked by PathGuard policies
    with cast(TextIO, PATH_GUARD.open_write_cp(cp, overwrite=True, binary=False)) as fh:
        json.dump(data, fh, ensure_ascii=False, separators=(",", ":"))
    return JSONResponse({"ok": True, "path": str(cp)})


@app.delete("/profiles/{name}")
def delete_profile(name: str) -> Dict[str, Any]:
    # Derive CanonicalPath to enforce leaf policy and root containment
    cp = _profile_cp(name)
    p = cp.as_path()
    if p.exists():
        try:
            p.unlink()
        except Exception:
            raise HTTPException(status_code=500, detail="delete failed")
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


# Minimal API health endpoint used by external checks and tests
@app.get("/api/health")
async def api_health() -> Dict[str, Any]:
    return {"status": "ok"}


@app.head("/api/health")
async def api_health_head() -> Response:
    return Response(status_code=200)


# Model defaults management
@app.get("/settings/defaults")
def get_model_defaults() -> Dict[str, Any]:
    mgr = get_model_defaults_manager()
    return mgr.get_defaults().to_dict()


class _ModelDefaultsUpdate(BaseModel):
    asr_model_id: Optional[str] = None
    asr_device: Optional[str] = None
    asr_compute_type: Optional[str] = None
    mt_model_id: Optional[str] = None
    mt_device: Optional[str] = None
    mt_compute_type: Optional[str] = None
    tts_model_id: Optional[str] = None
    tts_device: Optional[str] = None


@app.post("/settings/defaults")
def post_model_defaults(update: _ModelDefaultsUpdate) -> Dict[str, Any]:
    mgr = get_model_defaults_manager()
    updated = mgr.update_defaults(**{k: v for k, v in update.model_dump().items()})
    return updated.to_dict()


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

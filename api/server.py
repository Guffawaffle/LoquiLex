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
import os
import uuid
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from .model_discovery import list_asr_models, list_mt_models, mt_supported_languages
from .supervisor import SessionConfig, SessionManager


app = FastAPI(title="Greenfield API", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve outputs directory for easy linking from UI
out_dir = os.getenv("GF_OUT_DIR", "greenfield/out")
if os.path.isdir(out_dir):
    app.mount("/out", StaticFiles(directory=out_dir), name="out")


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


class DownloadReq(BaseModel):
    repo_id: str
    type: str = Field(description="asr|mt|other")


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
        raise HTTPException(status_code=400, detail=str(e))


@app.delete("/sessions/{sid}")
async def stop_session(sid: str) -> Dict[str, Any]:
    ok = MANAGER.stop_session(sid)
    if not ok:
        raise HTTPException(status_code=404, detail="session not found")
    return {"stopped": True}


@app.websocket("/events/{sid}")
async def ws_events(ws: WebSocket, sid: str) -> None:
    await ws.accept()
    try:
        await MANAGER.register_ws(sid, ws)
        # Keep connection open; we don't expect client->server messages right now
        while True:
            try:
                await ws.receive_text()
            except Exception:
                # Ignore client messages; heartbeat could be implemented later
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

from __future__ import annotations

import asyncio
import json
import os
import queue
import signal
import subprocess
import sys
import threading
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from fastapi import WebSocket


@dataclass
class SessionConfig:
    name: str
    asr_model_id: str
    mt_enabled: bool
    mt_model_id: Optional[str]
    dest_lang: str
    device: str
    vad: bool
    beams: int
    pause_flush_sec: float
    segment_max_sec: float
    partial_word_cap: int
    save_audio: str


class Session:
    def __init__(self, sid: str, cfg: SessionConfig, run_dir: Path) -> None:
        self.sid = sid
        self.cfg = cfg
        self.run_dir = run_dir
        self.proc: Optional[subprocess.Popen] = None
        self._stop_evt = threading.Event()
        self.queue = queue.Queue(maxsize=1000)  # type: ignore[var-annotated]
        self._reader_thread: Optional[threading.Thread] = None

    def start(self) -> None:
        # Configure env overrides for the existing pipeline
        env = os.environ.copy()
        env["GF_ASR_MODEL"] = self.cfg.asr_model_id
        env["GF_DEVICE"] = self.cfg.device
        env["GF_ASR_VAD"] = "1" if self.cfg.vad else "0"
        env["GF_ASR_BEAM"] = str(self.cfg.beams)
        env["GF_PAUSE_FLUSH_SEC"] = str(self.cfg.pause_flush_sec)
        env["GF_SEGMENT_MAX_SEC"] = str(self.cfg.segment_max_sec)
        env["GF_PARTIAL_WORD_CAP"] = str(self.cfg.partial_word_cap)
        env["GF_OUT_DIR"] = str(self.run_dir)
        env["GF_SAVE_AUDIO"] = self.cfg.save_audio
        # MT is controlled inside Translator via defaults; for now we don't pass mt_model_id explicitly

        # Run the live CLI pipeline which writes outputs to files
        script = [sys.executable, "-m", "greenfield.cli.live_en_to_zh", "--seconds", "-1"]
        self.proc = subprocess.Popen(
            script,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            env=env,
        )
        # Start a line reader thread to avoid blocking in manager
        def _reader():
            if not self.proc or not self.proc.stdout:
                return
            f = self.proc.stdout
            while self.proc.poll() is None and not self._stop_evt.is_set():
                try:
                    line = f.readline()
                except Exception:
                    break
                if not line:
                    time.sleep(0.05)
                    continue
                try:
                    self.queue.put_nowait(line.decode("utf-8", errors="ignore"))
                except queue.Full:
                    try:
                        _ = self.queue.get_nowait()
                    except Exception:
                        pass
        self._reader_thread = threading.Thread(target=_reader, daemon=True)
        self._reader_thread.start()

    def stop(self) -> None:
        if self.proc and self.proc.poll() is None:
            try:
                self.proc.terminate()
                try:
                    self.proc.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    self.proc.kill()
            except Exception:
                pass
        self._stop_evt.set()
        if self._reader_thread:
            self._reader_thread.join(timeout=1.0)


class SessionManager:
    def __init__(self) -> None:
        self._sessions: Dict[str, Session] = {}
        self._ws: Dict[str, List[WebSocket]] = {}
        self._bg_threads: List[threading.Thread] = []
        self._lock = threading.Lock()
        self._downloads: Dict[str, Tuple[str, str]] = {}
        self._stop = False
        self._max_cuda_sessions = int(os.getenv("GF_MAX_CUDA_SESSIONS", "1"))

        # Start a log tailer that forwards textual logs as WS 'status' events
        t = threading.Thread(target=self._log_pump, daemon=True)
        t.start()
        self._bg_threads.append(t)

        # Start a VU meter poller reading RMS/peak from saved audio if available (best effort)
        t2 = threading.Thread(target=self._vu_pump, daemon=True)
        t2.start()
        self._bg_threads.append(t2)

    def start_session(self, cfg: SessionConfig) -> str:
        # Simple CUDA guard
        if cfg.device == "cuda":
            with self._lock:
                running_cuda = sum(1 for s in self._sessions.values() if s.cfg.device == "cuda")
            if running_cuda >= self._max_cuda_sessions:
                raise RuntimeError("GPU busy: maximum concurrent CUDA sessions reached")
        sid = str(uuid.uuid4())
        run_dir = Path("greenfield/out") / sid
        run_dir.mkdir(parents=True, exist_ok=True)
        sess = Session(sid, cfg, run_dir)
        sess.start()
        with self._lock:
            self._sessions[sid] = sess
        # Announce status
        asyncio.create_task(self._broadcast(sid, {"type": "status", "stage": "initializing"}))
        return sid

    def stop_session(self, sid: str) -> bool:
        with self._lock:
            sess = self._sessions.pop(sid, None)
        if not sess:
            return False
        sess.stop()
        asyncio.create_task(self._broadcast(sid, {"type": "status", "stage": "stopped"}))
        return True

    async def register_ws(self, sid: str, ws: WebSocket) -> None:
        with self._lock:
            lst = self._ws.setdefault(sid, [])
            lst.append(ws)
        # Send initial hello
        await ws.send_json({"type": "hello", "sid": sid})

    async def unregister_ws(self, sid: str, ws: WebSocket) -> None:
        with self._lock:
            lst = self._ws.get(sid, [])
            if ws in lst:
                lst.remove(ws)

    async def _broadcast(self, sid: str, payload: Dict[str, Any]) -> None:
        conns: List[WebSocket]
        with self._lock:
            conns = list(self._ws.get(sid, []))
        for ws in conns:
            try:
                await ws.send_json(payload)
            except Exception:
                pass

    def _log_pump(self) -> None:
        # Tail each session's process stdout and emit status and partial/final lines heuristically
        while not self._stop:
            time.sleep(0.2)
            with self._lock:
                items = list(self._sessions.items())
            for sid, sess in items:
                # Drain a few lines from the session queue
                drained = 0
                while drained < 20:
                    try:
                        line = sess.queue.get_nowait()
                    except queue.Empty:
                        break
                    drained += 1
                    text = line.strip()
                    if not text:
                        continue
                    payload: Optional[Dict[str, Any]] = None
                    if text.startswith("EN ≫ "):
                        payload = {"type": "partial_en", "text": text[len("EN ≫ "):].strip()}
                    elif text.startswith("ZH* ≫ "):
                        payload = {"type": "partial_zh", "text": text[len("ZH* ≫ "):].strip()}
                    elif text.startswith("EN(final):"):
                        payload = {"type": "final_en", "text": text.split(":", 1)[1].strip()}
                    elif text.startswith("ZH:"):
                        payload = {"type": "final_zh", "text": text.split(":", 1)[1].strip()}
                    elif "Ready — start speaking now" in text:
                        payload = {"type": "status", "stage": "operational", "log": text}
                    else:
                        payload = {"type": "status", "log": text}
                    # Fire and forget
                    try:
                        asyncio.run(self._broadcast(sid, payload))
                    except RuntimeError:
                        # If already in an event loop, schedule a task via loop
                        loop = asyncio.get_event_loop()
                        loop.create_task(self._broadcast(sid, payload))

    def _vu_pump(self) -> None:
        # Best-effort VU meter: if session configured to save audio as WAV/FLAC, we can't tail easily.
        # Instead, estimate from recent partial/final print cadence — as a placeholder, emit random-like levels.
        import random

        while not self._stop:
            time.sleep(0.5)
            with self._lock:
                sids = list(self._sessions.keys())
            for sid in sids:
                vu = {"type": "vu", "rms": random.uniform(0.05, 0.35), "peak": random.uniform(0.2, 0.8)}
                try:
                    asyncio.run(self._broadcast(sid, vu))
                except RuntimeError:
                    loop = asyncio.get_event_loop()
                    loop.create_task(self._broadcast(sid, vu))

    # Download management
    def start_download_job(self, job_id: str, repo_id: str, typ: str) -> None:
        t = threading.Thread(target=self._download_worker, args=(job_id, repo_id, typ), daemon=True)
        t.start()
        self._bg_threads.append(t)

    def _download_worker(self, job_id: str, repo_id: str, typ: str) -> None:
        # Lazy import to keep server fast
        try:
            from huggingface_hub import snapshot_download  # type: ignore
        except Exception:
            # Emit error
            asyncio.run(self._broadcast("_download", {"type": "error", "job_id": job_id, "error": "huggingface_hub not installed"}))
            return

        def cb(prog: int, total: int) -> None:
            pct = int(100 * (prog / max(1, total)))
            try:
                asyncio.run(self._broadcast("_download", {"type": "download_progress", "job_id": job_id, "repo_id": repo_id, "progress": pct}))
            except RuntimeError:
                loop = asyncio.get_event_loop()
                loop.create_task(self._broadcast("_download", {"type": "download_progress", "job_id": job_id, "repo_id": repo_id, "progress": pct}))

        try:
            # Some versions of huggingface_hub accept a progress callback via hooks.
            snapshot_download(repo_id, local_dir=None)
            cb(1, 1)
        except Exception as e:
            try:
                asyncio.run(self._broadcast("_download", {"type": "error", "job_id": job_id, "error": str(e)}))
            except RuntimeError:
                loop = asyncio.get_event_loop()
                loop.create_task(self._broadcast("_download", {"type": "error", "job_id": job_id, "error": str(e)}))

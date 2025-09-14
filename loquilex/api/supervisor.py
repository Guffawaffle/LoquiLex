from __future__ import annotations

import asyncio
import logging
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
from typing import Any, Dict, List, Optional, Tuple, Union

from fastapi import WebSocket

from .events import EventStamper

logger = logging.getLogger(__name__)


class StreamingSession:
    """In-process streaming session using the new StreamingASR pipeline."""

    def __init__(self, sid: str, cfg: SessionConfig, run_dir: Path) -> None:
        from typing import Callable, Awaitable

        self.sid = sid
        self.cfg = cfg
        self.run_dir = run_dir
        self.proc = None  # No subprocess for streaming sessions
        self._stop_evt = threading.Event()
        self.stamper = EventStamper.new()
        self.queue: "queue.Queue[str]" = queue.Queue(maxsize=1000)  # Add queue for compatibility

        # Event loop reference for thread-safe asyncio calls
        self._event_loop: Optional[asyncio.AbstractEventLoop] = None
        self._broadcast_fn: Optional[Callable[[str, Dict[str, Any]], Awaitable[None]]] = None

        # Streaming ASR components
        self.asr: Optional[Any] = None  # StreamingASR
        self.aggregator: Optional[Any] = None  # PartialFinalAggregator
        self._audio_thread: Optional[threading.Thread] = None

        # MT integration
        self.mt_integration: Optional[Any] = None  # MTIntegration

    def set_broadcast_fn(self, broadcast_fn) -> None:
        """Set the broadcast function for emitting events."""
        self._broadcast_fn = broadcast_fn

        # Also set broadcast function for MT integration
        if self.mt_integration:
            self.mt_integration.set_broadcast_fn(broadcast_fn)

    def _schedule_broadcast(self, event: Dict[str, Any]) -> None:
        """Safely schedule a broadcast coroutine from any thread."""
        if self._event_loop is None or self._broadcast_fn is None:
            print("[StreamingSession] dropping event (no loop or broadcast_fn)")
            return

        # Ensure _broadcast_fn returns a coroutine
        def coro():
            return self._broadcast_fn(self.sid, event)

        self._event_loop.call_soon_threadsafe(lambda: asyncio.create_task(coro()))

    def start(self) -> None:
        """Start the streaming ASR session."""
        # Store event loop reference for thread-safe asyncio calls
        try:
            self._event_loop = asyncio.get_running_loop()
        except RuntimeError:
            self._event_loop = None  # Will be set later if needed
        # Configure ASR environment
        os.environ["LX_ASR_MODEL"] = self.cfg.asr_model_id
        os.environ["LX_DEVICE"] = self.cfg.device
        os.environ["LX_ASR_VAD"] = "1" if self.cfg.vad else "0"
        os.environ["LX_ASR_BEAM"] = str(self.cfg.beams)
        os.environ["LX_PAUSE_FLUSH_SEC"] = str(self.cfg.pause_flush_sec)
        os.environ["LX_SEGMENT_MAX_SEC"] = str(self.cfg.segment_max_sec)

        try:
            # Import here to avoid circular imports and to get proper fake during tests
            from loquilex.asr.stream import StreamingASR
            from loquilex.asr.aggregator import PartialFinalAggregator

            # Initialize streaming components
            self.asr = StreamingASR(stream_id=self.sid)
            self.aggregator = PartialFinalAggregator(self.sid)

            # Initialize MT integration if enabled
            if self.cfg.mt_enabled:
                try:
                    from loquilex.mt.integration import MTIntegration

                    self.mt_integration = MTIntegration(
                        session_id=self.sid,
                        mt_enabled=self.cfg.mt_enabled,
                        dest_lang=self.cfg.dest_lang,
                    )
                    if self._broadcast_fn:
                        self.mt_integration.set_broadcast_fn(self._broadcast_fn)
                except Exception as e:
                    print(f"[StreamingSession] MT initialization failed: {e}")
                    self.mt_integration = None

            # Warmup ASR
            self.asr.warmup()

            # Start audio processing thread
            def audio_worker():
                stop_capture = None
                try:
                    # Import audio capture
                    from loquilex.audio.capture import capture_stream

                    def on_audio_frame(frame):
                        if self._stop_evt.is_set():
                            return
                        try:
                            self.asr.process_audio_chunk(
                                frame.data, self._on_partial, self._on_final
                            )
                        except Exception as e:
                            print(f"[StreamingSession] Audio processing error: {e}")

                    # Start audio capture
                    stop_capture = capture_stream(on_audio_frame)

                    # Broadcast ready status using safe scheduling
                    self._schedule_broadcast(
                        {
                            "type": "status",
                            "stage": "operational",
                            "log": "Ready — start speaking now (streaming mode)",
                        }
                    )

                    # Keep thread alive until stopped
                    while not self._stop_evt.is_set():
                        time.sleep(0.1)

                except Exception as e:
                    print(f"[StreamingSession] Audio worker error: {e}")
                    self._schedule_broadcast(
                        {
                            "type": "status",
                            "stage": "error",
                            "log": f"Audio error: {e}",
                        }
                    )
                finally:
                    # Guarantee audio capture cleanup
                    if stop_capture is not None:
                        try:
                            stop_capture()
                        except Exception:
                            logger.exception("stop_capture failed")

            self._audio_thread = threading.Thread(target=audio_worker, daemon=True)
            self._audio_thread.start()

        except Exception as e:
            print(f"[StreamingSession] Startup error: {e}")
            raise

    def _on_partial(self, partial_event) -> None:
        """Handle partial ASR events."""
        # Early-out if core pieces aren't ready
        if self.aggregator is None or self._broadcast_fn is None or self._event_loop is None:
            return

        def emit_event(event_dict: Dict[str, Any]) -> None:
            self._schedule_broadcast(event_dict)

        try:
            self.aggregator.add_partial(partial_event, emit_event)
        except Exception as e:
            print(f"[StreamingSession] Partial event error: {e}")

    def _on_final(self, final_event) -> None:
        """Handle final ASR events."""
        # Early-out if core pieces aren't ready
        if self.aggregator is None or self._broadcast_fn is None or self._event_loop is None:
            return

        def emit_event(event_dict: Dict[str, Any]) -> None:
            self._schedule_broadcast(event_dict)

            # Trigger MT translation for final ASR events
            if (
                event_dict.get("type") == "asr.final"
                and self.mt_integration
                and event_dict.get("text")
            ):

                async def translate_and_emit():
                    await self.mt_integration.translate_and_emit(
                        text=event_dict["text"],
                        segment_id=event_dict.get("segment_id", "unknown"),
                        is_final=True,
                        src_lang="en",
                    )

                # Schedule translation in event loop
                if self._event_loop:
                    self._event_loop.call_soon_threadsafe(
                        lambda: asyncio.create_task(translate_and_emit())
                    )

        try:
            self.aggregator.add_final(final_event, emit_event)
        except Exception as e:
            print(f"[StreamingSession] Final event error: {e}")

    def stop(self) -> None:
        """Stop the streaming session."""
        self._stop_evt.set()
        if self._audio_thread:
            try:
                self._audio_thread.join(timeout=2.0)
            except Exception:
                pass

    def pause(self) -> None:
        """Pause audio processing (placeholder)."""
        # Could implement by pausing audio capture
        pass

    def resume(self) -> None:
        """Resume audio processing (placeholder)."""
        # Could implement by resuming audio capture
        pass

    def finalize_now(self) -> None:
        """Force finalize current segment."""
        if self.asr:
            try:
                self.asr.force_finalize(self._on_final)
            except Exception as e:
                print(f"[StreamingSession] Force finalize error: {e}")

    def get_metrics(self) -> Optional[Dict[str, Any]]:
        """Get performance metrics."""
        if self.aggregator:
            try:
                return self.aggregator.get_metrics_summary()
            except Exception as e:
                print(f"[StreamingSession] Metrics error: {e}")
        return None

    def get_asr_snapshot(self) -> Optional[Dict[str, Any]]:
        """Get ASR snapshot for reconnects."""
        if self.aggregator:
            try:
                return self.aggregator.get_snapshot()
            except Exception as e:
                print(f"[StreamingSession] Snapshot error: {e}")
        return None

    def get_mt_status(self) -> Dict[str, Any]:
        """Get MT integration status."""
        if self.mt_integration:
            try:
                return self.mt_integration.get_status()
            except Exception as e:
                print(f"[StreamingSession] MT status error: {e}")
                return {"enabled": False, "error": str(e)}

        return {"enabled": self.cfg.mt_enabled, "available": False, "dest_lang": self.cfg.dest_lang}


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
    # New streaming mode flag
    streaming_mode: bool = False


class Session:
    def __init__(self, sid: str, cfg: SessionConfig, run_dir: Path) -> None:
        self.sid = sid
        self.cfg = cfg
        self.run_dir = run_dir
        self.proc: Optional[subprocess.Popen] = None
        self._stop_evt = threading.Event()
        self.queue: "queue.Queue[str]" = queue.Queue(maxsize=1000)
        self._reader_thread: Optional[threading.Thread] = None
        self.stamper = EventStamper.new()

    def start(self) -> None:
        env = os.environ.copy()
        env["LX_ASR_MODEL"] = self.cfg.asr_model_id
        env["LX_DEVICE"] = self.cfg.device
        env["LX_ASR_VAD"] = "1" if self.cfg.vad else "0"
        env["LX_ASR_BEAM"] = str(self.cfg.beams)
        env["LX_PAUSE_FLUSH_SEC"] = str(self.cfg.pause_flush_sec)
        env["LX_SEGMENT_MAX_SEC"] = str(self.cfg.segment_max_sec)
        env["LX_PARTIAL_WORD_CAP"] = str(self.cfg.partial_word_cap)
        env["LX_OUT_DIR"] = str(self.run_dir)
        env["LX_SAVE_AUDIO"] = self.cfg.save_audio

        script = [sys.executable, "-m", "loquilex.cli.live_en_to_zh", "--seconds", "-1"]
        self.proc = subprocess.Popen(
            script,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            env=env,
            start_new_session=True,
        )

        def _reader() -> None:
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
                try:
                    os.killpg(self.proc.pid, signal.SIGTERM)
                except Exception:
                    self.proc.terminate()
                try:
                    self.proc.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    try:
                        os.killpg(self.proc.pid, signal.SIGKILL)
                    except Exception:
                        self.proc.kill()
            except Exception:
                pass
        self._stop_evt.set()
        if self._reader_thread:
            try:
                self._reader_thread.join(timeout=1.0)
            except Exception:
                pass

    def pause(self) -> None:
        # Send SIGSTOP to process group to pause audio ingest and decoding
        if self.proc and self.proc.poll() is None:
            try:
                os.killpg(self.proc.pid, signal.SIGSTOP)
            except Exception:
                pass

    def resume(self) -> None:
        if self.proc and self.proc.poll() is None:
            try:
                os.killpg(self.proc.pid, signal.SIGCONT)
            except Exception:
                pass

    def finalize_now(self) -> None:
        if self.proc and self.proc.poll() is None:
            try:
                os.killpg(self.proc.pid, signal.SIGUSR1)
            except Exception:
                pass


class SessionManager:
    def __init__(self) -> None:
        # Holds both types; narrow at call sites.
        self._sessions: Dict[str, Union[Session, StreamingSession]] = {}
        self._ws: Dict[str, List[WebSocket]] = {}
        self._bg_threads: List[threading.Thread] = []
        self._lock = threading.Lock()
        self._downloads: Dict[str, Tuple[str, str]] = {}
        self._stop = False
        self._max_cuda_sessions = int(os.getenv("LX_MAX_CUDA_SESSIONS", "1"))
        self._stampers: Dict[str, EventStamper] = {}
        self._dl_procs: Dict[str, subprocess.Popen] = {}

        t = threading.Thread(target=self._log_pump, daemon=True)
        t.start()
        self._bg_threads.append(t)

    def start_session(self, cfg: SessionConfig) -> str:
        if cfg.device == "cuda":
            with self._lock:
                running_cuda = sum(1 for s in self._sessions.values() if s.cfg.device == "cuda")
            if running_cuda >= self._max_cuda_sessions:
                raise RuntimeError("GPU busy: maximum concurrent CUDA sessions reached")

        sid = str(uuid.uuid4())
        run_dir = Path("loquilex/out") / sid
        run_dir.mkdir(parents=True, exist_ok=True)

        # Choose session type based on streaming_mode flag
        sess: Union[Session, StreamingSession]
        if cfg.streaming_mode:
            sess = StreamingSession(sid, cfg, run_dir)
            sess.set_broadcast_fn(self._broadcast)
        else:
            sess = Session(sid, cfg, run_dir)

        sess.start()

        with self._lock:
            self._sessions[sid] = sess
            self._stampers[sid] = sess.stamper

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
        try:
            await ws.send_json(self._stamp({"type": "hello", "sid": sid}, sid))
        except Exception:
            pass

    async def unregister_ws(self, sid: str, ws: WebSocket) -> None:
        with self._lock:
            lst = self._ws.get(sid, [])
            if ws in lst:
                lst.remove(ws)

    def _stamp(self, payload: Dict[str, Any], sid: str) -> Dict[str, Any]:
        with self._lock:
            stamper = self._stampers.get(sid)
            if not stamper:
                stamper = EventStamper.new()
                self._stampers[sid] = stamper
        return stamper.stamp(payload)

    async def _broadcast(self, sid: str, payload: Dict[str, Any]) -> None:
        with self._lock:
            conns = list(self._ws.get(sid, []))
        for ws in conns:
            try:
                await ws.send_json(self._stamp(payload, sid))
            except Exception:
                pass

    def _log_pump(self) -> None:
        while not self._stop:
            time.sleep(0.2)
            with self._lock:
                items = list(self._sessions.items())
            for sid, sess in items:
                drained = 0
                while drained < 50:
                    try:
                        line = sess.queue.get_nowait()
                    except queue.Empty:
                        break
                    drained += 1
                    text = (line or "").strip()
                    if not text:
                        continue
                    payload: Dict[str, Any]
                    if text.startswith("EN ≫ "):
                        payload = {"type": "partial_en", "text": text[len("EN ≫ ") :].strip()}
                    elif text.startswith("ZH* ≫ "):
                        payload = {"type": "partial_zh", "text": text[len("ZH* ≫ ") :].strip()}
                    elif text.startswith("EN(final):"):
                        payload = {"type": "final_en", "text": text.split(":", 1)[1].strip()}
                    elif text.startswith("ZH:"):
                        payload = {"type": "final_zh", "text": text.split(":", 1)[1].strip()}
                    elif text.startswith("VU "):
                        parts = text.split()
                        payload = {"type": "vu"}
                        try:
                            if len(parts) >= 3:
                                payload.update({"rms": float(parts[1]), "peak": float(parts[2])})
                            if len(parts) >= 4:
                                payload.update({"clip_pct": float(parts[3])})
                        except Exception:
                            pass
                    elif "Ready — start speaking now" in text:
                        payload = {"type": "status", "stage": "operational", "log": text}
                    else:
                        payload = {"type": "status", "log": text}
                    try:
                        asyncio.run(self._broadcast(sid, payload))
                    except RuntimeError:
                        loop = asyncio.get_event_loop()
                        loop.create_task(self._broadcast(sid, payload))

    # Download management
    def start_download_job(self, job_id: str, repo_id: str, _typ: str) -> None:
        t = threading.Thread(
            target=self._download_worker, args=(job_id, repo_id, _typ), daemon=True
        )
        t.start()
        self._bg_threads.append(t)

    def _download_worker(self, job_id: str, repo_id: str, _typ: str) -> None:
        chan = f"_download/{job_id}"
        try:
            asyncio.run(
                self._broadcast(
                    chan,
                    {"type": "download_progress", "job_id": job_id, "repo_id": repo_id, "pct": 0},
                )
            )
        except RuntimeError:
            loop = asyncio.get_event_loop()
            loop.create_task(
                self._broadcast(
                    chan,
                    {"type": "download_progress", "job_id": job_id, "repo_id": repo_id, "pct": 0},
                )
            )

        code = (
            "from huggingface_hub import snapshot_download;"
            f"p=snapshot_download('{repo_id}', local_dir=None);"
            "print(p)"
        )
        try:
            proc = subprocess.Popen(
                [sys.executable, "-c", code],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                start_new_session=True,
            )
        except Exception as e:
            try:
                asyncio.run(
                    self._broadcast(
                        chan, {"type": "download_error", "job_id": job_id, "message": str(e)}
                    )
                )
            except RuntimeError:
                loop = asyncio.get_event_loop()
                loop.create_task(
                    self._broadcast(
                        chan, {"type": "download_error", "job_id": job_id, "message": str(e)}
                    )
                )
            return

        with self._lock:
            self._dl_procs[job_id] = proc
            if chan not in self._stampers:
                self._stampers[chan] = EventStamper.new()

        def heartbeats() -> None:
            pct = 0
            while proc.poll() is None and not self._stop:
                try:
                    asyncio.run(
                        self._broadcast(
                            chan,
                            {
                                "type": "download_progress",
                                "job_id": job_id,
                                "repo_id": repo_id,
                                "pct": pct,
                            },
                        )
                    )
                except RuntimeError:
                    loop = asyncio.get_event_loop()
                    loop.create_task(
                        self._broadcast(
                            chan,
                            {
                                "type": "download_progress",
                                "job_id": job_id,
                                "repo_id": repo_id,
                                "pct": pct,
                            },
                        )
                    )
                pct = min(99, pct + 1)
                time.sleep(1.0)

        hb = threading.Thread(target=heartbeats, daemon=True)
        hb.start()

        out = ""
        try:
            if proc.stdout:
                try:
                    out = proc.stdout.read().decode("utf-8", errors="ignore").strip()
                except Exception:
                    out = ""
            ret = proc.wait()
        finally:
            with self._lock:
                self._dl_procs.pop(job_id, None)

        if ret == 0:
            try:
                asyncio.run(
                    self._broadcast(
                        chan, {"type": "download_done", "job_id": job_id, "local_path": out}
                    )
                )
            except RuntimeError:
                loop = asyncio.get_event_loop()
                loop.create_task(
                    self._broadcast(
                        chan, {"type": "download_done", "job_id": job_id, "local_path": out}
                    )
                )
        else:
            try:
                asyncio.run(
                    self._broadcast(
                        chan,
                        {"type": "download_error", "job_id": job_id, "message": out or f"rc={ret}"},
                    )
                )
            except RuntimeError:
                loop = asyncio.get_event_loop()
                loop.create_task(
                    self._broadcast(
                        chan,
                        {"type": "download_error", "job_id": job_id, "message": out or f"rc={ret}"},
                    )
                )

    def cancel_download(self, job_id: str) -> bool:
        with self._lock:
            proc = self._dl_procs.get(job_id)
        if not proc or proc.poll() is not None:
            return False
        try:
            os.killpg(proc.pid, signal.SIGTERM)
            try:
                proc.wait(timeout=3)
            except subprocess.TimeoutExpired:
                os.killpg(proc.pid, signal.SIGKILL)
            return True
        except Exception:
            try:
                proc.terminate()
                return True
            except Exception:
                return False

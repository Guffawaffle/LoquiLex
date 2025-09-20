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
from .ws_protocol import WSProtocolManager
from .ws_types import MessageType, HeartbeatConfig, ServerLimits
from ..logging import PerformanceMetrics, create_logger

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

    async def __aenter__(self):
        """Support async context manager for automatic cleanup."""
        return self

    async def __aexit__(self, exc_type, exc, tb):
        """Ensure cleanup when exiting context manager."""
        self.stop()

    def __del__(self):
        """Destructor to ensure cleanup if not already done."""
        # If audio thread is still running, set stop event and attempt join
        if self._audio_thread and self._audio_thread.is_alive():
            self._stop_evt.set()
            try:
                self._audio_thread.join(timeout=1.0)
            except Exception:
                pass

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

    async def __aenter__(self):
        """Support async context manager for automatic cleanup."""
        return self

    async def __aexit__(self, exc_type, exc, tb):
        """Ensure cleanup when exiting context manager."""
        self.stop()

    def __del__(self):
        """Destructor to ensure cleanup if not already done."""
        # Stop subprocess if still running
        if self.proc and self.proc.poll() is None:
            self._stop_evt.set()
            try:
                self.proc.terminate()
            except Exception:
                pass
        # Join reader thread
        if self._reader_thread and self._reader_thread.is_alive():
            self._stop_evt.set()
            try:
                self._reader_thread.join(timeout=1.0)
            except Exception:
                pass

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

        # New WebSocket protocol managers
        self._ws_protocols: Dict[str, WSProtocolManager] = {}

        # Default WebSocket configuration
        self._default_hb_config = HeartbeatConfig(
            interval_ms=int(os.getenv("LX_WS_HB_INTERVAL_MS", "10000")),
            timeout_ms=int(os.getenv("LX_WS_HB_TIMEOUT_MS", "30000")),
        )
        self._default_limits = ServerLimits(
            max_in_flight=int(os.getenv("LX_WS_MAX_IN_FLIGHT", "64")),
            max_msg_bytes=int(os.getenv("LX_WS_MAX_MSG_BYTES", "131072")),
        )

        # Initialize structured logging and metrics
        self.logger = create_logger(
            component="session_manager",
            session_id="supervisor",
        )
        self.metrics = PerformanceMetrics(
            logger=self.logger,
            component="session_manager",
        )

        # Set performance thresholds
        self.metrics.set_threshold("session_startup_time", warning=5000.0, critical=15000.0)
        self.metrics.set_threshold("websocket_message_latency", warning=100.0, critical=500.0)

        self.logger.info(
            "SessionManager initialized",
            max_cuda_sessions=self._max_cuda_sessions,
            websocket_config={
                "heartbeat_interval_ms": self._default_hb_config.interval_ms,
                "heartbeat_timeout_ms": self._default_hb_config.timeout_ms,
                "max_in_flight": self._default_limits.max_in_flight,
                "max_msg_bytes": self._default_limits.max_msg_bytes,
            }
        )

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

        self.logger.info("Starting session", session_id=sid, config=cfg.__dict__)
        self.metrics.start_timer(f"session_startup_{sid}")

        try:
            # Choose session type based on streaming_mode flag
            sess: Union[Session, StreamingSession]
            if cfg.streaming_mode:
                sess = StreamingSession(sid, cfg, run_dir)
                sess.set_broadcast_fn(self._broadcast)
                session_type = "streaming"
            else:
                sess = Session(sid, cfg, run_dir)
                session_type = "subprocess"

            sess.start()

            with self._lock:
                self._sessions[sid] = sess
                self._stampers[sid] = sess.stamper

            startup_time_ms = self.metrics.end_timer(f"session_startup_{sid}")
            self.metrics.increment_counter("sessions_started")
            self.metrics.set_gauge("active_sessions", len(self._sessions))

            self.logger.info(
                "Session started successfully",
                session_id=sid,
                session_type=session_type,
                startup_time_ms=startup_time_ms,
                total_sessions=len(self._sessions),
                run_dir=str(run_dir),
            )

            asyncio.create_task(self._broadcast(sid, {"type": "status", "stage": "initializing"}))
            return sid

        except Exception as e:
            self.logger.error(
                "Failed to start session",
                session_id=sid,
                error=str(e),
                config=cfg.__dict__,
            )
            self.metrics.increment_counter("session_start_failures")
            raise

    def stop_session(self, sid: str) -> bool:
        self.logger.info("Stopping session", session_id=sid)

        with self._lock:
            sess = self._sessions.pop(sid, None)

        if not sess:
            self.logger.warning("Attempted to stop non-existent session", session_id=sid)
            return False

        sess.stop()
        self.metrics.increment_counter("sessions_stopped")
        self.metrics.set_gauge("active_sessions", len(self._sessions))

        self.logger.info(
            "Session stopped successfully",
            session_id=sid,
            total_sessions=len(self._sessions),
        )

        asyncio.create_task(self._broadcast(sid, {"type": "status", "stage": "stopped"}))
        return True

    async def register_ws(self, sid: str, ws: WebSocket) -> None:
        """Register WebSocket connection with new envelope protocol."""
        # Get or create protocol manager for this session
        with self._lock:
            protocol_manager = self._ws_protocols.get(sid)
            if not protocol_manager:
                protocol_manager = WSProtocolManager(
                    sid=sid, hb_config=self._default_hb_config, limits=self._default_limits
                )
                protocol_manager.set_disconnect_callback(self._cleanup_ws_protocol)
                protocol_manager.set_session_snapshot_callback(self._get_session_snapshot)
                self._ws_protocols[sid] = protocol_manager

            # Also maintain legacy WebSocket list for compatibility
            lst = self._ws.setdefault(sid, [])
            lst.append(ws)

        # Add connection to protocol manager (sends welcome)
        await protocol_manager.add_connection(ws)

    async def unregister_ws(self, sid: str, ws: WebSocket) -> None:
        """Unregister WebSocket connection."""
        with self._lock:
            # Remove from legacy list
            lst = self._ws.get(sid, [])
            if ws in lst:
                lst.remove(ws)

            # Remove from protocol manager
            protocol_manager = self._ws_protocols.get(sid)

        if protocol_manager:
            await protocol_manager.remove_connection(ws)

    def _cleanup_ws_protocol(self, sid: str) -> None:
        """Cleanup callback for protocol manager."""
        with self._lock:
            self._ws_protocols.pop(sid, None)

    async def _get_session_snapshot(self, sid: str) -> Optional[Dict[str, Any]]:
        """Get session snapshot data for resume functionality."""
        with self._lock:
            session = self._sessions.get(sid)

        if not session:
            return None

        # Only StreamingSession supports snapshots currently
        if isinstance(session, StreamingSession):
            snapshot_data = {}

            # Get ASR snapshot
            asr_snapshot = session.get_asr_snapshot()
            if asr_snapshot:
                # Extract finalized transcript and active partials
                snapshot_data["finalized_transcript"] = asr_snapshot.get("recent_finals", [])
                snapshot_data["active_partials"] = []
                if asr_snapshot.get("live_partial"):
                    snapshot_data["active_partials"] = [asr_snapshot["live_partial"]]

            # Get MT status
            snapshot_data["mt_status"] = session.get_mt_status()

            return snapshot_data

        return None

    def _stamp(self, payload: Dict[str, Any], sid: str) -> Dict[str, Any]:
        with self._lock:
            stamper = self._stampers.get(sid)
            if not stamper:
                stamper = EventStamper.new()
                self._stampers[sid] = stamper
        return stamper.stamp(payload)

    async def handle_ws_message(self, sid: str, ws: WebSocket, message: str) -> None:
        """Handle incoming WebSocket message through protocol manager."""
        with self._lock:
            protocol_manager = self._ws_protocols.get(sid)

        if protocol_manager:
            await protocol_manager.handle_message(ws, message)
        else:
            logger.warning(f"No protocol manager for session {sid}")

    async def _broadcast(self, sid: str, payload: Dict[str, Any]) -> None:
        """Broadcast message using new envelope protocol."""
        with self._lock:
            protocol_manager = self._ws_protocols.get(sid)

        if protocol_manager:
            # Convert legacy payload to new envelope format
            event_type = self._map_legacy_type_to_envelope(payload.get("type", "status"))
            success = await protocol_manager.send_domain_event(event_type, payload)
            if not success:
                logger.warning(f"Flow control prevented sending message to {sid}")
        else:
            # Fallback to legacy broadcast for compatibility
            await self._legacy_broadcast(sid, payload)

    def _map_legacy_type_to_envelope(self, legacy_type: str) -> MessageType:
        """Map legacy message types to envelope message types."""
        mapping = {
            "partial_en": MessageType.ASR_PARTIAL,
            "final_en": MessageType.ASR_FINAL,
            "partial_translation": MessageType.ASR_PARTIAL,  # Multilingual support
            "final_translation": MessageType.ASR_FINAL,
            "mt_final": MessageType.MT_FINAL,
            "status": MessageType.STATUS,
        }
        return mapping.get(legacy_type, MessageType.STATUS)

    async def _legacy_broadcast(self, sid: str, payload: Dict[str, Any]) -> None:
        """Legacy broadcast method for backward compatibility."""
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

    async def shutdown(self) -> None:
        """Shutdown all sessions and cleanup resources."""
        logger.info("SessionManager shutdown initiated")
        
        # Stop flag to halt background threads
        self._stop = True
        
        # Stop all active sessions
        with self._lock:
            session_ids = list(self._sessions.keys())
            
        for sid in session_ids:
            try:
                self.stop_session(sid)
            except Exception as e:
                logger.warning(f"Error stopping session {sid}: {e}")
                
        # Close all WebSocket protocol managers
        with self._lock:
            protocol_managers = list(self._ws_protocols.values())
            
        for protocol_manager in protocol_managers:
            try:
                await protocol_manager.close()
            except Exception as e:
                logger.warning(f"Error closing protocol manager: {e}")
                
        # Cancel all download processes
        with self._lock:
            download_procs = list(self._dl_procs.items())
            
        for job_id, proc in download_procs:
            try:
                self.cancel_download(job_id)
            except Exception as e:
                logger.warning(f"Error canceling download {job_id}: {e}")
                
        # Wait for background threads to finish
        for thread in self._bg_threads:
            if thread.is_alive():
                try:
                    thread.join(timeout=3.0)
                except Exception as e:
                    logger.warning(f"Error joining background thread: {e}")
                    
        logger.info("SessionManager shutdown completed")

    def __del__(self):
        """Destructor to ensure cleanup if not already done."""
        # Set stop flag for background threads
        self._stop = True
        
        # Stop all sessions
        with self._lock:
            sessions = list(self._sessions.values())
        for session in sessions:
            try:
                session.stop()
            except Exception:
                pass

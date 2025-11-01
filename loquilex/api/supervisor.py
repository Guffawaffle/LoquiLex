from __future__ import annotations

import asyncio
import logging
import weakref
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
from typing import Any, Dict, List, Optional, Set, Tuple, Union

from fastapi import WebSocket


def _session_manager_finalize_stop(self_proxy: Any) -> None:
    """Module-level finalizer that doesn't keep strong refs to self."""
    try:
        setattr(self_proxy, "_stop", True)
        sessions = (getattr(self_proxy, "_sessions", {}) or {}).values()
        for sess in sessions:
            try:
                stop = getattr(sess, "stop", None)
                if callable(stop):
                    stop()
            except Exception:
                pass
    except Exception:
        pass


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
        loop = self._event_loop
        if loop is None or self._broadcast_fn is None:
            return
        # Avoid scheduling onto a closed loop during teardown
        # Assume open if loop lacks is_closed (e.g., mock in tests)
        if getattr(loop, "is_closed", lambda: False)():
            return

        # Capture the broadcast function into a local variable so mypy
        # understands it's not None inside the nested invoker.
        broadcast_fn = self._broadcast_fn

        def _invoke() -> None:
            try:
                result = broadcast_fn(self.sid, event)
                if asyncio.iscoroutine(result):
                    try:
                        asyncio.get_running_loop().create_task(result)
                    except RuntimeError:
                        # No running loop available; drop
                        pass
            except Exception:
                # Swallow exceptions during teardown
                pass

        try:
            loop.call_soon_threadsafe(_invoke)
        except RuntimeError:
            # Event loop may be closing; drop silently
            pass

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

            self._audio_thread = threading.Thread(target=audio_worker)
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
    # required (no defaults)
    name: str
    asr_model_id: str
    mt_enabled: bool
    dest_lang: str
    device: str
    vad: bool
    beams: int
    pause_flush_sec: float
    segment_max_sec: float
    partial_word_cap: int
    save_audio: str
    # optional (with defaults) — MUST come after all required fields
    mt_model_id: Optional[str] = None
    # New streaming mode flag
    streaming_mode: bool = False

    def __post_init__(self) -> None:
        # Require mt_model_id only when MT is enabled
        if self.mt_enabled and not self.mt_model_id:
            raise ValueError("mt_model_id is required when mt_enabled=True")


class Session:
    """DEPRECATED: Subprocess-based session orchestration.
    
    This class spawns CLI orchestrators as subprocesses, which duplicates
    orchestration logic that should now be handled by TypeScript.
    
    Migration: Use StreamingSession for in-process execution, or refactor
    to call executor services directly from TypeScript orchestration layer.
    
    See: docs/architecture/js-first.md for the JS-first architecture pattern.
    """
    def __init__(self, sid: str, cfg: SessionConfig, run_dir: Path) -> None:
        import warnings
        warnings.warn(
            "Session class (subprocess orchestration) is deprecated. "
            "Use StreamingSession for in-process execution or refactor to "
            "TypeScript orchestration with Python executors.",
            DeprecationWarning,
            stacklevel=2
        )
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
        creationflags = 0
        if os.name == "nt":
            # Windows: create new process group to enable CTRL_BREAK_EVENT
            creationflags = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
        # POSIX: rely on start_new_session=True for killpg compatibility
        self.proc = subprocess.Popen(
            script,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            env=env,
            start_new_session=(os.name != "nt"),
            creationflags=creationflags,
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

        self._reader_thread = threading.Thread(target=_reader)
        self._reader_thread.start()

    def stop(self) -> None:
        if self.proc and self.proc.poll() is None:
            try:
                if os.name == "nt":
                    try:
                        self.proc.send_signal(getattr(signal, "CTRL_BREAK_EVENT", signal.SIGTERM))
                    except Exception:
                        self.proc.terminate()
                else:
                    try:
                        pgid = os.getpgid(self.proc.pid)
                    except Exception:
                        pgid = None
                    if pgid and pgid == self.proc.pid:
                        try:
                            os.killpg(pgid, signal.SIGTERM)
                        except Exception:
                            self.proc.terminate()
                    else:
                        self.proc.terminate()
                try:
                    self.proc.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    if os.name == "nt":
                        self.proc.kill()
                    else:
                        try:
                            pgid = os.getpgid(self.proc.pid)
                        except Exception:
                            pgid = None
                        if pgid and pgid == self.proc.pid:
                            os.killpg(pgid, signal.SIGKILL)
                        else:
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
                pgid = None
                try:
                    pgid = os.getpgid(self.proc.pid)
                except Exception:
                    pass
                if pgid and pgid == self.proc.pid:
                    os.killpg(pgid, signal.SIGSTOP)
            except Exception:
                pass

    def resume(self) -> None:
        if self.proc and self.proc.poll() is None:
            try:
                pgid = None
                try:
                    pgid = os.getpgid(self.proc.pid)
                except Exception:
                    pass
                if pgid and pgid == self.proc.pid:
                    os.killpg(pgid, signal.SIGCONT)
            except Exception:
                pass

    def finalize_now(self) -> None:
        if self.proc and self.proc.poll() is None:
            try:
                pgid = None
                try:
                    pgid = os.getpgid(self.proc.pid)
                except Exception:
                    pass
                if pgid and pgid == self.proc.pid:
                    os.killpg(pgid, signal.SIGUSR1)
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
        self._download_status: Dict[str, Dict[str, Any]] = {}  # Track download status
        self._bandwidth_limit_mbps = 0  # 0 = unlimited
        self._paused_downloads: Set[str] = set()  # Track paused downloads
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
            },
        )

        def _bg_runner(self_ref: Any) -> None:
            try:
                mgr = self_ref()
                if mgr is None:
                    return
                mgr._log_pump()
            except Exception:
                pass

        t = threading.Thread(target=_bg_runner, args=(weakref.ref(self),))
        t.daemon = True
        t.start()
        self._bg_threads.append(t)

        # Register finalizer to ensure best-effort stop on GC
        # Declare attribute as Optional[Any] so assigning None is compatible
        # with static type checkers when finalizer registration fails.
        self._finalizer: Optional[Any] = None
        try:
            self._finalizer = weakref.finalize(
                self, _session_manager_finalize_stop, weakref.proxy(self)
            )
        except Exception:
            self._finalizer = None

    def start_session(self, cfg: SessionConfig) -> str:
        if cfg.device == "cuda":
            with self._lock:
                running_cuda = sum(1 for s in self._sessions.values() if s.cfg.device == "cuda")
            if running_cuda >= self._max_cuda_sessions:
                raise RuntimeError("GPU busy: maximum concgurrent CUDA sessions reached")

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

            try:
                loop = asyncio.get_running_loop()
                loop.create_task(self._broadcast(sid, {"type": "status", "stage": "initializing"}))
            except RuntimeError:
                # No running loop in this context; best-effort skip
                pass
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

        try:
            loop = asyncio.get_running_loop()
            loop.create_task(self._broadcast(sid, {"type": "status", "stage": "stopped"}))
        except RuntimeError:
            pass
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
            # Also drop legacy list to avoid leaks when unregister isn't called
            self._ws.pop(sid, None)

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

    def _safe_broadcast(self, sid: str, payload: Dict[str, Any]) -> None:
        """Best-effort schedule of a broadcast without requiring a running loop.
        Drops silently if no event loop is running (e.g., during shutdown or
        when called from sync/test contexts).
        """
        try:
            loop = asyncio.get_running_loop()
            loop.create_task(self._broadcast(sid, payload))
        except RuntimeError:
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
                    self._safe_broadcast(sid, payload)

    # Download management
    def start_download_job(self, job_id: str, repo_id: str, _typ: str) -> None:
        # Initialize download status
        with self._lock:
            self._download_status[job_id] = {
                "job_id": job_id,
                "repo_id": repo_id,
                "type": _typ,
                "status": "queued",
                "progress": 0,
                "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ"),
                "started_at": None,
                "completed_at": None,
                "error_message": None,
            }

        t = threading.Thread(target=self._download_worker, args=(job_id, repo_id, _typ))
        t.start()
        self._bg_threads.append(t)

    def _download_worker(self, job_id: str, repo_id: str, _typ: str) -> None:
        chan = f"_download/{job_id}"

        # Update status to downloading
        with self._lock:
            if job_id in self._download_status:
                self._download_status[job_id].update(
                    {"status": "downloading", "started_at": time.strftime("%Y-%m-%dT%H:%M:%SZ")}
                )

        # Initial progress
        self._safe_broadcast(
            chan,
            {"type": "download_progress", "job_id": job_id, "repo_id": repo_id, "pct": 0},
        )

        # Launch downloader subprocess
        try:
            creationflags = (
                getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0) if os.name == "nt" else 0
            )
            start_new_session = os.name != "nt"
            proc = subprocess.Popen(
                [
                    sys.executable,
                    "-c",
                    (
                        "from huggingface_hub import snapshot_download; import sys; "
                        "p = snapshot_download(sys.argv[1], local_dir=None); print(p)"
                    ),
                    "--",
                    repo_id,
                ],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                start_new_session=start_new_session,
                creationflags=creationflags,
            )
        except Exception as e:
            self._safe_broadcast(
                chan, {"type": "download_error", "job_id": job_id, "message": str(e)}
            )
            return

        with self._lock:
            self._dl_procs[job_id] = proc
            if chan not in self._stampers:
                self._stampers[chan] = EventStamper.new()

        # Heartbeat thread emitting progress
        def heartbeats() -> None:
            pct = 0
            while proc.poll() is None and not self._stop:
                # Update progress in status tracking
                with self._lock:
                    if job_id in self._download_status:
                        self._download_status[job_id]["progress"] = pct

                self._safe_broadcast(
                    chan,
                    {
                        "type": "download_progress",
                        "job_id": job_id,
                        "repo_id": repo_id,
                        "pct": pct,
                    },
                )
                pct = min(99, pct + 1)
                time.sleep(1.0)

        hb = threading.Thread(target=heartbeats)
        hb.start()

        # Read output and wait
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

        try:
            hb.join(timeout=1.0)
        except Exception:
            pass

        # Final status
        if ret == 0:
            # Update status to completed
            with self._lock:
                if job_id in self._download_status:
                    self._download_status[job_id].update(
                        {
                            "status": "completed",
                            "progress": 100,
                            "completed_at": time.strftime("%Y-%m-%dT%H:%M:%SZ"),
                        }
                    )

            self._safe_broadcast(
                chan, {"type": "download_done", "job_id": job_id, "local_path": out}
            )
        else:
            # Update status to failed
            error_msg = out or f"Process exited with code {ret}"
            with self._lock:
                if job_id in self._download_status:
                    self._download_status[job_id].update(
                        {
                            "status": "failed",
                            "completed_at": time.strftime("%Y-%m-%dT%H:%M:%SZ"),
                            "error_message": error_msg,
                        }
                    )

            self._safe_broadcast(
                chan, {"type": "download_error", "job_id": job_id, "message": error_msg}
            )

    def cancel_download(self, job_id: str) -> bool:
        with self._lock:
            proc = self._dl_procs.get(job_id)
        if not proc or proc.poll() is not None:
            return False
        try:
            if os.name == "nt":
                try:
                    proc.send_signal(getattr(signal, "CTRL_BREAK_EVENT", signal.SIGTERM))
                except Exception:
                    proc.terminate()
            else:
                try:
                    pgid = os.getpgid(proc.pid)
                except Exception:
                    pgid = None
                if pgid and pgid == proc.pid:
                    try:
                        os.killpg(pgid, signal.SIGTERM)
                    except Exception:
                        proc.terminate()
                else:
                    proc.terminate()
            try:
                proc.wait(timeout=3)
            except subprocess.TimeoutExpired:
                if os.name == "nt":
                    proc.kill()
                else:
                    try:
                        pgid = os.getpgid(proc.pid)
                    except Exception:
                        pgid = None
                    if pgid and pgid == proc.pid:
                        os.killpg(pgid, signal.SIGKILL)
                    else:
                        proc.kill()
            return True
        except Exception:
            try:
                proc.terminate()
                return True
            except Exception:
                return False

    def get_download_status(self) -> Dict[str, Dict[str, Any]]:
        """Get status of all downloads."""
        with self._lock:
            return self._download_status.copy()

    def set_bandwidth_limit(self, limit_mbps: int) -> None:
        """Set bandwidth limit for downloads."""
        with self._lock:
            self._bandwidth_limit_mbps = limit_mbps

    def get_bandwidth_limit(self) -> int:
        """Get current bandwidth limit."""
        with self._lock:
            return self._bandwidth_limit_mbps

    def pause_all_downloads(self) -> int:
        """Pause all active downloads."""
        paused_count = 0
        with self._lock:
            for job_id, proc in self._dl_procs.items():
                if proc.poll() is None:  # Process is still running
                    self._paused_downloads.add(job_id)
                    # Note: Actual pausing would require process suspension
                    # For now, we just track the paused state
                    paused_count += 1
        return paused_count

    def resume_all_downloads(self) -> int:
        """Resume all paused downloads."""
        resumed_count = 0
        with self._lock:
            resumed_count = len(self._paused_downloads)
            self._paused_downloads.clear()
        return resumed_count

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
        """Best-effort, non-async cleanup for tests; no heavy work."""
        try:
            _session_manager_finalize_stop(self)
        except Exception:
            pass

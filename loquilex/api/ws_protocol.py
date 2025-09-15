"""WebSocket Protocol Manager: envelope handling, heartbeats, and acknowledgements.

This module implements the core WebSocket protocol logic including:
- Envelope creation and validation
- Heartbeat scheduling and monitoring
- Acknowledgement tracking and flow control
- Resume/reconnect with replay buffer
- Session lifecycle management
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
import uuid
from datetime import datetime, timezone
from typing import Any, Awaitable, Callable, Dict, Optional, Set

from fastapi import WebSocket

from .ws_types import (
    AckData,
    ClientHelloData,
    ResumeInfo,
    FlowControlData,
    HeartbeatConfig,
    HeartbeatData,
    MessageType,
    QueueDropData,
    ResumeWindow,
    ServerLimits,
    ServerWelcomeData,
    SessionResumeData,
    SessionSnapshotData,
    SessionNewData,
    SessionAckData,
    SessionState,
    SystemHeartbeatData,
    WSEnvelope,
)

logger = logging.getLogger(__name__)


class WSProtocolManager:
    async def __aenter__(self):
        """Support async context manager for automatic cleanup."""
        return self

    async def __aexit__(self, exc_type, exc, tb):
        await self.close()

    def __del__(self):
        """Destructor to ensure cleanup if not already done."""
        # If tasks are still running, schedule their cancellation
        if self._hb_task and not self._hb_task.done():
            self._hb_task.cancel()
        if self._hb_timeout_task and not self._hb_timeout_task.done():
            self._hb_timeout_task.cancel()
        if self._system_hb_task and not self._system_hb_task.done():
            self._system_hb_task.cancel()

    """Manages WebSocket protocol for a single session."""

    def __init__(
        self,
        sid: str,
        hb_config: Optional[HeartbeatConfig] = None,
        resume_window: Optional[ResumeWindow] = None,
        limits: Optional[ServerLimits] = None,
    ):
        self.sid = sid
        self.state = SessionState(
            sid=sid,
            t0_mono=time.monotonic(),
            t0_wall=datetime.now(timezone.utc).isoformat(),
            epoch=int(time.time()) % 10000,  # Simple epoch based on timestamp
        )

        # Configuration with environment variable support
        from ..config.defaults import _env_time_seconds, _env_int

        # Default configuration with unit suffix support
        default_hb_config = HeartbeatConfig(
            interval_ms=int(_env_time_seconds("LX_WS_HEARTBEAT_SEC", 5.0) * 1000),
            timeout_ms=int(_env_time_seconds("LX_WS_HEARTBEAT_TIMEOUT_SEC", 15.0) * 1000),
        )

        default_resume_window = ResumeWindow(
            seconds=int(_env_time_seconds("LX_WS_RESUME_TTL", 10.0)),
        )

        default_limits = ServerLimits(
            max_in_flight=_env_int("LX_WS_MAX_IN_FLIGHT", 64),
            max_msg_bytes=_env_int("LX_WS_MAX_MSG_BYTES", 131072),
        )

        self.hb_config = hb_config or default_hb_config
        self.resume_window = resume_window or default_resume_window
        self.limits = limits or default_limits

        # WebSocket connections
        self.connections: Set[WebSocket] = set()

        # Heartbeat tracking
        self._hb_task: Optional[asyncio.Task] = None
        self._hb_timeout_task: Optional[asyncio.Task] = None

        # System heartbeat for resilient comms
        self._system_hb_task: Optional[asyncio.Task] = None

        # Callbacks
        self._on_disconnect: Optional[Callable[[str], None]] = None
        self._session_snapshot_callback: Optional[Callable[[str], Awaitable[Any]]] = None

        # Bounded queues and telemetry
        from .bounded_queue import BoundedQueue, ReplayBuffer

        # Replace simple replay buffer with bounded replay buffer
        max_replay_events = _env_int("LX_WS_RESUME_MAX_EVENTS", 500)
        self._replay_buffer = ReplayBuffer(
            maxsize=max_replay_events, ttl_seconds=self.resume_window.seconds
        )

        # Outbound event queue for each connection
        self._outbound_queues: Dict[WebSocket, BoundedQueue] = {}

        # Telemetry
        self._metrics: Dict[str, Dict[str, Any]] = {
            "queue_depths": {},
            "drop_counts": {},
            "latency_metrics": {},
            "resume_metrics": {
                "attempts": 0,
                "success": 0,
                "miss": 0,
                "snapshot_sizes": [],
                "replay_durations": [],
            },
        }

    def set_disconnect_callback(self, callback: Callable[[str], None]) -> None:
        """Set callback for when session should be cleaned up."""
        self._on_disconnect = callback

    def set_session_snapshot_callback(self, callback: Callable[[str], Awaitable[Any]]) -> None:
        """Set callback for getting session snapshot data for resume."""
        self._session_snapshot_callback = callback

    async def add_connection(self, ws: WebSocket) -> None:
        """Add a new WebSocket connection."""
        self.connections.add(ws)

        # Send welcome message
        welcome = self._create_envelope(
            MessageType.SERVER_WELCOME,
            ServerWelcomeData(
                hb=self.hb_config,
                resume_window=self.resume_window,
                limits=self.limits,
            ).model_dump(),
            seq=0,  # Welcome message uses seq 0, domain events start from 1
        )
        await self._send_to_connection(ws, welcome)

        # Start heartbeat if this is the first connection
        if len(self.connections) == 1:
            await self._start_heartbeat()
            await self._start_system_heartbeat()

        # Create bounded outbound queue for this connection
        from .bounded_queue import BoundedQueue
        from ..config.defaults import _env_int

        client_buffer_size = _env_int("LX_CLIENT_EVENT_BUFFER", 300)
        self._outbound_queues[ws] = BoundedQueue(
            maxsize=client_buffer_size, name=f"outbound_{id(ws)}"
        )

    async def remove_connection(self, ws: WebSocket) -> None:
        """Remove a WebSocket connection."""
        self.connections.discard(ws)

        # Clean up outbound queue for this connection
        if ws in self._outbound_queues:
            del self._outbound_queues[ws]

        # Stop heartbeat if no connections remain
        if not self.connections:
            await self._stop_heartbeat()
            await self._stop_system_heartbeat()

    async def handle_message(self, ws: WebSocket, message: str) -> None:
        """Handle incoming WebSocket message."""
        try:
            data = json.loads(message)
            envelope = WSEnvelope.model_validate(data)

            # Route based on message type
            if envelope.t == MessageType.CLIENT_HELLO:
                await self._handle_client_hello(ws, envelope)
            elif envelope.t == MessageType.SESSION_RESUME:
                await self._handle_session_resume(ws, envelope)
            elif envelope.t == MessageType.CLIENT_ACK:
                await self._handle_client_ack(envelope)
            elif envelope.t == MessageType.CLIENT_HB:
                await self._handle_client_heartbeat(envelope)
            elif envelope.t == MessageType.CLIENT_FLOW:
                await self._handle_client_flow(envelope)
            else:
                logger.warning(f"Unknown message type: {envelope.t}")

        except Exception as e:
            logger.exception(f"Error handling WebSocket message: {e}")
            await self._send_error(ws, "invalid_message", str(e))

    async def _handle_client_hello(self, ws: WebSocket, envelope: WSEnvelope) -> None:
        """Handle client hello message."""
        try:
            hello_data = ClientHelloData.model_validate(envelope.data)

            # Handle resume request
            if hello_data.resume:
                await self._handle_resume_request(ws, hello_data.resume)
                return

            # Update session state based on client preferences
            self.state.ack_mode = hello_data.ack_mode
            self.state.max_in_flight = min(hello_data.max_in_flight, self.limits.max_in_flight)

            logger.info(f"Client hello processed for session {self.sid}")

        except Exception as e:
            await self._send_error(ws, "invalid_hello", str(e))

    async def _handle_resume_request(self, ws: WebSocket, resume: ResumeInfo) -> None:
        """Process a resume request coming from a ClientHello.resume field.

        This is a small shim so both explicit SESSION_RESUME messages and
        embedded resume requests in ClientHello share the same resume handling
        implemented in `_handle_session_resume`.
        """
        # Construct a minimal envelope-like object to reuse existing handler
        envelope = WSEnvelope(
            v=1,
            t=MessageType.SESSION_RESUME,
            sid=self.sid,
            id=None,
            seq=None,
            corr=None,
            t_wall=None,
            data=resume.model_dump(),
        )
        await self._handle_session_resume(ws, envelope)

    async def _handle_session_resume(self, ws: WebSocket, envelope: WSEnvelope) -> None:
        """Handle session resume request."""
        try:
            start_time = time.monotonic()
            self._metrics["resume_metrics"]["attempts"] += 1

            resume_data = SessionResumeData.model_validate(envelope.data)

            # Check session ID match
            if resume_data.session_id != self.sid:
                self._metrics["resume_metrics"]["miss"] += 1
                await self._send_session_new(ws, envelope.corr, "session_id_mismatch")
                return

            # Check epoch if provided
            if resume_data.epoch is not None and resume_data.epoch != self.state.epoch:
                self._metrics["resume_metrics"]["miss"] += 1
                await self._send_session_new(ws, envelope.corr, "epoch_mismatch")
                return

            # Check if resume is within window
            elapsed = time.monotonic() - self.state.t0_mono
            if elapsed > self.resume_window.seconds:
                self._metrics["resume_metrics"]["miss"] += 1
                await self._send_session_new(ws, envelope.corr, "resume_expired")
                return

            # Get replay messages
            replay_messages = self._replay_buffer.get_messages_after(resume_data.last_seq)

            # Send session snapshot with replay data
            await self._send_session_snapshot(ws, envelope.corr, replay_messages)

            # Record success metrics
            self._metrics["resume_metrics"]["success"] += 1
            duration_ms = (time.monotonic() - start_time) * 1000
            self._metrics["resume_metrics"]["replay_durations"].append(duration_ms)

            # Keep only recent durations (last 100)
            if len(self._metrics["resume_metrics"]["replay_durations"]) > 100:
                self._metrics["resume_metrics"]["replay_durations"] = self._metrics[
                    "resume_metrics"
                ]["replay_durations"][-100:]

            logger.info(
                f"Session {self.sid} resumed, replayed {len(replay_messages)} messages in {duration_ms:.1f}ms"
            )

        except Exception as e:
            self._metrics["resume_metrics"]["miss"] += 1
            logger.exception(f"Error handling session resume: {e}")
            await self._send_error(ws, "invalid_resume", str(e))

    async def _send_session_snapshot(
        self, ws: WebSocket, corr: Optional[str], replay_messages: list
    ) -> None:
        """Send session snapshot for successful resume."""
        # Get actual finalized transcript and active partials from session
        finalized_transcript = []
        active_partials = []
        mt_status = None

        if self._session_snapshot_callback:
            try:
                snapshot = await self._session_snapshot_callback(self.sid)
                if snapshot:
                    finalized_transcript = snapshot.get("finalized_transcript", [])
                    active_partials = snapshot.get("active_partials", [])
                    mt_status = snapshot.get("mt_status")
            except Exception as e:
                logger.warning(f"Failed to get session snapshot for {self.sid}: {e}")

        snapshot_data = SessionSnapshotData(
            session_id=self.sid,
            epoch=self.state.epoch,
            current_seq=self.state.seq,
            finalized_transcript=finalized_transcript,
            active_partials=active_partials,
            mt_status=mt_status,
        )

        # Record snapshot metrics
        snapshot_size = len(finalized_transcript) + len(active_partials) + len(replay_messages)
        self._metrics["resume_metrics"]["snapshot_sizes"].append(snapshot_size)

        # Keep only recent sizes (last 100)
        if len(self._metrics["resume_metrics"]["snapshot_sizes"]) > 100:
            self._metrics["resume_metrics"]["snapshot_sizes"] = self._metrics["resume_metrics"][
                "snapshot_sizes"
            ][-100:]

        snapshot_envelope = self._create_envelope(
            MessageType.SESSION_SNAPSHOT,
            snapshot_data.model_dump(),
            corr=corr,
        )
        await self._send_to_connection(ws, snapshot_envelope)

        # Send replay messages
        for msg in replay_messages:
            await self._send_to_connection(ws, msg)

        # Send session ack to complete handshake
        ack_data = SessionAckData(session_id=self.sid, status="resumed")
        ack_envelope = self._create_envelope(
            MessageType.SESSION_ACK,
            ack_data.model_dump(),
            corr=corr,
        )
        await self._send_to_connection(ws, ack_envelope)

    async def _send_session_new(self, ws: WebSocket, corr: Optional[str], reason: str) -> None:
        """Send session new response for failed resume."""
        # Reset session state for fresh start
        self.state.epoch += 1
        self.state.seq = 0
        self.state.last_ack_seq = 0
        self._replay_buffer.clear()

        new_data = SessionNewData(
            session_id=self.sid,
            epoch=self.state.epoch,
            reason=reason,
        )

        new_envelope = self._create_envelope(
            MessageType.SESSION_NEW,
            new_data.model_dump(),
            corr=corr,
        )
        await self._send_to_connection(ws, new_envelope)

    async def _handle_client_ack(self, envelope: WSEnvelope) -> None:
        """Handle client acknowledgement."""
        try:
            ack_data = AckData.model_validate(envelope.data)
            # Protect against ack spoofing: client cannot ack beyond latest delivered seq
            if ack_data.ack_seq > self.state.seq:
                logger.warning(
                    f"Client ack beyond latest seq: {ack_data.ack_seq} > {self.state.seq}"
                )
                # Send structured error back to client
                # Find a connection to reply on (use first connection)
                ws = next(iter(self.connections), None)
                if ws:
                    await self._send_error(
                        ws,
                        "invalid_ack",
                        f"Ack {ack_data.ack_seq} beyond latest delivered seq {self.state.seq}",
                    )
                return

            self.state.process_ack(ack_data.ack_seq)
            logger.debug(f"Processed ack for seq {ack_data.ack_seq}")

        except Exception as e:
            logger.exception(f"Error processing ack: {e}")

    async def _handle_client_heartbeat(self, envelope: WSEnvelope) -> None:  # noqa: ARG002
        """Handle client heartbeat."""
        self.state.last_hb_recv = time.monotonic()

        # Reset heartbeat timeout
        if self._hb_timeout_task:
            self._hb_timeout_task.cancel()
            self._hb_timeout_task = asyncio.create_task(self._heartbeat_timeout())

    async def _handle_client_flow(self, envelope: WSEnvelope) -> None:
        """Handle client flow control update."""
        try:
            flow_data = FlowControlData.model_validate(envelope.data)
            new_limit = min(flow_data.max_in_flight, self.limits.max_in_flight)
            self.state.max_in_flight = new_limit
            logger.info(f"Updated flow control limit to {new_limit}")

        except Exception as e:
            logger.exception(f"Error processing flow control: {e}")

    async def send_domain_event(self, event_type: MessageType, data: Dict[str, Any]) -> bool:
        """Send a domain event (ASR, MT, status) to all connections.

        Returns True if message was sent, False if flow control prevented it.
        """
        if not self.state.can_send_message():
            logger.warning(f"Flow control prevents sending {event_type}")
            return False

        envelope = self._create_envelope(event_type, data)

        # Add to both state and bounded replay buffer for compatibility
        self.state.add_to_replay_buffer(envelope)
        if envelope.seq is not None:
            self._replay_buffer.add_message(envelope.seq, envelope)

        await self._broadcast(envelope)
        return True

    def _create_envelope(
        self,
        msg_type: MessageType,
        data: Dict[str, Any],
        corr: Optional[str] = None,
        seq: Optional[int] = None,
    ) -> WSEnvelope:
        """Create a properly formatted envelope."""
        if seq is None:
            seq = self.state.next_seq()
        else:
            # For specific seq (like welcome message), update state if needed
            if seq > self.state.seq:
                self.state.seq = seq

        return WSEnvelope(
            v=1,
            t=msg_type,
            sid=self.sid,
            id=f"msg_{uuid.uuid4().hex[:8]}",
            seq=seq,
            corr=corr,
            t_wall=datetime.now(timezone.utc).isoformat(),
            t_mono_ns=self.state.get_monotonic_ns(),
            data=data,
        )

    async def _broadcast(self, envelope: WSEnvelope) -> None:
        """Broadcast envelope to all connections."""
        if not self.connections:
            return

        # Convert to JSON once
        message = envelope.model_dump_json()

        # Send to all connections
        failed_connections = []
        for ws in self.connections:
            try:
                await ws.send_text(message)
            except Exception as e:
                logger.warning(f"Failed to send to connection: {e}")
                failed_connections.append(ws)

        # Remove failed connections
        for ws in failed_connections:
            self.connections.discard(ws)

        # If all connections failed, cleanup session
        if failed_connections and not self.connections:
            await self._cleanup_session()

    async def _send_to_connection(self, ws: WebSocket, envelope: WSEnvelope) -> None:
        """Send envelope to specific connection."""
        try:
            message = envelope.model_dump_json()
            await ws.send_text(message)
        except Exception as e:
            logger.warning(f"Failed to send to connection: {e}")
            self.connections.discard(ws)

    async def _send_error(
        self, ws: WebSocket, code: str, detail: str, retry_after_ms: Optional[int] = None
    ) -> None:
        """Send error message to specific connection."""
        from .ws_types import ErrorCode, ServerErrorData

        # Accept code as str or ErrorCode
        try:
            code_enum = ErrorCode(code)
        except ValueError:
            code_enum = ErrorCode.INTERNAL
        error_envelope = self._create_envelope(
            MessageType.SERVER_ERROR,
            ServerErrorData(
                code=code_enum, detail=detail, retry_after_ms=retry_after_ms
            ).model_dump(),
        )
        await self._send_to_connection(ws, error_envelope)

    async def _start_heartbeat(self) -> None:
        """Start heartbeat scheduling."""
        if self._hb_task:
            return

        self._hb_task = asyncio.create_task(self._heartbeat_loop())
        self._hb_timeout_task = asyncio.create_task(self._heartbeat_timeout())

    async def _start_system_heartbeat(self) -> None:
        """Start system heartbeat for resilient comms."""
        if self._system_hb_task:
            return

        self._system_hb_task = asyncio.create_task(self._system_heartbeat_loop())

    async def _stop_heartbeat(self) -> None:
        """Stop heartbeat scheduling and await tasks."""
        tasks = []
        if self._hb_task:
            self._hb_task.cancel()
            tasks.append(self._hb_task)
            self._hb_task = None

        if self._hb_timeout_task:
            self._hb_timeout_task.cancel()
            tasks.append(self._hb_timeout_task)
            self._hb_timeout_task = None

        # Await cancelled tasks to ensure proper cleanup
        for t in tasks:
            try:
                await t
            except asyncio.CancelledError:
                pass

    async def _stop_system_heartbeat(self) -> None:
        """Stop system heartbeat."""
        if self._system_hb_task:
            self._system_hb_task.cancel()
            try:
                await self._system_hb_task
            except asyncio.CancelledError:
                pass
            self._system_hb_task = None

    async def _heartbeat_loop(self) -> None:
        """Send periodic heartbeats."""
        try:
            while True:
                await asyncio.sleep(self.hb_config.interval_ms / 1000.0)

                if not self.connections:
                    break

                # Send heartbeat
                hb_data = HeartbeatData(
                    ts=datetime.now(timezone.utc).isoformat(),
                    q_out=len(self.state.replay_buffer),
                    q_in=0,  # We don't track inbound queue depth
                    latency_ms_est=None,  # Could be calculated from round-trip
                )

                hb_envelope = self._create_envelope(MessageType.SERVER_HB, hb_data.model_dump())
                await self._broadcast(hb_envelope)

                self.state.last_hb_sent = time.monotonic()

        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.exception(f"Heartbeat loop error: {e}")

    async def _heartbeat_timeout(self) -> None:
        """Monitor heartbeat timeout."""
        try:
            await asyncio.sleep(self.hb_config.timeout_ms / 1000.0)

            # Check if we've received a heartbeat recently
            if self.state.last_hb_recv > 0:
                elapsed = time.monotonic() - self.state.last_hb_recv
                if elapsed > (self.hb_config.timeout_ms / 1000.0):
                    logger.warning(f"Heartbeat timeout for session {self.sid}")
                    await self._cleanup_session()

        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.exception(f"Heartbeat timeout error: {e}")

    async def _system_heartbeat_loop(self) -> None:
        """Send system heartbeats with comprehensive metrics."""
        try:
            while True:
                await asyncio.sleep(self.hb_config.interval_ms / 1000.0)

                if not self.connections:
                    break

                # Collect telemetry
                queue_depths = {}
                drop_counts = {}

                # Replay buffer metrics
                replay_telemetry = self._replay_buffer.get_telemetry()
                queue_depths["replay_buffer"] = replay_telemetry["size"]
                drop_counts["replay_buffer"] = replay_telemetry["total_dropped"]

                # Outbound queue metrics
                for i, (ws, queue) in enumerate(self._outbound_queues.items()):
                    queue_telemetry = queue.get_telemetry()
                    queue_depths[f"outbound_{i}"] = queue_telemetry["size"]
                    drop_counts[f"outbound_{i}"] = queue_telemetry["total_dropped"]

                # System heartbeat
                system_hb_data = SystemHeartbeatData(
                    ts=datetime.now(timezone.utc).isoformat(),
                    t_mono_ms=self.state.get_monotonic_ns(),
                    queue_depths=queue_depths,
                    drop_counts=drop_counts,
                    latency_metrics=self._metrics.get("latency_metrics", {}),
                )

                system_hb_envelope = self._create_envelope(
                    MessageType.SYSTEM_HEARTBEAT, system_hb_data.model_dump()
                )
                await self._broadcast(system_hb_envelope)

        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.exception(f"System heartbeat loop error: {e}")

    async def _cleanup_session(self) -> None:
        """Clean up session resources."""
        await self._stop_heartbeat()
        await self._stop_system_heartbeat()

        # Close all connections
        for ws in list(self.connections):
            try:
                await ws.close()
            except Exception:
                pass
        self.connections.clear()

        # Clear outbound queues
        self._outbound_queues.clear()

        # Notify parent to remove session
        if self._on_disconnect:
            self._on_disconnect(self.sid)

    async def close(self) -> None:
        """Gracefully close the session."""
        await self._cleanup_session()

    async def emit_queue_drop(self, path: str, count: int, reason: str, total: int) -> None:
        """Emit queue drop notification."""
        drop_data = QueueDropData(
            path=path,
            count=count,
            reason=reason,
            total_dropped=total,
        )

        drop_envelope = self._create_envelope(MessageType.QUEUE_DROP, drop_data.model_dump())
        await self._broadcast(drop_envelope)

    def get_telemetry_summary(self) -> Dict[str, Any]:
        """Get comprehensive telemetry summary."""
        queue_depths = {}
        drop_totals = {}

        # Replay buffer
        replay_tel = self._replay_buffer.get_telemetry()
        queue_depths["replay_buffer"] = replay_tel["size"]
        drop_totals["replay_buffer"] = replay_tel["total_dropped"]

        # Outbound queues
        for i, (_, queue) in enumerate(self._outbound_queues.items()):
            queue_tel = queue.get_telemetry()
            queue_depths[f"outbound_{i}"] = queue_tel["size"]
            drop_totals[f"outbound_{i}"] = queue_tel["total_dropped"]

        uptime = time.monotonic() - self.state.t0_mono

        # Calculate resume metrics statistics
        resume_metrics = self._metrics["resume_metrics"]
        avg_snapshot_size = 0
        avg_replay_duration = 0
        success_rate = 0

        if resume_metrics["snapshot_sizes"]:
            avg_snapshot_size = sum(resume_metrics["snapshot_sizes"]) / len(
                resume_metrics["snapshot_sizes"]
            )

        if resume_metrics["replay_durations"]:
            avg_replay_duration = sum(resume_metrics["replay_durations"]) / len(
                resume_metrics["replay_durations"]
            )

        if resume_metrics["attempts"] > 0:
            success_rate = resume_metrics["success"] / resume_metrics["attempts"]

        return {
            "session_id": self.sid,
            "epoch": self.state.epoch,
            "uptime_seconds": uptime,
            "queue_depths": queue_depths,
            "drop_totals": drop_totals,
            "latency_metrics": self._metrics.get("latency_metrics", {}),
            "connections": len(self.connections),
            "resume_metrics": {
                "attempts": resume_metrics["attempts"],
                "success": resume_metrics["success"],
                "miss": resume_metrics["miss"],
                "success_rate": success_rate,
                "avg_snapshot_size": avg_snapshot_size,
                "avg_replay_duration_ms": avg_replay_duration,
            },
        }

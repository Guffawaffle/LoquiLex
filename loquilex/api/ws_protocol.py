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
from typing import Any, Callable, Dict, Optional, Set

from fastapi import WebSocket

from .ws_types import (
    AckData,
    ClientHelloData,
    FlowControlData,
    HeartbeatConfig,
    HeartbeatData,
    MessageType,
    ResumeInfo,
    ResumeWindow,
    ServerErrorData,
    ServerLimits,
    ServerWelcomeData,
    SessionState,
    WSEnvelope,
)

logger = logging.getLogger(__name__)


class WSProtocolManager:
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
        )

        # Configuration
        self.hb_config = hb_config or HeartbeatConfig()
        self.resume_window = resume_window or ResumeWindow()
        self.limits = limits or ServerLimits()

        # WebSocket connections
        self.connections: Set[WebSocket] = set()

        # Heartbeat tracking
        self._hb_task: Optional[asyncio.Task] = None
        self._hb_timeout_task: Optional[asyncio.Task] = None

        # Callbacks
        self._on_disconnect: Optional[Callable[[str], None]] = None

    def set_disconnect_callback(self, callback: Callable[[str], None]) -> None:
        """Set callback for when session should be cleaned up."""
        self._on_disconnect = callback

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

    async def remove_connection(self, ws: WebSocket) -> None:
        """Remove a WebSocket connection."""
        self.connections.discard(ws)

        # Stop heartbeat if no connections remain
        if not self.connections:
            await self._stop_heartbeat()

    async def handle_message(self, ws: WebSocket, message: str) -> None:
        """Handle incoming WebSocket message."""
        try:
            data = json.loads(message)
            envelope = WSEnvelope.model_validate(data)

            # Route based on message type
            if envelope.t == MessageType.CLIENT_HELLO:
                await self._handle_client_hello(ws, envelope)
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

    async def _handle_resume_request(self, ws: WebSocket, resume_info: ResumeInfo) -> None:
        """Handle resume request from client."""
        if resume_info.sid != self.sid:
            await self._send_error(ws, "invalid_session", "Session ID mismatch")
            return

        # Check if resume is within window
        elapsed = time.monotonic() - self.state.t0_mono
        if elapsed > self.resume_window.seconds:
            await self._send_error(ws, "resume_expired", "Resume window exceeded")
            return

        # Replay messages
        replay_messages = self.state.get_replay_messages(resume_info.last_seq)
        for msg in replay_messages:
            await self._send_to_connection(ws, msg)

        logger.info(f"Resumed session {self.sid}, replayed {len(replay_messages)} messages")

    async def _handle_client_ack(self, envelope: WSEnvelope) -> None:
        """Handle client acknowledgement."""
        try:
            ack_data = AckData.model_validate(envelope.data)
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
        self.state.add_to_replay_buffer(envelope)

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
            t_mono_ms=self.state.get_monotonic_ms(),
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

    async def _send_error(self, ws: WebSocket, code: str, detail: str) -> None:
        """Send error message to specific connection."""
        error_envelope = self._create_envelope(
            MessageType.SERVER_ERROR,
            ServerErrorData(code=code, detail=detail).model_dump(),
        )
        await self._send_to_connection(ws, error_envelope)

    async def _start_heartbeat(self) -> None:
        """Start heartbeat scheduling."""
        if self._hb_task:
            return

        self._hb_task = asyncio.create_task(self._heartbeat_loop())
        self._hb_timeout_task = asyncio.create_task(self._heartbeat_timeout())

    async def _stop_heartbeat(self) -> None:
        """Stop heartbeat scheduling."""
        if self._hb_task:
            self._hb_task.cancel()
            self._hb_task = None

        if self._hb_timeout_task:
            self._hb_timeout_task.cancel()
            self._hb_timeout_task = None

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

    async def _cleanup_session(self) -> None:
        """Clean up session resources."""
        await self._stop_heartbeat()

        # Close all connections
        for ws in list(self.connections):
            try:
                await ws.close()
            except Exception:
                pass
        self.connections.clear()

        # Notify parent to remove session
        if self._on_disconnect:
            self._on_disconnect(self.sid)

    async def close(self) -> None:
        """Gracefully close the session."""
        await self._cleanup_session()

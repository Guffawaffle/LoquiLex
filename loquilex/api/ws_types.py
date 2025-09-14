"""WebSocket API Types: versioned envelope schema and control protocol.

This module defines the structured envelope format for all WebSocket messages
including control types (hello, welcome, heartbeats, acks) and domain events
(ASR partials/finals, MT finals, status updates).

Envelope design supports:
- Versioned schema for forward/backward compatibility
- Session management with server-issued IDs
- Sequence numbering for acknowledgements and replay
- Monotonic timing for latency measurement
- Correlation IDs for request/response linking
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, Optional

from pydantic import BaseModel, Field


class MessageType(str, Enum):
    """Standard message types for the WebSocket protocol."""

    # Connection control
    CLIENT_HELLO = "client.hello"
    SERVER_WELCOME = "server.welcome"
    SERVER_ERROR = "server.error"

    # Heartbeats
    CLIENT_HB = "client.hb"
    SERVER_HB = "server.hb"

    # Acknowledgements
    CLIENT_ACK = "client.ack"
    SERVER_ACK = "server.ack"

    # Flow control
    CLIENT_FLOW = "client.flow"

    # Domain events
    ASR_PARTIAL = "asr.partial"
    ASR_FINAL = "asr.final"
    MT_FINAL = "mt.final"
    STATUS = "status"


class WSEnvelope(BaseModel):
    """Versioned envelope for all WebSocket messages.

    All messages use this shared envelope structure with type-specific
    payloads in the 'data' field.
    """

    v: int = Field(default=1, description="Schema version")
    t: MessageType = Field(description="Message type (namespaced)")
    sid: Optional[str] = Field(default=None, description="Session ID (server-issued)")
    id: Optional[str] = Field(default=None, description="Message ID (server-unique)")
    seq: Optional[int] = Field(default=None, description="Sequence number per session")
    corr: Optional[str] = Field(default=None, description="Correlation ID for responses")
    t_wall: Optional[str] = Field(default=None, description="ISO8601 timestamp")
    t_mono_ms: Optional[int] = Field(
        default=None, description="Monotonic milliseconds since session start"
    )
    data: Dict[str, Any] = Field(default_factory=dict, description="Type-specific payload")

    def model_post_init(self) -> None:
        """Auto-generate message ID if not provided."""
        if self.id is None and self.sid is not None:
            self.id = f"msg_{uuid.uuid4().hex[:8]}"


class AckMode(str, Enum):
    """Acknowledgement modes for flow control."""

    CUMULATIVE = "cumulative"
    PER_MESSAGE = "per-message"


# Control message payloads


class ClientHelloData(BaseModel):
    """Client hello payload - announces capabilities and preferences."""

    agent: str = Field(description="Client agent string")
    accept: list[str] = Field(default_factory=list, description="Accepted message types")
    ack_mode: AckMode = Field(default=AckMode.CUMULATIVE, description="Acknowledgement mode")
    max_in_flight: int = Field(default=32, description="Requested sliding window size")
    resume: Optional[ResumeInfo] = Field(default=None, description="Resume information")


class ResumeInfo(BaseModel):
    """Resume information for reconnection."""

    sid: str = Field(description="Previous session ID")
    last_seq: int = Field(description="Last acknowledged sequence number")


class ServerWelcomeData(BaseModel):
    """Server welcome payload - provides session config and limits."""

    hb: HeartbeatConfig = Field(description="Heartbeat configuration")
    resume_window: ResumeWindow = Field(description="Resume window policy")
    limits: ServerLimits = Field(description="Server-imposed limits")


class HeartbeatConfig(BaseModel):
    """Heartbeat timing configuration."""

    interval_ms: int = Field(default=10000, description="Heartbeat interval in milliseconds")
    timeout_ms: int = Field(default=30000, description="Heartbeat timeout in milliseconds")


class ResumeWindow(BaseModel):
    """Resume window policy for reconnections."""

    seconds: int = Field(default=300, description="Resume window in seconds")
    token: Optional[str] = Field(default=None, description="Resume token")


class ServerLimits(BaseModel):
    """Server-imposed limits for flow control."""

    max_in_flight: int = Field(default=64, description="Maximum sliding window size")
    max_msg_bytes: int = Field(default=131072, description="Maximum message size in bytes")


class HeartbeatData(BaseModel):
    """Heartbeat payload with metrics."""

    ts: str = Field(description="ISO8601 timestamp")
    q_out: int = Field(default=0, description="Outbound queue depth")
    q_in: int = Field(default=0, description="Inbound queue depth")
    latency_ms_est: Optional[int] = Field(
        default=None, description="Estimated latency in milliseconds"
    )


class AckData(BaseModel):
    """Acknowledgement payload."""

    ack_seq: int = Field(description="Acknowledged sequence number")


class FlowControlData(BaseModel):
    """Flow control payload to adjust window size."""

    max_in_flight: int = Field(description="New maximum in-flight messages")


class ServerErrorData(BaseModel):
    """Server error payload."""

    code: str = Field(description="Error code")
    detail: str = Field(description="Error detail message")


# Domain event payloads


class ASRPartialData(BaseModel):
    """ASR partial transcription payload."""

    text: str = Field(description="Partial text")
    final: bool = Field(default=False, description="Whether this is final")
    segment_id: str = Field(description="Segment identifier")


class ASRFinalData(BaseModel):
    """ASR final transcription payload."""

    text: str = Field(description="Final transcribed text")
    segment_id: str = Field(description="Segment identifier")
    start_ms: Optional[int] = Field(default=None, description="Segment start time in milliseconds")
    end_ms: Optional[int] = Field(default=None, description="Segment end time in milliseconds")


class MTFinalData(BaseModel):
    """Machine translation final payload."""

    text: str = Field(description="Translated text")
    src: str = Field(description="Source language code")
    tgt: str = Field(description="Target language code")


class StatusData(BaseModel):
    """Status update payload."""

    stage: str = Field(description="Status stage")
    detail: Optional[str] = Field(default=None, description="Optional status detail")


@dataclass
class SessionState:
    """Session state for managing WebSocket connections."""

    sid: str
    t0_mono: float  # Session start time (monotonic)
    t0_wall: str  # Session start time (wall clock, ISO8601)
    seq: int = 0
    last_hb_sent: float = 0.0
    last_hb_recv: float = 0.0
    ack_mode: AckMode = AckMode.CUMULATIVE
    max_in_flight: int = 32
    last_ack_seq: int = 0
    replay_buffer: Dict[int, WSEnvelope] = field(default_factory=dict)
    resume_window_sec: int = 300

    def next_seq(self) -> int:
        """Get next sequence number."""
        self.seq += 1
        return self.seq

    def get_monotonic_ms(self) -> int:
        """Get milliseconds since session start (monotonic)."""
        return int((time.monotonic() - self.t0_mono) * 1000)

    def add_to_replay_buffer(self, envelope: WSEnvelope) -> None:
        """Add message to replay buffer with retention policy."""
        if envelope.seq is not None:
            self.replay_buffer[envelope.seq] = envelope

        # Cleanup old messages outside replay window
        cutoff_time = time.monotonic() - self.resume_window_sec
        to_remove = []
        for seq, env in self.replay_buffer.items():
            if env.t_mono_ms is not None:
                msg_time = self.t0_mono + (env.t_mono_ms / 1000.0)
                if msg_time < cutoff_time:
                    to_remove.append(seq)

        for seq in to_remove:
            self.replay_buffer.pop(seq, None)

    def get_replay_messages(self, last_seq: int) -> list[WSEnvelope]:
        """Get messages for replay after reconnect."""
        return [env for seq, env in sorted(self.replay_buffer.items()) if seq > last_seq]

    def can_send_message(self) -> bool:
        """Check if we can send a message within flow control limits."""
        in_flight = self.seq - self.last_ack_seq
        return in_flight < self.max_in_flight

    def process_ack(self, ack_seq: int) -> None:
        """Process acknowledgement and update flow control state."""
        if self.ack_mode == AckMode.CUMULATIVE:
            # Remove all messages <= ack_seq from replay buffer
            to_remove = [seq for seq in self.replay_buffer.keys() if seq <= ack_seq]
            for seq in to_remove:
                self.replay_buffer.pop(seq, None)
            self.last_ack_seq = max(self.last_ack_seq, ack_seq)
        else:
            # Per-message mode: only remove the specific message
            self.replay_buffer.pop(ack_seq, None)
            if ack_seq > self.last_ack_seq:
                self.last_ack_seq = ack_seq

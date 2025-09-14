"""Unit tests for WebSocket types and envelope schema."""

import time
from datetime import datetime, timezone

from loquilex.api.ws_types import (
    ASRFinalData,
    ASRPartialData,
    AckMode,
    ClientHelloData,
    HeartbeatConfig,
    MessageType,
    MTFinalData,
    ResumeInfo,
    ServerWelcomeData,
    SessionState,
    StatusData,
    WSEnvelope,
)


class TestWSEnvelope:
    """Test WebSocket envelope validation and serialization."""

    def test_minimal_envelope(self):
        """Test minimal envelope creation."""
        envelope = WSEnvelope(t=MessageType.STATUS, data={"stage": "test"})

        assert envelope.v == 1
        assert envelope.t == MessageType.STATUS
        assert envelope.data == {"stage": "test"}
        # Optional fields should be None/default
        assert envelope.sid is None
        assert envelope.seq is None

    def test_full_envelope(self):
        """Test envelope with all fields populated."""
        envelope = WSEnvelope(
            v=1,
            t=MessageType.ASR_FINAL,
            sid="sess_123",
            id="msg_abc",
            seq=42,
            corr="msg_prev",
            t_wall="2025-01-01T00:00:00Z",
            t_mono_ms=1500,
            data={"text": "hello world", "segment_id": "seg1"},
        )

        assert envelope.v == 1
        assert envelope.t == MessageType.ASR_FINAL
        assert envelope.sid == "sess_123"
        assert envelope.id == "msg_abc"
        assert envelope.seq == 42
        assert envelope.corr == "msg_prev"
        assert envelope.t_wall == "2025-01-01T00:00:00Z"
        assert envelope.t_mono_ms == 1500
        assert envelope.data["text"] == "hello world"

    def test_auto_message_id_generation(self):
        """Test that message ID is auto-generated when session ID is provided."""
        envelope = WSEnvelope(t=MessageType.STATUS, sid="sess_123", data={})

        # ID should be auto-generated
        assert envelope.id is not None
        assert envelope.id.startswith("msg_")
        assert len(envelope.id) == 12  # "msg_" + 8 hex chars

    def test_no_auto_id_without_sid(self):
        """Test that message ID is not auto-generated without session ID."""
        envelope = WSEnvelope(t=MessageType.STATUS, data={})

        # ID should remain None when no session ID
        assert envelope.id is None

    def test_json_serialization(self):
        """Test envelope can be serialized to/from JSON."""
        original = WSEnvelope(
            t=MessageType.ASR_PARTIAL,
            sid="sess_test",
            seq=1,
            data={"text": "hello", "segment_id": "seg1"},
        )

        # Serialize to JSON
        json_str = original.model_dump_json()

        # Deserialize back
        loaded = WSEnvelope.model_validate_json(json_str)

        assert loaded.t == original.t
        assert loaded.sid == original.sid
        assert loaded.seq == original.seq
        assert loaded.data == original.data


class TestDomainEventData:
    """Test domain event payload validation."""

    def test_asr_partial_data(self):
        """Test ASR partial data validation."""
        data = ASRPartialData(text="hello wo", segment_id="seg1")

        assert data.text == "hello wo"
        assert data.final is False  # Default
        assert data.segment_id == "seg1"

    def test_asr_final_data(self):
        """Test ASR final data validation."""
        data = ASRFinalData(text="hello world", segment_id="seg1", start_ms=0, end_ms=1500)

        assert data.text == "hello world"
        assert data.segment_id == "seg1"
        assert data.start_ms == 0
        assert data.end_ms == 1500

    def test_mt_final_data(self):
        """Test machine translation final data."""
        data = MTFinalData(text="你好世界", src="en", tgt="zh-Hans")

        assert data.text == "你好世界"
        assert data.src == "en"
        assert data.tgt == "zh-Hans"

    def test_status_data(self):
        """Test status data validation."""
        data = StatusData(stage="running", detail="Processing audio")

        assert data.stage == "running"
        assert data.detail == "Processing audio"


class TestControlMessages:
    """Test control message payloads."""

    def test_client_hello(self):
        """Test client hello data."""
        hello = ClientHelloData(
            agent="loquilex-ui/0.3.0",
            accept=["asr.partial", "asr.final", "mt.final"],
            ack_mode=AckMode.CUMULATIVE,
            max_in_flight=16,
        )

        assert hello.agent == "loquilex-ui/0.3.0"
        assert len(hello.accept) == 3
        assert hello.ack_mode == AckMode.CUMULATIVE
        assert hello.max_in_flight == 16
        assert hello.resume is None

    def test_client_hello_with_resume(self):
        """Test client hello with resume info."""
        resume_info = ResumeInfo(sid="sess_old", last_seq=42)
        hello = ClientHelloData(agent="test-client", resume=resume_info)

        assert hello.resume is not None
        assert hello.resume.sid == "sess_old"
        assert hello.resume.last_seq == 42

    def test_server_welcome(self):
        """Test server welcome data structure."""
        from loquilex.api.ws_types import ResumeWindow, ServerLimits

        welcome = ServerWelcomeData(
            hb=HeartbeatConfig(interval_ms=5000, timeout_ms=15000),
            resume_window=ResumeWindow(seconds=600, token="resume_token"),
            limits=ServerLimits(max_in_flight=32, max_msg_bytes=65536),
        )

        assert welcome.hb.interval_ms == 5000
        assert welcome.hb.timeout_ms == 15000
        assert welcome.resume_window.seconds == 600
        assert welcome.limits.max_in_flight == 32


class TestSessionState:
    """Test session state management."""

    def test_session_initialization(self):
        """Test session state initialization."""
        t0 = time.monotonic()
        state = SessionState(
            sid="test_session", t0_mono=t0, t0_wall=datetime.now(timezone.utc).isoformat()
        )

        assert state.sid == "test_session"
        assert state.t0_mono == t0
        assert state.seq == 0
        assert state.ack_mode == AckMode.CUMULATIVE
        assert state.max_in_flight == 32
        assert len(state.replay_buffer) == 0

    def test_sequence_generation(self):
        """Test sequence number generation."""
        state = SessionState(
            sid="test", t0_mono=time.monotonic(), t0_wall=datetime.now(timezone.utc).isoformat()
        )

        assert state.next_seq() == 1
        assert state.next_seq() == 2
        assert state.next_seq() == 3
        assert state.seq == 3

    def test_monotonic_time_calculation(self):
        """Test monotonic time calculation."""
        t0 = time.monotonic()
        state = SessionState(sid="test", t0_mono=t0, t0_wall=datetime.now(timezone.utc).isoformat())

        # Get monotonic time
        mono_ms = state.get_monotonic_ms()

        # Should be >= 0 and reasonable
        assert mono_ms >= 0
        assert mono_ms < 1000  # Less than 1 second since creation

    def test_flow_control_limits(self):
        """Test flow control checking."""
        state = SessionState(
            sid="test", t0_mono=time.monotonic(), t0_wall=datetime.now(timezone.utc).isoformat()
        )
        state.max_in_flight = 3

        # Initially can send
        assert state.can_send_message() is True

        # After sending 3 messages without acks
        state.seq = 3
        state.last_ack_seq = 0
        assert state.can_send_message() is False

        # After ack, can send again
        state.last_ack_seq = 1
        assert state.can_send_message() is True

    def test_replay_buffer_management(self):
        """Test replay buffer operations."""
        state = SessionState(
            sid="test", t0_mono=time.monotonic(), t0_wall=datetime.now(timezone.utc).isoformat()
        )

        # Add messages to replay buffer
        envelope1 = WSEnvelope(t=MessageType.ASR_PARTIAL, seq=1, data={"text": "hello"})
        envelope2 = WSEnvelope(t=MessageType.ASR_FINAL, seq=2, data={"text": "hello world"})

        state.add_to_replay_buffer(envelope1)
        state.add_to_replay_buffer(envelope2)

        assert len(state.replay_buffer) == 2
        assert state.replay_buffer[1] == envelope1
        assert state.replay_buffer[2] == envelope2

    def test_replay_message_retrieval(self):
        """Test getting messages for replay."""
        state = SessionState(
            sid="test", t0_mono=time.monotonic(), t0_wall=datetime.now(timezone.utc).isoformat()
        )

        # Add messages
        for i in range(1, 6):
            envelope = WSEnvelope(t=MessageType.ASR_PARTIAL, seq=i, data={"text": f"msg{i}"})
            state.add_to_replay_buffer(envelope)

        # Get messages after seq 2
        replay_msgs = state.get_replay_messages(last_seq=2)

        assert len(replay_msgs) == 3  # seq 3, 4, 5
        assert replay_msgs[0].seq == 3
        assert replay_msgs[1].seq == 4
        assert replay_msgs[2].seq == 5

    def test_cumulative_ack_processing(self):
        """Test cumulative acknowledgement processing."""
        state = SessionState(
            sid="test", t0_mono=time.monotonic(), t0_wall=datetime.now(timezone.utc).isoformat()
        )
        state.ack_mode = AckMode.CUMULATIVE

        # Add messages to replay buffer
        for i in range(1, 6):
            envelope = WSEnvelope(t=MessageType.ASR_PARTIAL, seq=i, data={"text": f"msg{i}"})
            state.add_to_replay_buffer(envelope)

        # Process cumulative ack for seq 3
        state.process_ack(3)

        # Messages 1, 2, 3 should be removed from replay buffer
        assert 1 not in state.replay_buffer
        assert 2 not in state.replay_buffer
        assert 3 not in state.replay_buffer
        assert 4 in state.replay_buffer
        assert 5 in state.replay_buffer
        assert state.last_ack_seq == 3

    def test_per_message_ack_processing(self):
        """Test per-message acknowledgement processing."""
        state = SessionState(
            sid="test", t0_mono=time.monotonic(), t0_wall=datetime.now(timezone.utc).isoformat()
        )
        state.ack_mode = AckMode.PER_MESSAGE

        # Add messages to replay buffer
        for i in range(1, 6):
            envelope = WSEnvelope(t=MessageType.ASR_PARTIAL, seq=i, data={"text": f"msg{i}"})
            state.add_to_replay_buffer(envelope)

        # Process per-message ack for seq 3
        state.process_ack(3)

        # Only message 3 should be removed
        assert 1 in state.replay_buffer
        assert 2 in state.replay_buffer
        assert 3 not in state.replay_buffer
        assert 4 in state.replay_buffer
        assert 5 in state.replay_buffer
        assert state.last_ack_seq == 3

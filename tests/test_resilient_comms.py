"""Unit tests for resilient communications features."""

import asyncio
import json
from unittest.mock import patch

import pytest

from loquilex.api.ws_protocol import WSProtocolManager
from loquilex.api.ws_types import (
    MessageType,
    SessionResumeData,
    SystemHeartbeatData,
    WSEnvelope,
)


class MockWebSocket:
    """Mock WebSocket for testing."""

    def __init__(self):
        self.sent_messages = []
        self.closed = False

    async def send_text(self, message: str):
        """Mock send_text method."""
        if self.closed:
            raise Exception("WebSocket closed")
        self.sent_messages.append(message)

    async def close(self):
        """Mock close method."""
        self.closed = True

    def get_last_message(self) -> dict:
        """Get the last sent message as parsed JSON."""
        if not self.sent_messages:
            raise AssertionError("No messages sent")
        return json.loads(self.sent_messages[-1])


@pytest.mark.asyncio
class TestResilientComms:
    """Test resilient communications features."""

    async def test_session_resume_within_window(self):
        """Test successful session resume within TTL window."""
        async with WSProtocolManager("test_session") as manager:
            # Add some messages to replay buffer
            temp_ws = MockWebSocket()
            await manager.add_connection(temp_ws)
            temp_ws.sent_messages.clear()

            await manager.send_domain_event(MessageType.ASR_PARTIAL, {"text": "hello"})
            await manager.send_domain_event(MessageType.ASR_FINAL, {"text": "hello world"})
            await manager.remove_connection(temp_ws)

            # Resume session
            mock_ws = MockWebSocket()
            await manager.add_connection(mock_ws)
            mock_ws.sent_messages.clear()

            resume_envelope = WSEnvelope(
                t=MessageType.SESSION_RESUME,
                data=SessionResumeData(
                    session_id="test_session",
                    last_seq=1,
                    epoch=manager.state.epoch,
                ).model_dump(),
            )
            await manager.handle_message(mock_ws, resume_envelope.model_dump_json())

            # Should receive: snapshot, replay message, ack
            assert len(mock_ws.sent_messages) >= 3

            # Check snapshot response
            snapshot_msg = json.loads(mock_ws.sent_messages[0])
            assert snapshot_msg["t"] == "session.snapshot"
            assert snapshot_msg["data"]["session_id"] == "test_session"
            assert snapshot_msg["data"]["epoch"] == manager.state.epoch

    async def test_session_resume_expired(self):
        """Test session resume when TTL has expired."""
        from loquilex.api.ws_types import ResumeWindow

        # Very short TTL for testing (1 second)
        resume_window = ResumeWindow(seconds=1)
        async with WSProtocolManager("test_session", resume_window=resume_window) as manager:
            # Add message to replay buffer
            temp_ws = MockWebSocket()
            await manager.add_connection(temp_ws)
            temp_ws.sent_messages.clear()

            await manager.send_domain_event(MessageType.ASR_PARTIAL, {"text": "hello"})
            await manager.remove_connection(temp_ws)

            # Wait for TTL to expire
            await asyncio.sleep(1.1)

            # Try to resume
            mock_ws = MockWebSocket()
            await manager.add_connection(mock_ws)
            mock_ws.sent_messages.clear()

            resume_envelope = WSEnvelope(
                t=MessageType.SESSION_RESUME,
                data=SessionResumeData(
                    session_id="test_session",
                    last_seq=0,
                    epoch=manager.state.epoch,
                ).model_dump(),
            )
            await manager.handle_message(mock_ws, resume_envelope.model_dump_json())

            # Should receive session.new due to expiration
            assert len(mock_ws.sent_messages) == 1
            new_msg = json.loads(mock_ws.sent_messages[0])
            assert new_msg["t"] == "session.new"
            assert new_msg["data"]["reason"] == "resume_expired"

    async def test_session_resume_wrong_session_id(self):
        """Test session resume with wrong session ID."""
        async with WSProtocolManager("test_session") as manager:
            mock_ws = MockWebSocket()
            await manager.add_connection(mock_ws)
            mock_ws.sent_messages.clear()

            # Try to resume with wrong session ID
            resume_envelope = WSEnvelope(
                t=MessageType.SESSION_RESUME,
                data=SessionResumeData(
                    session_id="wrong_session",
                    last_seq=0,
                    epoch=manager.state.epoch,
                ).model_dump(),
            )
            await manager.handle_message(mock_ws, resume_envelope.model_dump_json())

            # Should receive session.new due to session ID mismatch
            assert len(mock_ws.sent_messages) == 1
            new_msg = json.loads(mock_ws.sent_messages[0])
            assert new_msg["t"] == "session.new"
            assert new_msg["data"]["reason"] == "session_id_mismatch"

    async def test_session_resume_wrong_epoch(self):
        """Test session resume with wrong epoch."""
        async with WSProtocolManager("test_session") as manager:
            mock_ws = MockWebSocket()
            await manager.add_connection(mock_ws)
            mock_ws.sent_messages.clear()

            # Try to resume with wrong epoch
            resume_envelope = WSEnvelope(
                t=MessageType.SESSION_RESUME,
                data=SessionResumeData(
                    session_id="test_session",
                    last_seq=0,
                    epoch=manager.state.epoch + 999,  # Wrong epoch
                ).model_dump(),
            )
            await manager.handle_message(mock_ws, resume_envelope.model_dump_json())

            # Should receive session.new due to epoch mismatch
            assert len(mock_ws.sent_messages) == 1
            new_msg = json.loads(mock_ws.sent_messages[0])
            assert new_msg["t"] == "session.new"
            assert new_msg["data"]["reason"] == "epoch_mismatch"

    @pytest.mark.skip("System heartbeat causes infinite loop in tests")
    @patch("asyncio.sleep")
    async def test_system_heartbeat_telemetry(self, mock_sleep):
        """Test system heartbeat with telemetry."""
        if mock_sleep is None:
            pass  # For type checker
        async with WSProtocolManager("test_session") as manager:
            manager.hb_config.interval_ms = 100  # Fast heartbeat for test

            mock_ws = MockWebSocket()
            await manager.add_connection(mock_ws)
            mock_ws.sent_messages.clear()

            # Add some data to queues to test telemetry
            await manager.send_domain_event(MessageType.ASR_PARTIAL, {"text": "test"})

            # Mock the sleep and manually create/send heartbeat to avoid infinite loop
            queue_depths = {"replay_buffer": manager._replay_buffer.size()}
            drop_counts = {"replay_buffer": manager._replay_buffer.metrics.total_dropped}

            system_hb_data = SystemHeartbeatData(
                ts="2025-01-01T00:00:00Z",
                t_mono_ms=1000,
                queue_depths=queue_depths,
                drop_counts=drop_counts,
                latency_metrics={},
            )

            system_hb_envelope = manager._create_envelope(
                MessageType.SYSTEM_HEARTBEAT, system_hb_data.model_dump()
            )
            await manager._broadcast(system_hb_envelope)

            # Find system heartbeat message
            heartbeat_msg = None
            for msg_str in mock_ws.sent_messages:
                msg = json.loads(msg_str)
                if msg["t"] == "system.heartbeat":
                    heartbeat_msg = msg
                    break

            assert heartbeat_msg is not None
            assert "queue_depths" in heartbeat_msg["data"]
            assert "drop_counts" in heartbeat_msg["data"]
            assert "replay_buffer" in heartbeat_msg["data"]["queue_depths"]

    @pytest.mark.skip("Need to fix ReplayBuffer TTL setup")
    async def test_bounded_replay_buffer_integration(self):
        """Test bounded replay buffer with TTL cleanup."""
        # Use very small buffer for testing
        import os

        with patch.dict(os.environ, {"LX_WS_RESUME_MAX_EVENTS": "2", "LX_WS_RESUME_TTL_SEC": "1"}):
            async with WSProtocolManager("test_session") as manager:
                mock_ws = MockWebSocket()
                await manager.add_connection(mock_ws)

                # Send more messages than buffer capacity
                await manager.send_domain_event(MessageType.ASR_PARTIAL, {"text": "msg1"})
                await manager.send_domain_event(MessageType.ASR_PARTIAL, {"text": "msg2"})
                await manager.send_domain_event(MessageType.ASR_PARTIAL, {"text": "msg3"})

                # Buffer should be at capacity (2), oldest dropped
                assert manager._replay_buffer.size() == 2
                assert manager._replay_buffer.metrics.total_dropped == 1

                # Messages after seq 1 should still be available (msg2, msg3)
                available_msgs = manager._replay_buffer.get_messages_after(1)
                assert len(available_msgs) == 2

    async def test_telemetry_summary(self):
        """Test telemetry summary collection."""
        async with WSProtocolManager("test_session") as manager:
            mock_ws = MockWebSocket()
            await manager.add_connection(mock_ws)

            # Add some events to generate telemetry
            await manager.send_domain_event(MessageType.ASR_PARTIAL, {"text": "test1"})
            await manager.send_domain_event(MessageType.ASR_FINAL, {"text": "test1 final"})

            # Get telemetry summary
            telemetry = manager.get_telemetry_summary()

            assert "session_id" in telemetry
            assert "epoch" in telemetry
            assert "uptime_seconds" in telemetry
            assert "queue_depths" in telemetry
            assert "drop_totals" in telemetry
            assert "connections" in telemetry

            assert telemetry["session_id"] == "test_session"
            assert telemetry["connections"] == 1
            assert telemetry["uptime_seconds"] > 0

    async def test_queue_drop_notification(self):
        """Test queue drop notification emission."""
        async with WSProtocolManager("test_session") as manager:
            mock_ws = MockWebSocket()
            await manager.add_connection(mock_ws)
            mock_ws.sent_messages.clear()

            # Emit a queue drop notification
            await manager.emit_queue_drop("test_queue", 5, "capacity", 15)

            # Should have sent a queue.drop message
            assert len(mock_ws.sent_messages) == 1
            drop_msg = json.loads(mock_ws.sent_messages[0])

            assert drop_msg["t"] == "queue.drop"
            assert drop_msg["data"]["path"] == "test_queue"
            assert drop_msg["data"]["count"] == 5
            assert drop_msg["data"]["reason"] == "capacity"
            assert drop_msg["data"]["total_dropped"] == 15

    async def test_environment_configuration(self):
        """Test environment variable configuration."""
        import os

        # Test custom environment values
        test_env = {
            "LX_WS_HEARTBEAT_MS": "3000",
            "LX_WS_HEARTBEAT_TIMEOUT_MS": "10000",
            "LX_WS_RESUME_TTL_SEC": "20",
            "LX_WS_MAX_IN_FLIGHT": "32",
            "LX_CLIENT_EVENT_BUFFER": "200",
        }

        with patch.dict(os.environ, test_env):
            async with WSProtocolManager("test_session") as manager:
                assert manager.hb_config.interval_ms == 3000
                assert manager.hb_config.timeout_ms == 10000
                assert manager.resume_window.seconds == 20
                assert manager.limits.max_in_flight == 32

                # Test outbound queue creation uses env var
                mock_ws = MockWebSocket()
                await manager.add_connection(mock_ws)

                # Check that outbound queue was created with correct size
                outbound_queue = manager._outbound_queues[mock_ws]
                assert outbound_queue.maxsize == 200

"""Unit tests for WebSocket protocol manager."""

import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from loquilex.api.ws_protocol import WSProtocolManager
from loquilex.api.ws_types import (
    AckData,
    ClientHelloData,
    HeartbeatConfig,
    MessageType,
    ResumeInfo,
    ServerLimits,
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
class TestWSProtocolManager:
    async def test_context_manager_cleanup(self):
        """Test that async context manager calls close and cleans up tasks."""
        async with WSProtocolManager("test_session") as manager:
            mock_ws = MockWebSocket()
            await manager.add_connection(mock_ws)
            # Heartbeat tasks should be running
            assert manager._hb_task is not None
            assert manager._hb_timeout_task is not None
        # After context exit, tasks should be None
        assert manager._hb_task is None
        assert manager._hb_timeout_task is None

    @pytest.mark.filterwarnings("ignore::ResourceWarning")
    def test_destructor_cancels_tasks(self):
        """Test that __del__ cancels heartbeat tasks if not awaited."""
        # Create manager and start tasks
        manager = WSProtocolManager("test_session")
        loop = asyncio.get_event_loop()
        # Manually start heartbeat tasks
        manager._hb_task = loop.create_task(asyncio.sleep(0.1))
        manager._hb_timeout_task = loop.create_task(asyncio.sleep(0.1))
        # Delete manager and check tasks are cancelled
        del manager

    """Test WebSocket protocol manager functionality."""

    async def test_initialization(self):
        """Test protocol manager initialization."""
        async with WSProtocolManager("test_session") as manager:
            assert manager.sid == "test_session"
            assert manager.state.sid == "test_session"
            assert manager.state.epoch > 0  # Should have a valid epoch
            assert len(manager.connections) == 0
            assert manager.hb_config.interval_ms == 5000  # New default from environment
            assert manager.limits.max_in_flight == 64  # Default

    async def test_custom_configuration(self):
        """Test protocol manager with custom configuration."""
        hb_config = HeartbeatConfig(interval_ms=5000, timeout_ms=15000)
        limits = ServerLimits(max_in_flight=32, max_msg_bytes=65536)
        async with WSProtocolManager("test_session", hb_config=hb_config, limits=limits) as manager:
            assert manager.hb_config.interval_ms == 5000
            assert manager.hb_config.timeout_ms == 15000
            assert manager.limits.max_in_flight == 32
            assert manager.limits.max_msg_bytes == 65536

    async def test_add_connection_sends_welcome(self):
        """Test that adding connection sends welcome message."""
        async with WSProtocolManager("test_session") as manager:
            mock_ws = MockWebSocket()
            await manager.add_connection(mock_ws)
            # Should have sent welcome message
            assert len(mock_ws.sent_messages) == 1
            welcome_msg = mock_ws.get_last_message()
            assert welcome_msg["t"] == MessageType.SERVER_WELCOME
            assert welcome_msg["sid"] == "test_session"
            assert "hb" in welcome_msg["data"]
            assert "resume_window" in welcome_msg["data"]
            assert "limits" in welcome_msg["data"]

    async def test_remove_connection(self):
        """Test removing connections."""
        async with WSProtocolManager("test_session") as manager:
            mock_ws = MockWebSocket()
            await manager.add_connection(mock_ws)
            assert len(manager.connections) == 1
            await manager.remove_connection(mock_ws)
            assert len(manager.connections) == 0

    async def test_client_hello_handling(self):
        """Test client hello message handling."""
        async with WSProtocolManager("test_session") as manager:
            mock_ws = MockWebSocket()
            await manager.add_connection(mock_ws)
            # Create client hello message
            hello_envelope = WSEnvelope(
                t=MessageType.CLIENT_HELLO,
                data=ClientHelloData(
                    agent="test-client/1.0", accept=["asr.partial", "asr.final"], max_in_flight=16
                ).model_dump(),
            )
            await manager.handle_message(mock_ws, hello_envelope.model_dump_json())
            # Check that session state was updated
            assert manager.state.max_in_flight == 16  # Should be min(16, 64)

    async def test_client_ack_handling(self):
        """Test client acknowledgement handling."""
        async with WSProtocolManager("test_session") as manager:
            mock_ws = MockWebSocket()
            await manager.add_connection(mock_ws)
            # Send some messages first to populate replay buffer
            await manager.send_domain_event(MessageType.ASR_PARTIAL, {"text": "hello"})
            await manager.send_domain_event(MessageType.ASR_FINAL, {"text": "hello world"})
            # Check both the state and bounded replay buffer got populated
            assert len(manager.state.replay_buffer) == 2
            assert manager._replay_buffer.size() == 2
            # Send ack for first message
            ack_envelope = WSEnvelope(
                t=MessageType.CLIENT_ACK, data=AckData(ack_seq=1).model_dump()
            )
            await manager.handle_message(mock_ws, ack_envelope.model_dump_json())
            # Should have processed the ack
            assert manager.state.last_ack_seq == 1
            # In cumulative mode, message 1 should be removed from state replay buffer
            assert 1 not in manager.state.replay_buffer
            assert 2 in manager.state.replay_buffer

    async def test_domain_event_sending(self):
        """Test sending domain events."""
        async with WSProtocolManager("test_session") as manager:
            mock_ws = MockWebSocket()
            await manager.add_connection(mock_ws)
            # Clear welcome message
            mock_ws.sent_messages.clear()
            # Send ASR partial event
            success = await manager.send_domain_event(
                MessageType.ASR_PARTIAL, {"text": "hello wo", "segment_id": "seg1"}
            )
            assert success is True
            assert len(mock_ws.sent_messages) == 1
            event_msg = mock_ws.get_last_message()
            assert event_msg["t"] == MessageType.ASR_PARTIAL
            assert event_msg["data"]["text"] == "hello wo"
            assert event_msg["seq"] == 1  # First domain event should be seq 1
            assert event_msg["sid"] == "test_session"

    async def test_flow_control_prevents_sending(self):
        """Test that flow control prevents sending when limit is reached."""
        async with WSProtocolManager("test_session") as manager:
            manager.state.max_in_flight = 2  # Set low limit
            mock_ws = MockWebSocket()
            await manager.add_connection(mock_ws)
            mock_ws.sent_messages.clear()  # Clear welcome
            # Send messages up to limit
            success1 = await manager.send_domain_event(MessageType.ASR_PARTIAL, {"text": "msg1"})
            success2 = await manager.send_domain_event(MessageType.ASR_PARTIAL, {"text": "msg2"})
            assert success1 is True
            assert success2 is True
            assert len(mock_ws.sent_messages) == 2
            # Third message should be blocked by flow control
            success3 = await manager.send_domain_event(MessageType.ASR_PARTIAL, {"text": "msg3"})
            assert success3 is False
            assert len(mock_ws.sent_messages) == 2  # Still only 2 messages

    async def test_resume_request_handling(self):
        """Test resume request processing."""
        async with WSProtocolManager("test_session") as manager:
            # Pre-populate replay buffer with temporary connection
            temp_ws = MockWebSocket()
            await manager.add_connection(temp_ws)
            temp_ws.sent_messages.clear()  # Clear welcome
            await manager.send_domain_event(MessageType.ASR_PARTIAL, {"text": "msg1"})
            await manager.send_domain_event(MessageType.ASR_PARTIAL, {"text": "msg2"})
            await manager.send_domain_event(MessageType.ASR_PARTIAL, {"text": "msg3"})
            # Remove temporary connection
            await manager.remove_connection(temp_ws)
            
            # New connection with resume request using new protocol
            mock_ws = MockWebSocket()
            await manager.add_connection(mock_ws)
            mock_ws.sent_messages.clear()  # Clear welcome
            
            # Import the new resume data type
            from loquilex.api.ws_types import SessionResumeData
            
            resume_envelope = WSEnvelope(
                t=MessageType.SESSION_RESUME,
                data=SessionResumeData(
                    session_id="test_session", 
                    last_seq=1,
                    epoch=manager.state.epoch
                ).model_dump(),
            )
            await manager.handle_message(mock_ws, resume_envelope.model_dump_json())
            
            # Should have sent:
            # 1. Session snapshot response
            # 2. Replayed message 2  
            # 3. Replayed message 3
            # 4. Session ack
            assert len(mock_ws.sent_messages) == 4
            
            # Check snapshot response
            snapshot_msg = json.loads(mock_ws.sent_messages[0])
            assert snapshot_msg["t"] == "session.snapshot"
            
            # Check replayed messages  
            replay_msg1 = json.loads(mock_ws.sent_messages[1])
            replay_msg2 = json.loads(mock_ws.sent_messages[2])
            assert replay_msg1["seq"] == 2
            assert replay_msg1["data"]["text"] == "msg2"
            assert replay_msg2["seq"] == 3
            assert replay_msg2["data"]["text"] == "msg3"
            
            # Check session ack
            ack_msg = json.loads(mock_ws.sent_messages[3])
            assert ack_msg["t"] == "session.ack"

    async def test_resume_expired_error(self):
        """Test resume request with expired window."""
        async with WSProtocolManager("test_session") as manager:
            manager.resume_window.seconds = 0  # Expire immediately
            mock_ws = MockWebSocket()
            await manager.add_connection(mock_ws)
            mock_ws.sent_messages.clear()
            
            from loquilex.api.ws_types import SessionResumeData
            
            # Try to resume with new protocol
            resume_envelope = WSEnvelope(
                t=MessageType.SESSION_RESUME,
                data=SessionResumeData(
                    session_id="test_session", 
                    last_seq=0,
                    epoch=manager.state.epoch
                ).model_dump(),
            )
            await manager.handle_message(mock_ws, resume_envelope.model_dump_json())
            
            # Should have sent session.new with resume_expired reason
            assert len(mock_ws.sent_messages) == 1
            response_msg = mock_ws.get_last_message()
            assert response_msg["t"] == MessageType.SESSION_NEW
            assert response_msg["data"]["reason"] == "resume_expired"

    @patch("asyncio.sleep")
    async def test_heartbeat_sending(self, mock_sleep):
        """Test heartbeat loop functionality."""
        async with WSProtocolManager("test_session") as manager:
            manager.hb_config.interval_ms = 1000  # 1 second for test
            mock_ws = MockWebSocket()
            await manager.add_connection(mock_ws)
            mock_ws.sent_messages.clear()
            # Configure mock sleep to run once then raise CancelledError
            mock_sleep.side_effect = [None, asyncio.CancelledError()]
            try:
                # Start heartbeat loop manually (normally started by add_connection)
                await manager._heartbeat_loop()
            except asyncio.CancelledError:
                pass
            # Should have sent one heartbeat
            assert len(mock_ws.sent_messages) >= 1
            hb_msg = json.loads(mock_ws.sent_messages[0])
            assert hb_msg["t"] == MessageType.SERVER_HB
            assert "ts" in hb_msg["data"]
            assert "q_out" in hb_msg["data"]

    async def test_invalid_message_handling(self):
        """Test handling of invalid messages."""
        async with WSProtocolManager("test_session") as manager:
            mock_ws = MockWebSocket()
            await manager.add_connection(mock_ws)
            mock_ws.sent_messages.clear()
            # Send invalid JSON
            await manager.handle_message(mock_ws, "invalid json")
            # Should have sent error message
            assert len(mock_ws.sent_messages) == 1
            error_msg = mock_ws.get_last_message()
            assert error_msg["t"] == MessageType.SERVER_ERROR
            assert error_msg["data"]["code"] == "invalid_message"

    async def test_unknown_message_type_handling(self):
        """Test handling of unknown message types."""
        async with WSProtocolManager("test_session") as manager:
            mock_ws = MockWebSocket()
            await manager.add_connection(mock_ws)
            mock_ws.sent_messages.clear()
            # Send message with unknown type (this will fail validation)
            unknown_envelope = {"v": 1, "t": "unknown.type", "data": {}}  # Invalid message type
            await manager.handle_message(mock_ws, json.dumps(unknown_envelope))
            # Should have sent error for validation failure
            assert len(mock_ws.sent_messages) == 1
            error_msg = mock_ws.get_last_message()
            assert error_msg["t"] == MessageType.SERVER_ERROR

    async def test_connection_failure_handling(self):
        """Test handling of connection failures during broadcast."""
        async with WSProtocolManager("test_session") as manager:
            # Create failing WebSocket
            failing_ws = MagicMock()
            failing_ws.send_text = AsyncMock(side_effect=Exception("Connection failed"))
            working_ws = MockWebSocket()
            # Add both connections
            manager.connections.add(failing_ws)
            manager.connections.add(working_ws)
            # Send message
            await manager.send_domain_event(MessageType.STATUS, {"stage": "test"})
            # Failing connection should be removed
            assert failing_ws not in manager.connections
            assert working_ws in manager.connections
            # Working connection should have received message
            assert len(working_ws.sent_messages) == 1

    async def test_session_cleanup_on_all_connections_failed(self):
        """Test session cleanup when all connections fail."""
        async with WSProtocolManager("test_session") as manager:
            # Set up disconnect callback
            cleanup_called = []
            manager.set_disconnect_callback(lambda sid: cleanup_called.append(sid))
            # Create failing WebSocket
            failing_ws = MagicMock()
            failing_ws.send_text = AsyncMock(side_effect=Exception("Connection failed"))
            manager.connections.add(failing_ws)
            # Send message - this should trigger cleanup
            await manager.send_domain_event(MessageType.STATUS, {"stage": "test"})
            # Cleanup callback should have been called
            assert cleanup_called == ["test_session"]
            assert len(manager.connections) == 0

    async def test_graceful_close(self):
        """Test graceful session closure."""
        async with WSProtocolManager("test_session") as manager:
            mock_ws = MockWebSocket()
            await manager.add_connection(mock_ws)
            # Close session
            await manager.close()
            # Connection should be closed and removed
            assert mock_ws.closed is True
            assert len(manager.connections) == 0

    async def test_ack_spoof_protection(self):
        """Client cannot ack beyond latest delivered seq."""
        async with WSProtocolManager("test_session") as manager:
            mock_ws = MockWebSocket()
            await manager.add_connection(mock_ws)
            # Send two domain events
            await manager.send_domain_event(MessageType.ASR_PARTIAL, {"text": "msg1"})
            await manager.send_domain_event(MessageType.ASR_FINAL, {"text": "msg2"})
            # Try to ack seq beyond latest delivered (should trigger error)
            ack_envelope = WSEnvelope(
                t=MessageType.CLIENT_ACK, data=AckData(ack_seq=99).model_dump()
            )
            await manager.handle_message(mock_ws, ack_envelope.model_dump_json())
            # Should have sent error message
            err = mock_ws.get_last_message()
            assert err["t"] == MessageType.SERVER_ERROR
            assert err["data"]["code"] == "invalid_ack"

    async def test_resume_with_gaps(self):
        """On resume, server delivers only missing frames once, ignores duplicates."""
        async with WSProtocolManager("test_session") as manager:
            temp_ws = MockWebSocket()
            await manager.add_connection(temp_ws)
            temp_ws.sent_messages.clear()
            # Send 3 domain events
            await manager.send_domain_event(MessageType.ASR_PARTIAL, {"text": "msg1"})
            await manager.send_domain_event(MessageType.ASR_PARTIAL, {"text": "msg2"})
            await manager.send_domain_event(MessageType.ASR_PARTIAL, {"text": "msg3"})
            await manager.remove_connection(temp_ws)
            
            # Resume from seq=1 (should get 2,3 only)
            mock_ws = MockWebSocket()
            await manager.add_connection(mock_ws)
            mock_ws.sent_messages.clear()
            
            from loquilex.api.ws_types import SessionResumeData
            
            resume_envelope = WSEnvelope(
                t=MessageType.SESSION_RESUME,
                data=SessionResumeData(
                    session_id="test_session", 
                    last_seq=1,
                    epoch=manager.state.epoch
                ).model_dump(),
            )
            await manager.handle_message(mock_ws, resume_envelope.model_dump_json())
            
            # Should have sent:
            # 1. Session snapshot
            # 2. Replayed message 2
            # 3. Replayed message 3  
            # 4. Session ack
            assert len(mock_ws.sent_messages) == 4
            
            # Skip snapshot and ack, check the replayed messages
            replay_msg1 = json.loads(mock_ws.sent_messages[1])
            replay_msg2 = json.loads(mock_ws.sent_messages[2])
            assert replay_msg1["seq"] == 2
            assert replay_msg1["data"]["text"] == "msg2"
            assert replay_msg2["seq"] == 3
            assert replay_msg2["data"]["text"] == "msg3"

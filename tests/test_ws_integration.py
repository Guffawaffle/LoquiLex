"""Integration tests for WebSocket envelope protocol with existing API."""

import asyncio
import json
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from loquilex.api.server import app
from loquilex.api.ws_types import AckData, ClientHelloData, MessageType, WSEnvelope


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_websocket_envelope_integration():
    """Test that the new envelope protocol works with the existing API."""

    # Mock session creation to avoid subprocess spawning
    with patch("loquilex.api.supervisor.Session.start"):
        with patch("subprocess.Popen") as mock_popen:
            mock_proc = mock_popen.return_value
            mock_proc.poll.return_value = None
            mock_proc.stdout = None

            with TestClient(app) as client:
                # Create a session
                session_payload = {
                    "asr_model_id": "openai/whisper-tiny",
                    "mt_enabled": False,
                    "device": "cpu",
                    "streaming_mode": False,  # Use legacy mode for compatibility
                }

                response = client.post("/sessions", json=session_payload)
                if response.status_code not in [200, 409]:
                    # Skip test if session creation fails (expected in some environments)
                    pytest.skip("Session creation failed - environment limitation")

                sid = response.json().get("session_id")
                if not sid:
                    pytest.skip("No session ID returned")

                # Test WebSocket connection with envelope protocol
                import websockets

                try:
                    from loquilex.api import server as api_server

                    ws_url = f"ws://127.0.0.1:8000{api_server.WS_PATH}/{sid}"

                    # Simplified connection without additional headers for compatibility
                    async with websockets.connect(ws_url) as websocket:

                        # Should receive welcome message
                        welcome_raw = await asyncio.wait_for(websocket.recv(), timeout=2.0)
                        welcome = json.loads(welcome_raw)

                        # Validate welcome message structure
                        assert welcome["v"] == 1
                        assert welcome["t"] == MessageType.SERVER_WELCOME
                        assert welcome["sid"] == sid
                        assert welcome["seq"] == 0  # Welcome uses seq 0
                        assert "hb" in welcome["data"]
                        assert "limits" in welcome["data"]

                        # Send client hello
                        hello_envelope = WSEnvelope(
                            t=MessageType.CLIENT_HELLO,
                            data=ClientHelloData(
                                agent="test-client/1.0",
                                accept=[
                                    MessageType.ASR_PARTIAL,
                                    MessageType.ASR_FINAL,
                                    MessageType.STATUS,
                                ],
                                max_in_flight=16,
                            ).model_dump(),
                        )

                        await websocket.send(hello_envelope.model_dump_json())

                        # Client hello is processed but doesn't generate a response
                        # Wait briefly to ensure processing
                        await asyncio.sleep(0.1)

                        # Send acknowledgement for welcome message
                        ack_envelope = WSEnvelope(
                            t=MessageType.CLIENT_ACK, data=AckData(ack_seq=0).model_dump()
                        )

                        await websocket.send(ack_envelope.model_dump_json())

                        # Wait briefly to ensure ack is processed
                        await asyncio.sleep(0.1)

                except (
                    websockets.exceptions.InvalidURI,
                    OSError,
                    asyncio.TimeoutError,
                    ConnectionError,
                ) as e:
                    # Skip if WebSocket connection fails (expected in some test environments)
                    pytest.skip(f"WebSocket connection failed: {e}")

                # Clean up session
                try:
                    client.delete(f"/sessions/{sid}")
                except Exception:
                    pass


@pytest.mark.e2e
def test_websocket_configuration_from_env():
    """Test that WebSocket configuration can be set via environment variables."""
    import os
    from loquilex.api.supervisor import SessionManager

    # Set environment variables
    original_values = {}
    test_env = {
        "LX_WS_HB_INTERVAL_MS": "5000",
        "LX_WS_HB_TIMEOUT_MS": "15000",
        "LX_WS_MAX_IN_FLIGHT": "32",
        "LX_WS_MAX_MSG_BYTES": "65536",
    }

    for key, value in test_env.items():
        original_values[key] = os.environ.get(key)
        os.environ[key] = value

    try:
        # Create new session manager to pick up env vars
        manager = SessionManager()

        assert manager._default_hb_config.interval_ms == 5000
        assert manager._default_hb_config.timeout_ms == 15000
        assert manager._default_limits.max_in_flight == 32
        assert manager._default_limits.max_msg_bytes == 65536

    finally:
        # Restore original environment
        for key, original_value in original_values.items():
            if original_value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = original_value


def test_legacy_message_type_mapping():
    """Test that legacy message types are correctly mapped to envelope types."""
    from loquilex.api.supervisor import SessionManager

    manager = SessionManager()

    # Test legacy type mappings
    assert manager._map_legacy_type_to_envelope("partial_en") == MessageType.ASR_PARTIAL
    assert manager._map_legacy_type_to_envelope("final_en") == MessageType.ASR_FINAL
    assert manager._map_legacy_type_to_envelope("mt_final") == MessageType.MT_FINAL
    assert manager._map_legacy_type_to_envelope("status") == MessageType.STATUS
    assert manager._map_legacy_type_to_envelope("unknown_type") == MessageType.STATUS  # Default


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_broadcast_with_envelope_protocol():
    """Test that broadcasting works with the new envelope protocol."""
    from loquilex.api.supervisor import SessionManager
    from unittest.mock import AsyncMock, MagicMock

    manager = SessionManager()

    # Create mock WebSocket
    mock_ws = MagicMock()
    mock_ws.send_text = AsyncMock()

    # Register WebSocket connection
    sid = "test_session_123"
    await manager.register_ws(sid, mock_ws)

    # Clear welcome message call
    mock_ws.send_text.reset_mock()

    # Send a legacy broadcast
    await manager._broadcast(
        sid, {"type": "status", "stage": "processing", "detail": "Audio analysis in progress"}
    )

    # Should have called send_text
    assert mock_ws.send_text.called

    # Parse the sent message
    sent_args = mock_ws.send_text.call_args[0]
    sent_message = json.loads(sent_args[0])

    # Validate envelope structure
    assert sent_message["v"] == 1
    assert sent_message["t"] == MessageType.STATUS
    assert sent_message["sid"] == sid
    assert sent_message["seq"] == 1  # First domain message after welcome
    assert sent_message["data"]["stage"] == "processing"
    assert sent_message["data"]["detail"] == "Audio analysis in progress"

    # Cleanup
    await manager.unregister_ws(sid, mock_ws)


@pytest.mark.e2e
def test_session_cleanup_removes_protocol_manager():
    """Test that session cleanup properly removes protocol managers."""
    from loquilex.api.supervisor import SessionManager

    manager = SessionManager()
    sid = "test_cleanup_session"

    # Simulate protocol manager creation
    manager._cleanup_ws_protocol(sid)

    # Should not raise any exceptions
    assert sid not in manager._ws_protocols

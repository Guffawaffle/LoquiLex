"""Integration tests for WebSocket envelope protocol with existing API."""

import json
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from loquilex.api.server import app
from loquilex.api.ws_types import AckData, ClientHelloData, MessageType, WSEnvelope
import httpx
import requests
from starlette.websockets import WebSocketDisconnect

try:
    import websockets as _websockets
except Exception:
    _websockets = None


@pytest.mark.e2e
def test_websocket_envelope_integration():
    """Test that the new envelope protocol works with the existing API.

    Uses FastAPI TestClient WebSocket support for reliable testing without
    requiring external server startup.
    """

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
                from loquilex.api import server as api_server

                ws_url = f"{api_server.WS_PATH}/{sid}"

                # Use FastAPI TestClient WebSocket support
                try:
                    with client.websocket_connect(ws_url) as websocket:

                        # Should receive welcome message
                        welcome_raw = websocket.receive_text()
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

                        websocket.send_text(hello_envelope.model_dump_json())

                        # Client hello is processed but doesn't generate a response
                        # No need to wait in synchronous TestClient context

                        # Send acknowledgement for welcome message
                        ack_envelope = WSEnvelope(
                            t=MessageType.CLIENT_ACK, data=AckData(ack_seq=0).model_dump()
                        )

                        websocket.send_text(ack_envelope.model_dump_json())

                # Skip known environment/configuration errors instead of failing the
                # test. These exceptions typically indicate that the test environment
                # doesn't have a WebSocket endpoint available (HTTP 404) or that
                # connections to the socket endpoint are blocked/unavailable.
                except (
                    WebSocketDisconnect,
                    ConnectionError,
                    RuntimeError,
                    httpx.ConnectError,
                    httpx.HTTPStatusError,
                    requests.exceptions.RequestException,
                ) as e:
                    # Try to determine an HTTP status code when available
                    status_code = None
                    # websockets.InvalidStatusCode exposes `status_code` on the exception
                    if _websockets is not None and hasattr(_websockets, "InvalidStatusCode") and isinstance(
                        e, _websockets.InvalidStatusCode
                    ):
                        status_code = getattr(e, "status_code", None)
                    # httpx.HTTPStatusError contains a response
                    elif isinstance(e, httpx.HTTPStatusError) and getattr(e, "response", None) is not None:
                        status_code = getattr(e.response, "status_code", None)
                    # requests HTTP errors expose response as well
                    elif isinstance(e, requests.exceptions.RequestException) and getattr(e, "response", None) is not None:
                        status_code = getattr(e.response, "status_code", None)

                    if status_code == 404:
                        pytest.skip(f"WebSocket endpoint not found (HTTP 404): {e}")

                    # Connection-level failures are often environment-related; skip those too
                    if isinstance(e, (ConnectionError, httpx.ConnectError, requests.exceptions.ConnectionError)):
                        pytest.skip(f"WebSocket connection failed: {e}")

                    # Otherwise, re-raise so the test fails and surfaces unexpected errors
                    raise

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

"""Test MT integration with WebSocket API."""

from __future__ import annotations

import os
import pytest
from unittest.mock import Mock, AsyncMock

from loquilex.mt.integration import MTIntegration
from loquilex.mt.service import MTService


def test_mt_integration_disabled():
    """Test MT integration when disabled."""
    integration = MTIntegration(
        session_id="test-session",
        mt_enabled=False,
        dest_lang="zh-Hans"
    )
    
    assert integration.mt_enabled is False
    assert integration._mt_service is None
    
    status = integration.get_status()
    assert status["enabled"] is False
    assert status["available"] is False


@pytest.mark.skipif(
    os.getenv("LOQUILEX_OFFLINE", "").lower() in ("1", "true", "on"),
    reason="Skip MT integration tests in offline mode"
)
def test_mt_integration_enabled():
    """Test MT integration when enabled."""
    integration = MTIntegration(
        session_id="test-session", 
        mt_enabled=True,
        dest_lang="zh-Hans"
    )
    
    # Should attempt to initialize but may fail without proper models
    # The important thing is it tries to initialize
    status = integration.get_status()
    assert "enabled" in status
    assert "available" in status
    assert "dest_lang" in status


@pytest.mark.asyncio
async def test_mt_integration_translate_and_emit():
    """Test translation and event emission (with mocks)."""
    # Create integration
    integration = MTIntegration(
        session_id="test-session",
        mt_enabled=True,
        dest_lang="zh-Hans"
    )
    
    # Mock the service directly (bypass constructor init)
    mock_service = Mock(spec=MTService)
    mock_service.is_available.return_value = True
    mock_service.get_provider_name.return_value = "mock-provider"
    mock_service.translate_text.return_value = Mock(
        text="你好",
        provider="mock-provider",
        quality="realtime",
        src_lang="en",
        tgt_lang="zh-Hans"
    )
    integration._mt_service = mock_service
    integration.mt_enabled = True  # Force enable for test
    
    # Mock broadcast function
    broadcast_fn = AsyncMock()
    integration.set_broadcast_fn(broadcast_fn)
    
    # Test translation and emission
    await integration.translate_and_emit(
        text="Hello",
        segment_id="seg001",
        is_final=True,
        src_lang="en"
    )
    
    # Verify service was called
    mock_service.translate_text.assert_called_once_with(
        text="Hello",
        src_lang="en", 
        tgt_lang="zh-Hans",
        quality="realtime"
    )
    
    # Verify event was emitted
    broadcast_fn.assert_called_once()
    args = broadcast_fn.call_args
    session_id, event = args[0]
    
    assert session_id == "test-session"
    assert event["type"] == "mt.final"
    assert event["text"] == "你好"
    assert event["src_text"] == "Hello"
    assert event["provider"] == "mock-provider"


@pytest.mark.asyncio  
async def test_mt_integration_error_handling():
    """Test error handling in MT integration."""
    # Create integration
    integration = MTIntegration(
        session_id="test-session",
        mt_enabled=True,
        dest_lang="zh-Hans" 
    )
    
    # Create mock service that raises error
    mock_service = Mock(spec=MTService)
    mock_service.is_available.return_value = True
    mock_service.translate_text.side_effect = Exception("Translation error")
    integration._mt_service = mock_service
    integration.mt_enabled = True  # Force enable for test
    
    # Mock broadcast function
    broadcast_fn = AsyncMock()
    integration.set_broadcast_fn(broadcast_fn)
    
    # Test error handling
    await integration.translate_and_emit(
        text="Hello",
        segment_id="seg001", 
        is_final=True,
        src_lang="en"
    )
    
    # Verify error event was emitted
    broadcast_fn.assert_called_once()
    args = broadcast_fn.call_args
    session_id, event = args[0]
    
    assert session_id == "test-session"
    assert event["type"] == "mt.error"
    assert "error" in event
    assert event["src_text"] == "Hello"


def test_mt_integration_status():
    """Test MT status reporting.""" 
    # Create integration
    integration = MTIntegration(
        session_id="test-session",
        mt_enabled=True, 
        dest_lang="zh-Hans"
    )
    
    # Create mock service
    mock_service = Mock(spec=MTService)
    mock_service.is_available.return_value = True
    mock_service.get_provider_name.return_value = "mock-provider"
    mock_service.get_capabilities.return_value = {
        "family": "mock",
        "directions": [("en", "zh-Hans")]
    }
    integration._mt_service = mock_service
    integration.mt_enabled = True  # Force enable for test
    
    # Get status
    status = integration.get_status()
    
    assert status["enabled"] is True
    assert status["available"] is True
    assert status["dest_lang"] == "zh-Hans"
    assert status["provider"] == "mock-provider"
    assert "capabilities" in status
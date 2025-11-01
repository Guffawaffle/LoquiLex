"""Tests for the /health endpoint.

Validates health check endpoint requirements:
- Returns correct JSON structure
- Responds with HTTP 200 OK
- No authentication required
- Fast response time (< 100ms)
- Includes version and timestamp
"""

import time
from datetime import datetime

import pytest
from fastapi.testclient import TestClient

from loquilex.api.server import app
from loquilex import __version__


def test_health_endpoint_structure():
    """Test that /health returns correct JSON structure."""
    with TestClient(app) as client:
        response = client.get("/health")
        assert response.status_code == 200

        data = response.json()
        assert "status" in data
        assert "version" in data
        assert "timestamp" in data

        assert data["status"] == "ok"
        assert data["version"] == __version__
        assert isinstance(data["timestamp"], str)


def test_health_endpoint_timestamp_format():
    """Test that timestamp is in valid ISO8601 format."""
    with TestClient(app) as client:
        response = client.get("/health")
        assert response.status_code == 200

        data = response.json()
        timestamp_str = data["timestamp"]

        # Validate ISO8601 format by parsing it
        try:
            parsed = datetime.fromisoformat(timestamp_str.replace("Z", "+00:00"))
            assert parsed is not None
        except ValueError:
            pytest.fail(f"Timestamp is not valid ISO8601 format: {timestamp_str}")


def test_health_endpoint_response_time():
    """Test that /health responds quickly (< 100ms)."""
    with TestClient(app) as client:
        start = time.perf_counter()
        response = client.get("/health")
        elapsed_ms = (time.perf_counter() - start) * 1000

        assert response.status_code == 200
        # Allow some margin for test overhead, but should be well under 100ms
        assert elapsed_ms < 100, f"Response took {elapsed_ms:.2f}ms, expected < 100ms"


def test_health_endpoint_no_auth_required():
    """Test that /health does not require authentication."""
    with TestClient(app) as client:
        # Request without any authentication headers
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json()["status"] == "ok"


def test_health_endpoint_multiple_calls():
    """Test that /health can be called multiple times reliably."""
    with TestClient(app) as client:
        for _ in range(5):
            response = client.get("/health")
            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "ok"
            assert data["version"] == __version__


def test_health_endpoint_cors_headers():
    """Test that /health works with CORS (when DEV_MODE is enabled)."""
    with TestClient(app) as client:
        # Request with Origin header to test CORS compatibility
        headers = {"Origin": "http://localhost:5173"}
        response = client.get("/health", headers=headers)
        assert response.status_code == 200
        assert response.json()["status"] == "ok"


def test_health_endpoint_content_type():
    """Test that /health returns proper JSON content type."""
    with TestClient(app) as client:
        response = client.get("/health")
        assert response.status_code == 200
        assert "application/json" in response.headers.get("content-type", "")

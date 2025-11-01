"""Test provider configuration API endpoints."""

import pytest
from fastapi.testclient import TestClient
import tempfile
from pathlib import Path

from loquilex.api.server import app


@pytest.fixture
def client():
    """Create test client."""
    return TestClient(app)


@pytest.fixture
def temp_config_dir():
    """Create temporary config directory."""
    with tempfile.TemporaryDirectory() as tmpdir:
        config_path = Path(tmpdir) / ".loquilex"
        config_path.mkdir(parents=True, exist_ok=True)

        # Mock the home directory for testing
        original_home = Path.home
        Path.home = lambda: Path(tmpdir)

        try:
            yield config_path
        finally:
            Path.home = original_home


def test_get_providers_config(client):
    """Test getting provider configuration."""
    response = client.get("/api/providers/config")
    assert response.status_code == 200

    data = response.json()
    assert "providers" in data
    assert "backend" in data
    assert "huggingface" in data["providers"]


def test_api_health_includes_offline_status(client):
    """Test that health endpoint includes offline mode status."""
    response = client.get("/api/health")
    assert response.status_code == 200

    data = response.json()
    assert "status" in data
    assert "offline_mode" in data
    assert "providers" in data
    assert data["status"] == "ok"


def test_set_hf_token_invalid_format(client):
    """Test setting invalid HF token format."""
    response = client.post("/api/providers/hf/token", json={"token": "invalid_token"})
    assert response.status_code == 400
    assert "Invalid HuggingFace token format" in response.json()["detail"]


def test_set_hf_token_empty(client):
    """Test setting empty HF token."""
    response = client.post("/api/providers/hf/token", json={"token": ""})
    assert response.status_code == 400
    assert "Token cannot be empty" in response.json()["detail"]


def test_set_hf_token_valid_format(client):
    """Test setting valid HF token."""
    valid_token = "hf_" + "a" * 32  # Mock valid token format

    response = client.post("/api/providers/hf/token", json={"token": valid_token})
    assert response.status_code == 200

    data = response.json()
    assert data["status"] == "ok"
    assert "successfully" in data["message"]


def test_remove_hf_token(client):
    """Test removing HF token."""
    response = client.delete("/api/providers/hf/token")
    assert response.status_code == 200

    data = response.json()
    assert data["status"] == "ok"
    assert "removed successfully" in data["message"]


def test_set_offline_mode(client, monkeypatch):
    """Test setting offline mode."""
    # Clear the LX_OFFLINE env var for this test
    monkeypatch.delenv("LX_OFFLINE", raising=False)

    # Reset global config to pick up env changes
    import loquilex.config.providers

    loquilex.config.providers._config = None

    # Test enabling offline mode
    response = client.post("/api/providers/offline", json={"offline": True})
    assert response.status_code == 200

    data = response.json()
    assert data["status"] == "ok"
    assert "enabled successfully" in data["message"]

    # Test disabling offline mode
    response = client.post("/api/providers/offline", json={"offline": False})
    assert response.status_code == 200

    data = response.json()
    assert data["status"] == "ok"
    assert "disabled successfully" in data["message"]


def test_offline_mode_enforced_by_environment(client, monkeypatch):
    """Test that offline mode cannot be disabled when enforced by environment."""
    # Set environment variable to enforce offline mode
    monkeypatch.setenv("LX_OFFLINE", "1")

    # Reset global config to pick up env changes
    import loquilex.config.providers

    loquilex.config.providers._config = None

    response = client.post("/api/providers/offline", json={"offline": False})
    assert response.status_code == 400
    assert "enforced by environment" in response.json()["detail"]

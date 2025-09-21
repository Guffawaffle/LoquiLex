"""Tests for storage API endpoints."""

import pytest
from fastapi.testclient import TestClient
from loquilex.api.server import app


@pytest.fixture
def client():
    """Test client for the FastAPI app."""
    return TestClient(app)


def test_get_storage_info_default_path(client):
    """Test getting storage info for default path."""
    response = client.get("/storage/info")
    assert response.status_code == 200
    
    data = response.json()
    assert "path" in data
    assert "total_bytes" in data
    assert "free_bytes" in data
    assert "used_bytes" in data
    assert "percent_used" in data
    assert "writable" in data
    
    assert isinstance(data["total_bytes"], int)
    assert isinstance(data["free_bytes"], int)
    assert isinstance(data["used_bytes"], int)
    assert isinstance(data["percent_used"], float)
    assert isinstance(data["writable"], bool)
    
    assert data["total_bytes"] >= 0
    assert data["free_bytes"] >= 0
    assert data["used_bytes"] >= 0
    assert 0 <= data["percent_used"] <= 100


def test_get_storage_info_custom_path(client):
    """Test getting storage info for custom path."""
    response = client.get("/storage/info?path=/tmp")
    assert response.status_code == 200
    
    data = response.json()
    assert "/tmp" in data["path"]
    assert data["writable"] is True


def test_get_storage_info_invalid_path(client):
    """Test getting storage info for invalid path."""
    response = client.get("/storage/info?path=/nonexistent/invalid/path")
    assert response.status_code == 400
    assert "Cannot access path" in response.json()["detail"]


def test_set_base_directory_valid_path(client):
    """Test setting a valid base directory."""
    response = client.post(
        "/storage/base-directory",
        json={"path": "/tmp/loquilex-test"}
    )
    assert response.status_code == 200
    
    data = response.json()
    assert data["path"] == "/tmp/loquilex-test"
    assert data["valid"] is True
    assert "valid and writable" in data["message"].lower()


def test_set_base_directory_invalid_path(client):
    """Test setting an invalid base directory."""
    response = client.post(
        "/storage/base-directory",
        json={"path": "/root/protected"}
    )
    assert response.status_code == 200
    
    data = response.json()
    assert data["path"] == "/root/protected"
    assert data["valid"] is False
    assert "permission denied" in data["message"].lower() or "invalid path" in data["message"].lower()


def test_set_base_directory_relative_path(client):
    """Test setting a relative path (should be rejected)."""
    response = client.post(
        "/storage/base-directory",
        json={"path": "relative/path"}
    )
    assert response.status_code == 200
    
    data = response.json() 
    assert data["valid"] is False
    assert "absolute" in data["message"].lower()


def test_set_base_directory_missing_path(client):
    """Test setting base directory without path parameter."""
    response = client.post(
        "/storage/base-directory",
        json={}
    )
    assert response.status_code == 422  # Validation error
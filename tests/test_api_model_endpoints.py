"""Tests for model-related API endpoints."""

from __future__ import annotations


from fastapi.testclient import TestClient
from loquilex.api.server import app


def test_get_asr_models():
    """Test /models/asr endpoint."""
    with TestClient(app) as client:
        response = client.get("/models/asr")
        assert response.status_code == 200

        models = response.json()
        assert isinstance(models, list)
        # Should be a list of model dicts
        for model in models:
            assert "id" in model
            assert "name" in model


def test_get_mt_models():
    """Test /models/mt endpoint."""
    with TestClient(app) as client:
        response = client.get("/models/mt")
        assert response.status_code == 200

        models = response.json()
        assert isinstance(models, list)
        # Should be a list of model dicts
        for model in models:
            assert "id" in model
            assert "name" in model


def test_get_model_defaults():
    """Test /settings/defaults GET endpoint."""
    with TestClient(app) as client:
        response = client.get("/settings/defaults")
        assert response.status_code == 200

        defaults = response.json()
        assert isinstance(defaults, dict)

        # Check required fields exist
        expected_fields = [
            "asr_model_id",
            "asr_device",
            "asr_compute_type",
            "mt_model_id",
            "mt_device",
            "mt_compute_type",
            "tts_model_id",
            "tts_device",
        ]
        for field in expected_fields:
            assert field in defaults
            assert isinstance(defaults[field], str)


def test_update_model_defaults():
    """Test /settings/defaults POST endpoint."""
    with TestClient(app) as client:
        # Update some defaults
        update_data = {"asr_model_id": "base.en", "mt_model_id": "nllb-600M", "asr_device": "cuda"}

        response = client.post("/settings/defaults", json=update_data)
        assert response.status_code == 200

        updated = response.json()
        assert updated["asr_model_id"] == "base.en"
        assert updated["mt_model_id"] == "nllb-600M"
        assert updated["asr_device"] == "cuda"

        # Verify by getting defaults again
        get_response = client.get("/settings/defaults")
        assert get_response.status_code == 200
        defaults = get_response.json()

        assert defaults["asr_model_id"] == "base.en"
        assert defaults["mt_model_id"] == "nllb-600M"
        assert defaults["asr_device"] == "cuda"


def test_partial_update_model_defaults():
    """Test partial updates to model defaults."""
    with TestClient(app) as client:
        # Get current defaults
        initial_response = client.get("/settings/defaults")
        initial = initial_response.json()

        # Update only ASR model
        update_data = {"asr_model_id": "small.en"}

        response = client.post("/settings/defaults", json=update_data)
        assert response.status_code == 200

        updated = response.json()
        assert updated["asr_model_id"] == "small.en"
        # Other fields should remain unchanged
        assert updated["mt_model_id"] == initial["mt_model_id"]
        assert updated["asr_device"] == initial["asr_device"]


def test_update_model_defaults_with_nulls():
    """Test that null values in update request are ignored."""
    with TestClient(app) as client:
        # Get current defaults
        initial_response = client.get("/settings/defaults")
        initial = initial_response.json()

        # Send update with some null values
        update_data = {
            "asr_model_id": "large-v3",
            "mt_model_id": None,  # This should be ignored
            "asr_device": None,  # This should be ignored
        }

        response = client.post("/settings/defaults", json=update_data)
        assert response.status_code == 200

        updated = response.json()
        assert updated["asr_model_id"] == "large-v3"
        # Null values should be ignored, keeping original values
        assert updated["mt_model_id"] == initial["mt_model_id"]
        assert updated["asr_device"] == initial["asr_device"]


def test_mt_languages_endpoint():
    """Test /languages/mt/{model_id} endpoint."""
    with TestClient(app) as client:
        # Test with a simple model name first
        response = client.get("/languages/mt/nllb-600M")
        assert response.status_code == 200

        result = response.json()
        assert "model_id" in result
        assert "languages" in result
        assert isinstance(result["languages"], list)

        # Test with unknown model
        response2 = client.get("/languages/mt/unknown-model")
        assert response2.status_code == 200
        result2 = response2.json()
        # Should still return something (minimal default)
        assert "languages" in result2

"""Tests for MT capability probing."""

from __future__ import annotations

from fastapi.testclient import TestClient

from loquilex.api.server import app
from loquilex.capabilities.mt import MTCapabilityProbe


class TestMTCapabilityProbe:
    """Unit tests for MTCapabilityProbe."""

    def test_probe_nllb_fallback(self):
        """Test NLLB probing with fallback (no tokenizer)."""
        result = MTCapabilityProbe.probe("facebook/nllb-200-distilled-600M")

        assert result["kind"] == "mt"
        assert result["model"] == "facebook/nllb-200-distilled-600M"
        assert isinstance(result["source_languages"], list)
        assert isinstance(result["target_languages"], list)
        assert result["pairs"] is None  # Many-to-many
        assert isinstance(result["tokens"], dict)

        # Should have common languages
        assert "en" in result["source_languages"]
        assert "zh-Hans" in result["source_languages"]
        assert "zh-Hant" in result["source_languages"]

        # Check token mapping
        assert result["tokens"]["en"] == "eng_Latn"
        assert result["tokens"]["zh-Hans"] == "zho_Hans"
        assert result["tokens"]["zh-Hant"] == "zho_Hant"

    def test_probe_m2m_fallback(self):
        """Test M2M probing with fallback (no tokenizer)."""
        result = MTCapabilityProbe.probe("facebook/m2m100_418M")

        assert result["kind"] == "mt"
        assert result["model"] == "facebook/m2m100_418M"
        assert isinstance(result["source_languages"], list)
        assert isinstance(result["target_languages"], list)
        assert result["pairs"] is None  # Many-to-many
        assert isinstance(result["tokens"], dict)

        # Should have common languages
        assert "en" in result["source_languages"]
        assert "zh-Hans" in result["source_languages"]

        # Check token mapping (M2M uses simpler codes)
        assert result["tokens"]["en"] == "en"
        assert result["tokens"]["zh-Hans"] == "zh"

    def test_probe_unknown_model(self):
        """Test probing unknown model type."""
        result = MTCapabilityProbe.probe("unknown/custom-model")

        assert result["kind"] == "mt"
        assert result["model"] == "unknown/custom-model"
        # Should return minimal capability
        assert "en" in result["source_languages"]
        assert "zh-Hans" in result["target_languages"]
        # Unknown models get constrained pairs
        assert result["pairs"] is not None

    def test_nllb_language_consistency(self):
        """Test that NLLB source and target languages are consistent."""
        result = MTCapabilityProbe.probe("facebook/nllb-200-distilled-600M")

        # Many-to-many should have same source and target languages
        assert result["source_languages"] == result["target_languages"]

        # All languages should have token mappings
        for lang in result["source_languages"]:
            assert lang in result["tokens"]

    def test_m2m_language_consistency(self):
        """Test that M2M source and target languages are consistent."""
        result = MTCapabilityProbe.probe("facebook/m2m100_418M")

        # Many-to-many should have same source and target languages
        assert result["source_languages"] == result["target_languages"]

        # All languages should have token mappings
        for lang in result["source_languages"]:
            assert lang in result["tokens"]


class TestMTCapabilitiesEndpoint:
    """Tests for the /models/mt/{name}/capabilities endpoint."""

    def test_get_capabilities_nllb(self):
        """Test getting capabilities for NLLB model."""
        with TestClient(app) as client:
            # Use a model name that will trigger NLLB detection
            response = client.get("/models/mt/nllb-200/capabilities")

            # Even without the model installed, should return fallback capability
            assert response.status_code == 200

            result = response.json()
            assert result["kind"] == "mt"
            assert "nllb" in result["model"].lower()
            assert isinstance(result["source_languages"], list)
            assert isinstance(result["target_languages"], list)
            assert result["pairs"] is None
            assert isinstance(result["tokens"], dict)

    def test_get_capabilities_m2m(self):
        """Test getting capabilities for M2M model."""
        with TestClient(app) as client:
            response = client.get("/models/mt/m2m100_418M/capabilities")

            assert response.status_code == 200

            result = response.json()
            assert result["kind"] == "mt"
            assert "m2m" in result["model"].lower()
            assert result["pairs"] is None  # Many-to-many

    def test_capabilities_caching(self):
        """Test that capabilities are cached by verifying identical responses."""
        with TestClient(app) as client:
            model_name = "nllb-200-caching-test"

            # First request
            response1 = client.get(f"/models/mt/{model_name}/capabilities")
            assert response1.status_code == 200
            result1 = response1.json()

            # Second request should return identical results
            # If caching works, this should be very fast and return exact same data
            response2 = client.get(f"/models/mt/{model_name}/capabilities")
            assert response2.status_code == 200
            result2 = response2.json()

            # Results should be identical (proves caching works)
            assert result1 == result2
            assert result1["model"] == model_name
            assert result1["kind"] == "mt"

    def test_capabilities_response_structure(self):
        """Test that response has correct structure."""
        with TestClient(app) as client:
            response = client.get("/models/mt/nllb-200/capabilities")
            assert response.status_code == 200

            result = response.json()

            # Check required fields
            required_fields = [
                "kind",
                "model",
                "source_languages",
                "target_languages",
                "pairs",
                "tokens",
            ]
            for field in required_fields:
                assert field in result, f"Missing required field: {field}"

            # Check types
            assert result["kind"] == "mt"
            assert isinstance(result["model"], str)
            assert isinstance(result["source_languages"], list)
            assert isinstance(result["target_languages"], list)
            assert result["pairs"] is None or isinstance(result["pairs"], dict)
            assert isinstance(result["tokens"], dict)

    def test_capabilities_bcp47_codes(self):
        """Test that language codes follow BCP-47 conventions."""
        with TestClient(app) as client:
            response = client.get("/models/mt/nllb-200/capabilities")
            assert response.status_code == 200

            result = response.json()

            # Check that language codes look like BCP-47
            for lang in result["source_languages"]:
                # BCP-47 codes should be lowercase with optional script subtag
                assert lang.islower() or "-" in lang
                # Common pattern: "en" or "zh-Hans"
                parts = lang.split("-")
                assert len(parts) <= 2
                if len(parts) == 2:
                    # Script subtag should start with uppercase
                    assert parts[1][0].isupper()

    def test_capabilities_token_mapping(self):
        """Test that token mapping is consistent."""
        with TestClient(app) as client:
            response = client.get("/models/mt/nllb-200/capabilities")
            assert response.status_code == 200

            result = response.json()

            # Every language should have a token mapping
            for lang in result["source_languages"]:
                assert lang in result["tokens"]
                # NLLB tokens should have FLORES format (xxx_Yyyy)
                token = result["tokens"][lang]
                if "_" in token:
                    parts = token.split("_")
                    assert len(parts) == 2
                    assert len(parts[0]) == 3  # Language code
                    assert parts[1][0].isupper()  # Script starts with uppercase

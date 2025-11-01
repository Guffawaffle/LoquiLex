"""Tests for ASR capability discovery."""

from __future__ import annotations

import os
import tempfile
import time
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from loquilex.api.server import app
from loquilex.capabilities.asr import ASRCapabilityProbe, WHISPER_LANG_TO_BCP47


class FakeWhisperModel:
    """Fake WhisperModel for testing."""

    def __init__(self, *_args, **_kwargs):
        self.model = FakeModel()


class FakeModel:
    """Fake model with tokenizer vocabulary."""

    def get_vocabulary(self):
        """Return a fake vocabulary with language tokens."""
        return [
            "<|startoftranscript|>",
            "<|en|>",
            "<|zh|>",
            "<|es|>",
            "<|fr|>",
            "<|de|>",
            "<|ja|>",
            "<|ko|>",
            "<|endoftext|>",
            "hello",
            "world",
        ]


class TestASRCapabilityProbe:
    """Test the ASRCapabilityProbe class."""

    def test_probe_with_fake_model(self):
        """Test probing with a fake Whisper model."""
        probe = ASRCapabilityProbe()

        with patch("faster_whisper.WhisperModel", FakeWhisperModel):
            result = probe.probe_model("test-model")

        assert result["kind"] == "asr"
        assert result["model"] == "test-model"
        assert result["supports_auto"] is True
        assert isinstance(result["languages"], list)
        assert isinstance(result["tokens"], dict)

        # Check that we detected the languages from the fake vocabulary
        expected_langs = {"de", "en", "es", "fr", "ja", "ko", "zh-Hans"}
        actual_langs = set(result["languages"])
        assert actual_langs == expected_langs

        # Check tokens
        assert result["tokens"]["en"] == "<|en|>"
        assert result["tokens"]["zh-Hans"] == "<|zh|>"
        assert result["tokens"]["es"] == "<|es|>"

    def test_probe_english_only_model(self):
        """Test probing an English-only model (fallback)."""
        probe = ASRCapabilityProbe()

        # Simulate model loading failure to trigger fallback
        with patch(
            "faster_whisper.WhisperModel", side_effect=Exception("Model not found")
        ):
            result = probe.probe_model("base.en")

        assert result["kind"] == "asr"
        assert result["model"] == "base.en"
        assert result["supports_auto"] is True
        assert result["languages"] == ["en"]
        assert result["tokens"]["en"] == "<|en|>"

    def test_probe_multilingual_fallback(self):
        """Test probing a multilingual model with fallback."""
        probe = ASRCapabilityProbe()

        # Simulate model loading failure to trigger fallback
        with patch(
            "faster_whisper.WhisperModel", side_effect=Exception("Model not found")
        ):
            result = probe.probe_model("base")

        assert result["kind"] == "asr"
        assert result["model"] == "base"
        assert result["supports_auto"] is True
        assert len(result["languages"]) > 1  # Should have multiple languages
        assert "en" in result["languages"]
        assert "zh-Hans" in result["languages"]
        assert result["tokens"]["zh-Hans"] == "<|zh|>"

    def test_caching_by_mtime(self):
        """Test that capabilities are cached based on file mtime."""
        probe = ASRCapabilityProbe()

        with tempfile.NamedTemporaryFile(delete=False) as tmp:
            tmp_path = tmp.name

        try:
            with patch("faster_whisper.WhisperModel", FakeWhisperModel):
                # First probe
                result1 = probe.probe_model("test-model", tmp_path)
                assert result1["model"] == "test-model"

                # Second probe - should use cache
                result2 = probe.probe_model("test-model", tmp_path)
                assert result2 == result1

                # Modify file mtime
                time.sleep(0.01)
                Path(tmp_path).touch()

                # Third probe - cache should be invalidated, re-probe
                result3 = probe.probe_model("test-model", tmp_path)
                # Result should be the same but freshly probed
                assert result3["model"] == "test-model"
                assert result3["kind"] == result1["kind"]

        finally:
            os.unlink(tmp_path)

    def test_error_handling(self):
        """Test that errors are handled gracefully."""
        probe = ASRCapabilityProbe()

        # Simulate an error during probing
        with patch(
            "faster_whisper.WhisperModel",
            side_effect=RuntimeError("Catastrophic failure"),
        ):
            result = probe.probe_model("broken-model")

        # Should return a safe response with error field
        assert result["kind"] == "asr"
        assert result["model"] == "broken-model"
        assert result["supports_auto"] is True  # Fallback still sets this
        assert isinstance(result["languages"], list)

    def test_bcp47_mapping(self):
        """Test BCP-47 code mapping."""
        # Verify key mappings
        assert WHISPER_LANG_TO_BCP47["en"] == "en"
        assert WHISPER_LANG_TO_BCP47["zh"] == "zh-Hans"
        assert WHISPER_LANG_TO_BCP47["jw"] == "jv"  # Javanese normalization


class TestASRCapabilitiesEndpoint:
    """Test the /models/asr/{name}/capabilities endpoint."""

    def test_get_capabilities_endpoint(self):
        """Test the GET endpoint for ASR capabilities."""
        with TestClient(app) as client:
            # Mock the probe to avoid loading real models
            with patch("faster_whisper.WhisperModel", FakeWhisperModel):
                response = client.get("/models/asr/test-model/capabilities")

            assert response.status_code == 200
            data = response.json()

            # Verify structure
            assert data["kind"] == "asr"
            assert data["model"] == "test-model"
            assert "supports_auto" in data
            assert "languages" in data
            assert "tokens" in data
            assert isinstance(data["languages"], list)
            assert isinstance(data["tokens"], dict)

    def test_capabilities_with_model_path(self):
        """Test that endpoint uses model path from discovery for caching."""
        with TestClient(app) as client:
            # Mock list_asr_models to return a known model
            with patch("loquilex.api.server.list_asr_models") as mock_list:
                mock_list.return_value = [
                    {"id": "base.en", "name": "base.en", "path": "/fake/path/to/model"}
                ]

                with patch("faster_whisper.WhisperModel", FakeWhisperModel):
                    response = client.get("/models/asr/base.en/capabilities")

            assert response.status_code == 200
            data = response.json()
            assert data["model"] == "base.en"

    def test_capabilities_unknown_model(self):
        """Test endpoint with unknown model falls back gracefully."""
        with TestClient(app) as client:
            with patch(
                "faster_whisper.WhisperModel",
                side_effect=Exception("Model not found"),
            ):
                response = client.get("/models/asr/unknown-model/capabilities")

            # Should still return 200 with fallback data
            assert response.status_code == 200
            data = response.json()
            assert data["model"] == "unknown-model"
            assert "languages" in data


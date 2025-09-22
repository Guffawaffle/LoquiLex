"""Tests for model defaults persistence."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

from loquilex.config.model_defaults import ModelDefaults, ModelDefaultsManager

def test_model_defaults_serialization():
    """Test ModelDefaults serialization to/from dict."""
    defaults = ModelDefaults(
        asr_model_id="small.en",
        asr_device="cuda",
        asr_compute_type="float16",
        mt_model_id="nllb-600M",
        mt_device="auto",
        mt_compute_type="int8_float16",
        tts_model_id="",
        tts_device="auto",
    )

    # Test to_dict
    data = defaults.to_dict()
    assert data["asr_model_id"] == "small.en"
    assert data["asr_device"] == "cuda"
    assert data["mt_model_id"] == "nllb-600M"

    # Test from_dict
    restored = ModelDefaults.from_dict(data)
    assert restored == defaults


def test_model_defaults_from_dict_filtering():
    """Test that from_dict filters unknown fields gracefully."""
    data = {
        "asr_model_id": "small.en",
        "unknown_field": "should_be_ignored",
        "another_unknown": 123,
        "mt_device": "cuda",
    }

    defaults = ModelDefaults.from_dict(data)
    assert defaults.asr_model_id == "small.en"
    assert defaults.mt_device == "cuda"
    # Unknown fields should be ignored, not cause errors
    assert not hasattr(defaults, "unknown_field")


def test_model_defaults_manager_basic():
    """Test basic ModelDefaultsManager functionality."""
    with tempfile.TemporaryDirectory() as tmpdir:
        storage_path = Path(tmpdir) / "defaults.json"
        manager = ModelDefaultsManager(storage_path=storage_path)

        # Get initial defaults
        defaults = manager.get_defaults()
        assert isinstance(defaults, ModelDefaults)

        # Check storage was created
        assert storage_path.exists()


def test_model_defaults_manager_updates(monkeypatch):
    """Test updating defaults."""
    # Clear env vars that might interfere
    monkeypatch.delenv("LX_ASR_MODEL", raising=False)
    monkeypatch.delenv("LX_NLLB_MODEL", raising=False)

    with tempfile.TemporaryDirectory() as tmpdir:
        storage_path = Path(tmpdir) / "defaults.json"
        manager = ModelDefaultsManager(storage_path=storage_path)

        # Update some defaults
        updated = manager.update_defaults(asr_model_id="base.en", mt_model_id="nllb-600M")

        assert updated.asr_model_id == "base.en"
        assert updated.mt_model_id == "nllb-600M"

        # Verify persistence
        with open(storage_path) as f:
            saved_data = json.load(f)
        assert saved_data["asr_model_id"] == "base.en"
        assert saved_data["mt_model_id"] == "nllb-600M"


def test_model_defaults_manager_convenience_methods():
    """Test convenience methods for getting/setting specific defaults."""
    with tempfile.TemporaryDirectory() as tmpdir:
        storage_path = Path(tmpdir) / "defaults.json"
        manager = ModelDefaultsManager(storage_path=storage_path)

        # Set individual defaults
        manager.set_asr_default("large-v3")
        manager.set_mt_default("nllb-1.3B")
        manager.set_tts_default("espeak-ng")

        # Get individual defaults
        assert manager.get_asr_default() == "large-v3"
        assert manager.get_mt_default() == "nllb-1.3B"
        assert manager.get_tts_default() == "espeak-ng"


def test_model_defaults_manager_env_fallback(monkeypatch):
    """Test fallback to environment variables for initial defaults."""
    # Set some env vars
    monkeypatch.setenv("LX_ASR_MODEL", "medium.en")
    monkeypatch.setenv("LX_NLLB_MODEL", "facebook/nllb-200-distilled-600M")
    monkeypatch.setenv("LX_DEVICE", "cuda")
    monkeypatch.setenv("LX_ASR_COMPUTE", "float32")

    with tempfile.TemporaryDirectory() as tmpdir:
        storage_path = Path(tmpdir) / "defaults.json"
        manager = ModelDefaultsManager(storage_path=storage_path)

        defaults = manager.get_defaults()
        assert defaults.asr_model_id == "medium.en"
        assert defaults.mt_model_id == "facebook/nllb-200-distilled-600M"
        assert defaults.asr_device == "cuda"
        assert defaults.asr_compute_type == "float32"


def test_model_defaults_manager_loading_existing():
    """Test loading from existing storage file."""
    with tempfile.TemporaryDirectory() as tmpdir:
        storage_path = Path(tmpdir) / "defaults.json"

        # Create existing storage
        existing_data = {
            "asr_model_id": "stored.en",
            "mt_model_id": "stored-mt",
            "asr_device": "cpu",
            "mt_device": "cuda",
            "asr_compute_type": "float32",
            "mt_compute_type": "float16",
            "tts_model_id": "stored-tts",
            "tts_device": "auto",
        }
        with open(storage_path, "w") as f:
            json.dump(existing_data, f)

        # Create manager - should load existing data
        manager = ModelDefaultsManager(storage_path=storage_path)
        defaults = manager.get_defaults()

        assert defaults.asr_model_id == "stored.en"
        assert defaults.mt_model_id == "stored-mt"
        assert defaults.asr_device == "cpu"
        assert defaults.mt_device == "cuda"


def test_model_defaults_manager_invalid_updates():
    """Test that invalid update fields are handled gracefully."""
    with tempfile.TemporaryDirectory() as tmpdir:
        storage_path = Path(tmpdir) / "defaults.json"
        manager = ModelDefaultsManager(storage_path=storage_path)

        # Try updating with invalid field (should log warning but not crash)
        manager.update_defaults(asr_model_id="valid.en", invalid_field="should_be_ignored")

        # Valid field should be updated
        assert manager.get_asr_default() == "valid.en"

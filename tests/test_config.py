"""Tests for loquilex.config module - centralized runtime settings."""

from __future__ import annotations

import importlib
import os
import pytest


@pytest.fixture
def reload_config_after():
    """Restore config module to default state after test.
    
    This fixture reloads the config module after tests that modify env vars
    to ensure changes don't affect other tests. Use this fixture explicitly
    in tests that reload config.
    """
    yield
    # After test: clear any test env vars and reload config with defaults
    test_env_vars = [
        "LX_FALLBACK_MEMORY_TOTAL_GB",
        "LX_FALLBACK_MEMORY_AVAILABLE_GB",
        "LX_MIN_MEMORY_GB",
        "LX_MIN_CPU_CORES",
        "LX_MAX_CPU_USAGE",
        "LX_MIN_GPU_MEMORY_GB",
    ]
    for var in test_env_vars:
        os.environ.pop(var, None)
    
    # Reload config and detection modules to restore defaults
    from loquilex import config
    from loquilex.hardware import detection

    importlib.reload(config)
    importlib.reload(detection)


class TestSettings:
    """Test Settings dataclass and environment variable overrides."""

    def test_default_settings_values(self):
        """Test that default settings are loaded correctly."""
        from loquilex.config import settings

        # Memory defaults
        assert settings.fallback_memory_total_gb == 8.0
        assert settings.fallback_memory_available_gb == 4.0
        assert settings.min_memory_gb == 8.0

        # CPU defaults
        assert settings.min_cpu_cores == 2
        assert settings.max_cpu_usage_percent == 80.0

        # GPU defaults
        assert settings.min_gpu_memory_gb == 4.0

    def test_settings_is_frozen(self):
        """Test that Settings dataclass is frozen (immutable)."""
        from loquilex.config import settings

        with pytest.raises(Exception):  # FrozenInstanceError
            settings.min_cpu_cores = 10  # type: ignore

    def test_env_var_override_memory(self, monkeypatch, reload_config_after):  # noqa: ARG002
        """Test that environment variables override memory defaults."""
        monkeypatch.setenv("LX_FALLBACK_MEMORY_TOTAL_GB", "16.0")
        monkeypatch.setenv("LX_FALLBACK_MEMORY_AVAILABLE_GB", "12.0")
        monkeypatch.setenv("LX_MIN_MEMORY_GB", "16.0")

        # Reload the config module to pick up new env vars
        from loquilex import config

        importlib.reload(config)

        assert config.settings.fallback_memory_total_gb == 16.0
        assert config.settings.fallback_memory_available_gb == 12.0
        assert config.settings.min_memory_gb == 16.0

    def test_env_var_override_cpu(self, monkeypatch, reload_config_after):  # noqa: ARG002
        """Test that environment variables override CPU defaults."""
        monkeypatch.setenv("LX_MIN_CPU_CORES", "4")
        monkeypatch.setenv("LX_MAX_CPU_USAGE", "90.0")

        # Reload the config module to pick up new env vars
        from loquilex import config

        importlib.reload(config)

        assert config.settings.min_cpu_cores == 4
        assert config.settings.max_cpu_usage_percent == 90.0

    def test_env_var_override_gpu(self, monkeypatch, reload_config_after):  # noqa: ARG002
        """Test that environment variables override GPU defaults."""
        monkeypatch.setenv("LX_MIN_GPU_MEMORY_GB", "8.0")

        # Reload the config module to pick up new env vars
        from loquilex import config

        importlib.reload(config)

        assert config.settings.min_gpu_memory_gb == 8.0

    def test_invalid_env_var_falls_back_to_default(self, monkeypatch, reload_config_after):  # noqa: ARG002
        """Test that invalid env var values fall back to defaults."""
        monkeypatch.setenv("LX_MIN_CPU_CORES", "not-a-number")
        monkeypatch.setenv("LX_MIN_MEMORY_GB", "invalid")

        # Reload the config module to pick up new env vars
        from loquilex import config

        importlib.reload(config)

        # Should fall back to defaults
        assert config.settings.min_cpu_cores == 2
        assert config.settings.min_memory_gb == 8.0

    def test_settings_class_can_be_instantiated(self):
        """Test that Settings class can be directly instantiated for testing."""
        from loquilex.config import Settings

        custom_settings = Settings()
        assert custom_settings.min_cpu_cores == 2
        assert custom_settings.min_memory_gb == 8.0


class TestBackwardsCompatibility:
    """Test that existing imports still work."""

    def test_can_import_asr_defaults(self):
        """Test that ASR defaults can still be imported."""
        from loquilex.config import ASR

        assert ASR.language == "en"
        assert ASR.model == "small.en"

    def test_can_import_from_defaults_module(self):
        """Test that defaults module still works."""
        from loquilex.config.defaults import ASR, MT, RT, SEG

        assert ASR is not None
        assert MT is not None
        assert RT is not None
        assert SEG is not None

    def test_can_import_pick_device(self):
        """Test that pick_device helper is still available."""
        from loquilex.config import pick_device

        device, dtype = pick_device()
        assert device in ["cpu", "cuda"]
        assert dtype in ["float16", "float32"]


class TestHardwareDetectionIntegration:
    """Test that hardware detection uses config settings."""

    def test_hardware_detection_uses_config_fallbacks(self, monkeypatch, reload_config_after):  # noqa: ARG002
        """Test that hardware detection respects config fallback values."""
        # Set custom fallback values
        monkeypatch.setenv("LX_FALLBACK_MEMORY_TOTAL_GB", "16.0")
        monkeypatch.setenv("LX_FALLBACK_MEMORY_AVAILABLE_GB", "12.0")

        # Reload config to pick up env vars
        from loquilex import config

        importlib.reload(config)

        # Verify settings loaded
        assert config.settings.fallback_memory_total_gb == 16.0

        # Mock psutil to be unavailable
        import sys

        original_psutil = sys.modules.get("psutil")
        sys.modules["psutil"] = None  # type: ignore

        try:
            # Reload hardware detection to pick up the mocked psutil
            from loquilex.hardware import detection

            importlib.reload(detection)

            snapshot = detection.get_hardware_snapshot()

            # Should use our custom fallback values
            assert snapshot.memory_total_gb == 16.0
            assert snapshot.memory_available_gb == 12.0

        finally:
            # Restore psutil
            if original_psutil is not None:
                sys.modules["psutil"] = original_psutil
            else:
                sys.modules.pop("psutil", None)

    def test_hardware_detection_uses_config_thresholds(self, monkeypatch, reload_config_after):  # noqa: ARG002
        """Test that hardware detection respects config threshold values."""
        # Set custom thresholds
        monkeypatch.setenv("LX_MIN_CPU_CORES", "8")
        monkeypatch.setenv("LX_MAX_CPU_USAGE", "70.0")
        monkeypatch.setenv("LX_MIN_MEMORY_GB", "16.0")

        # Reload config and detection modules
        from loquilex import config
        from loquilex.hardware import detection

        importlib.reload(config)
        importlib.reload(detection)

        # Get hardware info
        snapshot = detection.get_hardware_snapshot()

        # CPU should likely not meet threshold with 8 cores requirement
        # (most CI systems have fewer than 8 cores)
        if snapshot.cpu.cores_logical < 8:
            assert not snapshot.cpu.meets_threshold
            assert any("minimum recommended: 8" in w for w in snapshot.cpu.warnings)

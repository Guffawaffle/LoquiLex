"""Tests for hardware detection module."""

import importlib
import os
from unittest.mock import Mock, patch

import pytest

from loquilex.hardware.detection import (
    get_hardware_snapshot,
    _get_cpu_info,
    _get_gpu_info,
    _get_audio_devices,
    _calculate_overall_score,
    CPUInfo,
    GPUInfo,
    AudioDeviceInfo,
)


@pytest.fixture
def reload_config_after():
    """Restore config module to default state after test.

    This fixture reloads the config module after tests that modify env vars
    to ensure changes don't affect other tests.
    """
    yield
    # After test: clear any test env vars and reload config with defaults
    test_env_vars = [
        "LX_MIN_CPU_CORES",
        "LX_MAX_CPU_USAGE",
    ]
    for var in test_env_vars:
        os.environ.pop(var, None)

    # Reload config and detection modules to restore defaults
    from loquilex import config
    from loquilex.hardware import detection

    importlib.reload(config)
    importlib.reload(detection)


class TestCPUInfo:
    """Test CPU information detection."""

    def test_get_cpu_info_basic(self):
        """Test basic CPU information retrieval."""
        cpu = _get_cpu_info()

        # Use type().__name__ instead of isinstance() to avoid issues with module reloading
        # (other tests may reload detection module, changing CPUInfo class identity)
        assert type(cpu).__name__ == "CPUInfo"
        assert cpu.cores_logical >= 1
        assert cpu.cores_physical >= 1
        assert isinstance(cpu.warnings, list)
        assert isinstance(cpu.meets_threshold, bool)

    @patch.dict("os.environ", {"LX_MIN_CPU_CORES": "8"})
    def test_cpu_threshold_warning(self, reload_config_after):  # noqa: ARG002
        """Test CPU threshold warnings."""
        # Reload config to pick up env var changes
        import importlib
        from loquilex import config
        from loquilex.hardware import detection

        importlib.reload(config)
        importlib.reload(detection)

        cpu = detection._get_cpu_info()

        # Should warn if we have fewer than 8 cores (most systems do)
        if cpu.cores_logical < 8:
            assert not cpu.meets_threshold
            assert any("minimum recommended" in w for w in cpu.warnings)


class TestGPUInfo:
    """Test GPU information detection."""

    def test_get_gpu_info_no_torch(self):
        """Test GPU detection when PyTorch is not available."""
        with patch.dict("sys.modules", {"torch": None}):
            gpus = _get_gpu_info()

        assert len(gpus) == 1
        assert gpus[0].name == "No GPU detected"
        assert not gpus[0].cuda_available
        assert not gpus[0].meets_threshold

    def test_get_gpu_info_with_mock_torch(self):
        """Test GPU detection with mocked PyTorch."""
        mock_torch = Mock()
        mock_torch.cuda.is_available.return_value = False

        with patch.dict("sys.modules", {"torch": mock_torch}):
            gpus = _get_gpu_info()

        assert len(gpus) == 1
        assert not gpus[0].cuda_available


class TestAudioDevices:
    """Test audio device detection."""

    def test_get_audio_devices_no_sounddevice(self):
        """Test audio device detection when sounddevice is not available."""
        with patch.dict("sys.modules", {"sounddevice": None}):
            devices = _get_audio_devices()

        assert len(devices) >= 1
        assert devices[0].name == "Default Input (sounddevice not available)"
        assert not devices[0].is_available

    def test_get_audio_devices_with_mock_sounddevice(self):
        """Test audio device detection with mocked sounddevice."""
        mock_sd = Mock()
        mock_device = {
            "name": "Test Microphone",
            "max_input_channels": 2,
            "default_samplerate": 44100,
        }
        mock_sd.query_devices.return_value = [mock_device]
        mock_sd.default.device = [0]
        mock_sd.check_input_settings.return_value = None  # No exception = available

        with patch.dict("sys.modules", {"sounddevice": mock_sd}):
            devices = _get_audio_devices()

        assert len(devices) >= 1
        assert devices[0].name == "Test Microphone"
        assert devices[0].channels == 2
        assert devices[0].is_default
        assert devices[0].is_available


class TestOverallScore:
    """Test overall system scoring."""

    def test_calculate_overall_score_excellent(self):
        """Test excellent system score calculation."""
        cpu = CPUInfo(
            name="Test CPU",
            cores_physical=8,
            cores_logical=16,
            frequency_mhz=3000.0,
            usage_percent=25.0,
            meets_threshold=True,
            warnings=[],
        )

        gpu = GPUInfo(
            name="Test GPU",
            memory_total_mb=8192,  # 8GB
            memory_free_mb=6144,
            memory_used_mb=2048,
            temperature_c=65,
            utilization_percent=30,
            cuda_available=True,
            meets_threshold=True,
            warnings=[],
        )

        audio = AudioDeviceInfo(
            name="Test Mic",
            device_id=0,
            channels=2,
            sample_rate=16000,
            is_default=True,
            is_available=True,
            warnings=[],
        )

        score, status = _calculate_overall_score(cpu, [gpu], [audio])

        assert score >= 90
        assert status == "excellent"

    def test_calculate_overall_score_poor(self):
        """Test poor system score calculation."""
        cpu = CPUInfo(
            name="Old CPU",
            cores_physical=1,
            cores_logical=1,
            frequency_mhz=1000.0,
            usage_percent=95.0,
            meets_threshold=False,
            warnings=["CPU below threshold"],
        )

        gpu = GPUInfo(
            name="No GPU",
            memory_total_mb=0,
            memory_free_mb=0,
            memory_used_mb=0,
            temperature_c=None,
            utilization_percent=None,
            cuda_available=False,
            meets_threshold=False,
            warnings=["No GPU detected"],
        )

        audio = AudioDeviceInfo(
            name="No Audio",
            device_id=0,
            channels=0,
            sample_rate=0,
            is_default=False,
            is_available=False,
            warnings=["No audio device"],
        )

        score, status = _calculate_overall_score(cpu, [gpu], [audio])

        assert score < 45
        assert status == "unusable"


class TestHardwareSnapshot:
    """Test complete hardware snapshot."""

    def test_get_hardware_snapshot(self):
        """Test getting complete hardware snapshot."""
        snapshot = get_hardware_snapshot()

        # Basic structure validation
        assert snapshot.cpu is not None
        assert isinstance(snapshot.gpus, list)
        assert len(snapshot.gpus) >= 1
        assert isinstance(snapshot.audio_devices, list)
        assert len(snapshot.audio_devices) >= 1
        assert snapshot.memory_total_gb > 0
        assert snapshot.memory_available_gb >= 0
        assert isinstance(snapshot.platform_info, dict)
        assert snapshot.overall_status in ["excellent", "good", "fair", "poor", "unusable"]
        assert 0 <= snapshot.overall_score <= 100
        assert isinstance(snapshot.warnings, list)

        # Platform info validation
        assert "system" in snapshot.platform_info
        assert "python_version" in snapshot.platform_info

    def test_hardware_snapshot_to_dict(self):
        """Test hardware snapshot serialization."""
        snapshot = get_hardware_snapshot()
        data = snapshot.to_dict()

        assert isinstance(data, dict)
        assert "cpu" in data
        assert "gpus" in data
        assert "audio_devices" in data
        assert "overall_score" in data
        assert "overall_status" in data

        # Ensure all nested objects are also dictionaries
        assert isinstance(data["cpu"], dict)
        assert isinstance(data["gpus"], list)
        assert isinstance(data["audio_devices"], list)
        if data["gpus"]:
            assert isinstance(data["gpus"][0], dict)
        if data["audio_devices"]:
            assert isinstance(data["audio_devices"][0], dict)

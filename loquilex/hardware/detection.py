"""Hardware detection and system information for LoquiLex.

Detects GPU/CPU capabilities and audio devices, providing threshold warnings.
"""

from __future__ import annotations

import os
import platform
from dataclasses import dataclass, asdict
from typing import Any, Dict, List, Optional, Tuple

try:
    import psutil
except ImportError:
    psutil = None


@dataclass
class CPUInfo:
    """CPU information."""

    name: str
    cores_physical: int
    cores_logical: int
    frequency_mhz: float
    usage_percent: float
    meets_threshold: bool
    warnings: List[str]


@dataclass
class GPUInfo:
    """GPU information."""

    name: str
    memory_total_mb: int
    memory_free_mb: int
    memory_used_mb: int
    temperature_c: Optional[int]
    utilization_percent: Optional[int]
    cuda_available: bool
    meets_threshold: bool
    warnings: List[str]


@dataclass
class AudioDeviceInfo:
    """Audio device information."""

    name: str
    device_id: int
    channels: int
    sample_rate: int
    is_default: bool
    is_available: bool
    warnings: List[str]


@dataclass
class HardwareSnapshot:
    """Complete hardware system snapshot."""

    cpu: CPUInfo
    gpus: List[GPUInfo]
    audio_devices: List[AudioDeviceInfo]
    memory_total_gb: float
    memory_available_gb: float
    platform_info: Dict[str, str]
    overall_status: str  # "excellent", "good", "fair", "poor", "unusable"
    overall_score: int  # 0-100
    warnings: List[str]

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return asdict(self)


def _get_cpu_info() -> CPUInfo:
    """Get CPU information with threshold checking."""
    warnings = []

    # Get CPU info
    try:
        cpu_name = platform.processor() or "Unknown CPU"

        if psutil:
            cores_physical = psutil.cpu_count(logical=False) or 1
            cores_logical = psutil.cpu_count(logical=True) or 1

            # Get frequency (fallback to 0 if not available)
            try:
                freq_info = psutil.cpu_freq()
                frequency_mhz = freq_info.current if freq_info else 0.0
            except Exception:
                frequency_mhz = 0.0

            # Get current usage
            usage_percent = psutil.cpu_percent(interval=0.1)
        else:
            # Fallback without psutil
            cores_physical = cores_logical = os.cpu_count() or 1
            frequency_mhz = 0.0
            usage_percent = 0.0
            warnings.append("psutil not available - limited CPU info")

    except Exception as e:
        cpu_name = f"Error getting CPU info: {e}"
        cores_physical = cores_logical = 1
        frequency_mhz = 0.0
        usage_percent = 0.0
        warnings.append(f"Failed to get CPU info: {e}")

    # Threshold checking
    min_cores = int(os.getenv("LX_MIN_CPU_CORES", "2"))
    max_usage = float(os.getenv("LX_MAX_CPU_USAGE", "80.0"))

    meets_threshold = True

    if cores_logical < min_cores:
        meets_threshold = False
        warnings.append(f"CPU has {cores_logical} cores, minimum recommended: {min_cores}")

    if usage_percent > max_usage:
        meets_threshold = False
        warnings.append(f"CPU usage {usage_percent:.1f}% exceeds threshold {max_usage}%")

    return CPUInfo(
        name=cpu_name,
        cores_physical=cores_physical,
        cores_logical=cores_logical,
        frequency_mhz=frequency_mhz,
        usage_percent=usage_percent,
        meets_threshold=meets_threshold,
        warnings=warnings,
    )


def _get_gpu_info() -> List[GPUInfo]:
    """Get GPU information with CUDA detection."""
    gpus = []

    # Try to detect CUDA GPUs first
    cuda_available = False
    try:
        import torch

        cuda_available = torch.cuda.is_available()

        if cuda_available:
            device_count = torch.cuda.device_count()
            for i in range(device_count):
                warnings = []

                try:
                    props = torch.cuda.get_device_properties(i)
                    name = props.name
                    memory_total_mb = props.total_memory // (1024 * 1024)

                    # Get current memory usage
                    memory_reserved = torch.cuda.memory_reserved(i) // (1024 * 1024)
                    memory_allocated = torch.cuda.memory_allocated(i) // (1024 * 1024)
                    memory_free_mb = memory_total_mb - memory_reserved
                    memory_used_mb = memory_allocated

                    # Try to get temperature and utilization (optional)
                    temperature_c = None
                    utilization_percent = None

                    # Threshold checking
                    min_memory_gb = float(os.getenv("LX_MIN_GPU_MEMORY_GB", "4.0"))
                    min_memory_mb = int(min_memory_gb * 1024)

                    meets_threshold = True
                    if memory_total_mb < min_memory_mb:
                        meets_threshold = False
                        warnings.append(
                            f"GPU memory {memory_total_mb/1024:.1f}GB below threshold {min_memory_gb}GB"
                        )

                    gpus.append(
                        GPUInfo(
                            name=name,
                            memory_total_mb=memory_total_mb,
                            memory_free_mb=memory_free_mb,
                            memory_used_mb=memory_used_mb,
                            temperature_c=temperature_c,
                            utilization_percent=utilization_percent,
                            cuda_available=True,
                            meets_threshold=meets_threshold,
                            warnings=warnings,
                        )
                    )

                except Exception as e:
                    warnings.append(f"Error getting GPU {i} details: {e}")
                    gpus.append(
                        GPUInfo(
                            name=f"CUDA GPU {i} (Error)",
                            memory_total_mb=0,
                            memory_free_mb=0,
                            memory_used_mb=0,
                            temperature_c=None,
                            utilization_percent=None,
                            cuda_available=True,
                            meets_threshold=False,
                            warnings=warnings,
                        )
                    )

    except ImportError:
        pass  # PyTorch not available
    except Exception:
        pass  # Other CUDA detection errors

    # If no CUDA GPUs found, add a placeholder
    if not gpus:
        warnings = ["No CUDA-capable GPUs detected"]
        if not cuda_available:
            warnings.append("PyTorch CUDA support not available")

        gpus.append(
            GPUInfo(
                name="No GPU detected",
                memory_total_mb=0,
                memory_free_mb=0,
                memory_used_mb=0,
                temperature_c=None,
                utilization_percent=None,
                cuda_available=False,
                meets_threshold=False,
                warnings=warnings,
            )
        )

    return gpus


def _get_audio_devices() -> List[AudioDeviceInfo]:
    """Get audio input devices."""
    devices = []

    # Try sounddevice first
    try:
        import sounddevice as sd

        device_list = sd.query_devices()
        default_input = sd.default.device[0] if sd.default.device else None

        for i, device in enumerate(device_list):
            if device["max_input_channels"] > 0:  # Input device
                warnings = []

                # Check if device is available
                is_available = True
                try:
                    # Quick test to see if we can access the device
                    sd.check_input_settings(device=i, samplerate=16000, channels=1)
                except Exception as e:
                    is_available = False
                    warnings.append(f"Device not accessible: {e}")

                devices.append(
                    AudioDeviceInfo(
                        name=device["name"],
                        device_id=i,
                        channels=device["max_input_channels"],
                        sample_rate=int(device.get("default_samplerate", 16000)),
                        is_default=(i == default_input),
                        is_available=is_available,
                        warnings=warnings,
                    )
                )

    except ImportError:
        # Fallback: try to detect basic audio capability
        devices.append(
            AudioDeviceInfo(
                name="Default Input (sounddevice not available)",
                device_id=0,
                channels=1,
                sample_rate=16000,
                is_default=True,
                is_available=False,
                warnings=["sounddevice package not available for device detection"],
            )
        )
    except Exception as e:
        devices.append(
            AudioDeviceInfo(
                name="Audio detection failed",
                device_id=0,
                channels=0,
                sample_rate=0,
                is_default=False,
                is_available=False,
                warnings=[f"Audio device detection failed: {e}"],
            )
        )

    return devices


def _calculate_overall_score(
    cpu: CPUInfo, gpus: List[GPUInfo], audio_devices: List[AudioDeviceInfo]
) -> Tuple[int, str]:
    """Calculate overall system score and status."""
    score = 0

    # CPU scoring (40% of total)
    cpu_score = 40
    if cpu.cores_logical >= 4:
        cpu_score = 40
    elif cpu.cores_logical >= 2:
        cpu_score = 30
    else:
        cpu_score = 15

    if not cpu.meets_threshold:
        cpu_score = max(0, cpu_score - 15)

    score += cpu_score

    # GPU scoring (35% of total)
    gpu_score = 0
    best_gpu = None
    for gpu in gpus:
        if gpu.cuda_available and gpu.memory_total_mb > 0:
            best_gpu = gpu
            break

    if best_gpu and best_gpu.memory_total_mb >= 4096:  # 4GB+
        gpu_score = 35
    elif best_gpu and best_gpu.memory_total_mb >= 2048:  # 2GB+
        gpu_score = 25
    elif best_gpu and best_gpu.cuda_available:
        gpu_score = 15
    else:
        gpu_score = 5  # CPU fallback

    if best_gpu and not best_gpu.meets_threshold:
        gpu_score = max(0, gpu_score - 10)

    score += gpu_score

    # Audio scoring (25% of total)
    audio_score = 0
    available_devices = [d for d in audio_devices if d.is_available]

    if len(available_devices) >= 1:
        audio_score = 25
    elif len(audio_devices) >= 1:  # Detected but not available
        audio_score = 10
    else:
        audio_score = 0

    score += audio_score

    # Determine status
    if score >= 90:
        status = "excellent"
    elif score >= 75:
        status = "good"
    elif score >= 60:
        status = "fair"
    elif score >= 45:
        status = "poor"
    else:
        status = "unusable"

    return score, status


def get_hardware_snapshot() -> HardwareSnapshot:
    """Get complete hardware system snapshot."""
    cpu = _get_cpu_info()
    gpus = _get_gpu_info()
    audio_devices = _get_audio_devices()

    # Memory information
    if psutil:
        memory = psutil.virtual_memory()
        memory_total_gb = memory.total / (1024**3)
        memory_available_gb = memory.available / (1024**3)
    else:
        # Fallback without psutil
        memory_total_gb = 8.0  # Assume 8GB
        memory_available_gb = 4.0  # Assume 4GB available

    # Platform information
    platform_info = {
        "system": platform.system(),
        "release": platform.release(),
        "version": platform.version(),
        "machine": platform.machine(),
        "processor": platform.processor(),
        "python_version": platform.python_version(),
    }

    # Calculate overall score and status
    overall_score, overall_status = _calculate_overall_score(cpu, gpus, audio_devices)

    # Collect all warnings
    warnings = []
    warnings.extend(cpu.warnings)
    for gpu in gpus:
        warnings.extend(gpu.warnings)
    for device in audio_devices:
        warnings.extend(device.warnings)

    # Add memory warnings
    min_memory_gb = float(os.getenv("LX_MIN_MEMORY_GB", "8.0"))
    if memory_total_gb < min_memory_gb:
        warnings.append(f"System memory {memory_total_gb:.1f}GB below threshold {min_memory_gb}GB")

    if memory_available_gb < 2.0:
        warnings.append(f"Available memory {memory_available_gb:.1f}GB is very low")

    return HardwareSnapshot(
        cpu=cpu,
        gpus=gpus,
        audio_devices=audio_devices,
        memory_total_gb=memory_total_gb,
        memory_available_gb=memory_available_gb,
        platform_info=platform_info,
        overall_status=overall_status,
        overall_score=overall_score,
        warnings=warnings,
    )

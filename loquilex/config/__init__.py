"""LoquiLex centralized configuration for runtime settings.

Provides typed settings for hardware detection, thresholds, and system defaults.
All settings are backed by environment variables following the LX_* naming convention.

Example:
    >>> from loquilex.config import settings
    >>> settings.fallback_memory_total_gb
    8.0
    >>> settings.min_cpu_cores
    2

Environment Variables:
    LX_FALLBACK_MEMORY_TOTAL_GB: Fallback total system memory in GB (default: 8.0)
    LX_FALLBACK_MEMORY_AVAILABLE_GB: Fallback available memory in GB (default: 4.0)
    LX_MIN_MEMORY_GB: Minimum recommended system memory in GB (default: 8.0)
    LX_MIN_CPU_CORES: Minimum recommended CPU cores (default: 2)
    LX_MAX_CPU_USAGE: Maximum CPU usage threshold in percent (default: 80.0)
    LX_MIN_GPU_MEMORY_GB: Minimum GPU memory in GB (default: 4.0)
"""

from __future__ import annotations

import os
from dataclasses import dataclass


def _env(name: str, default: str) -> str:
    """Get environment variable with LX_* prefix validation."""
    if not name.startswith("LX_"):
        raise ValueError(f"Only LX_* env vars are allowed, got: {name}")
    return os.getenv(name, default)


def _env_int(name: str, default: int) -> int:
    """Get environment variable as integer."""
    raw = _env(name, str(default))
    try:
        return int(raw)
    except Exception:
        return default


def _env_float(name: str, default: float) -> float:
    """Get environment variable as float."""
    raw = _env(name, str(default))
    try:
        return float(raw)
    except Exception:
        return default


@dataclass(frozen=True)
class Settings:
    """Centralized runtime settings for LoquiLex.

    All values can be overridden via environment variables.
    This dataclass is frozen to prevent accidental mutation at runtime.
    For testing, override environment variables before importing this module,
    or use monkeypatch to modify the module-level `settings` instance.
    """

    # Memory fallback values (used when psutil is unavailable)
    fallback_memory_total_gb: float = _env_float("LX_FALLBACK_MEMORY_TOTAL_GB", 8.0)
    fallback_memory_available_gb: float = _env_float("LX_FALLBACK_MEMORY_AVAILABLE_GB", 4.0)

    # Hardware thresholds
    min_memory_gb: float = _env_float("LX_MIN_MEMORY_GB", 8.0)
    min_cpu_cores: int = _env_int("LX_MIN_CPU_CORES", 2)
    max_cpu_usage_percent: float = _env_float("LX_MAX_CPU_USAGE", 80.0)
    min_gpu_memory_gb: float = _env_float("LX_MIN_GPU_MEMORY_GB", 4.0)


# Module-level instance for convenient access
settings = Settings()

# Re-export existing config modules for backwards compatibility
from loquilex.config.defaults import ASR, MT, RT, SEG, pick_device  # noqa: E402, F401
from loquilex.config.model_defaults import *  # noqa: E402, F401, F403
from loquilex.config.paths import *  # noqa: E402, F401, F403
from loquilex.config.providers import *  # noqa: E402, F401, F403

__all__ = [
    "settings",
    "Settings",
    "ASR",
    "MT",
    "RT", 
    "SEG",
    "pick_device",
]

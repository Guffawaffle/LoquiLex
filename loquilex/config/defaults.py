"""LoquiLex config defaults.

No side effects on import. Values can be overridden via env/.env.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import TypeVar

T = TypeVar("T")


def _env(name: str, default: str) -> str:
    if not name.startswith("LX_"):
        raise ValueError(f"Only LX_* env vars are allowed, got: {name}")
    return os.getenv(name, default)


def _env_bool(name: str, default: bool) -> bool:
    raw = _env(name, str(default))
    return raw.lower() in {"1", "true", "yes", "on"}


def _env_int(name: str, default: int) -> int:
    raw = _env(name, str(default))
    try:
        return int(raw)
    except Exception:
        return default


def _env_float(name: str, default: float) -> float:
    raw = _env(name, str(default))
    try:
        return float(raw)
    except Exception:
        return default


def _env_time_seconds(name: str, default_seconds: float) -> float:
    """Parse time value with unit suffixes (s, ms, m, h) and return seconds."""
    raw = _env(name, str(default_seconds))
    try:
        # Handle plain numbers (assume seconds)
        if raw.isdigit() or (raw.replace(".", "").isdigit()):
            return float(raw)

        # Handle unit suffixes
        raw = raw.strip().lower()
        if raw.endswith("s"):
            # Could be 's' or 'ms'
            if raw.endswith("ms"):
                return float(raw[:-2]) / 1000.0  # milliseconds to seconds
            else:
                return float(raw[:-1])  # seconds
        elif raw.endswith("m"):
            return float(raw[:-1]) * 60.0  # minutes to seconds
        elif raw.endswith("h"):
            return float(raw[:-1]) * 3600.0  # hours to seconds
        else:
            # No recognized suffix, assume seconds
            return float(raw)
    except Exception:
        return default_seconds


def _env_path_absolute(name: str, default: str, legacy_name: str | None = None) -> str:
    """Get an environment variable as an absolute path string.
    
    Resolves relative paths to absolute paths to ensure consistency.
    Supports optional legacy environment variable name as fallback.
    
    Args:
        name: Primary environment variable name
        default: Default value if neither env var is set
        legacy_name: Optional legacy environment variable to check as fallback
    
    Returns:
        Absolute path string
    """
    from pathlib import Path
    
    # Check primary name first, then legacy, then default
    raw = os.getenv(name) or (os.getenv(legacy_name) if legacy_name else None) or default
    return str(Path(raw).expanduser().resolve())


_DEFAULT_SAVE_AUDIO = _env("LX_SAVE_AUDIO", "off")
_DEFAULT_SAVE_AUDIO_PATH = _env("LX_SAVE_AUDIO_PATH", "loquilex/out/session.wav")


@dataclass(frozen=True)
class ASRDefaults:
    language: str = _env("LX_ASR_LANGUAGE", "en")
    model: str = _env("LX_ASR_MODEL", "small.en")
    compute_type: str = _env("LX_ASR_COMPUTE", "float16")
    beam_size: int = _env_int("LX_ASR_BEAM", 1)
    vad_filter: bool = _env_bool("LX_ASR_VAD", True)
    no_speech_threshold: float = _env_float("LX_ASR_NO_SPEECH", 0.6)
    log_prob_threshold: float = _env_float("LX_ASR_LOGPROB", -1.0)
    condition_on_previous_text: bool = _env_bool("LX_ASR_COND_PREV", False)
    sample_rate: int = _env_int("LX_ASR_SAMPLE_RATE", 16000)
    cpu_threads: int = _env_int("LX_ASR_CPU_THREADS", max(1, (os.cpu_count() or 2) - 1))
    word_timestamps: bool = _env_bool("LX_ASR_WORD_TS", True)
    # Streaming-specific settings
    silence_ms: int = _env_int("LX_ASR_SILENCE_MS", 300)
    max_seg_ms: int = _env_int("LX_ASR_MAX_SEG_MS", 10000)
    punctuation: str = _env("LX_ASR_PUNCTUATION", ".?!;:")
    max_partials: int = _env_int("LX_ASR_MAX_PARTIALS", 100)


@dataclass(frozen=True)
class SegmentationDefaults:
    pause_flush_sec: float = _env_float("LX_PAUSE_FLUSH_SEC", 0.7)
    segment_max_sec: float = _env_float("LX_SEGMENT_MAX_SEC", 7.0)
    partial_debounce_ms: int = _env_int("LX_PARTIAL_DEBOUNCE_MS", 250)


@dataclass(frozen=True)
class MTDefaults:
    # Legacy HF model names (for backward compatibility)
    nllb_model: str = _env("LX_NLLB_MODEL", "facebook/nllb-200-distilled-600M")
    m2m_model: str = _env("LX_M2M_MODEL", "facebook/m2m100_418M")
    num_beams: int = _env_int("LX_MT_BEAMS", 1)
    no_repeat_ngram_size: int = _env_int("LX_MT_NO_REPEAT", 2)
    max_input_tokens: int = _env_int("LX_MT_MAX_INPUT", 96)
    max_new_tokens: int = _env_int("LX_MT_MAX_NEW", 96)

    # New CT2-based MT config
    provider: str = _env("LX_MT_PROVIDER", "ct2-nllb")
    model_dir: str = _env("LX_MT_MODEL_DIR", "")
    device: str = _env("LX_MT_DEVICE", "auto")
    compute_type: str = _env("LX_MT_COMPUTE_TYPE", "int8_float16")
    workers: int = _env_int("LX_MT_WORKERS", 2)
    lang_variant_zh: str = _env("LX_LANG_VARIANT_ZH", "Hans")


@dataclass(frozen=True)
class RuntimeDefaults:
    out_dir: str = _env_path_absolute("LX_OUT_DIR", "loquilex/out", "LLX_OUT_DIR")
    hf_cache: str | None = os.getenv("HF_HOME") or os.getenv("HF_DATASETS_CACHE")
    device_preference: str = _env("LX_DEVICE", "auto")  # auto|cuda|cpu
    # streaming controls
    pause_flush_sec: float = _env_float("LX_PAUSE_FLUSH_SEC", 0.7)
    decode_interval_sec: float = _env_float("LX_DECODE_INTERVAL_SEC", 0.25)
    partial_debounce_sec: float = _env_float("LX_PARTIAL_DEBOUNCE_SEC", 0.25)
    max_buffer_sec: float = _env_float("LX_MAX_BUFFER_SEC", 8.0)
    # new IO options
    max_lines: int = _env_int("LX_MAX_LINES", 1000)
    partial_word_cap: int = _env_int("LX_PARTIAL_WORD_CAP", 0)
    save_audio: str = _DEFAULT_SAVE_AUDIO  # off|wav|flac
    save_audio_path: str = _DEFAULT_SAVE_AUDIO_PATH


ASR = ASRDefaults()
SEG = SegmentationDefaults()
MT = MTDefaults()
RT = RuntimeDefaults()


def pick_device() -> tuple[str, str]:
    """Pick (device, dtype).

    Returns (device_str, dtype_str) where dtype_str is either "float16" or "float32".
    """
    pref = RT.device_preference
    try:
        import torch

        has_cuda = torch.cuda.is_available()
    except Exception:
        has_cuda = False

    if pref == "cuda" and has_cuda:
        return ("cuda", "float16")
    if pref == "auto" and has_cuda:
        return ("cuda", "float16")
    return ("cpu", "float32")

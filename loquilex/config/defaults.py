"""LoquiLex config defaults.

No side effects on import. Values can be overridden via env/.env.
"""

from __future__ import annotations

import os
import warnings
from dataclasses import dataclass
from typing import Callable, TypeVar

T = TypeVar("T")


# Module-level deprecation guard
_WARNED_GF = set()


def _warn_once(name_gf: str) -> None:
    if name_gf not in _WARNED_GF:
        warnings.warn(
            f"[LoquiLex] Using legacy env var {name_gf}. Please migrate to LX_*.",
            category=DeprecationWarning,
            stacklevel=2,
        )
        _WARNED_GF.add(name_gf)


def _coerce(val: str, caster: Callable[[str], T]) -> T:
    return caster(val)


def _env_lx_or_gf(name_lx: str, name_gf: str, default: str) -> str:
    if (v := os.getenv(name_lx)) is not None:
        return v
    if name_gf and (v := os.getenv(name_gf)) is not None:
        _warn_once(name_gf)
        return v
    return default

    return default


def _env_bool(name_lx: str, name_gf: str, default: bool) -> bool:
    raw = _env_lx_or_gf(name_lx, name_gf, str(default))
    return raw.lower() in {"1", "true", "yes", "on"}


def _env_int(name_lx: str, name_gf: str, default: int) -> int:
    raw = _env_lx_or_gf(name_lx, name_gf, str(default))
    try:
        return int(raw)
    except Exception:
        return default


def _env_float(name_lx: str, name_gf: str, default: float) -> float:
    raw = _env_lx_or_gf(name_lx, name_gf, str(default))
    try:
        return float(raw)
    except Exception:
        return default


_DEFAULT_SAVE_AUDIO = _env_lx_or_gf("LX_SAVE_AUDIO", "GF_SAVE_AUDIO", "off")
_DEFAULT_SAVE_AUDIO_PATH = _env_lx_or_gf(
    "LX_SAVE_AUDIO_PATH", "GF_SAVE_AUDIO_PATH", "loquilex/out/session.wav"  # fallback default
)


@dataclass(frozen=True)
class ASRDefaults:
    language: str = _env_lx_or_gf("LX_ASR_LANGUAGE", "GF_ASR_LANGUAGE", "en")
    model: str = _env_lx_or_gf("LX_ASR_MODEL", "GF_ASR_MODEL", "small.en")
    compute_type: str = _env_lx_or_gf("LX_ASR_COMPUTE", "GF_ASR_COMPUTE", "float16")
    beam_size: int = _env_int("LX_ASR_BEAM", "GF_ASR_BEAM", 1)
    vad_filter: bool = _env_bool("LX_ASR_VAD", "GF_ASR_VAD", True)
    no_speech_threshold: float = _env_float("LX_ASR_NO_SPEECH", "GF_ASR_NO_SPEECH", 0.6)
    log_prob_threshold: float = _env_float("LX_ASR_LOGPROB", "GF_ASR_LOGPROB", -1.0)
    condition_on_previous_text: bool = _env_bool("LX_ASR_COND_PREV", "GF_ASR_COND_PREV", False)
    sample_rate: int = _env_int("LX_ASR_SAMPLE_RATE", "GF_ASR_SAMPLE_RATE", 16000)
    cpu_threads: int = _env_int(
        "LX_ASR_CPU_THREADS", "GF_ASR_CPU_THREADS", max(1, (os.cpu_count() or 2) - 1)
    )
    word_timestamps: bool = _env_bool("LX_ASR_WORD_TS", "GF_ASR_WORD_TS", False)


@dataclass(frozen=True)
class SegmentationDefaults:
    pause_flush_sec: float = _env_float("LX_PAUSE_FLUSH_SEC", "GF_PAUSE_FLUSH_SEC", 0.7)
    segment_max_sec: float = _env_float("LX_SEGMENT_MAX_SEC", "GF_SEGMENT_MAX_SEC", 7.0)
    partial_debounce_ms: int = _env_int("LX_PARTIAL_DEBOUNCE_MS", "GF_PARTIAL_DEBOUNCE_MS", 250)


@dataclass(frozen=True)
class MTDefaults:
    nllb_model: str = _env_lx_or_gf(
        "LX_NLLB_MODEL", "GF_NLLB_MODEL", "facebook/nllb-200-distilled-600M"
    )
    m2m_model: str = _env_lx_or_gf("LX_M2M_MODEL", "GF_M2M_MODEL", "facebook/m2m100_418M")
    num_beams: int = _env_int("LX_MT_BEAMS", "GF_MT_BEAMS", 1)
    no_repeat_ngram_size: int = _env_int("LX_MT_NO_REPEAT", "GF_MT_NO_REPEAT", 2)
    max_input_tokens: int = _env_int("LX_MT_MAX_INPUT", "GF_MT_MAX_INPUT", 96)
    max_new_tokens: int = _env_int("LX_MT_MAX_NEW", "GF_MT_MAX_NEW", 96)


@dataclass(frozen=True)
class RuntimeDefaults:
    out_dir: str = _env_lx_or_gf("LX_OUT_DIR", "GF_OUT_DIR", "loquilex/out")
    hf_cache: str | None = os.getenv("HF_HOME") or os.getenv("HF_DATASETS_CACHE")
    device_preference: str = _env_lx_or_gf("LX_DEVICE", "GF_DEVICE", "auto")  # auto|cuda|cpu
    # streaming controls
    pause_flush_sec: float = _env_float("LX_PAUSE_FLUSH_SEC", "GF_PAUSE_FLUSH_SEC", 0.7)
    decode_interval_sec: float = _env_float(
        "LX_DECODE_INTERVAL_SEC", "GF_DECODE_INTERVAL_SEC", 0.25
    )
    partial_debounce_sec: float = _env_float(
        "LX_PARTIAL_DEBOUNCE_SEC", "GF_PARTIAL_DEBOUNCE_SEC", 0.25
    )
    max_buffer_sec: float = _env_float("LX_MAX_BUFFER_SEC", "GF_MAX_BUFFER_SEC", 8.0)
    # new IO options
    max_lines: int = _env_int("LX_MAX_LINES", "GF_MAX_LINES", 1000)
    partial_word_cap: int = _env_int("LX_PARTIAL_WORD_CAP", "GF_PARTIAL_WORD_CAP", 0)
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
        import torch  # type: ignore

        has_cuda = torch.cuda.is_available()
    except Exception:
        has_cuda = False

    if pref == "cuda" and has_cuda:
        return ("cuda", "float16")
    if pref == "auto" and has_cuda:
        return ("cuda", "float16")
    return ("cpu", "float32")

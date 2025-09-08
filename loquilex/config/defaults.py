"""LoquiLex config defaults.

No side effects on import. Values can be overridden via env/.env.
"""
from __future__ import annotations

from dataclasses import dataclass
import os
import warnings


def _parse_bool(v: str) -> bool:\n    return v.strip().lower() in {"1", "true", "yes", "on"}


def _get_env(name_new: str, default, *, legacy: str | None = None, cast=None):
    v = os.getenv(name_new)
    if v is not None:
        return cast(v) if cast else v
    if legacy and (lv := os.getenv(legacy)) is not None:
        warnings.warn(f"ENV {legacy} is deprecated; use {name_new}", DeprecationWarning, stacklevel=2)
        return cast(lv) if cast else lv
    return default


def _get_bool(name_new: str, default: bool, *, legacy: str | None = None) -> bool:
    v = os.getenv(name_new)
    if v is not None:
        return _parse_bool(v)
    if legacy and (lv := os.getenv(legacy)) is not None:
        warnings.warn(f"ENV {legacy} is deprecated; use {name_new}", DeprecationWarning, stacklevel=2)
        return _parse_bool(lv)
    return default


_DEFAULT_SAVE_AUDIO = _get_env("LLX_SAVE_AUDIO", "off", legacy="GF_SAVE_AUDIO")
_DEFAULT_SAVE_AUDIO_PATH = _get_env(
    "LLX_SAVE_AUDIO_PATH",
    f"loquilex/out/session.{ 'flac' if _DEFAULT_SAVE_AUDIO == 'flac' else 'wav' }",
    legacy="GF_SAVE_AUDIO_PATH",
)


@dataclass(frozen=True)
class ASRDefaults:
    language: str = _get_env("LLX_ASR_LANGUAGE", "en", legacy="GF_ASR_LANGUAGE")
    model: str = _get_env("LLX_ASR_MODEL", "small.en", legacy="GF_ASR_MODEL")
    compute_type: str = _get_env("LLX_ASR_COMPUTE", "float16", legacy="GF_ASR_COMPUTE")
    beam_size: int = _get_env("LLX_ASR_BEAM", 1, legacy="GF_ASR_BEAM", cast=int)
    vad_filter: bool = _get_bool("LLX_ASR_VAD", True, legacy="GF_ASR_VAD")
    no_speech_threshold: float = _get_env("LLX_ASR_NO_SPEECH", 0.6, legacy="GF_ASR_NO_SPEECH", cast=float)
    log_prob_threshold: float = _get_env("LLX_ASR_LOGPROB", -1.0, legacy="GF_ASR_LOGPROB", cast=float)
    condition_on_previous_text: bool = _get_bool("LLX_ASR_COND_PREV", False, legacy="GF_ASR_COND_PREV")
    sample_rate: int = _get_env("LLX_ASR_SAMPLE_RATE", 16000, legacy="GF_ASR_SAMPLE_RATE", cast=int)
    cpu_threads: int = _get_env("LLX_ASR_CPU_THREADS", max(1, (os.cpu_count() or 2) - 1), legacy="GF_ASR_CPU_THREADS", cast=int)
    word_timestamps: bool = _get_bool("LLX_ASR_WORD_TS", False, legacy="GF_ASR_WORD_TS")


@dataclass(frozen=True)
class SegmentationDefaults:
    pause_flush_sec: float = _get_env("LLX_PAUSE_FLUSH_SEC", 0.7, legacy="GF_PAUSE_FLUSH_SEC", cast=float)
    segment_max_sec: float = _get_env("LLX_SEGMENT_MAX_SEC", 7.0, legacy="GF_SEGMENT_MAX_SEC", cast=float)
    partial_debounce_ms: int = _get_env("LLX_PARTIAL_DEBOUNCE_MS", 250, legacy="GF_PARTIAL_DEBOUNCE_MS", cast=int)


@dataclass(frozen=True)
class MTDefaults:
    nllb_model: str = _get_env("LLX_NLLB_MODEL", "facebook/nllb-200-distilled-600M", legacy="GF_NLLB_MODEL")
    m2m_model: str = _get_env("LLX_M2M_MODEL", "facebook/m2m100_418M", legacy="GF_M2M_MODEL")
    num_beams: int = _get_env("LLX_MT_BEAMS", 1, legacy="GF_MT_BEAMS", cast=int)
    no_repeat_ngram_size: int = _get_env("LLX_MT_NO_REPEAT", 2, legacy="GF_MT_NO_REPEAT", cast=int)
    max_input_tokens: int = _get_env("LLX_MT_MAX_INPUT", 96, legacy="GF_MT_MAX_INPUT", cast=int)
    max_new_tokens: int = _get_env("LLX_MT_MAX_NEW", 96, legacy="GF_MT_MAX_NEW", cast=int)


@dataclass(frozen=True)
class RuntimeDefaults:
    out_dir: str = _get_env("LLX_OUT_DIR", "loquilex/out", legacy="GF_OUT_DIR")
    hf_cache: str | None = os.getenv("HF_HOME") or os.getenv("HF_DATASETS_CACHE")
    device_preference: str = _get_env("LLX_DEVICE", "auto", legacy="GF_DEVICE")  # auto|cuda|cpu
    # streaming controls
    pause_flush_sec: float = _get_env("LLX_PAUSE_FLUSH_SEC", 0.7, legacy="GF_PAUSE_FLUSH_SEC", cast=float)
    decode_interval_sec: float = _get_env("LLX_DECODE_INTERVAL_SEC", 0.25, legacy="GF_DECODE_INTERVAL_SEC", cast=float)
    partial_debounce_sec: float = _get_env("LLX_PARTIAL_DEBOUNCE_SEC", 0.25, legacy="GF_PARTIAL_DEBOUNCE_SEC", cast=float)
    max_buffer_sec: float = _get_env("LLX_MAX_BUFFER_SEC", 8.0, legacy="GF_MAX_BUFFER_SEC", cast=float)
    # new IO options
    max_lines: int = _get_env("LLX_MAX_LINES", 1000, legacy="GF_MAX_LINES", cast=int)
    partial_word_cap: int = _get_env("LLX_PARTIAL_WORD_CAP", 0, legacy="GF_PARTIAL_WORD_CAP", cast=int)
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

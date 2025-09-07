"""Greenfield config defaults.

No side effects on import. Values can be overridden via env/.env.
"""
from __future__ import annotations

from dataclasses import dataclass
import os
_DEFAULT_SAVE_AUDIO = os.getenv("GF_SAVE_AUDIO", "off")
_DEFAULT_SAVE_AUDIO_PATH = os.getenv(
    "GF_SAVE_AUDIO_PATH",
    f"greenfield/out/session.{'flac' if _DEFAULT_SAVE_AUDIO == 'flac' else 'wav'}",
)


def _get_bool(name: str, default: bool) -> bool:
    v = os.getenv(name)
    if v is None:
        return default
    return v.lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class ASRDefaults:
    language: str = os.getenv("GF_ASR_LANGUAGE", "en")
    model: str = os.getenv("GF_ASR_MODEL", "small.en")
    compute_type: str = os.getenv("GF_ASR_COMPUTE", "float16")
    beam_size: int = int(os.getenv("GF_ASR_BEAM", "1"))
    vad_filter: bool = _get_bool("GF_ASR_VAD", True)
    no_speech_threshold: float = float(os.getenv("GF_ASR_NO_SPEECH", "0.6"))
    log_prob_threshold: float = float(os.getenv("GF_ASR_LOGPROB", "-1.0"))
    condition_on_previous_text: bool = _get_bool("GF_ASR_COND_PREV", False)
    sample_rate: int = int(os.getenv("GF_ASR_SAMPLE_RATE", "16000"))
    cpu_threads: int = int(os.getenv("GF_ASR_CPU_THREADS", str(max(1, (os.cpu_count() or 2) - 1))))
    word_timestamps: bool = _get_bool("GF_ASR_WORD_TS", False)


@dataclass(frozen=True)
class SegmentationDefaults:
    pause_flush_sec: float = float(os.getenv("GF_PAUSE_FLUSH_SEC", "0.7"))
    segment_max_sec: float = float(os.getenv("GF_SEGMENT_MAX_SEC", "7.0"))
    partial_debounce_ms: int = int(os.getenv("GF_PARTIAL_DEBOUNCE_MS", "250"))


@dataclass(frozen=True)
class MTDefaults:
    nllb_model: str = os.getenv("GF_NLLB_MODEL", "facebook/nllb-200-distilled-600M")
    m2m_model: str = os.getenv("GF_M2M_MODEL", "facebook/m2m100_418M")
    num_beams: int = int(os.getenv("GF_MT_BEAMS", "1"))
    no_repeat_ngram_size: int = int(os.getenv("GF_MT_NO_REPEAT", "2"))
    max_input_tokens: int = int(os.getenv("GF_MT_MAX_INPUT", "96"))
    max_new_tokens: int = int(os.getenv("GF_MT_MAX_NEW", "96"))


@dataclass(frozen=True)
class RuntimeDefaults:
    out_dir: str = os.getenv("GF_OUT_DIR", "greenfield/out")
    hf_cache: str | None = os.getenv("HF_HOME") or os.getenv("HF_DATASETS_CACHE")
    device_preference: str = os.getenv("GF_DEVICE", "auto")  # auto|cuda|cpu
    # streaming controls
    pause_flush_sec: float = float(os.getenv("GF_PAUSE_FLUSH_SEC", "0.7"))
    decode_interval_sec: float = float(os.getenv("GF_DECODE_INTERVAL_SEC", "0.25"))
    partial_debounce_sec: float = float(os.getenv("GF_PARTIAL_DEBOUNCE_SEC", "0.25"))
    max_buffer_sec: float = float(os.getenv("GF_MAX_BUFFER_SEC", "8.0"))
    # new IO options
    max_lines: int = int(os.getenv("GF_MAX_LINES", "1000"))
    partial_word_cap: int = int(os.getenv("GF_PARTIAL_WORD_CAP", "0"))
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

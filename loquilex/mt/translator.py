from __future__ import annotations

import contextlib
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Optional

from loquilex.config.defaults import MT, pick_device
from loquilex.mt.core.util import normalize_lang
from ..logging import PerformanceMetrics, create_logger


from typing import Any

if TYPE_CHECKING:
    torch: Any
else:
    try:  # optional dependency
        import torch
    except Exception:  # torch might not be installed in test env
        torch = None

if TYPE_CHECKING:  # only for typing; avoid runtime hard dep
    pass


# ============================================================================
# Constants for translation behavior
# ============================================================================

# FLORES-200 language code mappings for NLLB model
NLLB_FLORES_MAP = {
    "en": "eng_Latn",
    "zh-Hans": "zho_Hans",
    "zh-Hant": "zho_Hant",
    "es": "spa_Latn",
    "fr": "fra_Latn",
    "de": "deu_Latn",
    "ja": "jpn_Jpan",
    "ko": "kor_Hang",
    "ru": "rus_Cyrl",
    "ar": "arb_Arab",
}

# M2M language code mappings (simpler format than FLORES)
M2M_LANG_MAP = {
    "en": "en",
    "zh-Hans": "zh",
    "zh-Hant": "zh",
    "es": "es",
    "fr": "fr",
    "de": "de",
    "ja": "ja",
    "ko": "ko",
    "ru": "ru",
    "ar": "ar",
}

# Draft mode generation parameters for faster low-latency translation
DRAFT_MAX_TOKENS = 48  # Maximum tokens for draft quality translations
DRAFT_NO_REPEAT_NGRAM_SIZE = 0  # Disable n-gram repetition penalty for speed


def _log(msg: str) -> None:
    print(f"[mt] {msg}")


def _dtype_kwargs(torch_mod, device_str: str):
    """Return a version-aware dtype kwarg for transformers.from_pretrained.

    Newer transformers deprecate torch_dtype in favor of dtype. Choose based on version.
    """
    import transformers as tr  # soft dependency

    try:
        major, minor, *_ = (int(x) for x in tr.__version__.split("."))
    except Exception:
        major, minor = 4, 0
    key = "dtype" if (major, minor) >= (4, 56) else "torch_dtype"
    if torch_mod is None:
        # Let HF default dtype if torch isn't available
        return {}
    val = torch_mod.float16 if device_str == "cuda" else torch_mod.float32
    return {key: val}


@dataclass
class TranslationResult:
    text: str
    model: str
    src_lang: str
    tgt_lang: str
    duration_ms: float
    confidence: Optional[float] = None


class Translator:
    def __init__(self, session_id: Optional[str] = None) -> None:
        device, _ = pick_device()
        self.device_str = device
        is_cuda = False
        if torch is not None and device == "cuda":
            try:
                is_cuda = torch.cuda.is_available()
            except Exception:
                is_cuda = False
        self.torch_device = "cuda" if is_cuda else "cpu"
        self._nllb = None
        self._m2m = None

        # Initialize structured logging and metrics
        self.logger = create_logger(
            component="mt_translator",
            session_id=session_id,
        )
        self.metrics = PerformanceMetrics(
            logger=self.logger,
            component="mt_translator",
        )

        # Set performance thresholds for MT latency
        self.metrics.set_threshold("translation_latency", warning=1500.0, critical=3000.0)
        self.metrics.set_threshold("model_load_time", warning=10000.0, critical=30000.0)

        self.logger.info(
            "Translator initialized",
            device=self.device_str,
            torch_device=self.torch_device,
            cuda_available=is_cuda,
        )

    def translate(
        self,
        text: str,
        src_lang: str = "en",
        tgt_lang: str = "zh",
        quality: str = "final",
    ) -> TranslationResult:
        """Generic translation method supporting any language pair.

        Args:
            text: Text to translate
            src_lang: Source language code (e.g., 'en', 'zh', 'es')
            tgt_lang: Target language code (e.g., 'zh', 'en', 'es')
            quality: Translation quality mode ('final' or 'realtime'/'draft')

        Returns:
            TranslationResult with translated text and metadata

        Example:
            tr = Translator()
            result = tr.translate("Hello", src_lang="en", tgt_lang="zh", quality="final")
            result = tr.translate("你好", src_lang="zh", tgt_lang="en", quality="draft")
        """
        text = text.strip()
        if not text:
            return TranslationResult(
                "",
                "echo",
                src_lang=src_lang,
                tgt_lang=tgt_lang,
                duration_ms=0.0,
            )

        self.logger.debug(
            "Starting generic translation",
            text_length=len(text),
            src_lang=src_lang,
            tgt_lang=tgt_lang,
            quality=quality,
        )

        self.metrics.start_timer("translation_latency")

        # Normalize language codes (map "zh" → "zh-Hans" based on variant config)
        try:
            src = normalize_lang(src_lang)
            tgt = normalize_lang(tgt_lang)
        except ValueError as e:
            self.logger.error(f"Unsupported language: {e}")
            # Echo fallback
            return TranslationResult(
                text,
                "echo",
                src_lang=src_lang,
                tgt_lang=tgt_lang,
                duration_ms=0.0,
            )

        # Determine translation strategy based on quality and language pair
        is_draft = quality in ("realtime", "draft")

        # Use generic provider-based translation for all language pairs
        # Try NLLB first (supports more language pairs)
        try:
            tok, model = self._load_nllb()

            src_flores = NLLB_FLORES_MAP.get(src, "eng_Latn")
            tgt_flores = NLLB_FLORES_MAP.get(tgt, "zho_Hans")

            tok.src_lang = src_flores
            inputs = tok(text, return_tensors="pt", truncation=True, max_length=MT.max_input_tokens)
            inputs = {k: v.to(self.torch_device) for k, v in inputs.items()}
            cm = torch.no_grad() if torch is not None else contextlib.nullcontext()

            # Adjust generation params based on quality
            beam_size = 1 if is_draft else MT.num_beams
            max_tokens = min(DRAFT_MAX_TOKENS, MT.max_new_tokens) if is_draft else MT.max_new_tokens

            with cm:
                gen = model.generate(
                    **inputs,
                    forced_bos_token_id=tok.convert_tokens_to_ids(tgt_flores),
                    num_beams=beam_size,
                    no_repeat_ngram_size=MT.no_repeat_ngram_size if not is_draft else DRAFT_NO_REPEAT_NGRAM_SIZE,
                    max_new_tokens=max_tokens,
                )
            out = tok.batch_decode(gen, skip_special_tokens=True)[0]

            duration_ms = self.metrics.end_timer("translation_latency")
            self.metrics.increment_counter("translations_success")

            result = TranslationResult(
                out,
                f"{MT.nllb_model}:{quality}",
                src_lang=src,
                tgt_lang=tgt,
                duration_ms=duration_ms,
            )

            self.logger.info(
                "Translation completed successfully",
                method="nllb",
                src_lang=src,
                tgt_lang=tgt,
                quality=quality,
                input_length=len(text),
                output_length=len(out),
                duration_ms=duration_ms,
            )

            return result

        except Exception as e:
            self.logger.warning(
                "NLLB translation failed, trying M2M",
                error=str(e),
                src_lang=src,
                tgt_lang=tgt,
            )

        # Try M2M fallback
        try:
            tok, model = self._load_m2m()

            src_m2m = M2M_LANG_MAP.get(src, "en")
            tgt_m2m = M2M_LANG_MAP.get(tgt, "zh")

            tok.src_lang = src_m2m
            inputs = tok(text, return_tensors="pt", truncation=True, max_length=MT.max_input_tokens)
            inputs = {k: v.to(self.torch_device) for k, v in inputs.items()}
            cm = torch.no_grad() if torch is not None else contextlib.nullcontext()

            beam_size = 1 if is_draft else MT.num_beams
            max_tokens = min(DRAFT_MAX_TOKENS, MT.max_new_tokens) if is_draft else MT.max_new_tokens

            with cm:
                gen = model.generate(
                    **inputs,
                    forced_bos_token_id=tok.get_lang_id(tgt_m2m),
                    num_beams=beam_size,
                    max_new_tokens=max_tokens,
                    pad_token_id=getattr(tok, "pad_token_id", None),
                )
            out = tok.batch_decode(gen, skip_special_tokens=True)[0]

            duration_ms = self.metrics.end_timer("translation_latency")
            self.metrics.increment_counter("translations_success")

            result = TranslationResult(
                out,
                f"{MT.m2m_model}:{quality}",
                src_lang=src,
                tgt_lang=tgt,
                duration_ms=duration_ms,
            )

            self.logger.info(
                "Translation completed successfully",
                method="m2m",
                src_lang=src,
                tgt_lang=tgt,
                quality=quality,
                input_length=len(text),
                output_length=len(out),
                duration_ms=duration_ms,
            )

            return result

        except Exception as e:
            self.logger.error(
                "Both NLLB and M2M translation failed",
                error=str(e),
                src_lang=src,
                tgt_lang=tgt,
            )
            self.metrics.increment_counter("translations_failed")
            duration_ms = self.metrics.end_timer("translation_latency")

        # Echo fallback
        return TranslationResult(
            text,
            "echo",
            src_lang=src,
            tgt_lang=tgt,
            duration_ms=duration_ms,
        )

    def _load_nllb(self):
        if self._nllb is None:
            self.logger.info("Loading NLLB model", model=MT.nllb_model)
            self.metrics.start_timer("model_load_nllb")

            try:
                from transformers import AutoModelForSeq2SeqLM, AutoTokenizer

                tok = AutoTokenizer.from_pretrained(MT.nllb_model, use_safetensors=True)
                model = AutoModelForSeq2SeqLM.from_pretrained(
                    MT.nllb_model,
                    device_map=None,
                    **_dtype_kwargs(torch, self.torch_device),
                )
                model.to(self.torch_device).eval()
                self._nllb = (tok, model)

                load_time_ms = self.metrics.end_timer("model_load_nllb")
                self.logger.info(
                    "NLLB model loaded successfully",
                    model=MT.nllb_model,
                    load_time_ms=load_time_ms,
                    device=self.torch_device,
                )
                _log(f"loaded={MT.nllb_model}")

            except Exception as e:
                self.logger.error(
                    "Failed to load NLLB model",
                    model=MT.nllb_model,
                    error=str(e),
                )
                raise
        return self._nllb

    def _load_m2m(self):
        if self._m2m is None:
            self.logger.info("Loading M2M model", model=MT.m2m_model)
            self.metrics.start_timer("model_load_m2m")

            try:
                from transformers import M2M100ForConditionalGeneration, M2M100Tokenizer

                tok = M2M100Tokenizer.from_pretrained(MT.m2m_model, use_safetensors=True)
                model = M2M100ForConditionalGeneration.from_pretrained(
                    MT.m2m_model,
                    device_map=None,
                    **_dtype_kwargs(torch, self.torch_device),
                )
                model.to(self.torch_device).eval()
                self._m2m = (tok, model)

                load_time_ms = self.metrics.end_timer("model_load_m2m")
                self.logger.info(
                    "M2M model loaded successfully",
                    model=MT.m2m_model,
                    load_time_ms=load_time_ms,
                    device=self.torch_device,
                )
                _log(f"loaded={MT.m2m_model}")

            except Exception as e:
                self.logger.error(
                    "Failed to load M2M model",
                    model=MT.m2m_model,
                    error=str(e),
                )
                raise
        return self._m2m

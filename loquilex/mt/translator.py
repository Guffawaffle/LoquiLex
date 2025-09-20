from __future__ import annotations

import contextlib
import time
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Optional

from loquilex.config.defaults import MT, pick_device
from ..logging import StructuredLogger, PerformanceMetrics, create_logger #noqa: F401


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

    def translate_en_to_zh(self, text: str) -> TranslationResult:
        text = text.strip()
        if not text:
            return TranslationResult(
                "",
                "echo",
                src_lang="en",
                tgt_lang="zh",
                duration_ms=0.0,
            )

        self.logger.debug(
            "Starting translation",
            text_length=len(text),
            src_lang="en",
            tgt_lang="zh",
        )

        start_time = time.time() #noqa: F841
        self.metrics.start_timer("translation_latency")

        # Try NLLB first
        try:
            tok, model = self._load_nllb()
            tok.src_lang = "eng_Latn"
            inputs = tok(text, return_tensors="pt", truncation=True, max_length=MT.max_input_tokens)
            inputs = {k: v.to(self.torch_device) for k, v in inputs.items()}
            cm = torch.no_grad() if torch is not None else contextlib.nullcontext()
            with cm:
                gen = model.generate(
                    **inputs,
                    forced_bos_token_id=tok.convert_tokens_to_ids("zho_Hans"),
                    num_beams=MT.num_beams,
                    no_repeat_ngram_size=MT.no_repeat_ngram_size,
                    max_new_tokens=MT.max_new_tokens,
                )
            out = tok.batch_decode(gen, skip_special_tokens=True)[0]

            duration_ms = self.metrics.end_timer("translation_latency")
            self.metrics.increment_counter("translations_success")

            result = TranslationResult(
                out,
                MT.nllb_model,
                src_lang="en",
                tgt_lang="zh",
                duration_ms=duration_ms,
            )

            self.logger.info(
                "Translation completed successfully",
                method="nllb",
                input_length=len(text),
                output_length=len(out),
                duration_ms=duration_ms,
            )

            return result

        except Exception as e:
            self.logger.warning(
                "NLLB translation failed, trying M2M",
                error=str(e),
                text_length=len(text),
            )
            self.metrics.increment_counter("nllb_failures")

        # Fallback M2M
        try:
            tok, model = self._load_m2m()
            tok.src_lang = "en"
            inputs = tok(text, return_tensors="pt", truncation=True, max_length=MT.max_input_tokens)
            inputs = {k: v.to(self.torch_device) for k, v in inputs.items()}
            cm = torch.no_grad() if torch is not None else contextlib.nullcontext()
            with cm:
                gen = model.generate(
                    **inputs,
                    forced_bos_token_id=tok.get_lang_id("zh"),
                    num_beams=max(1, min(2, MT.num_beams)),
                    no_repeat_ngram_size=MT.no_repeat_ngram_size,
                    max_new_tokens=MT.max_new_tokens,
                )
            out = tok.batch_decode(gen, skip_special_tokens=True)[0]

            duration_ms = self.metrics.end_timer("translation_latency")
            self.metrics.increment_counter("translations_success")

            result = TranslationResult(
                out,
                MT.m2m_model,
                src_lang="en",
                tgt_lang="zh",
                duration_ms=duration_ms,
            )

            self.logger.info(
                "Translation completed successfully",
                method="m2m",
                input_length=len(text),
                output_length=len(out),
                duration_ms=duration_ms,
            )

            return result

        except Exception as e:
            self.logger.error(
                "Both NLLB and M2M translation failed",
                error=str(e),
                text_length=len(text),
            )
            self.metrics.increment_counter("translations_failed")
            duration_ms = self.metrics.end_timer("translation_latency")

        # Echo fallback
        return TranslationResult(
            text,
            "echo",
            src_lang="en",
            tgt_lang="zh",
            duration_ms=duration_ms,
        )

    def translate_en_to_zh_draft(self, text: str) -> TranslationResult:
        """Low-latency 'draft' translation for live partials.

        Prioritize speed: beam_size=1, shorter max_new_tokens, minimal constraints.
        Try M2M first (often faster on CPU), then NLLB, then echo.
        """
        text = text.strip()
        if not text:
            return TranslationResult(
                "",
                "echo",
                src_lang="en",
                tgt_lang="zh",
                duration_ms=0.0,
            )

        # Draft via M2M
        try:
            tok, model = self._load_m2m()
            tok.src_lang = "en"
            inputs = tok(
                text, return_tensors="pt", truncation=True, max_length=min(64, MT.max_input_tokens)
            )
            inputs = {k: v.to(self.torch_device) for k, v in inputs.items()}
            cm = torch.no_grad() if torch is not None else contextlib.nullcontext()
            with cm:
                gen = model.generate(
                    **inputs,
                    forced_bos_token_id=tok.get_lang_id("zh"),
                    num_beams=1,
                    max_new_tokens=min(48, MT.max_new_tokens),
                    pad_token_id=getattr(tok, "pad_token_id", None),
                )
            out = tok.batch_decode(gen, skip_special_tokens=True)[0]
            return TranslationResult(
                out,
                f"{MT.m2m_model}:draft",
                src_lang="en",
                tgt_lang="zh",
                duration_ms=0.0,
            )
        except Exception as e:
            _log(f"m2m draft failed: {e}")

        # Draft via NLLB
        try:
            tok, model = self._load_nllb()
            tok.src_lang = "eng_Latn"
            inputs = tok(
                text, return_tensors="pt", truncation=True, max_length=min(64, MT.max_input_tokens)
            )
            inputs = {k: v.to(self.torch_device) for k, v in inputs.items()}
            cm = torch.no_grad() if torch is not None else contextlib.nullcontext()
            with cm:
                gen = model.generate(
                    **inputs,
                    forced_bos_token_id=tok.convert_tokens_to_ids("zho_Hans"),
                    num_beams=1,
                    max_new_tokens=min(48, MT.max_new_tokens),
                    pad_token_id=getattr(tok, "pad_token_id", None),
                )
            out = tok.batch_decode(gen, skip_special_tokens=True)[0]
            return TranslationResult(
                out,
                f"{MT.nllb_model}:draft",
                src_lang="en",
                tgt_lang="zh",
                duration_ms=0.0,
            )
        except Exception as e:
            _log(f"nllb draft failed: {e}")

        return TranslationResult(
            text,
            "echo:draft",
            src_lang="en",
            tgt_lang="zh",
            duration_ms=0.0,
        )

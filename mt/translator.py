from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from greenfield.config.defaults import MT, pick_device
import torch


def _log(msg: str) -> None:
    print(f"[mt] {msg}")


def _dtype_kwargs(torch, device_str: str):
    """Return a version-aware dtype kwarg for transformers.from_pretrained.

    Newer transformers deprecate torch_dtype in favor of dtype. Choose based on version.
    """
    import transformers as tr  # type: ignore

    try:
        major, minor, *_ = (int(x) for x in tr.__version__.split("."))
    except Exception:
        major, minor = 4, 0
    key = "dtype" if (major, minor) >= (4, 56) else "torch_dtype"
    val = torch.float16 if device_str == "cuda" else torch.float32
    return {key: val}


@dataclass
class TranslationResult:
    text: str
    model: str


class Translator:
    def __init__(self) -> None:
        device, _ = pick_device()
        self.device_str = device
        self.torch_device = (
            torch.device("cuda") if device == "cuda" and torch.cuda.is_available() else torch.device("cpu")
        )
        self._nllb = None
        self._m2m = None

    def _load_nllb(self):
        if self._nllb is None:
            from transformers import AutoTokenizer, AutoModelForSeq2SeqLM  # type: ignore

            tok = AutoTokenizer.from_pretrained(MT.nllb_model, use_safetensors=True)
            model = AutoModelForSeq2SeqLM.from_pretrained(
                MT.nllb_model,
                device_map=None,
                **_dtype_kwargs(torch, self.torch_device.type),
            )
            model.to(self.torch_device).eval()
            self._nllb = (tok, model)
            _log(f"loaded={MT.nllb_model}")
        return self._nllb

    def _load_m2m(self):
        if self._m2m is None:
            from transformers import M2M100Tokenizer, M2M100ForConditionalGeneration  # type: ignore

            tok = M2M100Tokenizer.from_pretrained(MT.m2m_model, use_safetensors=True)
            model = M2M100ForConditionalGeneration.from_pretrained(
                MT.m2m_model,
                device_map=None,
                **_dtype_kwargs(torch, self.torch_device.type),
            )
            model.to(self.torch_device).eval()
            self._m2m = (tok, model)
            _log(f"loaded={MT.m2m_model}")
        return self._m2m

    def translate_en_to_zh(self, text: str) -> TranslationResult:
        text = text.strip()
        if not text:
            return TranslationResult("", "echo")
        # Try NLLB first
        try:
            tok, model = self._load_nllb()
            tok.src_lang = "eng_Latn"
            inputs = tok(text, return_tensors="pt", truncation=True, max_length=MT.max_input_tokens)
            inputs = {k: v.to(self.torch_device) for k, v in inputs.items()}
            with torch.no_grad():
                gen = model.generate(
                    **inputs,
                    forced_bos_token_id=tok.convert_tokens_to_ids("zho_Hans"),
                    num_beams=MT.num_beams,
                    no_repeat_ngram_size=MT.no_repeat_ngram_size,
                    max_new_tokens=MT.max_new_tokens,
                )
            out = tok.batch_decode(gen, skip_special_tokens=True)[0]
            return TranslationResult(out, MT.nllb_model)
        except Exception as e:
            _log(f"nllb failed: {e}")

        # Fallback M2M
        try:
            tok, model = self._load_m2m()
            tok.src_lang = "en"
            inputs = tok(text, return_tensors="pt", truncation=True, max_length=MT.max_input_tokens)
            inputs = {k: v.to(self.torch_device) for k, v in inputs.items()}
            with torch.no_grad():
                gen = model.generate(
                    **inputs,
                    forced_bos_token_id=tok.get_lang_id("zh"),
                    num_beams=max(1, min(2, MT.num_beams)),
                    no_repeat_ngram_size=MT.no_repeat_ngram_size,
                    max_new_tokens=MT.max_new_tokens,
                )
            out = tok.batch_decode(gen, skip_special_tokens=True)[0]
            return TranslationResult(out, MT.m2m_model)
        except Exception as e:
            _log(f"m2m failed: {e}")

        # Echo fallback
        return TranslationResult(text, "echo")

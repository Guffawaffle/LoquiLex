"""NLLB tokenizer adapter."""

from __future__ import annotations

from ..core.types import Lang

# FLORES language codes for NLLB
FLORES = {"en": "eng_Latn", "zh-Hans": "zho_Hans", "zh-Hant": "zho_Hant"}


class NLLBTokenizerAdapter:
    """Tokenizer adapter for NLLB models."""

    def __init__(self, name: str = "facebook/nllb-200-distilled-600M"):
        # Lazy import to avoid heavy dependency on module load
        try:
            from transformers import AutoTokenizer
        except ImportError:
            raise ImportError("transformers package required for NLLB tokenizer")

        self._tok = AutoTokenizer.from_pretrained(name)

    def encode(self, text: str, src: Lang) -> list[str]:
        """Encode text with source language setting."""
        self._tok.src_lang = FLORES[src]
        return self._tok.convert_ids_to_tokens(self._tok.encode(text))

    def target_prefix(self, tgt: Lang) -> list[str]:
        """Get target language prefix token."""
        return [FLORES[tgt]]

    def decode(self, tokens: list[str]) -> str:
        """Decode tokens, stripping language prefixes if present."""
        # NLLB may emit the language tag as first token; drop if present
        if tokens and tokens[0] in FLORES.values():
            tokens = tokens[1:]
        ids = self._tok.convert_tokens_to_ids(tokens)
        return self._tok.decode(ids, skip_special_tokens=True)

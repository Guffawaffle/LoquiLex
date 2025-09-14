"""M2M tokenizer adapter."""

from __future__ import annotations

from ..core.types import Lang


class M2MTokenizerAdapter:
    """Tokenizer adapter for M2M100 models."""
    
    def __init__(self, name: str = "facebook/m2m100_418M"):
        # Lazy import to avoid heavy dependency on module load
        try:
            from transformers import AutoTokenizer
        except ImportError:
            raise ImportError("transformers package required for M2M tokenizer")
        
        self._tok = AutoTokenizer.from_pretrained(name)
    
    def encode(self, text: str, src: Lang) -> list[str]:
        """Encode text with source language setting."""
        # M2M uses simpler language codes
        self._tok.src_lang = "en" if src == "en" else "zh"
        return self._tok.convert_ids_to_tokens(self._tok.encode(text))
    
    def target_prefix(self, tgt: Lang) -> list[str]:
        """Get target language prefix token."""
        code = "en" if tgt == "en" else "zh"
        return [self._tok.lang_code_to_token[code]]
    
    def decode(self, tokens: list[str]) -> str:
        """Decode tokens, stripping BOS token if present."""
        # Strip possible target lang token at position 0
        if tokens and tokens[0].startswith("__"):
            tokens = tokens[1:]
        ids = self._tok.convert_tokens_to_ids(tokens)
        return self._tok.decode(ids, skip_special_tokens=True)
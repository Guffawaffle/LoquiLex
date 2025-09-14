"""CTranslate2 provider for M2M100 models."""

from __future__ import annotations

import os
from typing import Iterable, Iterator

from ..core.protocol import MTProvider, ProviderCapabilities
from ..core.types import Lang, QualityMode, MTModelLoadError, MTProviderError
from ..core.registry import register_provider
from ..tokenizers.m2m import M2MTokenizerAdapter


class CT2M2MProvider:
    """CTranslate2 provider for M2M100 models."""

    def __init__(self):
        self._model = None
        self._tokenizer = None
        self._model_dir = os.getenv("LX_MT_MODEL_DIR")
        self._device = os.getenv("LX_MT_DEVICE", "auto")
        self._compute_type = os.getenv("LX_MT_COMPUTE_TYPE", "int8_float16")
        self._workers = int(os.getenv("LX_MT_WORKERS", "2"))

        if not self._model_dir:
            raise MTModelLoadError(
                "LX_MT_MODEL_DIR environment variable required: set to the path of the directory containing converted CTranslate2 model files"
            )

    def _load_model(self):
        """Lazy load the CT2 model and tokenizer."""
        if self._model is not None:
            return

        try:
            # Lazy import CT2 to avoid heavy dependency on module load
            import ctranslate2 as ct2  # type: ignore[import-untyped]
        except ImportError:
            raise ImportError("ctranslate2 package required for CT2 provider")

        try:
            # Resolve device
            device = self._device
            if device == "auto":
                device = "cuda" if ct2.get_cuda_device_count() > 0 else "cpu"

            self._model = ct2.Translator(
                self._model_dir,
                device=device,
                compute_type=self._compute_type,
                inter_threads=self._workers,
            )

            self._tokenizer = M2MTokenizerAdapter()

        except Exception as e:
            raise MTModelLoadError(f"Failed to load M2M model: {e}")

    def translate_text(
        self, text: str, src: Lang, tgt: Lang, *, quality: QualityMode = "realtime"
    ) -> str:
        """Translate single text string."""
        if not text.strip():
            return ""

        self._load_model()

        try:
            # Encode source text
            tokens = self._tokenizer.encode(text, src)

            # Get target prefix
            target_prefix = self._tokenizer.target_prefix(tgt)

            # Translate with CT2
            beam_size = 1 if quality == "realtime" else 2
            results = self._model.translate_batch(
                [tokens],
                target_prefix=[target_prefix],
                beam_size=beam_size,
                max_decoding_length=256,
            )

            # Decode result
            result_tokens = results[0].hypotheses[0]
            return self._tokenizer.decode(result_tokens)

        except Exception as e:
            raise MTProviderError(f"Translation failed: {e}")

    def translate_chunked(
        self, chunks: Iterable[str], src: Lang, tgt: Lang, *, quality: QualityMode = "realtime"
    ) -> Iterator[str]:
        """Translate sequence of text chunks."""
        for chunk in chunks:
            if chunk.strip():
                yield self.translate_text(chunk, src, tgt, quality=quality)
            else:
                yield ""

    def capabilities(self) -> ProviderCapabilities:
        """Get provider capabilities."""
        return {
            "family": "m2m",
            "model_name": "m2m100_418M",
            "directions": [
                ("en", "zh-Hans"),
                ("zh-Hans", "en"),
                ("en", "zh-Hant"),
                ("zh-Hant", "en"),
            ],
            "requires_target_prefix": True,
            "device_types": ["cpu", "cuda"],
            "compute_types": ["int8", "int8_float16", "float16", "float32"],
            "supports_chunked": True,
            "supports_streaming_partials": False,
        }


def _create_ct2_m2m_provider() -> MTProvider:
    """Factory function for CT2 M2M provider."""
    return CT2M2MProvider()


# Register provider on module import
register_provider("ct2-m2m", _create_ct2_m2m_provider)

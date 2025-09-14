"""MT service layer for higher-level translation operations."""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Iterator, Optional

from .core import create, available, Lang, QualityMode
from .core.types import MTModelLoadError
from .core.util import normalize_lang


@dataclass
class TranslationResult:
    """Translation result with metadata."""

    text: str
    provider: str
    quality: QualityMode
    src_lang: Lang
    tgt_lang: Lang


class MTService:
    """High-level MT service using the new provider architecture."""

    def __init__(self, provider_name: Optional[str] = None):
        """Initialize MT service with specified or default provider."""
        self._provider_name = provider_name or os.getenv("LX_MT_PROVIDER", "ct2-nllb")
        self._provider = None
        self._provider_available = None

    def _get_provider(self):
        """Lazy load the MT provider."""
        if self._provider is None:
            # Check if provider is available
            if self._provider_available is None:
                self._provider_available = self._provider_name in available()

            if not self._provider_available:
                # Fall back to available providers or raise error
                available_providers = available()
                if not available_providers:
                    raise MTModelLoadError("No MT providers available")

                # Try to use first available provider
                fallback = available_providers[0]
                self._provider_name = fallback
                self._provider_available = True

            self._provider = create(self._provider_name)

        return self._provider

    def is_available(self) -> bool:
        """Check if MT service is available (has working provider)."""
        try:
            self._get_provider()
            return True
        except Exception:
            return False

    def get_provider_name(self) -> str:
        """Get the name of the active provider."""
        return self._provider_name or "unknown"

    def translate_text(
        self, text: str, src_lang: str, tgt_lang: str, *, quality: QualityMode = "realtime"
    ) -> TranslationResult:
        """Translate a single text string."""
        if not text.strip():
            return TranslationResult("", "echo", quality, "en", "en")

        try:
            provider = self._get_provider()

            # Normalize language codes
            src = normalize_lang(src_lang)
            tgt = normalize_lang(tgt_lang)

            # Translate using provider
            result_text = provider.translate_text(text, src, tgt, quality=quality)

            return TranslationResult(
                text=result_text,
                provider=self._provider_name or "unknown",
                quality=quality,
                src_lang=src,
                tgt_lang=tgt,
            )

        except Exception:
            # Fall back to echo on any error
            return TranslationResult(
                text=text, provider="echo", quality=quality, src_lang="en", tgt_lang="en"
            )

    def translate_chunked(
        self, chunks: list[str], src_lang: str, tgt_lang: str, *, quality: QualityMode = "realtime"
    ) -> Iterator[TranslationResult]:
        """Translate a sequence of text chunks."""
        if not chunks:
            return

        try:
            provider = self._get_provider()

            # Normalize language codes
            src = normalize_lang(src_lang)
            tgt = normalize_lang(tgt_lang)

            # Translate chunks using provider
            results = provider.translate_chunked(chunks, src, tgt, quality=quality)

            for result_text in results:
                yield TranslationResult(
                    text=result_text,
                    provider=self._provider_name or "unknown",
                    quality=quality,
                    src_lang=src,
                    tgt_lang=tgt,
                )

        except Exception:
            # Fall back to echo on any error
            for chunk in chunks:
                yield TranslationResult(
                    text=chunk, provider="echo", quality=quality, src_lang="en", tgt_lang="en"
                )

    def get_capabilities(self):
        """Get capabilities of the active provider."""
        try:
            provider = self._get_provider()
            return provider.capabilities()
        except Exception:
            return None


# Singleton instance for backward compatibility
_default_service = None


def get_mt_service() -> MTService:
    """Get the default MT service instance."""
    global _default_service
    if _default_service is None:
        _default_service = MTService()
    return _default_service


# Legacy compatibility functions
def translate_en_to_zh(text: str) -> TranslationResult:
    """Legacy function for backward compatibility."""
    service = get_mt_service()
    return service.translate_text(text, "en", "zh-Hans", quality="realtime")


def translate_en_to_zh_draft(text: str) -> TranslationResult:
    """Legacy function for backward compatibility."""
    service = get_mt_service()
    return service.translate_text(text, "en", "zh-Hans", quality="realtime")

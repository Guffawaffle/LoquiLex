"""Contract tests for MT providers.

These tests verify that all providers implement the same behavior.
"""

from __future__ import annotations

from typing import Iterable

from ..core.protocol import MTProvider
from ..core.types import Lang, QualityMode, MTError


class MTProviderContractTests:
    """Shared test suite for all MT providers."""

    def provider(self) -> MTProvider:
        """Override in subclasses to provide the provider under test."""
        raise NotImplementedError("Subclasses must implement provider()")

    def test_translate_text_basic(self):
        """Test basic text translation."""
        provider = self.provider()

        # Test English to Chinese
        result = provider.translate_text("Hello", "en", "zh-Hans")
        assert isinstance(result, str)
        assert len(result) > 0

        # Test Chinese to English
        result = provider.translate_text("你好", "zh-Hans", "en")
        assert isinstance(result, str)
        assert len(result) > 0

    def test_translate_text_empty(self):
        """Test translation of empty/whitespace text."""
        provider = self.provider()

        assert provider.translate_text("", "en", "zh-Hans") == ""
        assert provider.translate_text("   ", "en", "zh-Hans") == ""

    def test_translate_chunked(self):
        """Test chunked translation."""
        provider = self.provider()

        chunks = ["Hello", "world", ""]
        results = list(provider.translate_chunked(chunks, "en", "zh-Hans"))

        assert len(results) == 3
        assert isinstance(results[0], str) and len(results[0]) > 0
        assert isinstance(results[1], str) and len(results[1]) > 0
        assert results[2] == ""  # Empty chunk stays empty

    def test_quality_modes(self):
        """Test different quality modes."""
        provider = self.provider()

        text = "Hello world"

        # Both modes should work
        realtime = provider.translate_text(text, "en", "zh-Hans", quality="realtime")
        quality = provider.translate_text(text, "en", "zh-Hans", quality="quality")

        assert isinstance(realtime, str)
        assert isinstance(quality, str)

    def test_capabilities(self):
        """Test provider capabilities."""
        provider = self.provider()
        caps = provider.capabilities()

        # Check required fields
        assert "family" in caps
        assert "model_name" in caps
        assert "directions" in caps
        assert "requires_target_prefix" in caps
        assert "device_types" in caps
        assert "compute_types" in caps
        assert "supports_chunked" in caps
        assert "supports_streaming_partials" in caps

        # Check EN<->ZH directions supported
        directions = caps["directions"]
        assert ("en", "zh-Hans") in directions
        assert ("zh-Hans", "en") in directions

    def test_language_variants(self):
        """Test Chinese language variants."""
        provider = self.provider()
        caps = provider.capabilities()

        # If provider supports traditional Chinese, test it
        if ("en", "zh-Hant") in caps["directions"]:
            result = provider.translate_text("Hello", "en", "zh-Hant")
            assert isinstance(result, str)
            assert len(result) > 0


# Fake provider for unit testing without heavy dependencies
class FakeMTProvider:
    """Fake MT provider for testing without real models."""

    def translate_text(
        self, text: str, src: Lang, tgt: Lang, *, quality: QualityMode = "realtime"  # noqa: ARG002
    ) -> str:
        if not text.strip():
            return ""

        if src == "en" and tgt in ("zh-Hans", "zh-Hant"):
            return f"[{tgt}]{text}"
        elif src in ("zh-Hans", "zh-Hant") and tgt == "en":
            return f"[en]{text}"
        else:
            raise MTError(f"Unsupported direction: {src} -> {tgt}")

    def translate_chunked(
        self,
        chunks: Iterable[str],
        src: Lang,
        tgt: Lang,
        *,
        quality: QualityMode = "realtime",  # noqa: ARG002
    ):
        for chunk in chunks:
            yield self.translate_text(chunk, src, tgt, quality=quality)

    def capabilities(self):
        return {
            "family": "fake",
            "model_name": "fake-test-provider",
            "directions": [
                ("en", "zh-Hans"),
                ("zh-Hans", "en"),
                ("en", "zh-Hant"),
                ("zh-Hant", "en"),
            ],
            "requires_target_prefix": True,
            "device_types": ["cpu"],
            "compute_types": ["fake"],
            "supports_chunked": True,
            "supports_streaming_partials": False,
        }


class TestFakeProvider(MTProviderContractTests):
    """Test fake provider to verify contract tests work."""

    def provider(self) -> MTProvider:
        return FakeMTProvider()

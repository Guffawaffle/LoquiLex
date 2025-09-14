"""Test MT registry and provider loading."""

from __future__ import annotations

import os
import pytest

from loquilex.mt.core.registry import register_provider, available, create
from loquilex.mt.core.types import Lang, QualityMode


class MockProvider:
    """Mock provider for testing registry."""

    def translate_text(
        self, text: str, src: Lang, tgt: Lang, *, quality: QualityMode = "realtime"  # noqa: ARG002
    ) -> str:
        return f"mock-{src}-{tgt}-{text}"

    def translate_chunked(self, chunks, src: Lang, tgt: Lang, *, quality: QualityMode = "realtime"):
        for chunk in chunks:
            yield self.translate_text(chunk, src, tgt, quality=quality)

    def capabilities(self):
        return {
            "family": "mock",
            "model_name": "mock-model",
            "directions": [("en", "zh-Hans")],
            "requires_target_prefix": True,
            "device_types": ["cpu"],
            "compute_types": ["mock"],
            "supports_chunked": True,
            "supports_streaming_partials": False,
        }


def test_registry_operations():
    """Test provider registration and lookup."""
    # Register mock provider
    register_provider("test-mock", MockProvider)

    # Check it's available
    assert "test-mock" in available()

    # Create instance
    provider = create("test-mock")
    assert isinstance(provider, MockProvider)

    # Test basic functionality
    result = provider.translate_text("hello", "en", "zh-Hans")
    assert result == "mock-en-zh-Hans-hello"


def test_registry_unknown_provider():
    """Test error handling for unknown providers."""
    with pytest.raises(ValueError, match="Unknown MT provider: nonexistent"):
        create("nonexistent")


def test_mt_module_imports_without_heavy_deps():
    """Test that MT module can be imported without heavy dependencies."""
    # This tests offline-first principle - importing loquilex.mt should not
    # require ctranslate2, transformers, etc.

    try:
        import loquilex.mt

        # Should be able to access registry functions
        assert hasattr(loquilex.mt, "available")
        assert hasattr(loquilex.mt, "create")
        assert hasattr(loquilex.mt, "register_provider")

        # Should be able to access core types
        assert hasattr(loquilex.mt, "Lang")
        assert hasattr(loquilex.mt, "QualityMode")

    except ImportError as e:
        # If this fails, it means heavy deps are imported at module level
        pytest.fail(f"MT module import requires heavy dependencies: {e}")


@pytest.mark.skipif(
    os.getenv("LX_OFFLINE", "").lower() in ("1", "true", "on"),
    reason="Skip MT provider tests in offline mode",
)
def test_ct2_provider_registration():
    """Test that CT2 providers register correctly (when deps available)."""
    try:
        # Import providers to trigger registration
        import loquilex.mt.providers  # noqa: F401

        providers = available()

        # Should have registered CT2 providers if dependencies available
        # This test is gated to run only when not in offline mode
        if "ct2-nllb" in providers:
            assert "ct2-nllb" in providers
            # Don't actually create since it requires model files

        if "ct2-m2m" in providers:
            assert "ct2-m2m" in providers
            # Don't actually create since it requires model files

    except ImportError:
        # Dependencies not available, skip
        pytest.skip("CTranslate2 or transformers not available")

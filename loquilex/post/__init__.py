"""Post-processing registry for language-specific text cleanup."""

from __future__ import annotations

from typing import Callable

# Import language-specific post-processors
from .zh_text import post_process as zh_post_process


# Type alias for post-processor functions
PostProcessor = Callable[[str], str]


def identity_post_process(text: str) -> str:
    """Identity post-processor (no changes)."""
    return text


# Post-processor registry mapping language codes to processor functions
POST_PROCESSORS: dict[str, PostProcessor] = {
    "zh-Hans": zh_post_process,
    "zh-Hant": zh_post_process,
    "zh": zh_post_process,  # Generic Chinese (uses variant config)
    "en": identity_post_process,
    "es": identity_post_process,
    "fr": identity_post_process,
    "de": identity_post_process,
    "ja": identity_post_process,
    "ko": identity_post_process,
    "ru": identity_post_process,
    "ar": identity_post_process,
}


def post_process(text: str, lang: str) -> str:
    """Apply language-specific post-processing to translated text.

    Args:
        text: Translated text to process
        lang: Target language code (e.g., 'zh', 'en', 'es')

    Returns:
        Processed text with language-specific cleanup applied

    Example:
        >>> post_process("测试 文本 。", "zh")
        "测试文本。"
        >>> post_process("Hello world.", "en")
        "Hello world."
    """
    processor = POST_PROCESSORS.get(lang, identity_post_process)
    return processor(text)


def register_processor(lang: str, processor: PostProcessor) -> None:
    """Register a custom post-processor for a language.

    Args:
        lang: Language code to register processor for
        processor: Post-processor function

    Example:
        >>> def custom_es_processor(text: str) -> str:
        ...     return text.replace("  ", " ")
        >>> register_processor("es", custom_es_processor)
    """
    POST_PROCESSORS[lang] = processor


__all__ = ["post_process", "register_processor", "POST_PROCESSORS"]

"""MT utilities and helpers."""

from __future__ import annotations

import os
from .types import Lang


def resolve_zh_variant() -> Lang:
    """Resolve Chinese variant from environment."""
    variant = os.getenv("LX_LANG_VARIANT_ZH", "Hans")
    if variant == "Hans":
        return "zh-Hans"
    elif variant == "Hant":
        return "zh-Hant"
    else:
        # Default to Hans for unknown variants
        return "zh-Hans"


def normalize_lang(lang: str) -> Lang:
    """Normalize language code to supported Lang type."""
    if lang == "en":
        return "en"
    elif lang == "zh" or lang == "zho":
        # Map generic zh to environment-specified variant
        return resolve_zh_variant()
    elif lang == "zh-Hans":
        return "zh-Hans"
    elif lang == "zh-Hant":
        return "zh-Hant"
    else:
        raise ValueError(f"Unsupported language: {lang}")

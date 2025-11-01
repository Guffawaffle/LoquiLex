"""MT utilities and helpers."""

from __future__ import annotations

import os
from .types import Lang
from loquilex.capabilities import normalize_language_code


def resolve_zh_variant() -> Lang:
    """Resolve Chinese variant from environment.

    Deprecated: Use loquilex.capabilities.normalize_language_code instead.
    """
    variant = os.getenv("LX_LANG_VARIANT_ZH", "Hans")
    if variant == "Hans":
        return "zh-Hans"
    elif variant == "Hant":
        return "zh-Hant"
    else:
        # Default to Hans for unknown variants
        return "zh-Hans"


def normalize_lang(lang: str) -> Lang:
    """Normalize language code to supported Lang type.

    Uses the centralized BCP-47 canonicalizer.
    """
    return normalize_language_code(lang)  # type: ignore

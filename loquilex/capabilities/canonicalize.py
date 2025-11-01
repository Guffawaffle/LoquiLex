"""BCP-47 language code canonicalization and normalization.

This module provides centralized language code canonicalization, converting
various BCP-47 aliases and legacy codes to stable internal representations.
"""

from __future__ import annotations

import os
from typing import Optional


class LanguageCanonicalizer:
    """Normalize BCP-47 language codes to stable internal keys.

    Handles common aliases and variants:
    - zh, cmn, cmn-Hans → zh-Hans
    - zh-CN → zh-Hans
    - zh-TW, zh-HK → zh-Hant
    - yue, yue-Hant → zh-Hant (Cantonese uses traditional)

    Examples:
        >>> canon = LanguageCanonicalizer()
        >>> canon.normalize("zh")
        'zh-Hans'
        >>> canon.normalize("cmn-Hans")
        'zh-Hans'
        >>> canon.normalize("zh-TW")
        'zh-Hant'
        >>> canon.normalize("en")
        'en'
    """

    # Curated alias mapping for normalization
    _ALIASES = {
        # Chinese variants
        "zh": None,  # Resolved via environment LX_LANG_VARIANT_ZH
        "cmn": None,  # Mandarin → resolve via environment
        "cmn-Hans": "zh-Hans",
        "cmn-Hant": "zh-Hant",
        "zh-CN": "zh-Hans",  # Mainland China
        "zh-SG": "zh-Hans",  # Singapore
        "zh-TW": "zh-Hant",  # Taiwan
        "zh-HK": "zh-Hant",  # Hong Kong
        "zh-MO": "zh-Hant",  # Macau
        "yue": "zh-Hant",  # Cantonese (usually traditional)
        "yue-Hant": "zh-Hant",
        "yue-Hans": "zh-Hans",
        "zho": None,  # ISO 639-2 → resolve via environment
        # Other common aliases
        "eng": "en",  # ISO 639-2
        "fra": "fr",
        "deu": "de",
        "spa": "es",
        "jpn": "ja",
        "kor": "ko",
        "rus": "ru",
        "ara": "ar",
        "por": "pt",
        "ita": "it",
        "nld": "nl",
        "pol": "pl",
        "tur": "tr",
        "vie": "vi",
        "tha": "th",
        "hin": "hi",
        "ind": "id",
        "ukr": "uk",
    }

    # Supported canonical codes
    _SUPPORTED = {
        "en",
        "zh-Hans",
        "zh-Hant",
        "es",
        "fr",
        "de",
        "ja",
        "ko",
        "ru",
        "ar",
        "pt",
        "it",
        "nl",
        "pl",
        "tr",
        "vi",
        "th",
        "hi",
        "id",
        "uk",
    }

    def __init__(self, default_zh_variant: str = "Hans"):
        """Initialize canonicalizer.

        Args:
            default_zh_variant: Default Chinese variant when not specified.
                               Can be "Hans" or "Hant". Defaults to "Hans".
        """
        self.default_zh_variant = default_zh_variant

    def normalize(self, code: str) -> str:
        """Normalize a BCP-47 language code to canonical form.

        Args:
            code: BCP-47 language code or alias (e.g., 'zh', 'cmn-Hans', 'en')

        Returns:
            Canonical language code (e.g., 'zh-Hans', 'en')

        Raises:
            ValueError: If the language code is not supported

        Examples:
            >>> canon = LanguageCanonicalizer()
            >>> canon.normalize("zh")
            'zh-Hans'
            >>> canon.normalize("en")
            'en'
        """
        # Already canonical?
        if code in self._SUPPORTED:
            return code

        # Check aliases
        if code in self._ALIASES:
            canonical = self._ALIASES[code]
            if canonical is None:
                # Environment-dependent resolution
                return self._resolve_variant(code)
            return canonical

        # Unknown code
        raise ValueError(f"Unsupported language code: {code}")

    def _resolve_variant(self, code: str) -> str:
        """Resolve environment-dependent variants for generic codes.

        Args:
            code: Generic language code (e.g., 'zh', 'cmn', 'zho')

        Returns:
            Canonical code based on environment settings
        """
        if code in ("zh", "cmn", "zho"):
            # Use environment variable or default
            variant = os.getenv("LX_LANG_VARIANT_ZH", self.default_zh_variant)
            if variant == "Hans":
                return "zh-Hans"
            elif variant == "Hant":
                return "zh-Hant"
            else:
                # Fallback to default
                return "zh-Hans"
        raise ValueError(f"Cannot resolve variant for: {code}")

    def validate(self, code: str) -> bool:
        """Check if a language code is supported.

        Args:
            code: Language code to validate

        Returns:
            True if the code is supported (directly or via alias)

        Examples:
            >>> canon = LanguageCanonicalizer()
            >>> canon.validate("en")
            True
            >>> canon.validate("zh")
            True
            >>> canon.validate("xyz")
            False
        """
        try:
            self.normalize(code)
            return True
        except ValueError:
            return False

    def get_supported_codes(self) -> set[str]:
        """Get set of all supported canonical language codes.

        Returns:
            Set of canonical language codes

        Examples:
            >>> canon = LanguageCanonicalizer()
            >>> "en" in canon.get_supported_codes()
            True
        """
        return self._SUPPORTED.copy()


# Global singleton instance
_canonicalizer: Optional[LanguageCanonicalizer] = None


def get_canonicalizer() -> LanguageCanonicalizer:
    """Get the global LanguageCanonicalizer instance.

    Returns:
        Singleton LanguageCanonicalizer instance
    """
    global _canonicalizer
    if _canonicalizer is None:
        _canonicalizer = LanguageCanonicalizer()
    return _canonicalizer


def normalize_language_code(code: str) -> str:
    """Convenience function to normalize a language code.

    Args:
        code: BCP-47 language code or alias

    Returns:
        Canonical language code

    Examples:
        >>> normalize_language_code("zh")
        'zh-Hans'
    """
    return get_canonicalizer().normalize(code)

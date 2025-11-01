"""Token mapping between BCP-47 codes and model-specific tokens.

This module provides bidirectional mapping between BCP-47 language codes
and model-specific tokens for NLLB (FLORES-200), M2M-100, and Whisper.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Literal, Optional

from .canonicalize import get_canonicalizer

logger = logging.getLogger(__name__)

ModelFamily = Literal["nllb", "m2m", "whisper"]


class TokenMapper:
    """Map between BCP-47 codes and model-specific tokens.

    Supports NLLB (FLORES-200), M2M-100, and Whisper token formats.
    Falls back to curated maps when heuristic detection is insufficient.

    Examples:
        >>> mapper = TokenMapper()
        >>> mapper.bcp47_to_token("en", "nllb")
        'eng_Latn'
        >>> mapper.bcp47_to_token("zh-Hans", "whisper")
        '<|zh|>'
        >>> mapper.token_to_bcp47("eng_Latn", "nllb")
        'en'
    """

    def __init__(self):
        """Initialize token mapper with curated fallback maps."""
        self._canonicalizer = get_canonicalizer()
        self._maps = self._load_maps()
        self._reverse_maps = self._build_reverse_maps()

    def _load_maps(self) -> dict[str, dict[str, str]]:
        """Load curated token maps from JSON fixtures.

        Returns:
            Dictionary of maps keyed by model family
        """
        fixtures_dir = Path(__file__).parent / "fixtures"
        maps = {}

        for model_family in ("nllb", "m2m", "whisper"):
            fixture_path = fixtures_dir / f"{model_family}_map.json"
            try:
                with open(fixture_path) as f:
                    maps[model_family] = json.load(f)
            except Exception as e:
                logger.warning(f"Failed to load {model_family} map from {fixture_path}: {e}")
                maps[model_family] = {}

        return maps

    def _build_reverse_maps(self) -> dict[str, dict[str, str]]:
        """Build reverse mappings (token → BCP-47) for each model family.

        For ambiguous tokens (e.g., "zh" maps to both zh-Hans and zh-Hant),
        prefer zh-Hans as the canonical default.

        Returns:
            Dictionary of reverse maps keyed by model family
        """
        reverse = {}
        for family, forward_map in self._maps.items():
            rev_map = {}
            # Build reverse map, preferring zh-Hans over zh-Hant for ambiguous cases
            for bcp47, token in sorted(forward_map.items()):
                if token not in rev_map or bcp47 == "zh-Hans":
                    # Prefer zh-Hans when there's ambiguity
                    rev_map[token] = bcp47
            reverse[family] = rev_map
        return reverse

    def bcp47_to_token(self, code: str, model_family: ModelFamily, normalize: bool = True) -> str:
        """Convert BCP-47 code to model-specific token.

        Args:
            code: BCP-47 language code (e.g., 'en', 'zh', 'zh-Hans')
            model_family: Target model family ('nllb', 'm2m', 'whisper')
            normalize: Whether to normalize the code first (default: True)

        Returns:
            Model-specific token (e.g., 'eng_Latn', '<|en|>')

        Raises:
            ValueError: If code or model_family is not supported

        Examples:
            >>> mapper = TokenMapper()
            >>> mapper.bcp47_to_token("en", "nllb")
            'eng_Latn'
            >>> mapper.bcp47_to_token("zh", "whisper")
            '<|zh|>'
        """
        if model_family not in ("nllb", "m2m", "whisper"):
            raise ValueError(f"Unsupported model family: {model_family}")

        # Normalize the code first if requested
        if normalize:
            code = self._canonicalizer.normalize(code)

        # Look up in curated map
        token_map = self._maps.get(model_family, {})
        if code in token_map:
            return token_map[code]

        # Log warning when falling back (indicates detection gap)
        logger.warning(f"No {model_family} token mapping for '{code}', falling back to heuristic")

        # Heuristic fallback
        return self._heuristic_token(code, model_family)

    def token_to_bcp47(self, token: str, model_family: ModelFamily, normalize: bool = True) -> str:
        """Convert model-specific token to BCP-47 code.

        Args:
            token: Model-specific token (e.g., 'eng_Latn', '<|en|>')
            model_family: Source model family ('nllb', 'm2m', 'whisper')
            normalize: Whether to normalize the result (default: True)

        Returns:
            BCP-47 language code (e.g., 'en', 'zh-Hans')

        Raises:
            ValueError: If token or model_family is not supported

        Examples:
            >>> mapper = TokenMapper()
            >>> mapper.token_to_bcp47("eng_Latn", "nllb")
            'en'
            >>> mapper.token_to_bcp47("<|zh|>", "whisper")
            'zh-Hans'
        """
        if model_family not in ("nllb", "m2m", "whisper"):
            raise ValueError(f"Unsupported model family: {model_family}")

        # Look up in reverse map
        reverse_map = self._reverse_maps.get(model_family, {})
        if token in reverse_map:
            code = reverse_map[token]
            if normalize:
                code = self._canonicalizer.normalize(code)
            return code

        # Log warning when falling back
        logger.warning(f"No {model_family} BCP-47 mapping for token '{token}', using heuristic")

        # Heuristic reverse mapping
        return self._heuristic_bcp47(token, model_family, normalize)

    def _heuristic_token(self, code: str, model_family: str) -> str:
        """Generate model token using heuristics when curated map unavailable.

        Args:
            code: Canonical BCP-47 code
            model_family: Target model family

        Returns:
            Best-effort model token
        """
        # Simple heuristics for common cases
        if model_family == "whisper":
            # Whisper uses simple <|code|> format
            # Strip script/region for generic form
            base = code.split("-")[0]
            return f"<|{base}|>"
        elif model_family == "m2m":
            # M2M uses simple codes
            base = code.split("-")[0]
            return base
        elif model_family == "nllb":
            # FLORES-200 uses language_Script format
            # This is a fallback; proper mapping should use curated map
            if code.startswith("zh-"):
                script = "Hans" if "Hans" in code else "Hant"
                return f"zho_{script}"
            # Generic Latin script fallback
            base = code.split("-")[0]
            return f"{base}_Latn"

        return code

    def _heuristic_bcp47(self, token: str, model_family: str, normalize: bool) -> str:
        """Generate BCP-47 code using heuristics when reverse map unavailable.

        Args:
            token: Model-specific token
            model_family: Source model family
            normalize: Whether to normalize result

        Returns:
            Best-effort BCP-47 code
        """
        # Extract base language code from token
        if model_family == "whisper":
            # Format: <|code|>
            code = token.strip("<|>")
        elif model_family == "m2m":
            # Simple code
            code = token
        elif model_family == "nllb":
            # Format: lang_Script
            parts = token.split("_")
            if len(parts) >= 2:
                lang, script = parts[0], parts[1]
                if lang == "zho":
                    code = f"zh-{script}"
                elif lang == "eng":
                    code = "en"
                else:
                    code = lang
            else:
                code = token
        else:
            code = token

        if normalize:
            try:
                code = self._canonicalizer.normalize(code)
            except ValueError:
                # If normalization fails, return as-is
                pass

        return code

    def get_supported_codes(self, model_family: ModelFamily) -> set[str]:
        """Get all BCP-47 codes supported by a model family.

        Args:
            model_family: Model family to query

        Returns:
            Set of supported BCP-47 codes

        Examples:
            >>> mapper = TokenMapper()
            >>> codes = mapper.get_supported_codes("nllb")
            >>> "en" in codes
            True
        """
        return set(self._maps.get(model_family, {}).keys())

    def get_supported_tokens(self, model_family: ModelFamily) -> set[str]:
        """Get all tokens supported by a model family.

        Args:
            model_family: Model family to query

        Returns:
            Set of supported tokens

        Examples:
            >>> mapper = TokenMapper()
            >>> tokens = mapper.get_supported_tokens("nllb")
            >>> "eng_Latn" in tokens
            True
        """
        return set(self._maps.get(model_family, {}).values())


# Global singleton instance
_mapper: Optional[TokenMapper] = None


def get_mapper() -> TokenMapper:
    """Get the global TokenMapper instance.

    Returns:
        Singleton TokenMapper instance
    """
    global _mapper
    if _mapper is None:
        _mapper = TokenMapper()
    return _mapper

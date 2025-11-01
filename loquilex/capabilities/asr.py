"""ASR model capability discovery.

Probes ASR models (Whisper via CTranslate2) to extract supported languages
from tokenizer vocabulary and expose them via structured JSON.
"""

from __future__ import annotations

import logging
import os
import re
import time
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# Mapping from Whisper language tokens to BCP-47 codes
# Reference: https://github.com/openai/whisper/blob/main/whisper/tokenizer.py
WHISPER_LANG_TO_BCP47 = {
    "en": "en",
    "zh": "zh-Hans",  # Whisper uses 'zh' for Simplified Chinese
    "es": "es",
    "fr": "fr",
    "de": "de",
    "ja": "ja",
    "ko": "ko",
    "ru": "ru",
    "pt": "pt",
    "it": "it",
    "nl": "nl",
    "tr": "tr",
    "pl": "pl",
    "ar": "ar",
    "hi": "hi",
    "id": "id",
    "uk": "uk",
    "vi": "vi",
    "th": "th",
    "cs": "cs",
    "ro": "ro",
    "sv": "sv",
    "hu": "hu",
    "el": "el",
    "da": "da",
    "fi": "fi",
    "no": "no",
    "he": "he",
    "fa": "fa",
    "ms": "ms",
    "bn": "bn",
    "ta": "ta",
    "te": "te",
    "ur": "ur",
    "kn": "kn",
    "ml": "ml",
    "mr": "mr",
    "pa": "pa",
    "gu": "gu",
    "ne": "ne",
    "si": "si",
    "km": "km",
    "lo": "lo",
    "my": "my",
    "ka": "ka",
    "hy": "hy",
    "az": "az",
    "kk": "kk",
    "uz": "uz",
    "mn": "mn",
    "bo": "bo",
    "am": "am",
    "cy": "cy",
    "eu": "eu",
    "gl": "gl",
    "is": "is",
    "jw": "jv",  # Javanese: jw -> jv per BCP-47
    "su": "su",
    "la": "la",
    "ln": "ln",
    "mg": "mg",
    "mi": "mi",
    "oc": "oc",
    "ps": "ps",
    "sa": "sa",
    "sn": "sn",
    "so": "so",
    "sw": "sw",
    "tl": "tl",
    "yo": "yo",
    "af": "af",
    "sq": "sq",
    "be": "be",
    "bg": "bg",
    "bs": "bs",
    "ca": "ca",
    "hr": "hr",
    "et": "et",
    "fo": "fo",
    "ha": "ha",
    "ht": "ht",
    "lb": "lb",
    "lt": "lt",
    "lv": "lv",
    "mk": "mk",
    "mt": "mt",
    "sk": "sk",
    "sl": "sl",
    "sr": "sr",
    "tk": "tk",
    "tt": "tt",
    "tg": "tg",
}


class ASRCapabilityProbe:
    """Probe ASR models for supported languages and capabilities."""

    def __init__(self):
        """Initialize the capability probe with an empty cache."""
        self._cache: Dict[str, Dict[str, Any]] = {}
        self._cache_mtime: Dict[str, float] = {}

    def probe_model(self, model_name: str, model_path: Optional[str] = None) -> Dict[str, Any]:
        """Probe an ASR model for its capabilities.

        Args:
            model_name: Model identifier (e.g., "whisper-small", "base.en")
            model_path: Optional path to model files for mtime-based caching

        Returns:
            Dict with keys: kind, model, supports_auto, languages, tokens
        """
        # Check cache validity
        cache_key = model_name
        if model_path and os.path.exists(model_path):
            try:
                mtime = os.path.getmtime(model_path)
                if cache_key in self._cache and self._cache_mtime.get(cache_key) == mtime:
                    logger.debug(f"Returning cached capabilities for {model_name}")
                    return self._cache[cache_key]
            except OSError:
                pass

        # Probe the model
        start_time = time.monotonic()
        try:
            capabilities = self._probe_whisper_model(model_name, model_path)
            
            # Update cache
            self._cache[cache_key] = capabilities
            if model_path and os.path.exists(model_path):
                try:
                    self._cache_mtime[cache_key] = os.path.getmtime(model_path)
                except OSError:
                    pass
            
            elapsed = time.monotonic() - start_time
            logger.info(f"Probed {model_name} capabilities in {elapsed:.3f}s")
            
            return capabilities
            
        except Exception as e:
            logger.error(f"Failed to probe {model_name}: {e}", exc_info=True)
            # Return minimal safe response with fallback
            # Note: supports_auto is still True for Whisper models even on error
            fallback_langs, fallback_tokens = self._fallback_languages(model_name)
            return {
                "kind": "asr",
                "model": model_name,
                "supports_auto": True,
                "languages": fallback_langs,
                "tokens": fallback_tokens,
            }

    def _probe_whisper_model(
        self, model_name: str, _model_path: Optional[str] = None
    ) -> Dict[str, Any]:
        """Probe a Whisper model via CTranslate2.

        Args:
            model_name: Model identifier
            _model_path: Optional path to model directory (unused, reserved for future use)

        Returns:
            Capability dictionary
        """
        languages: List[str] = []
        tokens: Dict[str, str] = {}
        
        # Try to load model and inspect tokenizer
        try:
            from faster_whisper import WhisperModel  # type: ignore
            
            # Load model (will use cached version if available)
            model = WhisperModel(model_name, device="cpu", compute_type="int8")
            
            # Access tokenizer vocabulary
            # For CTranslate2 Whisper, the model has a tokenizer with a vocabulary
            if hasattr(model, "model") and hasattr(model.model, "get_vocabulary"):
                vocab = model.model.get_vocabulary()
                
                # Extract language tokens (format: <|en|>, <|zh|>, etc.)
                lang_pattern = re.compile(r"<\|([a-z]{2,3})\|>")
                for token in vocab:
                    match = lang_pattern.match(token)
                    if match:
                        lang_code = match.group(1)
                        if lang_code in WHISPER_LANG_TO_BCP47:
                            bcp47 = WHISPER_LANG_TO_BCP47[lang_code]
                            if bcp47 not in languages:
                                languages.append(bcp47)
                                tokens[bcp47] = token
            
        except Exception as e:
            logger.warning(f"Could not load model {model_name} for probing: {e}")
            # Fall back to curated list for known models
            languages, tokens = self._fallback_languages(model_name)
        
        # If we still don't have languages, use fallback
        if not languages:
            languages, tokens = self._fallback_languages(model_name)
        
        return {
            "kind": "asr",
            "model": model_name,
            "supports_auto": True,  # All Whisper models support auto language detection
            "languages": sorted(languages),
            "tokens": tokens,
        }

    def _fallback_languages(self, model_name: str) -> tuple[List[str], Dict[str, str]]:
        """Return fallback language list for known models.

        Args:
            model_name: Model identifier

        Returns:
            Tuple of (languages, tokens)
        """
        # English-only models
        if model_name.endswith(".en"):
            return ["en"], {"en": "<|en|>"}
        
        # Multilingual models: return common subset
        common_langs = [
            "ar", "de", "en", "es", "fr", "hi", "it", "ja", "ko", "nl", 
            "pl", "pt", "ru", "tr", "uk", "vi", "zh-Hans"
        ]
        common_tokens = {lang: f"<|{lang[:2]}|>" for lang in common_langs}
        # Adjust Chinese token
        common_tokens["zh-Hans"] = "<|zh|>"
        
        return common_langs, common_tokens

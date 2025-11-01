"""MT model capability probing for NLLB-200 and M2M-100 models."""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# Full FLORES-200 language code mapping (NLLB models)
# Maps BCP-47-like codes to FLORES codes used internally by NLLB
FLORES_TO_BCP47: Dict[str, str] = {
    "eng_Latn": "en",
    "zho_Hans": "zh-Hans",
    "zho_Hant": "zh-Hant",
    "spa_Latn": "es",
    "fra_Latn": "fr",
    "deu_Latn": "de",
    "jpn_Jpan": "ja",
    "kor_Hang": "ko",
    "rus_Cyrl": "ru",
    "arb_Arab": "ar",
    "ita_Latn": "it",
    "por_Latn": "pt",
    "nld_Latn": "nl",
    "pol_Latn": "pl",
    "tur_Latn": "tr",
    "vie_Latn": "vi",
    "tha_Thai": "th",
    "ind_Latn": "id",
    "heb_Hebr": "he",
    "ell_Grek": "el",
}

# Reverse mapping for encoding
BCP47_TO_FLORES: Dict[str, str] = {v: k for k, v in FLORES_TO_BCP47.items()}

# M2M-100 uses simpler language codes
M2M_LANG_CODES = {
    "en",
    "zh",
    "es",
    "fr",
    "de",
    "ja",
    "ko",
    "ru",
    "ar",
    "it",
    "pt",
    "nl",
    "pl",
    "tr",
    "vi",
    "th",
    "id",
    "he",
    "el",
}

# Map M2M codes to BCP-47
M2M_TO_BCP47: Dict[str, str] = {
    "en": "en",
    "zh": "zh-Hans",  # M2M uses generic zh, map to simplified
    "es": "es",
    "fr": "fr",
    "de": "de",
    "ja": "ja",
    "ko": "ko",
    "ru": "ru",
    "ar": "ar",
    "it": "it",
    "pt": "pt",
    "nl": "nl",
    "pl": "pl",
    "tr": "tr",
    "vi": "vi",
    "th": "th",
    "id": "id",
    "he": "he",
    "el": "el",
}


class MTCapabilityProbe:
    """Probe MT model capabilities for language support."""

    @staticmethod
    def probe(model_name: str, model_path: Optional[str] = None) -> Dict[str, Any]:
        """Probe MT model for supported languages and capabilities.

        Args:
            model_name: Name/ID of the model (e.g., "facebook/nllb-200-distilled-600M")
            model_path: Optional path to model directory

        Returns:
            Dictionary with capability information:
            {
                "kind": "mt",
                "model": str,
                "source_languages": List[str],  # BCP-47 codes
                "target_languages": List[str],  # BCP-47 codes
                "pairs": null | Dict[str, List[str]],  # null for many-to-many
                "tokens": Dict[str, str]  # BCP-47 -> internal token mapping
            }
        """
        logger.info("Probing MT model capabilities", extra={"model": model_name})

        # Determine model type from name
        is_nllb = "nllb" in model_name.lower()
        is_m2m = "m2m" in model_name.lower()

        if is_nllb:
            return MTCapabilityProbe._probe_nllb(model_name, model_path)
        elif is_m2m:
            return MTCapabilityProbe._probe_m2m(model_name, model_path)
        else:
            # Unknown model, return minimal capability
            logger.warning(
                "Unknown MT model type, returning minimal capability", extra={"model": model_name}
            )
            return {
                "kind": "mt",
                "model": model_name,
                "source_languages": ["en"],
                "target_languages": ["zh-Hans"],
                "pairs": {"en": ["zh-Hans"], "zh-Hans": ["en"]},
                "tokens": {"en": "en", "zh-Hans": "zh"},
            }

    @staticmethod
    def _is_offline_mode() -> bool:
        """Check if we're in offline mode (no network access)."""
        return os.getenv("HF_HUB_OFFLINE") == "1" or os.getenv("TRANSFORMERS_OFFLINE") == "1"

    @staticmethod
    def _probe_nllb(model_name: str, model_path: Optional[str] = None) -> Dict[str, Any]:
        """Probe NLLB-200 model capabilities.

        NLLB-200 is a many-to-many model supporting 200 languages.
        Uses FLORES-200 language codes internally.
        """
        logger.debug("Probing NLLB model", extra={"model": model_name})

        # Try to detect languages from tokenizer if available
        detected_langs = MTCapabilityProbe._detect_nllb_languages(model_path)

        if detected_langs:
            # Use detected languages
            bcp47_codes = sorted(detected_langs)
            tokens = {bcp: BCP47_TO_FLORES.get(bcp, bcp) for bcp in bcp47_codes}
        else:
            # Fallback to curated subset of commonly used languages
            bcp47_codes = [
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
                "it",
                "pt",
            ]
            tokens = {bcp: BCP47_TO_FLORES[bcp] for bcp in bcp47_codes}

        return {
            "kind": "mt",
            "model": model_name,
            "source_languages": bcp47_codes,
            "target_languages": bcp47_codes,
            "pairs": None,  # Many-to-many, all combinations supported
            "tokens": tokens,
        }

    @staticmethod
    def _probe_m2m(model_name: str, model_path: Optional[str] = None) -> Dict[str, Any]:
        """Probe M2M-100 model capabilities.

        M2M-100 is a many-to-many model supporting 100 languages.
        Uses simpler language codes than NLLB.
        """
        logger.debug("Probing M2M model", extra={"model": model_name})

        # Try to detect languages from tokenizer if available
        detected_langs = MTCapabilityProbe._detect_m2m_languages(model_path)

        # Build reverse mapping once
        bcp_to_m2m = {v: k for k, v in M2M_TO_BCP47.items()}

        if detected_langs:
            bcp47_codes = sorted(detected_langs)
            tokens = {
                bcp: bcp_to_m2m.get(bcp, bcp.split("-")[0])  # Fallback to language prefix
                for bcp in bcp47_codes
            }
        else:
            # Fallback to curated subset
            bcp47_codes = ["en", "zh-Hans", "es", "fr", "de", "ja", "ko", "ru", "ar", "it", "pt"]
            tokens = {bcp: bcp_to_m2m[bcp] for bcp in bcp47_codes}

        return {
            "kind": "mt",
            "model": model_name,
            "source_languages": bcp47_codes,
            "target_languages": bcp47_codes,
            "pairs": None,  # Many-to-many
            "tokens": tokens,
        }

    @staticmethod
    def _detect_nllb_languages(model_path: Optional[str]) -> List[str]:
        """Detect supported languages from NLLB tokenizer.

        Returns:
            List of BCP-47 language codes, or empty list if detection fails
        """
        if not model_path:
            return []

        try:
            # Avoid importing transformers at module level (heavy dependency)
            from transformers import AutoTokenizer

            # Check if we're in offline mode
            if MTCapabilityProbe._is_offline_mode() and not Path(model_path).exists():
                logger.debug("Skipping tokenizer load in offline mode without local model")
                return []

            tokenizer = AutoTokenizer.from_pretrained(
                model_path, local_files_only=MTCapabilityProbe._is_offline_mode()
            )

            # NLLB tokenizers have fairseq_tokens_to_ids or similar attributes
            # that contain the language tokens
            lang_tokens = []

            # Try different attribute patterns used by NLLB tokenizers
            if hasattr(tokenizer, "fairseq_tokens_to_ids"):
                # Extract tokens that look like FLORES codes (xxx_Yyyy pattern)
                for token in tokenizer.fairseq_tokens_to_ids.keys():
                    if "_" in token and len(token.split("_")) == 2:
                        lang_code, script = token.split("_")
                        if len(lang_code) == 3 and script[0].isupper():
                            lang_tokens.append(token)

            # Convert FLORES codes to BCP-47
            bcp47_codes = []
            for flores_code in lang_tokens:
                if flores_code in FLORES_TO_BCP47:
                    bcp47_codes.append(FLORES_TO_BCP47[flores_code])

            if bcp47_codes:
                logger.debug(
                    "Detected NLLB languages from tokenizer", extra={"count": len(bcp47_codes)}
                )
                return bcp47_codes

        except Exception as e:
            logger.debug("Failed to detect NLLB languages from tokenizer", extra={"error": str(e)})

        return []

    @staticmethod
    def _detect_m2m_languages(model_path: Optional[str]) -> List[str]:
        """Detect supported languages from M2M tokenizer.

        Returns:
            List of BCP-47 language codes, or empty list if detection fails
        """
        if not model_path:
            return []

        try:
            # Avoid importing transformers at module level
            from transformers import AutoTokenizer

            # Check if we're in offline mode
            if MTCapabilityProbe._is_offline_mode() and not Path(model_path).exists():
                logger.debug("Skipping tokenizer load in offline mode without local model")
                return []

            tokenizer = AutoTokenizer.from_pretrained(
                model_path, local_files_only=MTCapabilityProbe._is_offline_mode()
            )

            # M2M tokenizers have lang_code_to_token attribute
            lang_codes = []
            if hasattr(tokenizer, "lang_code_to_token"):
                lang_codes = list(tokenizer.lang_code_to_token.keys())

            # Convert M2M codes to BCP-47
            bcp47_codes = []
            for m2m_code in lang_codes:
                if m2m_code in M2M_TO_BCP47:
                    bcp47_codes.append(M2M_TO_BCP47[m2m_code])

            if bcp47_codes:
                logger.debug(
                    "Detected M2M languages from tokenizer", extra={"count": len(bcp47_codes)}
                )
                return bcp47_codes

        except Exception as e:
            logger.debug("Failed to detect M2M languages from tokenizer", extra={"error": str(e)})

        return []

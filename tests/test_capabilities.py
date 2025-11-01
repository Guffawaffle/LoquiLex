"""Tests for BCP-47 language canonicalization and token mapping."""

from __future__ import annotations

import os
import pytest

from loquilex.capabilities import (
    LanguageCanonicalizer,
    TokenMapper,
    get_canonicalizer,
    get_mapper,
    normalize_language_code,
)


class TestLanguageCanonicalizer:
    """Test LanguageCanonicalizer class."""

    def test_normalize_already_canonical(self):
        """Test normalization of already canonical codes."""
        canon = LanguageCanonicalizer()
        assert canon.normalize("en") == "en"
        assert canon.normalize("zh-Hans") == "zh-Hans"
        assert canon.normalize("zh-Hant") == "zh-Hant"
        assert canon.normalize("es") == "es"
        assert canon.normalize("fr") == "fr"

    def test_normalize_chinese_aliases(self):
        """Test normalization of Chinese language aliases."""
        canon = LanguageCanonicalizer()

        # Generic zh resolves to environment default (Hans)
        assert canon.normalize("zh") == "zh-Hans"

        # Regional codes
        assert canon.normalize("zh-CN") == "zh-Hans"
        assert canon.normalize("zh-SG") == "zh-Hans"
        assert canon.normalize("zh-TW") == "zh-Hant"
        assert canon.normalize("zh-HK") == "zh-Hant"
        assert canon.normalize("zh-MO") == "zh-Hant"

        # Mandarin codes
        assert canon.normalize("cmn-Hans") == "zh-Hans"
        assert canon.normalize("cmn-Hant") == "zh-Hant"

        # Cantonese (typically traditional)
        assert canon.normalize("yue") == "zh-Hant"
        assert canon.normalize("yue-Hant") == "zh-Hant"
        assert canon.normalize("yue-Hans") == "zh-Hans"

    def test_normalize_chinese_with_variant(self):
        """Test Chinese normalization with environment variant."""
        # Test with Hant variant
        canon_hant = LanguageCanonicalizer(default_zh_variant="Hant")
        assert canon_hant.normalize("zh") == "zh-Hant"
        assert canon_hant.normalize("cmn") == "zh-Hant"
        assert canon_hant.normalize("zho") == "zh-Hant"

        # Test with Hans variant (default)
        canon_hans = LanguageCanonicalizer(default_zh_variant="Hans")
        assert canon_hans.normalize("zh") == "zh-Hans"
        assert canon_hans.normalize("cmn") == "zh-Hans"
        assert canon_hans.normalize("zho") == "zh-Hans"

    def test_normalize_iso_639_2_codes(self):
        """Test normalization of ISO 639-2 three-letter codes."""
        canon = LanguageCanonicalizer()
        assert canon.normalize("eng") == "en"
        assert canon.normalize("fra") == "fr"
        assert canon.normalize("deu") == "de"
        assert canon.normalize("spa") == "es"
        assert canon.normalize("jpn") == "ja"
        assert canon.normalize("kor") == "ko"
        assert canon.normalize("rus") == "ru"

    def test_normalize_unsupported(self):
        """Test error handling for unsupported codes."""
        canon = LanguageCanonicalizer()
        with pytest.raises(ValueError, match="Unsupported language code"):
            canon.normalize("xyz")
        with pytest.raises(ValueError, match="Unsupported language code"):
            canon.normalize("unknown")

    def test_validate(self):
        """Test language code validation."""
        canon = LanguageCanonicalizer()
        assert canon.validate("en") is True
        assert canon.validate("zh") is True
        assert canon.validate("zh-Hans") is True
        assert canon.validate("eng") is True
        assert canon.validate("xyz") is False
        assert canon.validate("unknown") is False

    def test_get_supported_codes(self):
        """Test getting supported canonical codes."""
        canon = LanguageCanonicalizer()
        codes = canon.get_supported_codes()
        assert isinstance(codes, set)
        assert "en" in codes
        assert "zh-Hans" in codes
        assert "zh-Hant" in codes
        assert "es" in codes
        assert len(codes) >= 10  # Should have at least 10 languages

    def test_singleton_pattern(self):
        """Test global canonicalizer singleton."""
        canon1 = get_canonicalizer()
        canon2 = get_canonicalizer()
        assert canon1 is canon2

    def test_convenience_function(self):
        """Test convenience normalization function."""
        assert normalize_language_code("zh") == "zh-Hans"
        assert normalize_language_code("en") == "en"
        assert normalize_language_code("eng") == "en"


class TestTokenMapper:
    """Test TokenMapper class."""

    def test_bcp47_to_nllb(self):
        """Test BCP-47 to NLLB/FLORES-200 token mapping."""
        mapper = TokenMapper()
        assert mapper.bcp47_to_token("en", "nllb") == "eng_Latn"
        assert mapper.bcp47_to_token("zh-Hans", "nllb") == "zho_Hans"
        assert mapper.bcp47_to_token("zh-Hant", "nllb") == "zho_Hant"
        assert mapper.bcp47_to_token("es", "nllb") == "spa_Latn"
        assert mapper.bcp47_to_token("fr", "nllb") == "fra_Latn"
        assert mapper.bcp47_to_token("ja", "nllb") == "jpn_Jpan"
        assert mapper.bcp47_to_token("ko", "nllb") == "kor_Hang"
        assert mapper.bcp47_to_token("ar", "nllb") == "arb_Arab"

    def test_bcp47_to_m2m(self):
        """Test BCP-47 to M2M-100 token mapping."""
        mapper = TokenMapper()
        assert mapper.bcp47_to_token("en", "m2m") == "en"
        assert mapper.bcp47_to_token("zh-Hans", "m2m") == "zh"
        assert mapper.bcp47_to_token("zh-Hant", "m2m") == "zh"
        assert mapper.bcp47_to_token("es", "m2m") == "es"
        assert mapper.bcp47_to_token("fr", "m2m") == "fr"
        assert mapper.bcp47_to_token("ja", "m2m") == "ja"

    def test_bcp47_to_whisper(self):
        """Test BCP-47 to Whisper token mapping."""
        mapper = TokenMapper()
        assert mapper.bcp47_to_token("en", "whisper") == "<|en|>"
        assert mapper.bcp47_to_token("zh-Hans", "whisper") == "<|zh|>"
        assert mapper.bcp47_to_token("zh-Hant", "whisper") == "<|zh|>"
        assert mapper.bcp47_to_token("es", "whisper") == "<|es|>"
        assert mapper.bcp47_to_token("fr", "whisper") == "<|fr|>"
        assert mapper.bcp47_to_token("ja", "whisper") == "<|ja|>"

    def test_bcp47_to_token_with_normalization(self):
        """Test token mapping with automatic normalization."""
        mapper = TokenMapper()
        # Generic zh should normalize to zh-Hans
        assert mapper.bcp47_to_token("zh", "nllb") == "zho_Hans"
        assert mapper.bcp47_to_token("zh", "m2m") == "zh"
        assert mapper.bcp47_to_token("zh", "whisper") == "<|zh|>"

        # ISO 639-2 codes should normalize
        assert mapper.bcp47_to_token("eng", "nllb") == "eng_Latn"

    def test_token_to_bcp47_nllb(self):
        """Test NLLB token to BCP-47 mapping."""
        mapper = TokenMapper()
        assert mapper.token_to_bcp47("eng_Latn", "nllb") == "en"
        assert mapper.token_to_bcp47("zho_Hans", "nllb") == "zh-Hans"
        assert mapper.token_to_bcp47("zho_Hant", "nllb") == "zh-Hant"
        assert mapper.token_to_bcp47("spa_Latn", "nllb") == "es"
        assert mapper.token_to_bcp47("jpn_Jpan", "nllb") == "ja"

    def test_token_to_bcp47_m2m(self):
        """Test M2M token to BCP-47 mapping."""
        mapper = TokenMapper()
        assert mapper.token_to_bcp47("en", "m2m") == "en"
        assert mapper.token_to_bcp47("zh", "m2m") == "zh-Hans"
        assert mapper.token_to_bcp47("es", "m2m") == "es"
        assert mapper.token_to_bcp47("fr", "m2m") == "fr"

    def test_token_to_bcp47_whisper(self):
        """Test Whisper token to BCP-47 mapping."""
        mapper = TokenMapper()
        assert mapper.token_to_bcp47("<|en|>", "whisper") == "en"
        assert mapper.token_to_bcp47("<|zh|>", "whisper") == "zh-Hans"
        assert mapper.token_to_bcp47("<|es|>", "whisper") == "es"

    def test_bidirectional_mapping_nllb(self):
        """Test bidirectional NLLB mapping."""
        mapper = TokenMapper()
        # en → eng_Latn → en
        token = mapper.bcp47_to_token("en", "nllb")
        assert token == "eng_Latn"
        code = mapper.token_to_bcp47(token, "nllb")
        assert code == "en"

        # zh-Hans → zho_Hans → zh-Hans
        token = mapper.bcp47_to_token("zh-Hans", "nllb")
        assert token == "zho_Hans"
        code = mapper.token_to_bcp47(token, "nllb")
        assert code == "zh-Hans"

    def test_bidirectional_mapping_m2m(self):
        """Test bidirectional M2M mapping."""
        mapper = TokenMapper()
        # en → en → en
        token = mapper.bcp47_to_token("en", "m2m")
        code = mapper.token_to_bcp47(token, "m2m")
        assert code == "en"

    def test_bidirectional_mapping_whisper(self):
        """Test bidirectional Whisper mapping."""
        mapper = TokenMapper()
        # en → <|en|> → en
        token = mapper.bcp47_to_token("en", "whisper")
        assert token == "<|en|>"
        code = mapper.token_to_bcp47(token, "whisper")
        assert code == "en"

    def test_invalid_model_family(self):
        """Test error handling for invalid model family."""
        mapper = TokenMapper()
        with pytest.raises(ValueError, match="Unsupported model family"):
            mapper.bcp47_to_token("en", "unknown")  # type: ignore
        with pytest.raises(ValueError, match="Unsupported model family"):
            mapper.token_to_bcp47("eng_Latn", "unknown")  # type: ignore

    def test_get_supported_codes(self):
        """Test getting supported codes for each model family."""
        mapper = TokenMapper()

        nllb_codes = mapper.get_supported_codes("nllb")
        assert "en" in nllb_codes
        assert "zh-Hans" in nllb_codes

        m2m_codes = mapper.get_supported_codes("m2m")
        assert "en" in m2m_codes
        assert "zh-Hans" in m2m_codes

        whisper_codes = mapper.get_supported_codes("whisper")
        assert "en" in whisper_codes
        assert "zh-Hans" in whisper_codes

    def test_get_supported_tokens(self):
        """Test getting supported tokens for each model family."""
        mapper = TokenMapper()

        nllb_tokens = mapper.get_supported_tokens("nllb")
        assert "eng_Latn" in nllb_tokens
        assert "zho_Hans" in nllb_tokens

        m2m_tokens = mapper.get_supported_tokens("m2m")
        assert "en" in m2m_tokens
        assert "zh" in m2m_tokens

        whisper_tokens = mapper.get_supported_tokens("whisper")
        assert "<|en|>" in whisper_tokens
        assert "<|zh|>" in whisper_tokens

    def test_singleton_pattern(self):
        """Test global mapper singleton."""
        mapper1 = get_mapper()
        mapper2 = get_mapper()
        assert mapper1 is mapper2


class TestIntegration:
    """Integration tests combining canonicalizer and mapper."""

    def test_alias_to_token_flow(self):
        """Test complete flow from alias to model token."""
        mapper = TokenMapper()

        # cmn-Hans → zh-Hans → zho_Hans
        token = mapper.bcp47_to_token("cmn-Hans", "nllb", normalize=True)
        assert token == "zho_Hans"

        # zh-CN → zh-Hans → <|zh|>
        token = mapper.bcp47_to_token("zh-CN", "whisper", normalize=True)
        assert token == "<|zh|>"

        # eng → en → en
        token = mapper.bcp47_to_token("eng", "m2m", normalize=True)
        assert token == "en"

    def test_environment_zh_variant_integration(self):
        """Test that environment ZH variant affects token mapping."""
        # Default (Hans)
        mapper = TokenMapper()
        token = mapper.bcp47_to_token("zh", "nllb")
        assert token == "zho_Hans"

        # Set environment to Hant
        original = os.environ.get("LX_LANG_VARIANT_ZH")
        try:
            os.environ["LX_LANG_VARIANT_ZH"] = "Hant"
            # Need to create new canonicalizer to pick up env change
            from loquilex.capabilities.canonicalize import LanguageCanonicalizer
            from loquilex.capabilities.mapper import TokenMapper as TM

            canon = LanguageCanonicalizer()
            mapper_hant = TM()
            mapper_hant._canonicalizer = canon

            token = mapper_hant.bcp47_to_token("zh", "nllb")
            assert token == "zho_Hant"
        finally:
            if original is not None:
                os.environ["LX_LANG_VARIANT_ZH"] = original
            else:
                os.environ.pop("LX_LANG_VARIANT_ZH", None)

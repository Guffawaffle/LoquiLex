from __future__ import annotations

from dataclasses import dataclass


@dataclass
class TranslationResult:
    text: str
    model: str
    src_lang: str = "en"
    tgt_lang: str = "zh"
    duration_ms: float = 0.0
    confidence: float | None = None


class Translator:
    def translate(
        self,
        text: str,
        src_lang: str = "en",
        tgt_lang: str = "zh",
        quality: str = "final",
    ) -> TranslationResult:
        prefix = f"[{tgt_lang}]" if quality == "final" else f"[{tgt_lang}-draft]"
        return TranslationResult(
            f"{prefix}{text}",
            "echo",
            src_lang=src_lang,
            tgt_lang=tgt_lang,
            duration_ms=0.0,
        )

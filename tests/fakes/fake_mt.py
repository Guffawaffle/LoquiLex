from __future__ import annotations

from dataclasses import dataclass


@dataclass
class TranslationResult:
    text: str
    model: str


class Translator:
    def translate_en_to_zh(self, text: str) -> TranslationResult:
        return TranslationResult(f"[zh]{text}", "echo")

    def translate_en_to_zh_draft(self, text: str) -> TranslationResult:
        return TranslationResult(f"[zh-draft]{text}", "echo:draft")

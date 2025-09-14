"""MT core protocols and interfaces."""

from __future__ import annotations

from typing import Iterable, Iterator, Protocol, TypedDict, runtime_checkable

from .types import Lang, QualityMode


class ProviderCapabilities(TypedDict):
    """Provider capability metadata."""
    family: str  # "nllb" | "m2m" | "custom"
    model_name: str  # e.g., "nllb-200-d600M"
    directions: list[tuple[Lang, Lang]]
    requires_target_prefix: bool
    device_types: list[str]  # ["cpu","cuda"]
    compute_types: list[str]  # ["int8","int8_float16","float16","float32"]
    supports_chunked: bool
    supports_streaming_partials: bool


@runtime_checkable
class TokenizerAdapter(Protocol):
    """Tokenizer abstraction for different model families."""

    def encode(self, text: str, src: Lang) -> list[str]:
        """Encode text for source language."""
        ...

    def target_prefix(self, tgt: Lang) -> list[str]:
        """Get target language prefix tokens."""
        ...

    def decode(self, tokens: list[str]) -> str:
        """Decode tokens to text, handling language prefixes."""
        ...


@runtime_checkable
class MTProvider(Protocol):
    """Machine translation provider interface."""

    def translate_text(
        self, text: str, src: Lang, tgt: Lang, *, quality: QualityMode = "realtime"
    ) -> str:
        """Translate single text string."""
        ...

    def translate_chunked(
        self,
        chunks: Iterable[str],
        src: Lang,
        tgt: Lang,
        *,
        quality: QualityMode = "realtime"
    ) -> Iterator[str]:
        """Translate sequence of text chunks, yielding final translations."""
        ...

    def capabilities(self) -> ProviderCapabilities:
        """Get provider capabilities metadata."""
        ...
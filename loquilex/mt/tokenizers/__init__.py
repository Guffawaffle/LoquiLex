"""MT tokenizer adapters."""

from .nllb import NLLBTokenizerAdapter
from .m2m import M2MTokenizerAdapter

__all__ = [
    "NLLBTokenizerAdapter",
    "M2MTokenizerAdapter",
]
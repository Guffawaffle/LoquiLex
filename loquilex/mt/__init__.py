"""LoquiLex MT (Machine Translation) module."""

# Import core interfaces
from .core import MTProvider, TokenizerAdapter, Lang, QualityMode
from .core import register_provider, create, available

# Import providers (auto-registers on import)
from . import providers  # noqa: F401

__all__ = [
    "MTProvider",
    "TokenizerAdapter", 
    "Lang",
    "QualityMode",
    "register_provider",
    "create",
    "available",
]
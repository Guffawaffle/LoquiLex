"""MT core types and constants."""

from __future__ import annotations

from typing import Literal

# Language codes
Lang = Literal["en", "zh-Hans", "zh-Hant"]

# Quality modes for translation
QualityMode = Literal["realtime", "quality"]

# Error types
class MTError(Exception):
    """Base MT error."""
    pass

class MTProviderError(MTError):
    """Provider-specific error."""
    pass

class MTModelLoadError(MTError):
    """Model loading error."""
    pass
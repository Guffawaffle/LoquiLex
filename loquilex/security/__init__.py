"""Security-related utilities for LoquiLex."""

from .path_guard import PathGuard, PathSecurityError
from ._types import CanonicalPath  # re-export for convenience

__all__ = ["PathGuard", "PathSecurityError", "CanonicalPath"]

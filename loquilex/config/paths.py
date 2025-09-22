"""Path utilities for configurable storage locations."""

from __future__ import annotations

import os
from pathlib import Path

# Default output directory relative to project root when no environment override exists
_DEFAULT_OUT_DIR = "loquilex/out"


def resolve_out_dir() -> Path:
    """Return the configured output directory path.

    Prefers `LX_OUT_DIR` and falls back to legacy `LLX_OUT_DIR` before using the
    project default. The returned path expands `~` for user convenience but does
    not resolve symlinks so callers can decide how aggressively to normalise.
    """
    configured = os.getenv("LX_OUT_DIR") or os.getenv("LLX_OUT_DIR") or _DEFAULT_OUT_DIR
    return Path(configured).expanduser()


__all__ = ["resolve_out_dir"]

"""DEPRECATED: Backward compatibility shim for legacy import path.

This module is a shim to maintain backward compatibility with code that imports
from loquilex.cli.live_en_to_zh. The actual implementation has moved to
loquilex.cli.live.

DEPRECATION NOTICE:
Please update your imports to use `loquilex.cli.live` instead of
`loquilex.cli.live_en_to_zh`. This shim will be removed in a future release.

Example migration:
    # Old (deprecated):
    from loquilex.cli.live_en_to_zh import main
    
    # New (recommended):
    from loquilex.cli.live import main
"""
import warnings

warnings.warn(
    "Importing from loquilex.cli.live_en_to_zh is deprecated. "
    "Please use 'from loquilex.cli.live import main' instead. "
    "This compatibility shim will be removed in version 1.0.0.",
    DeprecationWarning,
    stacklevel=2,
)

# Re-export everything from the new location
from loquilex.cli.live import *  # noqa: F401, F403

__all__ = ["main"]

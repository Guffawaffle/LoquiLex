"""
Centralized environment helpers for LoquiLex scripts.

- Canonical prefix: LX_
- Legacy prefix: GF_ (supported with one-time DeprecationWarning)
"""
from __future__ import annotations
import os
import warnings
from typing import Iterable, Optional

_TRUE_SET = {"1", "true", "yes", "on"}
_warned: set[str] = set()

def is_truthy(value: Optional[str]) -> bool:
    if value is None:
        return False
    return value.strip().lower() in _TRUE_SET

def _warn_once(var: str) -> None:
    if var not in _warned:
        warnings.warn(
            f"[LoquiLex] Using legacy env var {var}. Please migrate to LX_*.",
            DeprecationWarning,
            stacklevel=2,
        )
        _warned.add(var)

def getenv(name: str, default: Optional[str] = None, aliases: Iterable[str] = ()) -> Optional[str]:
    """
    Read environment with preference:
      1) Exact 'name' (e.g., LX_FOO)
      2) First present alias in 'aliases' (e.g., GF_FOO) -> warn once
    """
    if name in os.environ:
        return os.environ[name]
    for a in aliases:
        if a in os.environ:
            _warn_once(a)
            return os.environ[a]
    return default

def getenv_bool(name: str, default: bool = False, aliases: Iterable[str] = ()) -> bool:
    val = getenv(name, None, aliases=aliases)
    if val is None:
        return default
    return is_truthy(val)

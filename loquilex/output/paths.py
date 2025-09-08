from __future__ import annotations

from pathlib import Path


def ensure_out_path(root: str | Path, p: str | Path) -> Path:
    """Return a path guaranteed to be within root (creating parents).

    If p is absolute and outside root, raise ValueError. Otherwise, join to root.
    """
    root_p = Path(root).resolve()
    p_in = Path(p)
    if not p_in.is_absolute():
        out = (root_p / p_in).resolve()
    else:
        out = p_in.resolve()
    try:
        out.relative_to(root_p)
    except Exception:
        raise ValueError(f"path {out} escapes output root {root_p}")
    out.parent.mkdir(parents=True, exist_ok=True)
    return out

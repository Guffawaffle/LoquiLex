from __future__ import annotations

import logging
import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Tuple, List

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class RetentionPolicy:
    ttl_seconds: int = 72 * 3600
    max_bytes: Optional[int] = None  # None means unlimited


def _iter_files(root: Path) -> List[Path]:
    try:
        return [p for p in root.rglob("*") if p.is_file()]
    except Exception:
        return []


def _safe_remove(p: Path) -> bool:
    try:
        p.unlink()
        return True
    except FileNotFoundError:
        return False
    except Exception:
        logger.exception("Failed to remove path during retention: %s", p)
        return False


def enforce_retention(root: Path, policy: RetentionPolicy) -> Tuple[int, int]:
    """Enforce retention on files under `root` according to `policy`.

    Returns (deleted_count, remaining_bytes).
    Behavior:
    - TTL pass: delete files with now - mtime > ttl_seconds.
    - Size cap pass: if max_bytes set (>0), compute total and delete oldest
      files (by mtime ascending) until total <= max_bytes.
    """
    root = Path(root)
    now = time.time()
    deleted = 0

    files = _iter_files(root)

    # TTL pass
    if policy.ttl_seconds and policy.ttl_seconds > 0:
        ttl_cutoff = now - float(policy.ttl_seconds)
        for p in files:
            try:
                mtime = p.stat().st_mtime
            except FileNotFoundError:
                continue
            except Exception:
                logger.exception("stat failed for %s", p)
                continue

            if mtime < ttl_cutoff:
                if _safe_remove(p):
                    deleted += 1

    # Recompute remaining files after TTL deletions
    files = [p for p in _iter_files(root)]

    # Compute total bytes
    total_bytes = 0
    file_mtimes = []  # list of (mtime, Path, size)
    for p in files:
        try:
            st = p.stat()
            size = st.st_size
            mtime = st.st_mtime
            total_bytes += size
            file_mtimes.append((mtime, p, size))
        except FileNotFoundError:
            continue
        except Exception:
            logger.exception("stat failed for %s", p)
            continue

    # Size cap pass (if configured and positive)
    if policy.max_bytes and policy.max_bytes > 0 and total_bytes > policy.max_bytes:
        # Sort by mtime ascending (oldest first)
        file_mtimes.sort(key=lambda x: x[0])
        for mtime, p, size in file_mtimes:
            if total_bytes <= policy.max_bytes:
                break
            if _safe_remove(p):
                deleted += 1
                total_bytes -= size

    return deleted, total_bytes

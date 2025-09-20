from __future__ import annotations

import os
import threading
from typing import List, Optional


def _ensure_parent_dir(path: str) -> None:
    d = os.path.dirname(path)
    if d:
        os.makedirs(d, exist_ok=True)


def _write_atomic(path: str, text: str) -> None:
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)
    os.replace(tmp, path)


class RollingTextFile:
    """Text writer that supports atomic single-line rewrites and rolling append with max_lines.

    Contract:
    - rewrite_current_line(line): replaces file contents with all finalized lines + one draft line (no timestamps).
    - append_final_line(line): appends a finalized line to internal buffer and writes file atomically; enforces max_lines by truncating from top.
    - reset(): truncates file and clears internal state.
    """

    def __init__(self, path: str, max_lines: Optional[int] = None, ensure_dir: bool = True):
        self.path = path
        self.max_lines = max_lines if (max_lines is None or max_lines > 0) else None
        self._final_lines: List[str] = []  # stored without trailing \n
        self._lock = threading.Lock()
        if ensure_dir:
            _ensure_parent_dir(self.path)

    def __enter__(self):
        """Support context manager for automatic cleanup."""
        return self

    def __exit__(self, exc_type, exc, tb):
        """Cleanup when exiting context manager."""
        # For file-based operations, no explicit cleanup needed
        # as we use atomic writes with proper context managers
        pass

    def __del__(self):
        """Destructor to ensure cleanup if not already done."""
        # No explicit cleanup needed for file operations
        # as we use atomic writes with proper context managers
        pass

    # Utilities
    def _serialize(self, draft: Optional[str]) -> str:
        parts: List[str] = []
        parts.extend(self._final_lines)
        if draft is not None:
            parts.append(draft)
        # Ensure trailing newline and \n newlines
        return "\n".join(parts) + "\n"

    # API
    def reset(self) -> None:
        with self._lock:
            self._final_lines.clear()
            _ensure_parent_dir(self.path)
            _write_atomic(self.path, "")

    def rewrite_current_line(self, line: str) -> None:
        # Replace entire file with finalized lines + one draft line
        with self._lock:
            text = self._serialize(line)
            _write_atomic(self.path, text)

    def append_final_line(self, line: str) -> None:
        line = (line or "").rstrip("\n")
        if not line:
            # Don't mutate file for empty finalized lines
            return
        with self._lock:
            self._final_lines.append(line)
            if self.max_lines is not None and len(self._final_lines) > self.max_lines:
                # Drop oldest lines (ring buffer behavior)
                overflow = len(self._final_lines) - self.max_lines
                if overflow > 0:
                    self._final_lines = self._final_lines[overflow:]
            text = self._serialize(None)
            _write_atomic(self.path, text)

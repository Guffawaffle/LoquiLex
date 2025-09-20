"""Structured logging with consistent format and offline safety."""

from __future__ import annotations

import json
import os
import sys
import time
import uuid
from enum import Enum
from pathlib import Path
from typing import Any, Dict, Optional, TextIO, Union

from .redaction import DataRedactor


class LogLevel(Enum):
    """Standard log levels."""

    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class StructuredLogger:
    """Offline-safe structured logger with consistent format and redaction."""

    def __init__(
        self,
        component: str,
        session_id: Optional[str] = None,
        output_file: Optional[Union[str, Path, TextIO]] = None,
        enable_console: bool = True,
        redactor: Optional[DataRedactor] = None,
        max_log_size_mb: Optional[int] = None,
        max_log_files: int = 5,
    ) -> None:
        """Initialize structured logger.

        Args:
            component: Component identifier (e.g., 'asr', 'mt', 'supervisor')
            session_id: Optional session ID for correlation
            output_file: Optional file path or handle for log output
            enable_console: Whether to output to console (default: True)
            redactor: Optional data redactor for sensitive information
            max_log_size_mb: Maximum log file size in MB before rotation (None = no limit)
            max_log_files: Maximum number of rotated log files to keep (default: 5)
        """
        self.component = component
        self.session_id = session_id or str(uuid.uuid4())[:8]
        self.start_time = time.time()
        self.redactor = redactor or DataRedactor()

        # Log rotation settings
        self.max_log_size_bytes = (max_log_size_mb * 1024 * 1024) if max_log_size_mb else None
        self.max_log_files = max_log_files
        self.log_file_path: Optional[Path] = None

        # Configure output streams
        self.console_enabled = enable_console
        self.log_file: Optional[TextIO] = None

        if output_file:
            if isinstance(output_file, (str, Path)):
                # Store path for rotation
                self.log_file_path = Path(output_file)
                # Ensure log directory exists
                self.log_file_path.parent.mkdir(parents=True, exist_ok=True)
                self._open_log_file()
            else:
                self.log_file = output_file

    def _format_log_entry(self, level: LogLevel, message: str, **context: Any) -> Dict[str, Any]:
        """Format log entry with consistent structure."""
        # Apply redaction to context
        safe_context = self.redactor.redact_dict(context)

        entry = {
            "timestamp": time.time(),
            "iso_timestamp": time.strftime("%Y-%m-%dT%H:%M:%S.%f", time.gmtime())[:-3] + "Z",
            "level": level.value,
            "component": self.component,
            "session_id": self.session_id,
            "session_time": time.time() - self.start_time,
            "message": message,
            **safe_context,
        }

        return entry

    def _open_log_file(self) -> None:
        """Open log file for writing."""
        if self.log_file_path:
            self.log_file = open(self.log_file_path, "a", encoding="utf-8")

    def _rotate_log_if_needed(self) -> None:
        """Rotate log file if size limit is exceeded."""
        if not self.log_file_path or not self.max_log_size_bytes:
            return

        try:
            if (
                self.log_file_path.exists()
                and self.log_file_path.stat().st_size > self.max_log_size_bytes
            ):
                # Close current file
                if self.log_file:
                    self.log_file.close()

                # Rotate existing files
                for i in range(self.max_log_files - 1, 0, -1):
                    old_file = self.log_file_path.with_suffix(f".{i}{self.log_file_path.suffix}")
                    new_file = self.log_file_path.with_suffix(f".{i+1}{self.log_file_path.suffix}")
                    if old_file.exists():
                        if new_file.exists():
                            new_file.unlink()
                        old_file.rename(new_file)

                # Move current log to .1
                rotated_file = self.log_file_path.with_suffix(f".1{self.log_file_path.suffix}")
                if rotated_file.exists():
                    rotated_file.unlink()
                self.log_file_path.rename(rotated_file)

                # Reopen current log file
                self._open_log_file()
        except Exception:
            # If rotation fails, continue with current file
            if not self.log_file:
                self._open_log_file()

    def _write_log(self, entry: Dict[str, Any]) -> None:
        """Write log entry to configured outputs."""
        json_line = json.dumps(entry, default=str, separators=(",", ":"))

        if self.console_enabled:
            print(json_line, file=sys.stdout, flush=True)

        if self.log_file:
            # Check for rotation before writing
            self._rotate_log_if_needed()

            self.log_file.write(json_line + "\n")
            self.log_file.flush()

    def debug(self, message: str, **context: Any) -> None:
        """Log debug message."""
        entry = self._format_log_entry(LogLevel.DEBUG, message, **context)
        self._write_log(entry)

    def info(self, message: str, **context: Any) -> None:
        """Log info message."""
        entry = self._format_log_entry(LogLevel.INFO, message, **context)
        self._write_log(entry)

    def warning(self, message: str, **context: Any) -> None:
        """Log warning message."""
        entry = self._format_log_entry(LogLevel.WARNING, message, **context)
        self._write_log(entry)

    def error(self, message: str, **context: Any) -> None:
        """Log error message."""
        entry = self._format_log_entry(LogLevel.ERROR, message, **context)
        self._write_log(entry)

    def critical(self, message: str, **context: Any) -> None:
        """Log critical message."""
        entry = self._format_log_entry(LogLevel.CRITICAL, message, **context)
        self._write_log(entry)

    def close(self) -> None:
        """Close log file handle if open."""
        if self.log_file and hasattr(self.log_file, "close"):
            self.log_file.close()
            self.log_file = None


def create_logger(
    component: str,
    session_id: Optional[str] = None,
    log_dir: Optional[Union[str, Path]] = None,
    **kwargs: Any,
) -> StructuredLogger:
    """Factory function to create structured logger with standard configuration.

    Args:
        component: Component identifier
        session_id: Optional session ID for correlation
        log_dir: Optional directory for log files (uses LX_LOG_DIR env var if not provided)
        **kwargs: Additional arguments passed to StructuredLogger

    Returns:
        Configured StructuredLogger instance
    """
    # Use environment variable for log directory if not provided
    if log_dir is None:
        log_dir = os.getenv("LX_LOG_DIR")

    # CI-specific log retention settings from environment
    if "max_log_size_mb" not in kwargs:
        ci_max_size = os.getenv("LX_LOG_MAX_SIZE_MB")
        if ci_max_size:
            kwargs["max_log_size_mb"] = int(ci_max_size)
        elif os.getenv("CI") == "true":
            # Default CI limit: 10MB per log file
            kwargs["max_log_size_mb"] = 10

    if "max_log_files" not in kwargs:
        ci_max_files = os.getenv("LX_LOG_MAX_FILES")
        if ci_max_files:
            kwargs["max_log_files"] = int(ci_max_files)
        elif os.getenv("CI") == "true":
            # Default CI limit: keep only 3 rotated files
            kwargs["max_log_files"] = 3

    output_file = None
    if log_dir:
        log_path = Path(log_dir) / f"{component}_{session_id or 'default'}.jsonl"
        output_file = log_path

    return StructuredLogger(
        component=component, session_id=session_id, output_file=output_file, **kwargs
    )

"""Structured logging and metrics for LoquiLex."""

from .structured import StructuredLogger, LogLevel, create_logger
from .metrics import PerformanceMetrics, MetricType
from .redaction import DataRedactor

__all__ = [
    "StructuredLogger",
    "LogLevel",
    "create_logger",
    "PerformanceMetrics",
    "MetricType",
    "DataRedactor",
    "cleanup_old_logs",
]


def cleanup_old_logs(log_dir: str, max_age_hours: int = 24, dry_run: bool = False) -> int:
    """Clean up old log files in a directory.

    Args:
        log_dir: Directory containing log files
        max_age_hours: Remove files older than this many hours (default: 24)
        dry_run: If True, only report what would be deleted

    Returns:
        Number of files that were (or would be) deleted
    """
    import os
    import time
    from pathlib import Path

    if not os.path.exists(log_dir):
        return 0

    log_path = Path(log_dir)
    cutoff_time = time.time() - (max_age_hours * 3600)
    deleted_count = 0

    for log_file in log_path.glob("*.jsonl*"):
        try:
            if log_file.stat().st_mtime < cutoff_time:
                if dry_run:
                    print(f"Would delete: {log_file}")
                else:
                    log_file.unlink()
                deleted_count += 1
        except Exception:
            # Skip files we can't process
            continue

    return deleted_count

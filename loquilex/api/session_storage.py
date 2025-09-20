"""Rolling session storage with capped history for transcripts and events.

This module provides durable, bounded storage for session transcripts and events
with configurable retention policies (count, size, time-based).
"""

from __future__ import annotations

import time
from collections import deque
from dataclasses import dataclass, field
from typing import Any, Deque, Dict, List, Optional
import uuid

__all__ = ["SessionCommit", "SessionStorage", "StorageConfig"]


@dataclass
class SessionCommit:
    """A finalized commit stored in session history."""

    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: float = field(default_factory=lambda: time.monotonic())
    seq: int = 0
    commit_type: str = "transcript"  # "transcript", "translation", "status"
    data: Dict[str, Any] = field(default_factory=dict)
    size_bytes: int = 0  # For size-based capping

    def __post_init__(self):
        """Calculate size after creation."""
        if self.size_bytes == 0:
            # Rough estimate of memory footprint
            import sys

            self.size_bytes = (
                sys.getsizeof(self.id)
                + sys.getsizeof(self.timestamp)
                + sys.getsizeof(self.seq)
                + sys.getsizeof(self.commit_type)
                + sys.getsizeof(self.data)
                + sum(sys.getsizeof(k) + sys.getsizeof(v) for k, v in self.data.items())
            )


@dataclass
class StorageConfig:
    """Configuration for session storage limits."""

    max_commits: int = 100  # Max number of commits to store
    max_size_bytes: int = 1024 * 1024  # Max total size (1MB default)
    max_age_seconds: float = 3600.0  # Max age of commits (1 hour default)

    def validate(self) -> None:
        """Validate configuration values."""
        if self.max_commits <= 0:
            raise ValueError("max_commits must be positive")
        if self.max_size_bytes <= 0:
            raise ValueError("max_size_bytes must be positive")
        if self.max_age_seconds <= 0:
            raise ValueError("max_age_seconds must be positive")


class SessionStorage:
    """Rolling session storage with capped history.

    Features:
    - Stores finalized commits with timestamps and IDs
    - Caps by max entries, size, and age with rotation
    - Thread-safe operations
    - Snapshot API for session rehydration
    """

    def __init__(self, session_id: str, config: Optional[StorageConfig] = None, now_fn=None):
        self.session_id = session_id
        self.config = config or StorageConfig()
        self.config.validate()
        self.now_fn = now_fn or time.monotonic

        # Storage for commits (ordered by insertion time)
        self._commits: Deque[SessionCommit] = deque()
        self._total_size_bytes = 0

        # Thread safety
        import threading

        self._lock = threading.RLock()

        # Metrics
        self._commits_added = 0
        self._commits_dropped = 0
        self._last_cleanup_time = self.now_fn()

    def add_commit(self, commit_type: str, data: Dict[str, Any], seq: int = 0) -> SessionCommit:
        """Add a finalized commit to storage with automatic rotation.

        Args:
            commit_type: Type of commit ("transcript", "translation", "status")
            data: Commit data payload
            seq: Sequence number for ordering

        Returns:
            The created commit with assigned ID and timestamp
        """
        commit = SessionCommit(
            timestamp=self.now_fn(),  # Use the injected time function
            seq=seq,
            commit_type=commit_type,
            data=data.copy(),  # Defensive copy
        )

        with self._lock:
            # Add the commit
            self._commits.append(commit)
            self._total_size_bytes += commit.size_bytes
            self._commits_added += 1

            # Enforce limits with rotation
            self._enforce_limits()

        return commit

    def _enforce_limits(self) -> None:
        """Enforce storage limits by dropping oldest commits (must hold lock)."""
        now = self.now_fn()

        # Time-based cleanup
        while self._commits:
            oldest = self._commits[0]
            if now - oldest.timestamp > self.config.max_age_seconds:
                dropped = self._commits.popleft()
                self._total_size_bytes -= dropped.size_bytes
                self._commits_dropped += 1
            else:
                break

        # Count-based cleanup
        while len(self._commits) > self.config.max_commits:
            dropped = self._commits.popleft()
            self._total_size_bytes -= dropped.size_bytes
            self._commits_dropped += 1

        # Size-based cleanup
        while self._total_size_bytes > self.config.max_size_bytes and len(self._commits) > 0:
            dropped = self._commits.popleft()
            self._total_size_bytes -= dropped.size_bytes
            self._commits_dropped += 1

        self._last_cleanup_time = now

    def get_commits(
        self,
        limit: Optional[int] = None,
        commit_type: Optional[str] = None,
        since_timestamp: Optional[float] = None,
    ) -> List[SessionCommit]:
        """Get stored commits with optional filtering.

        Args:
            limit: Maximum number of commits to return (most recent first)
            commit_type: Filter by commit type
            since_timestamp: Only return commits after this timestamp

        Returns:
            List of commits matching criteria, most recent first
        """
        with self._lock:
            # Clean up expired commits first
            self._enforce_limits()

            # Apply filters
            commits = list(self._commits)

            if commit_type:
                commits = [c for c in commits if c.commit_type == commit_type]

            if since_timestamp is not None:
                commits = [c for c in commits if c.timestamp > since_timestamp]

            # Sort by timestamp (most recent first) then apply limit
            commits.sort(key=lambda c: c.timestamp, reverse=True)

            if limit is not None:
                commits = commits[:limit]

            return commits

    def get_snapshot(self, max_commits: int = 20) -> Dict[str, Any]:
        """Generate snapshot for session rehydration.

        Args:
            max_commits: Maximum number of recent commits to include

        Returns:
            Snapshot data for session restoration
        """
        with self._lock:
            recent_commits = self.get_commits(limit=max_commits)

            return {
                "session_id": self.session_id,
                "timestamp": self.now_fn(),
                "total_commits": len(self._commits),
                "recent_commits": [
                    {
                        "id": c.id,
                        "timestamp": c.timestamp,
                        "seq": c.seq,
                        "type": c.commit_type,
                        "data": c.data,
                    }
                    for c in recent_commits
                ],
                "storage_stats": self.get_stats(),
            }

    def get_stats(self) -> Dict[str, Any]:
        """Get storage statistics.

        Returns:
            Dictionary with current storage metrics
        """
        with self._lock:
            return {
                "session_id": self.session_id,
                "total_commits": len(self._commits),
                "total_size_bytes": self._total_size_bytes,
                "commits_added": self._commits_added,
                "commits_dropped": self._commits_dropped,
                "config": {
                    "max_commits": self.config.max_commits,
                    "max_size_bytes": self.config.max_size_bytes,
                    "max_age_seconds": self.config.max_age_seconds,
                },
                "oldest_commit_age": (
                    self.now_fn() - self._commits[0].timestamp if self._commits else 0.0
                ),
            }

    def clear(self) -> int:
        """Clear all stored commits.

        Returns:
            Number of commits that were cleared
        """
        with self._lock:
            count = len(self._commits)
            self._commits.clear()
            self._total_size_bytes = 0
            return count

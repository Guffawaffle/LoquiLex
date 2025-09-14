"""Bounded Queue: drop-oldest with telemetry for resilient comms.

This module provides bounded queues with configurable drop policies and
comprehensive telemetry for implementing backpressure and monitoring.
"""

from __future__ import annotations

import time
from collections import deque
from dataclasses import dataclass, field
from typing import Any, Deque, Generic, Optional, TypeVar

T = TypeVar("T")


@dataclass
class DropMetrics:
    """Telemetry for dropped items."""

    total_dropped: int = 0
    drop_count_since_last_read: int = 0
    last_drop_time_mono: float = 0.0
    drop_reason: str = ""

    def record_drop(self, reason: str = "capacity") -> None:
        """Record a drop event."""
        self.total_dropped += 1
        self.drop_count_since_last_read += 1
        self.last_drop_time_mono = time.monotonic()
        self.drop_reason = reason

    def read_and_reset_recent(self) -> int:
        """Read drop count since last read and reset counter."""
        count = self.drop_count_since_last_read
        self.drop_count_since_last_read = 0
        return count


class BoundedQueue(Generic[T]):
    """Thread-safe bounded queue with drop-oldest policy and telemetry.
    
    Features:
    - Fixed capacity with drop-oldest behavior
    - Non-blocking producers (never block, may drop)
    - Comprehensive drop telemetry
    - Thread-safe operations
    """

    def __init__(self, maxsize: int, name: str = "queue"):
        if maxsize <= 0:
            raise ValueError("maxsize must be positive")
        
        self.maxsize = maxsize
        self.name = name
        self._queue: Deque[T] = deque(maxlen=maxsize)
        self.metrics = DropMetrics()
        self._lock = None  # Will be initialized when first accessed
        
    def _ensure_lock(self):
        """Lazy initialization of lock for thread safety."""
        if self._lock is None:
            import threading
            self._lock = threading.RLock()

    def put_nowait(self, item: T) -> bool:
        """Add item to queue, dropping oldest if at capacity.
        
        Returns:
            True if item was added, False if dropped (should not happen with deque)
        """
        self._ensure_lock()
        with self._lock:
            # Check if we're at capacity before adding
            dropped = len(self._queue) == self.maxsize
            
            # Add item (deque automatically drops oldest if at maxlen)
            self._queue.append(item)
            
            # Record drop if we were at capacity
            if dropped:
                self.metrics.record_drop("capacity")
                
            return True  # deque always accepts items

    def get_nowait(self) -> Optional[T]:
        """Remove and return item from front of queue.
        
        Returns:
            Item if available, None if queue is empty
        """
        self._ensure_lock()
        with self._lock:
            try:
                return self._queue.popleft()
            except IndexError:
                return None

    def peek(self) -> Optional[T]:
        """Return front item without removing it."""
        self._ensure_lock()
        with self._lock:
            if self._queue:
                return self._queue[0]
            return None

    def size(self) -> int:
        """Return current queue size."""
        self._ensure_lock()
        with self._lock:
            return len(self._queue)

    def is_empty(self) -> bool:
        """Check if queue is empty."""
        return self.size() == 0

    def is_full(self) -> bool:
        """Check if queue is at capacity."""
        return self.size() >= self.maxsize

    def clear(self) -> int:
        """Clear all items and return count of items removed."""
        self._ensure_lock()
        with self._lock:
            count = len(self._queue)
            self._queue.clear()
            return count

    def get_telemetry(self) -> dict[str, Any]:
        """Get comprehensive telemetry data."""
        self._ensure_lock()
        with self._lock:
            return {
                "name": self.name,
                "size": len(self._queue),
                "capacity": self.maxsize,
                "utilization": len(self._queue) / self.maxsize,
                "total_dropped": self.metrics.total_dropped,
                "recent_drops": self.metrics.drop_count_since_last_read,
                "last_drop_time_mono": self.metrics.last_drop_time_mono,
                "last_drop_reason": self.metrics.drop_reason,
            }

    def drain(self) -> list[T]:
        """Remove and return all items as a list."""
        self._ensure_lock()
        with self._lock:
            items = list(self._queue)
            self._queue.clear()
            return items


class ReplayBuffer(BoundedQueue[Any]):
    """Specialized bounded queue for WebSocket message replay.
    
    Maintains messages with sequence numbers for replay after reconnect.
    Supports both time-based and capacity-based eviction.
    """

    def __init__(self, maxsize: int = 500, ttl_seconds: float = 10.0):
        super().__init__(maxsize, name="replay_buffer")
        self.ttl_seconds = ttl_seconds

    def add_message(self, seq: int, envelope: Any) -> None:
        """Add message with sequence number and automatic cleanup."""
        # Clean up expired messages first
        self._cleanup_expired()
        
        # Store message with metadata
        message_record = {
            "seq": seq,
            "envelope": envelope,
            "timestamp": time.monotonic(),
        }
        
        self.put_nowait(message_record)

    def get_messages_after(self, last_seq: int) -> list[Any]:
        """Get all messages with seq > last_seq for replay."""
        self._ensure_lock()
        with self._lock:
            # Clean up expired messages
            self._cleanup_expired()
            
            result = []
            for record in self._queue:
                # Access seq from the record, not the envelope
                if record["seq"] > last_seq:
                    result.append(record["envelope"])
            
            return result

    def _cleanup_expired(self) -> None:
        """Remove messages older than TTL."""
        if self.ttl_seconds <= 0:
            return
            
        current_time = time.monotonic()
        cutoff_time = current_time - self.ttl_seconds
        
        # Remove from front while messages are expired
        while self._queue:
            if self._queue[0]["timestamp"] < cutoff_time:
                self._queue.popleft()
                self.metrics.record_drop("ttl_expired")
            else:
                break
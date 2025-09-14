"""Partial/final aggregator with ordering, stability, and reconnect snapshots."""

from __future__ import annotations

import time
from collections import deque
from dataclasses import dataclass
from typing import Any, Callable, Deque, Dict, List, Optional

from .stream import ASRPartialEvent, ASRFinalEvent
from .metrics import ASRMetrics

__all__ = ["PartialFinalAggregator"]


@dataclass
class PartialState:
    """Track partial events for a segment."""

    segment_id: str
    latest_seq: int
    latest_text: str
    latest_words: List[Dict[str, Any]]
    last_update: float


@dataclass
class FinalSegment:
    """Committed final segment."""

    segment_id: str
    text: str
    words: List[Dict[str, Any]]
    ts_monotonic: float
    eou_reason: str


class PartialFinalAggregator:
    """
    Aggregates partial/final ASR events with ordering guarantees and bounded queues.

    Features:
    - Monotonic sequence numbers per stream
    - Stable segment IDs for partials until finalized
    - Bounded queues with backpressure (drops oldest partials, preserves finals)
    - Snapshot rehydration for reconnects
    - No duplicate finals on reconnect
    """

    def __init__(
        self,
        stream_id: str,
        max_partials: int = 100,  # configurable via LX_ASR_MAX_PARTIALS
        max_recent_finals: int = 20,
        now_fn: Optional[Callable[[], float]] = None,
        enable_metrics: bool = True,
    ) -> None:
        self.stream_id = stream_id
        self.max_partials = max_partials
        self.max_recent_finals = max_recent_finals
        self.now = now_fn or time.monotonic

        # Sequence tracking
        self.global_seq = 0

        # Partial tracking (bounded queue)
        self.partials: Dict[str, PartialState] = {}
        self.partial_order: Deque[str] = deque()  # for LRU eviction

        # Final segments (keep recent for snapshots)
        self.recent_finals: Deque[FinalSegment] = deque()
        self.finalized_segment_ids = set()  # prevent duplicate finals

        # Live partial for snapshots
        self.current_partial: Optional[PartialState] = None

        # Performance metrics
        self.metrics = ASRMetrics(stream_id) if enable_metrics else None

    def add_partial(
        self,
        partial: ASRPartialEvent,
        emit_fn: Callable[[Dict[str, Any]], None],
    ) -> None:
        """Process a partial event with backpressure and deduplication."""

        # Update global sequence
        self.global_seq += 1

        # Check if segment was already finalized (ignore late partials)
        if partial.segment_id in self.finalized_segment_ids:
            return

        now = self.now()

        # Convert words to dict format for JSON serialization
        words_dict = [{"w": w.w, "t0": w.t0, "t1": w.t1, "conf": w.conf} for w in partial.words]

        # Update or create partial state
        if partial.segment_id in self.partials:
            # Update existing partial
            state = self.partials[partial.segment_id]
            state.latest_seq = partial.seq
            state.latest_text = partial.text
            state.latest_words = words_dict
            state.last_update = now
        else:
            # New partial - check if we need to evict old ones
            if len(self.partials) >= self.max_partials:
                # Evict oldest partial
                oldest_id = self.partial_order.popleft()
                if oldest_id in self.partials:
                    del self.partials[oldest_id]

            # Create new partial state
            state = PartialState(
                segment_id=partial.segment_id,
                latest_seq=partial.seq,
                latest_text=partial.text,
                latest_words=words_dict,
                last_update=now,
            )
            self.partials[partial.segment_id] = state
            self.partial_order.append(partial.segment_id)

        # Update current partial for snapshots
        self.current_partial = state

        # Emit enriched partial event
        enriched_event = {
            "type": "asr.partial",
            "stream_id": self.stream_id,
            "segment_id": partial.segment_id,
            "seq": self.global_seq,
            "text": partial.text,
            "words": words_dict,
            "stable": False,
            "ts_monotonic": now,
        }

        emit_fn(enriched_event)

        # Record metrics
        if self.metrics:
            self.metrics.on_partial_event(enriched_event)

    def add_final(
        self,
        final: ASRFinalEvent,
        emit_fn: Callable[[Dict[str, Any]], None],
    ) -> None:
        """Process a final event with deduplication."""

        # Check for duplicate final
        if final.segment_id in self.finalized_segment_ids:
            return  # Already finalized, ignore

        # Update global sequence
        self.global_seq += 1

        # Convert words to dict format
        words_dict = [{"w": w.w, "t0": w.t0, "t1": w.t1, "conf": w.conf} for w in final.words]

        # Create final segment record
        final_segment = FinalSegment(
            segment_id=final.segment_id,
            text=final.text,
            words=words_dict,
            ts_monotonic=final.ts_monotonic,
            eou_reason=final.eou_reason,
        )

        # Add to recent finals (bounded)
        self.recent_finals.append(final_segment)
        if len(self.recent_finals) > self.max_recent_finals:
            self.recent_finals.popleft()
            # Keep finalized_segment_ids for recent finals only
            # (older ones can be forgotten to prevent unbounded growth)

        # Mark as finalized
        self.finalized_segment_ids.add(final.segment_id)

        # Remove from partials if present
        if final.segment_id in self.partials:
            del self.partials[final.segment_id]
            # Remove from order tracking
            try:
                self.partial_order.remove(final.segment_id)
            except ValueError:
                pass  # Already removed

        # Clear current partial if it was this segment
        if self.current_partial and self.current_partial.segment_id == final.segment_id:
            self.current_partial = None

        # Emit enriched final event
        enriched_event = {
            "type": "asr.final",
            "stream_id": self.stream_id,
            "segment_id": final.segment_id,
            "text": final.text,
            "words": words_dict,
            "ts_monotonic": final.ts_monotonic,
            "eou_reason": final.eou_reason,
        }

        emit_fn(enriched_event)

        # Record metrics
        if self.metrics:
            self.metrics.on_final_event(enriched_event)

    def get_snapshot(self) -> Dict[str, Any]:
        """Generate snapshot for reconnect scenarios."""

        # Build recent finals list
        recent_finals_list = []
        for final_seg in self.recent_finals:
            recent_finals_list.append(
                {
                    "segment_id": final_seg.segment_id,
                    "text": final_seg.text,
                    "t0": final_seg.words[0]["t0"] if final_seg.words else 0.0,
                    "t1": final_seg.words[-1]["t1"] if final_seg.words else 0.0,
                }
            )

        # Build live partial (most recent partial state)
        live_partial = None
        if self.current_partial:
            live_partial = {
                "segment_id": self.current_partial.segment_id,
                "text": self.current_partial.latest_text,
                "words": self.current_partial.latest_words,
                "seq": self.global_seq,  # Use current global seq
            }

        snapshot = {
            "type": "asr.snapshot",
            "stream_id": self.stream_id,
            "recent_finals": recent_finals_list,
            "live_partial": live_partial,
            "ts_monotonic": self.now(),
        }

        return snapshot

    def get_stats(self) -> Dict[str, Any]:
        """Get aggregator statistics for monitoring."""
        base_stats = {
            "stream_id": self.stream_id,
            "global_seq": self.global_seq,
            "active_partials": len(self.partials),
            "recent_finals": len(self.recent_finals),
            "finalized_segments": len(self.finalized_segment_ids),
            "max_partials": self.max_partials,
            "max_recent_finals": self.max_recent_finals,
        }

        # Add performance metrics if available
        if self.metrics:
            base_stats["performance"] = self.metrics.get_summary()

        return base_stats

    def get_metrics_summary(self) -> Optional[Dict[str, Any]]:
        """Get performance metrics summary."""
        return self.metrics.get_summary() if self.metrics else None

    def log_metrics_summary(self) -> None:
        """Log performance metrics summary."""
        if self.metrics:
            self.metrics.log_summary()

    def clear_old_finals(self, keep_count: Optional[int] = None) -> None:
        """Clear old final segments to prevent unbounded growth."""
        if keep_count is None:
            keep_count = self.max_recent_finals // 2  # Keep half

        while len(self.recent_finals) > keep_count:
            old_final = self.recent_finals.popleft()
            # Remove from finalized set to allow memory cleanup
            self.finalized_segment_ids.discard(old_final.segment_id)

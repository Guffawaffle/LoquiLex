"""Performance metrics and structured logging for streaming ASR."""

from __future__ import annotations

import time
from collections import deque
from dataclasses import dataclass, field
from typing import Any, Deque, Dict, Optional

from ..logging import StructuredLogger, PerformanceMetrics, create_logger

__all__ = ["ASRMetrics"]


@dataclass
class LatencyMetrics:
    """Track latency statistics."""

    count: int = 0
    total: float = 0.0
    min_val: Optional[float] = None
    max_val: Optional[float] = None
    recent_values: Deque[float] = field(default_factory=lambda: deque(maxlen=100))

    def add(self, value: float) -> None:
        """Add a new latency measurement."""
        self.count += 1
        self.total += value
        self.recent_values.append(value)

        if self.min_val is None or value < self.min_val:
            self.min_val = value
        if self.max_val is None or value > self.max_val:
            self.max_val = value

    def get_stats(self) -> Dict[str, float]:
        """Get statistical summary."""
        if self.count == 0:
            return {"count": 0}

        recent = list(self.recent_values)
        if not recent:
            return {"count": self.count, "avg": self.total / self.count}

        recent_sorted = sorted(recent)
        n = len(recent_sorted)

        return {
            "count": self.count,
            "avg": self.total / self.count,
            "min": self.min_val or 0.0,
            "max": self.max_val or 0.0,
            "p50": recent_sorted[n // 2] if n > 0 else 0.0,
            "p95": recent_sorted[int(n * 0.95)] if n > 0 else 0.0,
            "recent_avg": sum(recent) / len(recent) if recent else 0.0,
        }


class ASRMetrics:
    """Collect and report ASR performance metrics."""

    def __init__(
        self, 
        stream_id: str, 
        logger: Optional[StructuredLogger] = None
    ) -> None:
        self.stream_id = stream_id
        self.start_time = time.monotonic()

        # Initialize structured logger
        self.logger = logger or create_logger(
            component="asr_metrics",
            session_id=stream_id,
        )
        
        # Initialize performance metrics
        self.perf_metrics = PerformanceMetrics(
            logger=self.logger,
            component="asr",
        )

        # Latency tracking (keep existing for compatibility)
        self.partial_intervals = LatencyMetrics()  # Time between partials
        self.final_latency = LatencyMetrics()  # Time from last partial to final

        # Event counters
        self.partial_count = 0
        self.final_count = 0
        self.eou_reasons: Dict[str, int] = {}

        # State for interval calculation
        self.last_partial_time: Optional[float] = None
        self.segment_start_time: Optional[float] = None
        
        # Set performance thresholds
        self.perf_metrics.set_threshold("partial_interval", warning=200.0, critical=300.0)
        self.perf_metrics.set_threshold("final_latency", warning=800.0, critical=1200.0)
        
        self.logger.info("ASR metrics initialized", stream_id=stream_id)

    def on_partial_event(self, event_dict: Dict[str, Any]) -> None:
        """Record partial event for metrics."""
        current_time = time.monotonic()
        self.partial_count += 1

        # Track inter-partial interval
        if self.last_partial_time is not None:
            interval = current_time - self.last_partial_time
            interval_ms = interval * 1000  # Convert to ms
            self.partial_intervals.add(interval_ms)
            
            # Record to performance metrics
            self.perf_metrics.record_latency(
                "partial_interval", 
                interval_ms,
                segment_id=event_dict.get("segment_id"),
                text_length=len(event_dict.get("text", "")),
            )

        self.last_partial_time = current_time

        # Mark segment start if this is the first partial for a segment
        if self.segment_start_time is None:
            self.segment_start_time = current_time

        # Log structured partial event
        self._log_event(
            "partial",
            {
                "text_length": len(event_dict.get("text", "")),
                "word_count": len(event_dict.get("words", [])),
                "seq": event_dict.get("seq"),
                "segment_id": event_dict.get("segment_id"),
            },
        )

    def on_final_event(self, event_dict: Dict[str, Any]) -> None:
        """Record final event for metrics."""
        current_time = time.monotonic()
        self.final_count += 1

        # Track finalization latency (from last partial to final)
        if self.last_partial_time is not None:
            latency = current_time - self.last_partial_time
            latency_ms = latency * 1000  # Convert to ms
            self.final_latency.add(latency_ms)
            
            # Record to performance metrics
            self.perf_metrics.record_latency(
                "final_latency",
                latency_ms,
                segment_id=event_dict.get("segment_id"),
                eou_reason=event_dict.get("eou_reason", "unknown"),
            )

        # Track EOU reasons
        eou_reason = event_dict.get("eou_reason", "unknown")
        self.eou_reasons[eou_reason] = self.eou_reasons.get(eou_reason, 0) + 1

        # Calculate segment duration
        segment_duration = None
        if self.segment_start_time is not None:
            segment_duration = current_time - self.segment_start_time

        # Log structured final event
        self._log_event(
            "final",
            {
                "text_length": len(event_dict.get("text", "")),
                "word_count": len(event_dict.get("words", [])),
                "eou_reason": eou_reason,
                "segment_duration_ms": segment_duration * 1000 if segment_duration else None,
                "segment_id": event_dict.get("segment_id"),
            },
        )

        # Reset segment state
        self.last_partial_time = None
        self.segment_start_time = None

    def _log_event(self, event_type: str, details: Dict[str, Any]) -> None:
        """Log structured event with metrics."""
        self.logger.info(
            f"ASR event: {event_type}",
            event_type=event_type,
            stream_id=self.stream_id,
            session_duration=time.monotonic() - self.start_time,
            **details,
        )

    def get_summary(self) -> Dict[str, Any]:
        """Generate a summary of all metrics."""
        session_duration = time.monotonic() - self.start_time
        summary: Dict[str, Any] = {
            "stream_id": self.stream_id,
            "events": {
                "partial_count": self.partial_count,
                "final_count": self.final_count,
            },
            "eou_reasons": dict(self.eou_reasons),
            "partial_intervals_ms": self.partial_intervals.get_stats(),
            "final_latency_ms": self.final_latency.get_stats(),
        }

        # Calculate derived metrics
        if session_duration > 0:
            summary["events_per_second"] = {
                "partials": self.partial_count / session_duration,
                "finals": self.final_count / session_duration,
            }

        # Performance assessment
        partial_stats = self.partial_intervals.get_stats()
        final_stats = self.final_latency.get_stats()

        performance: Dict[str, bool] = {}
        if "p50" in partial_stats:
            performance["partial_p50_target"] = partial_stats["p50"] <= 200  # < 200ms target
            performance["partial_p95_target"] = partial_stats.get("p95", 0) <= 300  # < 300ms target

        if "p95" in final_stats:
            performance["final_p95_target"] = final_stats["p95"] <= 800  # ≤ 800ms target

        if performance:
            summary["performance"] = performance

        return summary

    def log_summary(self) -> None:
        """Log a summary of all metrics."""
        summary = self.get_summary()
        self._log_event("session_summary", summary)

    def reset(self) -> None:
        """Reset all metrics (for testing or restart scenarios)."""
        self.partial_intervals = LatencyMetrics()
        self.final_latency = LatencyMetrics()
        self.partial_count = 0
        self.final_count = 0
        self.eou_reasons.clear()
        self.last_partial_time = None
        self.segment_start_time = None
        self.start_time = time.monotonic()
        
        # Reset performance metrics
        self.perf_metrics.reset()
        
        self.logger.info("ASR metrics reset", stream_id=self.stream_id)

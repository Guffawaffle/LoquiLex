"""Performance metrics collection with structured logging integration."""

from __future__ import annotations

import time
from collections import deque
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Deque, Dict, Optional

from .structured import StructuredLogger


class MetricType(Enum):
    """Types of performance metrics."""

    LATENCY = "latency"
    THROUGHPUT = "throughput"
    COUNTER = "counter"
    GAUGE = "gauge"


@dataclass
class MetricValue:
    """Individual metric measurement."""

    timestamp: float
    value: float
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class MetricStats:
    """Statistical summary of metric measurements."""

    count: int = 0
    sum: float = 0.0
    min: Optional[float] = None
    max: Optional[float] = None
    avg: Optional[float] = None
    p50: Optional[float] = None
    p95: Optional[float] = None
    p99: Optional[float] = None
    recent_avg: Optional[float] = None


class PerformanceMetrics:
    """Collect and report performance metrics with structured logging."""

    def __init__(
        self,
        logger: Optional[StructuredLogger] = None,
        window_size: int = 1000,
        component: Optional[str] = None,
    ) -> None:
        """Initialize performance metrics collector.

        Args:
            logger: Optional structured logger for metric events
            window_size: Size of sliding window for recent metrics
            component: Component name for metrics namespace
        """
        self.logger = logger
        self.component = component or "unknown"
        self.window_size = window_size

        # Metric storage by name
        self.metrics: Dict[str, Deque[MetricValue]] = {}
        self.counters: Dict[str, float] = {}
        self.gauges: Dict[str, float] = {}

        # Timing contexts
        self._active_timers: Dict[str, float] = {}

        # Performance thresholds for alerting
        self.thresholds: Dict[str, Dict[str, float]] = {}

    def record_latency(
        self,
        name: str,
        duration_ms: float,
        **metadata: Any
    ) -> None:
        """Record latency measurement.

        Args:
            name: Metric name
            duration_ms: Duration in milliseconds
            **metadata: Additional context for the measurement
        """
        self._add_measurement(name, duration_ms, MetricType.LATENCY, metadata)

    def record_throughput(
        self,
        name: str,
        count: float,
        **metadata: Any
    ) -> None:
        """Record throughput measurement.

        Args:
            name: Metric name
            count: Number of operations/events
            **metadata: Additional context for the measurement
        """
        self._add_measurement(name, count, MetricType.THROUGHPUT, metadata)

    def increment_counter(self, name: str, value: float = 1.0) -> None:
        """Increment a counter metric.

        Args:
            name: Counter name
            value: Value to add (default: 1.0)
        """
        self.counters[name] = self.counters.get(name, 0.0) + value

        if self.logger:
            self.logger.debug(
                f"Counter incremented: {name}",
                metric_type=MetricType.COUNTER.value,
                metric_name=name,
                counter_value=self.counters[name],
                increment=value,
            )

    def set_gauge(self, name: str, value: float) -> None:
        """Set a gauge metric value.

        Args:
            name: Gauge name
            value: Current value
        """
        self.gauges[name] = value

        if self.logger:
            self.logger.debug(
                f"Gauge updated: {name}",
                metric_type=MetricType.GAUGE.value,
                metric_name=name,
                gauge_value=value,
            )

    def start_timer(self, name: str) -> None:
        """Start timing a latency measurement.

        Args:
            name: Timer/metric name
        """
        self._active_timers[name] = time.time()

    def end_timer(self, name: str, **metadata: Any) -> float:
        """End timing and record latency.

        Args:
            name: Timer/metric name
            **metadata: Additional context for the measurement

        Returns:
            Duration in milliseconds

        Raises:
            KeyError: If timer was not started
        """
        if name not in self._active_timers:
            raise KeyError(f"Timer '{name}' was not started")

        start_time = self._active_timers.pop(name)
        duration_ms = (time.time() - start_time) * 1000

        self.record_latency(name, duration_ms, **metadata)
        return duration_ms

    def _add_measurement(
        self,
        name: str,
        value: float,
        metric_type: MetricType,
        metadata: Dict[str, Any],
    ) -> None:
        """Add a measurement to the metrics storage."""
        if name not in self.metrics:
            self.metrics[name] = deque(maxlen=self.window_size)

        measurement = MetricValue(
            timestamp=time.time(),
            value=value,
            metadata=metadata,
        )
        self.metrics[name].append(measurement)

        # Check thresholds and log if needed
        self._check_thresholds(name, value, metric_type)

        if self.logger:
            self.logger.debug(
                f"Metric recorded: {name}",
                metric_type=metric_type.value,
                metric_name=name,
                metric_value=value,
                **metadata,
            )

    def get_stats(self, name: str) -> Optional[MetricStats]:
        """Get statistical summary for a metric.

        Args:
            name: Metric name

        Returns:
            Statistical summary or None if metric doesn't exist
        """
        if name not in self.metrics or not self.metrics[name]:
            return None

        values = [m.value for m in self.metrics[name]]
        values_sorted = sorted(values)
        n = len(values_sorted)

        stats = MetricStats()
        stats.count = n
        stats.sum = sum(values)
        stats.min = min(values)
        stats.max = max(values)
        stats.avg = stats.sum / n

        # Percentiles
        if n > 0:
            stats.p50 = values_sorted[n // 2]
            stats.p95 = values_sorted[int(n * 0.95)] if n > 1 else values_sorted[0]
            stats.p99 = values_sorted[int(n * 0.99)] if n > 1 else values_sorted[0]

        # Recent average (last 10% of measurements)
        recent_count = max(1, n // 10)
        recent_values = values[-recent_count:]
        stats.recent_avg = sum(recent_values) / len(recent_values)

        return stats

    def set_threshold(
        self,
        name: str,
        warning: Optional[float] = None,
        critical: Optional[float] = None,
    ) -> None:
        """Set performance thresholds for a metric.

        Args:
            name: Metric name
            warning: Warning threshold value
            critical: Critical threshold value
        """
        self.thresholds[name] = {}
        if warning is not None:
            self.thresholds[name]["warning"] = warning
        if critical is not None:
            self.thresholds[name]["critical"] = critical

    def _check_thresholds(
        self,
        name: str,
        value: float,
        metric_type: MetricType
    ) -> None:
        """Check if metric value exceeds thresholds."""
        if name not in self.thresholds or not self.logger:
            return

        thresholds = self.thresholds[name]

        if "critical" in thresholds and value >= thresholds["critical"]:
            self.logger.critical(
                f"Metric threshold exceeded (critical): {name}",
                metric_name=name,
                metric_value=value,
                threshold_type="critical",
                threshold_value=thresholds["critical"],
                metric_type=metric_type.value,
            )
        elif "warning" in thresholds and value >= thresholds["warning"]:
            self.logger.warning(
                f"Metric threshold exceeded (warning): {name}",
                metric_name=name,
                metric_value=value,
                threshold_type="warning",
                threshold_value=thresholds["warning"],
                metric_type=metric_type.value,
            )

    def get_all_metrics(self) -> Dict[str, Any]:
        """Get summary of all collected metrics.

        Returns:
            Dictionary with metric summaries, counters, and gauges
        """
        result: Dict[str, Any] = {
            "component": self.component,
            "timestamp": time.time(),
            "counters": dict(self.counters),
            "gauges": dict(self.gauges),
            "metrics": {},
        }
        metrics_summary: Dict[str, Any] = {}

        for name in self.metrics:
            stats = self.get_stats(name)
            if stats:
                metrics_summary[name] = {
                    "count": stats.count,
                    "avg": stats.avg,
                    "min": stats.min,
                    "max": stats.max,
                    "p50": stats.p50,
                    "p95": stats.p95,
                    "p99": stats.p99,
                    "recent_avg": stats.recent_avg,
                }
        result["metrics"] = metrics_summary

        return result

    def log_summary(self) -> None:
        """Log summary of all metrics."""
        if not self.logger:
            return

        summary = self.get_all_metrics()
        self.logger.info("Performance metrics summary", **summary)

    def reset(self) -> None:
        """Reset all metrics (for testing or restart scenarios)."""
        self.metrics.clear()
        self.counters.clear()
        self.gauges.clear()
        self._active_timers.clear()
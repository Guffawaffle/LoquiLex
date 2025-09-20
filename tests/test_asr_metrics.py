"""Tests for ASR performance metrics and structured logging."""

from __future__ import annotations

import time
from unittest.mock import patch

from loquilex.asr.metrics import ASRMetrics, LatencyMetrics
from loquilex.asr.aggregator import PartialFinalAggregator
from loquilex.asr.stream import ASRPartialEvent, ASRFinalEvent, ASRWord
from loquilex.logging import StructuredLogger #noqa: F401


class TestLatencyMetrics:
    """Test latency metrics collection."""

    def test_empty_metrics(self):
        """Test empty metrics state."""
        metrics = LatencyMetrics()
        stats = metrics.get_stats()

        assert stats["count"] == 0

    def test_single_measurement(self):
        """Test single measurement."""
        metrics = LatencyMetrics()
        metrics.add(150.0)

        stats = metrics.get_stats()
        assert stats["count"] == 1
        assert stats["avg"] == 150.0
        assert stats["min"] == 150.0
        assert stats["max"] == 150.0
        assert stats["p50"] == 150.0
        assert stats["p95"] == 150.0

    def test_multiple_measurements(self):
        """Test multiple measurements and percentiles."""
        metrics = LatencyMetrics()

        # Add values from 1 to 100
        for i in range(1, 101):
            metrics.add(float(i))

        stats = metrics.get_stats()
        assert stats["count"] == 100
        assert stats["avg"] == 50.5  # (1+100)/2
        assert stats["min"] == 1.0
        assert stats["max"] == 100.0
        assert stats["p50"] == 51.0  # Median of 1..100 (0-indexed)
        assert stats["p95"] == 96.0  # Correct p95 for sorted 1..100

    def test_bounded_recent_values(self):
        """Test that recent values are bounded."""
        metrics = LatencyMetrics()

        # Add more than the max recent values (100)
        for i in range(150):
            metrics.add(float(i))

        assert len(metrics.recent_values) == 100
        assert metrics.count == 150

        # Recent values should be the last 100
        assert list(metrics.recent_values) == list(range(50, 150))


class TestASRMetrics:
    """Test ASR metrics collection and reporting."""

    def test_basic_metrics(self):
        """Test basic ASR metrics functionality."""
        metrics = ASRMetrics("test_stream")

        # Test partial event
        metrics.on_partial_event({"text": "hello", "segment_id": "seg1"})
        assert metrics.partial_count == 1

        # Test final event
        metrics.on_final_event({
            "text": "hello world",
            "segment_id": "seg1",
            "eou_reason": "silence"
        })
        assert metrics.final_count == 1
        assert metrics.eou_reasons["silence"] == 1

    def test_asr_metrics_with_structured_logging(self):
        """Test ASR metrics with structured logging integration."""
        with patch("loquilex.logging.structured.StructuredLogger") as mock_logger_class:
            mock_logger = mock_logger_class.return_value

            metrics = ASRMetrics("test_stream", logger=mock_logger)

            # Verify logger was used for initialization
            mock_logger.info.assert_called()

            # Test partial event logging
            metrics.on_partial_event({"text": "hello", "segment_id": "seg1"})

            # Test final event logging
            metrics.on_final_event({
                "text": "hello world",
                "segment_id": "seg1",
                "eou_reason": "silence",
            })

            # Verify structured logging calls
            assert mock_logger.info.call_count >= 3  # init + events

    def test_initialization(self):
        """Test metrics initialization."""
        metrics = ASRMetrics("test_stream")

        assert metrics.stream_id == "test_stream"
        assert metrics.partial_count == 0
        assert metrics.final_count == 0
        assert len(metrics.eou_reasons) == 0

    def test_partial_event_tracking(self):
        """Test partial event tracking."""
        metrics = ASRMetrics("test_stream")

        # Mock time to control intervals
        start_time = time.monotonic()

        # Create partial events
        partial1 = {
            "type": "asr.partial",
            "text": "hello",
            "words": [{"w": "hello", "t0": 0.0, "t1": 0.5, "conf": 0.9}],
            "seq": 1,
            "segment_id": "seg1",
        }

        partial2 = {
            "type": "asr.partial",
            "text": "hello world",
            "words": [{"w": "hello", "t0": 0.0, "t1": 0.5, "conf": 0.9}],
            "seq": 2,
            "segment_id": "seg1",
        }

        with (
            patch("loquilex.asr.metrics.time.monotonic") as mock_time,
            patch("loquilex.asr.metrics.time.time") as mock_wall_time,
        ):
            # Need more mock values to cover all time.monotonic() calls
            times = [start_time + i * 0.05 for i in range(10)]  # Enough values
            mock_time.side_effect = times
            mock_wall_time.return_value = 1000.0  # Fixed wall time for logging

            metrics.on_partial_event(partial1)
            assert metrics.partial_count == 1
            assert metrics.last_partial_time is not None

            metrics.on_partial_event(partial2)
            assert metrics.partial_count == 2

            # Should have recorded interval (approximately 100ms)
            stats = metrics.partial_intervals.get_stats()
            assert stats["count"] == 1
            # Allow some tolerance for timing differences
            assert 90.0 <= stats["avg"] <= 110.0

    def test_final_event_tracking(self):
        """Test final event tracking."""
        metrics = ASRMetrics("test_stream")

        # Add a partial first
        partial_event = {
            "type": "asr.partial",
            "text": "hello",
            "words": [],
            "seq": 1,
            "segment_id": "seg1",
        }

        final_event = {
            "type": "asr.final",
            "text": "hello world.",
            "words": [{"w": "hello", "t0": 0.0, "t1": 0.5, "conf": 0.9}],
            "eou_reason": "punctuation",
            "segment_id": "seg1",
        }

        start_time = time.monotonic()

        with patch("time.monotonic") as mock_time, patch("time.time") as mock_wall_time:
            times = [start_time + i * 0.05 for i in range(10)]  # Enough values
            mock_time.side_effect = times
            mock_wall_time.return_value = 1000.0

            metrics.on_partial_event(partial_event)
            metrics.on_final_event(final_event)

            assert metrics.final_count == 1
            assert metrics.eou_reasons["punctuation"] == 1

            # Should have recorded finalization latency (gap between calls)
            stats = metrics.final_latency.get_stats()
            assert stats["count"] == 1
            # The latency should be around 100ms (0.1s gap)
            assert 90.0 <= stats["avg"] <= 110.0

    def test_eou_reason_counting(self):
        """Test EOU reason counting."""
        metrics = ASRMetrics("test_stream")

        # Add finals with different EOU reasons
        reasons = ["punctuation", "silence", "timeout", "punctuation"]

        for i, reason in enumerate(reasons):
            final_event = {
                "type": "asr.final",
                "text": f"text {i}",
                "words": [],
                "eou_reason": reason,
                "segment_id": f"seg{i}",
            }
            metrics.on_final_event(final_event)

        assert metrics.eou_reasons["punctuation"] == 2
        assert metrics.eou_reasons["silence"] == 1
        assert metrics.eou_reasons["timeout"] == 1

    def test_summary_generation(self):
        """Test metrics summary generation."""
        metrics = ASRMetrics("test_stream")

        # Add some simple events without complex mocking
        partial1 = {
            "type": "asr.partial",
            "text": "hello",
            "words": [],
            "seq": 1,
            "segment_id": "seg1",
        }
        final1 = {
            "type": "asr.final",
            "text": "hello world.",
            "words": [],
            "eou_reason": "punctuation",
            "segment_id": "seg1",
        }

        metrics.on_partial_event(partial1)
        metrics.on_final_event(final1)

        summary = metrics.get_summary()

        assert summary["stream_id"] == "test_stream"
        assert summary["events"]["partial_count"] == 1
        assert summary["events"]["final_count"] == 1
        assert "punctuation" in summary["eou_reasons"]
        assert "partial_intervals_ms" in summary
        assert "final_latency_ms" in summary

    def test_performance_targets(self):
        """Test performance target evaluation."""
        # Add measurements that meet targets
        with (
            patch("time.monotonic") as mock_time_test,
            patch("loquilex.asr.metrics.time.monotonic") as mock_time,
            patch("loquilex.asr.metrics.time.time") as mock_wall_time,
        ):
            # Seed with a real float so arithmetic stays numeric (not MagicMock)
            base_time = 1000.0
            # Give each patched function its own long sequence (avoid StopIteration)
            seq_len = 100
            times_for_module = [base_time + i * 0.1 for i in range(seq_len)]
            times_for_stdlib = [base_time + i * 0.1 for i in range(seq_len)]
            mock_time.side_effect = times_for_module
            mock_time_test.side_effect = times_for_stdlib
            mock_wall_time.return_value = 1000.0
            metrics = ASRMetrics("test_stream")

            partial1 = {
                "type": "asr.partial",
                "text": "hello",
                "words": [],
                "seq": 1,
                "segment_id": "seg1",
            }
            partial2 = {
                "type": "asr.partial",
                "text": "hello world",
                "words": [],
                "seq": 2,
                "segment_id": "seg1",
            }
            final1 = {
                "type": "asr.final",
                "text": "hello world.",
                "words": [],
                "eou_reason": "punctuation",
                "segment_id": "seg1",
            }

            metrics.on_partial_event(partial1)
            metrics.on_partial_event(partial2)
            metrics.on_final_event(final1)

            summary = metrics.get_summary()
            performance = summary.get("performance", {})

            # Should meet targets
            assert performance.get("partial_p50_target") is True  # < 200ms
            assert performance.get("partial_p95_target") is True  # < 300ms
            assert performance.get("final_p95_target") is True  # < 800ms


class TestMetricsIntegration:
    """Test metrics integration with aggregator."""

    def test_aggregator_with_metrics(self):
        """Test aggregator collecting metrics."""
        aggregator = PartialFinalAggregator("test_stream", enable_metrics=True)

        # Create events
        partial = ASRPartialEvent(
            stream_id="test_stream",
            segment_id="seg1",
            seq=1,
            text="hello",
            words=[ASRWord(w="hello", t0=0.0, t1=0.5, conf=0.9)],
            ts_monotonic=time.monotonic(),
        )

        final = ASRFinalEvent(
            stream_id="test_stream",
            segment_id="seg1",
            text="hello world.",
            words=[ASRWord(w="hello", t0=0.0, t1=0.5, conf=0.9)],
            ts_monotonic=time.monotonic(),
            eou_reason="punctuation",
        )

        events_collected = []

        # Process events through aggregator
        aggregator.add_partial(partial, events_collected.append)
        aggregator.add_final(final, events_collected.append)

        # Check that metrics were collected
        assert aggregator.metrics is not None
        assert aggregator.metrics.partial_count == 1
        assert aggregator.metrics.final_count == 1

        # Get metrics summary
        summary = aggregator.get_metrics_summary()
        assert summary is not None
        assert summary["events"]["partial_count"] == 1
        assert summary["events"]["final_count"] == 1

    def test_aggregator_without_metrics(self):
        """Test aggregator with metrics disabled."""
        aggregator = PartialFinalAggregator("test_stream", enable_metrics=False)

        assert aggregator.metrics is None
        assert aggregator.get_metrics_summary() is None

    def test_metrics_in_stats(self):
        """Test that metrics are included in aggregator stats."""
        aggregator = PartialFinalAggregator("test_stream", enable_metrics=True)

        stats = aggregator.get_stats()
        assert "performance" in stats

        # Initially should be empty performance metrics
        performance = stats["performance"]
        assert performance["events"]["partial_count"] == 0
        assert performance["events"]["final_count"] == 0

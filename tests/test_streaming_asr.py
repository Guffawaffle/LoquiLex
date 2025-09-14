"""Tests for streaming ASR pipeline and partial/final aggregator."""

from __future__ import annotations

import asyncio
import time
from typing import Any, Dict, List
from unittest.mock import patch

import numpy as np

from loquilex.asr.aggregator import PartialFinalAggregator
from loquilex.asr.stream import ASRWord, ASRPartialEvent, ASRFinalEvent
from tests.fakes.fake_streaming_asr import FakeStreamingASR


class TestPartialFinalAggregator:
    """Test partial/final aggregator functionality."""

    def test_partial_event_processing(self):
        """Test basic partial event processing."""
        aggregator = PartialFinalAggregator("test_stream")
        emitted_events: List[Dict[str, Any]] = []

        # Create test partial event
        partial = ASRPartialEvent(
            stream_id="test_stream",
            segment_id="seg1",
            seq=1,
            text="hello",
            words=[ASRWord(w="hello", t0=0.0, t1=0.5, conf=0.9)],
            ts_monotonic=time.monotonic(),
        )

        aggregator.add_partial(partial, emitted_events.append)

        assert len(emitted_events) == 1
        event = emitted_events[0]
        assert event["type"] == "asr.partial"
        assert event["stream_id"] == "test_stream"
        assert event["segment_id"] == "seg1"
        assert event["text"] == "hello"
        assert event["stable"] is False
        assert len(event["words"]) == 1
        assert event["words"][0]["w"] == "hello"

    def test_final_event_processing(self):
        """Test basic final event processing."""
        aggregator = PartialFinalAggregator("test_stream")
        emitted_events: List[Dict[str, Any]] = []

        # Create test final event
        final = ASRFinalEvent(
            stream_id="test_stream",
            segment_id="seg1",
            text="hello world.",
            words=[
                ASRWord(w="hello", t0=0.0, t1=0.5, conf=0.9),
                ASRWord(w="world.", t0=0.5, t1=1.0, conf=0.85),
            ],
            ts_monotonic=time.monotonic(),
            eou_reason="punctuation",
        )

        aggregator.add_final(final, emitted_events.append)

        assert len(emitted_events) == 1
        event = emitted_events[0]
        assert event["type"] == "asr.final"
        assert event["stream_id"] == "test_stream"
        assert event["segment_id"] == "seg1"
        assert event["text"] == "hello world."
        assert event["eou_reason"] == "punctuation"
        assert len(event["words"]) == 2

    def test_duplicate_final_prevention(self):
        """Test that duplicate finals are prevented."""
        aggregator = PartialFinalAggregator("test_stream")
        emitted_events: List[Dict[str, Any]] = []

        # Create identical final events
        final1 = ASRFinalEvent(
            stream_id="test_stream",
            segment_id="seg1",
            text="hello world.",
            words=[ASRWord(w="hello", t0=0.0, t1=0.5, conf=0.9)],
            ts_monotonic=time.monotonic(),
            eou_reason="punctuation",
        )

        final2 = ASRFinalEvent(
            stream_id="test_stream",
            segment_id="seg1",  # Same segment ID
            text="hello world.",
            words=[ASRWord(w="hello", t0=0.0, t1=0.5, conf=0.9)],
            ts_monotonic=time.monotonic(),
            eou_reason="punctuation",
        )

        # Add first final - should emit
        aggregator.add_final(final1, emitted_events.append)
        assert len(emitted_events) == 1

        # Add duplicate final - should not emit
        aggregator.add_final(final2, emitted_events.append)
        assert len(emitted_events) == 1  # No new event

    def test_partials_after_final_ignored(self):
        """Test that partials are ignored after segment is finalized."""
        aggregator = PartialFinalAggregator("test_stream")
        emitted_events: List[Dict[str, Any]] = []

        # Add partial
        partial = ASRPartialEvent(
            stream_id="test_stream",
            segment_id="seg1",
            seq=1,
            text="hello",
            words=[ASRWord(w="hello", t0=0.0, t1=0.5, conf=0.9)],
            ts_monotonic=time.monotonic(),
        )
        aggregator.add_partial(partial, emitted_events.append)
        assert len(emitted_events) == 1

        # Add final
        final = ASRFinalEvent(
            stream_id="test_stream",
            segment_id="seg1",
            text="hello world.",
            words=[ASRWord(w="hello", t0=0.0, t1=0.5, conf=0.9)],
            ts_monotonic=time.monotonic(),
            eou_reason="punctuation",
        )
        aggregator.add_final(final, emitted_events.append)
        assert len(emitted_events) == 2

        # Add another partial for same segment - should be ignored
        late_partial = ASRPartialEvent(
            stream_id="test_stream",
            segment_id="seg1",  # Same segment, but it's finalized
            seq=2,
            text="hello world late",
            words=[ASRWord(w="hello", t0=0.0, t1=0.5, conf=0.9)],
            ts_monotonic=time.monotonic(),
        )
        aggregator.add_partial(late_partial, emitted_events.append)
        assert len(emitted_events) == 2  # No new event

    def test_partial_backpressure(self):
        """Test that partial queue has bounded size with LRU eviction."""
        aggregator = PartialFinalAggregator("test_stream", max_partials=2)
        emitted_events: List[Dict[str, Any]] = []

        # Add 3 partials for different segments
        for i in range(3):
            partial = ASRPartialEvent(
                stream_id="test_stream",
                segment_id=f"seg{i}",
                seq=i + 1,
                text=f"text{i}",
                words=[ASRWord(w=f"word{i}", t0=0.0, t1=0.5, conf=0.9)],
                ts_monotonic=time.monotonic(),
            )
            aggregator.add_partial(partial, emitted_events.append)

        # Should have emitted 3 events but only keep 2 in memory
        assert len(emitted_events) == 3
        assert len(aggregator.partials) == 2

        # First segment should be evicted
        assert "seg0" not in aggregator.partials
        assert "seg1" in aggregator.partials
        assert "seg2" in aggregator.partials

    def test_snapshot_generation(self):
        """Test snapshot generation for reconnect scenarios."""
        aggregator = PartialFinalAggregator("test_stream")
        emitted_events: List[Dict[str, Any]] = []

        # Add some finals
        for i in range(2):
            final = ASRFinalEvent(
                stream_id="test_stream",
                segment_id=f"final_seg{i}",
                text=f"Final text {i}",
                words=[ASRWord(w=f"word{i}", t0=0.0, t1=0.5, conf=0.9)],
                ts_monotonic=time.monotonic(),
                eou_reason="silence",
            )
            aggregator.add_final(final, emitted_events.append)

        # Add a current partial
        partial = ASRPartialEvent(
            stream_id="test_stream",
            segment_id="live_seg",
            seq=3,
            text="Current partial",
            words=[ASRWord(w="Current", t0=0.0, t1=0.5, conf=0.9)],
            ts_monotonic=time.monotonic(),
        )
        aggregator.add_partial(partial, emitted_events.append)

        # Get snapshot
        snapshot = aggregator.get_snapshot()

        assert snapshot["type"] == "asr.snapshot"
        assert snapshot["stream_id"] == "test_stream"
        assert len(snapshot["recent_finals"]) == 2
        assert snapshot["live_partial"] is not None
        assert snapshot["live_partial"]["segment_id"] == "live_seg"
        assert snapshot["live_partial"]["text"] == "Current partial"

    def test_stats_tracking(self):
        """Test statistics tracking."""
        aggregator = PartialFinalAggregator("test_stream", max_partials=5)
        emitted_events: List[Dict[str, Any]] = []

        # Initial stats
        stats = aggregator.get_stats()
        assert stats["global_seq"] == 0
        assert stats["active_partials"] == 0
        assert stats["recent_finals"] == 0

        # Add partial and final
        partial = ASRPartialEvent(
            stream_id="test_stream",
            segment_id="seg1",
            seq=1,
            text="hello",
            words=[ASRWord(w="hello", t0=0.0, t1=0.5, conf=0.9)],
            ts_monotonic=time.monotonic(),
        )
        aggregator.add_partial(partial, emitted_events.append)

        final = ASRFinalEvent(
            stream_id="test_stream",
            segment_id="seg2",
            text="world.",
            words=[ASRWord(w="world.", t0=0.0, t1=0.5, conf=0.9)],
            ts_monotonic=time.monotonic(),
            eou_reason="punctuation",
        )
        aggregator.add_final(final, emitted_events.append)

        # Check updated stats
        stats = aggregator.get_stats()
        assert stats["global_seq"] == 2
        assert stats["active_partials"] == 1  # seg1 partial still active
        assert stats["recent_finals"] == 1  # seg2 final added


class TestFakeStreamingASR:
    """Test fake streaming ASR for offline testing."""

    def test_deterministic_behavior(self):
        """Test that fake ASR produces deterministic events."""
        fake_asr = FakeStreamingASR("test_stream")
        partials: List[ASRPartialEvent] = []
        finals: List[ASRFinalEvent] = []

        def on_partial(event):
            partials.append(event)

        def on_final(event):
            finals.append(event)

        # Process several audio chunks
        dummy_audio = np.zeros(1000, dtype=np.float32)
        for _ in range(5):
            fake_asr.process_audio_chunk(dummy_audio, on_partial, on_final)

        # Should get 3 partials and 1 final
        assert len(partials) == 3
        assert len(finals) == 1

        # Check final event
        final = finals[0]
        assert final.eou_reason == "punctuation"
        assert "test." in final.text  # Should end with punctuation
        assert len(final.words) > 0

    def test_snapshot_functionality(self):
        """Test snapshot generation."""
        fake_asr = FakeStreamingASR("test_stream")

        # Process some chunks to generate state
        dummy_audio = np.zeros(1000, dtype=np.float32)
        fake_asr.process_audio_chunk(dummy_audio, lambda _: None, lambda _: None)

        snapshot = fake_asr.get_snapshot()

        assert snapshot.stream_id == "test_stream"
        assert snapshot.type == "asr.snapshot"

    def test_force_finalize(self):
        """Test force finalization."""
        fake_asr = FakeStreamingASR("test_stream")
        finals: List[ASRFinalEvent] = []

        def on_final(event):
            finals.append(event)

        # Process a chunk to create partial state
        dummy_audio = np.zeros(1000, dtype=np.float32)
        fake_asr.process_audio_chunk(dummy_audio, lambda _: None, lambda _: None)

        # Force finalize
        fake_asr.force_finalize(on_final)

        # Should get a final event
        assert len(finals) == 1
        final = finals[0]
        assert final.eou_reason == "forced"


class TestIntegration:
    """Integration tests combining components."""

    def test_streaming_asr_with_aggregator(self):
        """Test streaming ASR with aggregator integration."""
        # Use fake ASR for offline testing
        fake_asr = FakeStreamingASR("integration_test")
        aggregator = PartialFinalAggregator("integration_test")

        all_events: List[Dict[str, Any]] = []

        def event_handler(event_dict):
            all_events.append(event_dict)

        def on_partial(partial_event):
            aggregator.add_partial(partial_event, event_handler)

        def on_final(final_event):
            aggregator.add_final(final_event, event_handler)

        # Process audio to generate events
        dummy_audio = np.zeros(1000, dtype=np.float32)
        for _ in range(5):
            fake_asr.process_audio_chunk(dummy_audio, on_partial, on_final)

        # Check that events were processed through aggregator
        assert len(all_events) > 0

        # Should have both partials and finals
        partial_events = [e for e in all_events if e["type"] == "asr.partial"]
        final_events = [e for e in all_events if e["type"] == "asr.final"]

        assert len(partial_events) > 0
        assert len(final_events) > 0

        # Check sequence numbers are monotonic
        seq_numbers = [e["seq"] for e in all_events if "seq" in e]
        assert seq_numbers == sorted(seq_numbers)

        # Get snapshot after processing
        snapshot = aggregator.get_snapshot()
        assert snapshot["type"] == "asr.snapshot"
        assert len(snapshot["recent_finals"]) > 0


class TestAsyncBridge:
    """Test thread-safe asyncio bridge in StreamingSession."""

    @patch("asyncio.run_coroutine_threadsafe")
    @patch("asyncio.get_running_loop")
    def test_async_bridge_with_event_loop(self, mock_get_loop, mock_run_coroutine):
        """Test that run_coroutine_threadsafe is used when event loop is available."""
        from loquilex.api.supervisor import StreamingSession, SessionConfig
        from pathlib import Path

        # Mock event loop
        mock_loop = asyncio.new_event_loop()
        mock_get_loop.return_value = mock_loop

        # Create session
        cfg = SessionConfig(
            name="test_session",
            asr_model_id="tiny.en",
            mt_enabled=False,
            mt_model_id=None,
            dest_lang="zh",
            device="cpu",
            vad=True,
            beams=1,
            pause_flush_sec=0.5,
            segment_max_sec=10.0,
            partial_word_cap=10,
            save_audio="none",
            streaming_mode=True,
        )
        session = StreamingSession("test_sid", cfg, Path("/tmp"))
        session._event_loop = mock_loop

        # Mock aggregator to trigger emit_event
        from unittest.mock import MagicMock
        mock_aggregator = MagicMock()
        # Make add_partial call the emit_fn with a dummy event
        def mock_add_partial(_partial_event, emit_fn):
            emit_fn({"type": "test"})
        mock_aggregator.add_partial.side_effect = mock_add_partial
        session._aggregator = mock_aggregator

        # Mock broadcast function
        broadcast_calls = []
        session._broadcast_fn = lambda sid, event: broadcast_calls.append((sid, event))

        # Call _on_partial (simulates thread context)
        partial_event = ASRPartialEvent(
            stream_id="test_stream",
            segment_id="test_seg",
            seq=1,
            text="test",
            words=[ASRWord(w="test", t0=0.0, t1=0.5, conf=0.9)],
            ts_monotonic=1000.0,
        )

        # This should use run_coroutine_threadsafe
        session._on_partial(partial_event)

        # Verify run_coroutine_threadsafe was called
        mock_run_coroutine.assert_called_once()
        args, kwargs = mock_run_coroutine.call_args
        assert args[1] == mock_loop  # Second arg should be the loop

    @patch("asyncio.get_running_loop", side_effect=RuntimeError("No running loop"))
    def test_async_bridge_no_event_loop(self, _mock_get_loop):
        """Test fallback behavior when no event loop is available."""
        from loquilex.api.supervisor import StreamingSession, SessionConfig
        from pathlib import Path

        # Create session without event loop
        cfg = SessionConfig(
            name="test_session",
            asr_model_id="tiny.en",
            mt_enabled=False,
            mt_model_id=None,
            dest_lang="zh",
            device="cpu",
            vad=True,
            beams=1,
            pause_flush_sec=0.5,
            segment_max_sec=10.0,
            partial_word_cap=10,
            save_audio="none",
            streaming_mode=True,
        )
        session = StreamingSession("test_sid", cfg, Path("/tmp"))
        session._event_loop = None  # No loop stored

        # Mock aggregator to trigger emit_event
        from unittest.mock import MagicMock
        mock_aggregator = MagicMock()
        # Make add_partial call the emit_fn with a dummy event
        def mock_add_partial(_partial_event, emit_fn):
            emit_fn({"type": "test"})
        mock_aggregator.add_partial.side_effect = mock_add_partial
        session._aggregator = mock_aggregator

        # Mock broadcast function
        broadcast_calls = []
        session._broadcast_fn = lambda sid, event: broadcast_calls.append((sid, event))

        # Call _on_partial (simulates thread context)
        partial_event = ASRPartialEvent(
            stream_id="test_stream",
            segment_id="test_seg",
            seq=1,
            text="test",
            words=[ASRWord(w="test", t0=0.0, t1=0.5, conf=0.9)],
            ts_monotonic=1000.0,
        )

        # This should not crash and should handle the RuntimeError gracefully
        session._on_partial(partial_event)

        # Should have logged the partial text since broadcast failed
        # (In real scenario, this would print to console)

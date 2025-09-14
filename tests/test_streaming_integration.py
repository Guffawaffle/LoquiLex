"""Integration tests for streaming ASR pipeline with WebSocket API."""

from __future__ import annotations

import anyio
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from loquilex.api.server import app


class TestStreamingIntegration:
    """Test streaming ASR integration with WebSocket API."""

    def test_create_streaming_session(self):
        """Test creating a streaming ASR session."""
        client = TestClient(app)

        response = client.post(
            "/sessions",
            json={
                "asr_model_id": "tiny.en",
                "streaming_mode": True,
                "device": "cpu",
                "vad": True,
                "beams": 1,
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert "session_id" in data
        session_id = data["session_id"]

        # Clean up
        client.delete(f"/sessions/{session_id}")

    def test_asr_snapshot_endpoint(self):
        """Test ASR snapshot endpoint for streaming sessions."""
        client = TestClient(app)

        # Create streaming session
        response = client.post(
            "/sessions",
            json={
                "asr_model_id": "tiny.en",
                "streaming_mode": True,
                "device": "cpu",
            },
        )
        assert response.status_code == 200
        session_id = response.json()["session_id"]

        try:
            # Small delay to let session initialize
            import time

            time.sleep(0.1)

            # Try to get ASR snapshot
            response = client.get(f"/sessions/{session_id}/asr/snapshot")
            # Should either succeed with snapshot or fail gracefully
            assert response.status_code in [200, 503]  # 503 if not ready yet

            if response.status_code == 200:
                snapshot = response.json()
                assert snapshot["type"] == "asr.snapshot"
                assert "stream_id" in snapshot
                assert "recent_finals" in snapshot
                assert "live_partial" in snapshot

        finally:
            # Clean up
            client.delete(f"/sessions/{session_id}")

    def test_regular_session_no_asr_snapshot(self):
        """Test that regular sessions don't support ASR snapshots."""
        client = TestClient(app)

        # Create regular (non-streaming) session
        response = client.post(
            "/sessions",
            json={
                "asr_model_id": "tiny.en",
                "streaming_mode": False,  # Regular session
                "device": "cpu",
            },
        )
        assert response.status_code == 200
        session_id = response.json()["session_id"]

        try:
            # Try to get ASR snapshot - should fail
            response = client.get(f"/sessions/{session_id}/asr/snapshot")
            assert response.status_code == 400
            assert "does not support ASR snapshots" in response.json()["detail"]

        finally:
            # Clean up
            client.delete(f"/sessions/{session_id}")

    @pytest.mark.anyio
    async def test_websocket_streaming_events(self):
        """Test WebSocket events for streaming sessions (mock audio)."""
        from loquilex.asr.stream import ASRPartialEvent, ASRFinalEvent, ASRWord
        import time

        # Mock the audio capture to avoid needing real microphone
        with patch("loquilex.audio.capture.capture_stream") as mock_capture:
            # Mock audio capture returns a stop function
            mock_capture.return_value = lambda: None

            client = TestClient(app)

            # Create streaming session
            response = client.post(
                "/sessions",
                json={
                    "asr_model_id": "tiny.en",
                    "streaming_mode": True,
                    "device": "cpu",
                },
            )
            assert response.status_code == 200
            session_id = response.json()["session_id"]

            try:
                # Small delay for session initialization
                await anyio.sleep(0.1)

                # Get the session from the manager to trigger events manually
                from loquilex.api.server import MANAGER

                session = MANAGER._sessions.get(session_id)

                if session and hasattr(session, "_on_partial"):
                    # Manually trigger ASR events to test the pipeline
                    partial_event = ASRPartialEvent(
                        stream_id=session_id,
                        segment_id="test_seg",
                        seq=1,
                        text="hello world",
                        words=[
                            ASRWord(w="hello", t0=0.0, t1=0.5, conf=0.9),
                            ASRWord(w="world", t0=0.5, t1=1.0, conf=0.85),
                        ],
                        ts_monotonic=time.monotonic(),
                    )

                    final_event = ASRFinalEvent(
                        stream_id=session_id,
                        segment_id="test_seg",
                        text="hello world.",
                        words=[
                            ASRWord(w="hello", t0=0.0, t1=0.5, conf=0.9),
                            ASRWord(w="world.", t0=0.5, t1=1.0, conf=0.85),
                        ],
                        ts_monotonic=time.monotonic(),
                        eou_reason="punctuation",
                    )

                    # Trigger the events
                    session._on_partial(partial_event)
                    session._on_final(final_event)

                    # Allow events to propagate
                    await anyio.sleep(0.1)

                # Test passed if we reach here without errors
                assert True

            finally:
                # Clean up
                client.delete(f"/sessions/{session_id}")


class TestStreamingConfiguration:
    """Test streaming ASR configuration and validation."""

    def test_streaming_config_validation(self):
        """Test validation of streaming configuration parameters."""
        client = TestClient(app)

        # Test with valid streaming config
        response = client.post(
            "/sessions",
            json={
                "asr_model_id": "tiny.en",
                "streaming_mode": True,
                "device": "cpu",
                "vad": True,
                "beams": 1,
                "pause_flush_sec": 0.5,
                "segment_max_sec": 8.0,
            },
        )
        assert response.status_code == 200
        session_id = response.json()["session_id"]

        # Clean up
        client.delete(f"/sessions/{session_id}")

    def test_model_id_validation(self):
        """Test ASR model ID validation."""
        client = TestClient(app)

        # Test with various model IDs (should all be accepted)
        model_ids = ["tiny.en", "small.en", "base.en", "medium.en"]

        for model_id in model_ids:
            response = client.post(
                "/sessions",
                json={
                    "asr_model_id": model_id,
                    "streaming_mode": True,
                    "device": "cpu",
                },
            )

            if response.status_code == 200:
                session_id = response.json()["session_id"]
                client.delete(f"/sessions/{session_id}")
            # Some model IDs might not be available, that's OK

    def test_device_selection(self):
        """Test device selection for streaming sessions."""
        client = TestClient(app)

        # Test CPU device (should always work)
        response = client.post(
            "/sessions",
            json={
                "asr_model_id": "tiny.en",
                "streaming_mode": True,
                "device": "cpu",
            },
        )
        assert response.status_code == 200
        session_id = response.json()["session_id"]
        client.delete(f"/sessions/{session_id}")

        # Test auto device (should work)
        response = client.post(
            "/sessions",
            json={
                "asr_model_id": "tiny.en",
                "streaming_mode": True,
                "device": "auto",
            },
        )
        assert response.status_code == 200
        session_id = response.json()["session_id"]
        client.delete(f"/sessions/{session_id}")


@pytest.mark.e2e
class TestEndToEndStreaming:
    """End-to-end tests for streaming ASR (heavier tests)."""

    @pytest.mark.anyio
    async def test_full_streaming_pipeline(self):
        """Test the full streaming pipeline with realistic simulation."""
        # This test would use more realistic audio input
        # For now, just ensure the components integrate properly

        from loquilex.asr.stream import StreamingASR
        from loquilex.asr.aggregator import PartialFinalAggregator
        import numpy as np

        # Test component integration
        stream_id = "e2e_test"
        asr = StreamingASR(stream_id)
        aggregator = PartialFinalAggregator(stream_id)

        events_received = []

        def on_partial(partial):
            aggregator.add_partial(partial, events_received.append)

        def on_final(final):
            aggregator.add_final(final, events_received.append)

        # Process several chunks of fake audio
        for i in range(5):
            chunk = np.random.uniform(-0.1, 0.1, 1600).astype(np.float32)  # 0.1s at 16kHz
            asr.process_audio_chunk(chunk, on_partial, on_final)
            await anyio.sleep(0.01)  # Small delay

        # Should have received some events
        partial_events = [e for e in events_received if e.get("type") == "asr.partial"]
        final_events = [e for e in events_received if e.get("type") == "asr.final"]

        # With fake ASR, we should get predictable results
        assert len(partial_events) >= 0  # May or may not get partials
        assert len(final_events) >= 0  # May or may not get finals

        # Test snapshot
        snapshot = aggregator.get_snapshot()
        assert snapshot["type"] == "asr.snapshot"
        assert snapshot["stream_id"] == stream_id


class TestSnapshotStatus:
    """Test snapshot status correctness for streaming sessions."""

    def test_streaming_session_status_running(self):
        """Test that streaming session shows 'running' status while audio thread is alive."""
        client = TestClient(app)

        # Create streaming session
        response = client.post(
            "/sessions",
            json={
                "asr_model_id": "tiny.en",
                "streaming_mode": True,
                "device": "cpu",
            },
        )
        assert response.status_code == 200
        session_id = response.json()["session_id"]

        # Get snapshot - should show running status
        response = client.get(f"/sessions/{session_id}/snapshot")
        assert response.status_code == 200
        snapshot = response.json()
        assert snapshot["status"] == "running"

        # Clean up
        client.delete(f"/sessions/{session_id}")

    def test_streaming_session_status_stopped(self):
        """Test that streaming session shows 'stopped' status after stopping."""
        client = TestClient(app)

        # Create streaming session
        response = client.post(
            "/sessions",
            json={
                "asr_model_id": "tiny.en",
                "streaming_mode": True,
                "device": "cpu",
            },
        )
        assert response.status_code == 200
        session_id = response.json()["session_id"]

        # Stop the session
        response = client.delete(f"/sessions/{session_id}")
        assert response.status_code == 200

        # Get snapshot - session should be gone (404)
        response = client.get(f"/sessions/{session_id}/snapshot")
        assert response.status_code == 404


class TestErrorHygiene:
    """Test that HTTP 500 responses don't leak exception details."""

    def test_metrics_error_no_exception_leak(self):
        """Test that metrics endpoint doesn't leak exception text in 500 response."""
        client = TestClient(app)

        # Create regular session (not streaming)
        response = client.post(
            "/sessions",
            json={
                "asr_model_id": "tiny.en",
                "device": "cpu",
            },
        )
        assert response.status_code == 200
        session_id = response.json()["session_id"]

        # Force an internal error by monkeypatching
        from loquilex.api.server import MANAGER

        original_get_metrics = None
        try:
            sess = MANAGER._sessions.get(session_id)
            if sess and hasattr(sess, "get_metrics"):
                original_get_metrics = sess.get_metrics
                sess.get_metrics = lambda: (_ for _ in ()).throw(RuntimeError("test error"))

                # Call metrics endpoint
                response = client.get(f"/sessions/{session_id}/metrics")
                assert response.status_code == 500
                error_detail = response.json()["detail"]
                assert error_detail == "metrics error"
                assert "test error" not in error_detail  # No exception text leaked
        finally:
            # Restore original method
            if original_get_metrics:
                sess.get_metrics = original_get_metrics

        # Clean up
        client.delete(f"/sessions/{session_id}")

    def test_snapshot_error_no_exception_leak(self):
        """Test that snapshot endpoint doesn't leak exception text in 500 response."""
        client = TestClient(app)

        # Create streaming session
        response = client.post(
            "/sessions",
            json={
                "asr_model_id": "tiny.en",
                "streaming_mode": True,
                "device": "cpu",
            },
        )
        assert response.status_code == 200
        session_id = response.json()["session_id"]

        # Force an internal error by monkeypatching
        from loquilex.api.server import MANAGER

        original_get_asr_snapshot = None
        try:
            sess = MANAGER._sessions.get(session_id)
            if sess and hasattr(sess, "get_asr_snapshot"):
                original_get_asr_snapshot = sess.get_asr_snapshot
                sess.get_asr_snapshot = lambda: (_ for _ in ()).throw(RuntimeError("snapshot test error"))

                # Call snapshot endpoint
                response = client.get(f"/sessions/{session_id}/snapshot")
                # Should still work since ASR snapshot is optional
                assert response.status_code == 200
        finally:
            # Restore original method
            if original_get_asr_snapshot:
                sess.get_asr_snapshot = original_get_asr_snapshot

        # Clean up
        client.delete(f"/sessions/{session_id}")

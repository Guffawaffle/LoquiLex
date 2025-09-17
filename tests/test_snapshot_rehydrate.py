"""Test snapshot rehydrate functionality."""

import asyncio  # noqa: F401
import json
import pytest
from unittest.mock import AsyncMock, MagicMock  # noqa: F401

from loquilex.api.ws_protocol import WSProtocolManager
from loquilex.api.ws_types import (
    MessageType,
    SessionResumeData,
    WSEnvelope,
)


class MockWebSocket:
    """Mock WebSocket for testing."""

    def __init__(self):
        self.sent_messages = []
        self.closed = False

    async def send_text(self, message: str):
        """Mock send_text method."""
        if self.closed:
            raise Exception("WebSocket closed")
        self.sent_messages.append(message)

    async def close(self):
        """Mock close method."""
        self.closed = True

    def get_last_message(self) -> dict:
        """Get the last sent message as parsed JSON."""
        if not self.sent_messages:
            raise AssertionError("No messages sent")
        return json.loads(self.sent_messages[-1])


@pytest.mark.asyncio
class TestSnapshotRehydrate:
    """Test snapshot rehydrate functionality."""

    async def test_snapshot_with_finalized_transcript(self):
        """Test that snapshot includes actual finalized transcript from session."""
        # Create protocol manager with snapshot callback
        manager = WSProtocolManager("test_session")

        # Mock session snapshot data
        mock_snapshot_data = {
            "finalized_transcript": [
                {
                    "segment_id": "seg1",
                    "text": "Hello world.",
                    "t0": 0.0,
                    "t1": 1.5,
                    "final_seq_range": [1, 2, 3],
                }
            ],
            "active_partials": [
                {
                    "segment_id": "seg2",
                    "text": "This is a partial",
                    "words": [],
                    "seq": 4,
                }
            ],
            "mt_status": {"enabled": True, "dest_lang": "zh"},
        }

        async def mock_get_snapshot(sid):
            if sid is None:
                pass  # For type checker
            return mock_snapshot_data

        manager.set_session_snapshot_callback(mock_get_snapshot)

        async with manager:
            # Add connection and some messages to replay buffer
            mock_ws = MockWebSocket()
            await manager.add_connection(mock_ws)
            mock_ws.sent_messages.clear()

            # Add some domain events
            await manager.send_domain_event(MessageType.ASR_PARTIAL, {"text": "msg1"})
            await manager.send_domain_event(MessageType.ASR_FINAL, {"text": "msg2"})

            # Remove connection to simulate disconnect
            await manager.remove_connection(mock_ws)

            # Reconnect and resume
            mock_ws2 = MockWebSocket()
            await manager.add_connection(mock_ws2)
            mock_ws2.sent_messages.clear()

            resume_envelope = WSEnvelope(
                t=MessageType.SESSION_RESUME,
                data=SessionResumeData(
                    session_id="test_session",
                    last_seq=0,
                    epoch=manager.state.epoch,
                ).model_dump(),
            )
            await manager.handle_message(mock_ws2, resume_envelope.model_dump_json())

            # Should have sent: snapshot, replay messages, ack
            assert len(mock_ws2.sent_messages) >= 3

            # Check snapshot message contains actual data
            snapshot_msg = json.loads(mock_ws2.sent_messages[0])
            assert snapshot_msg["t"] == "session.snapshot"

            snapshot_data = snapshot_msg["data"]
            assert len(snapshot_data["finalized_transcript"]) == 1
            assert snapshot_data["finalized_transcript"][0]["text"] == "Hello world."
            assert snapshot_data["finalized_transcript"][0]["final_seq_range"] == [1, 2, 3]

            assert len(snapshot_data["active_partials"]) == 1
            assert snapshot_data["active_partials"][0]["text"] == "This is a partial"

            assert snapshot_data["mt_status"]["dest_lang"] == "zh"

    async def test_resume_metrics_tracking(self):
        """Test that resume operations are properly tracked in metrics."""
        async with WSProtocolManager("test_session") as manager:
            mock_ws = MockWebSocket()
            await manager.add_connection(mock_ws)
            mock_ws.sent_messages.clear()

            # Mock session snapshot callback
            async def mock_get_snapshot(sid):
                if sid is None:
                    pass  # For type checker
                return {
                    "finalized_transcript": [{"text": "test"}],
                    "active_partials": [],
                    "mt_status": None,
                }

            manager.set_session_snapshot_callback(mock_get_snapshot)

            # Add some messages to replay buffer
            await manager.send_domain_event(MessageType.ASR_PARTIAL, {"text": "hello"})

            # Simulate resume request
            resume_envelope = WSEnvelope(
                t=MessageType.SESSION_RESUME,
                data=SessionResumeData(
                    session_id="test_session",
                    last_seq=0,
                    epoch=manager.state.epoch,
                ).model_dump(),
            )
            await manager.handle_message(mock_ws, resume_envelope.model_dump_json())

            # Check metrics
            telemetry = manager.get_telemetry_summary()
            resume_metrics = telemetry["resume_metrics"]

            assert resume_metrics["attempts"] == 1
            assert resume_metrics["success"] == 1
            assert resume_metrics["miss"] == 0
            assert resume_metrics["success_rate"] == 1.0
            assert resume_metrics["avg_snapshot_size"] > 0
            assert resume_metrics["avg_replay_duration_ms"] >= 0

    async def test_resume_miss_tracking(self):
        """Test that failed resume attempts are tracked as misses."""
        async with WSProtocolManager("test_session") as manager:
            mock_ws = MockWebSocket()
            await manager.add_connection(mock_ws)
            mock_ws.sent_messages.clear()

            # Wrong session ID should be a miss
            resume_envelope = WSEnvelope(
                t=MessageType.SESSION_RESUME,
                data=SessionResumeData(
                    session_id="wrong_session",
                    last_seq=0,
                    epoch=manager.state.epoch,
                ).model_dump(),
            )
            await manager.handle_message(mock_ws, resume_envelope.model_dump_json())

            # Check metrics
            telemetry = manager.get_telemetry_summary()
            resume_metrics = telemetry["resume_metrics"]

            assert resume_metrics["attempts"] == 1
            assert resume_metrics["success"] == 0
            assert resume_metrics["miss"] == 1
            assert resume_metrics["success_rate"] == 0.0

    async def test_monotonic_timing_in_envelopes(self):
        """Test that all envelopes include monotonic timing (t_mono_ns)."""
        async with WSProtocolManager("test_session") as manager:
            mock_ws = MockWebSocket()
            await manager.add_connection(mock_ws)

            # Welcome message should have monotonic timing
            welcome_msg = json.loads(mock_ws.sent_messages[0])
            assert "t_mono_ns" in welcome_msg
            assert welcome_msg["t_mono_ns"] is not None
            assert welcome_msg["t_mono_ns"] > 0

            mock_ws.sent_messages.clear()

            # Domain events should have monotonic timing
            await manager.send_domain_event(MessageType.ASR_PARTIAL, {"text": "test"})

            partial_msg = json.loads(mock_ws.sent_messages[0])
            assert "t_mono_ns" in partial_msg
            assert partial_msg["t_mono_ns"] is not None
            assert partial_msg["t_mono_ns"] > welcome_msg["t_mono_ns"]  # Should be later

    async def test_final_seq_range_in_snapshot(self):
        """Test that final_seq_range is properly included in snapshot data."""
        async with WSProtocolManager("test_session") as manager:
            # Mock session snapshot with final_seq_range
            async def mock_get_snapshot(sid):
                if sid is None:
                    pass  # For type checker
                return {
                    "finalized_transcript": [
                        {
                            "segment_id": "seg1",
                            "text": "First segment.",
                            "final_seq_range": [
                                1,
                                2,
                                3,
                            ],  # This final covers partials with seq 1, 2, 3
                        },
                        {
                            "segment_id": "seg2",
                            "text": "Second segment.",
                            "final_seq_range": [4, 5],  # This final covers partials with seq 4, 5
                        },
                    ],
                    "active_partials": [],
                    "mt_status": None,
                }

            manager.set_session_snapshot_callback(mock_get_snapshot)

            mock_ws = MockWebSocket()
            await manager.add_connection(mock_ws)
            mock_ws.sent_messages.clear()

            # Simulate resume request
            resume_envelope = WSEnvelope(
                t=MessageType.SESSION_RESUME,
                data=SessionResumeData(
                    session_id="test_session",
                    last_seq=0,
                    epoch=manager.state.epoch,
                ).model_dump(),
            )
            await manager.handle_message(mock_ws, resume_envelope.model_dump_json())

            # Check snapshot contains final_seq_range
            snapshot_msg = json.loads(mock_ws.sent_messages[0])
            finalized_transcript = snapshot_msg["data"]["finalized_transcript"]

            assert len(finalized_transcript) == 2
            assert finalized_transcript[0]["final_seq_range"] == [1, 2, 3]
            assert finalized_transcript[1]["final_seq_range"] == [4, 5]

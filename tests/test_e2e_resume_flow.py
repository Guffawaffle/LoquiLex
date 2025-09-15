"""End-to-end test for resume flow with no duplicate finals."""

import asyncio
import json
import pytest
from unittest.mock import AsyncMock # noqa: F401

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

    def get_messages_by_type(self, msg_type: str) -> list:
        """Get all messages of a specific type."""
        messages = []
        for msg_str in self.sent_messages:
            msg = json.loads(msg_str)
            if msg.get("t") == msg_type:
                messages.append(msg)
        return messages


@pytest.mark.asyncio
class TestE2EResumeFlow:
    """End-to-end test for resume flow demonstrating no duplicate finals."""

    async def test_resume_flow_no_duplicate_finals(self):
        """Test complete resume flow ensuring no duplicate finals and proper sequence ordering."""

        # Mock session data with finalized transcript and sequence ranges
        session_snapshot = {
            "finalized_transcript": [
                {
                    "segment_id": "seg1",
                    "text": "Hello world.",
                    "t0": 0.0,
                    "t1": 1.5,
                    "final_seq_range": [1, 2, 3],  # Final covers partial sequences 1,2,3
                },
                {
                    "segment_id": "seg2",
                    "text": "How are you?",
                    "t0": 2.0,
                    "t1": 3.5,
                    "final_seq_range": [4, 5],  # Final covers partial sequences 4,5
                }
            ],
            "active_partials": [
                {
                    "segment_id": "seg3",
                    "text": "I am fine",  # In-progress partial
                    "words": [],
                    "seq": 6,
                }
            ],
            "mt_status": {"enabled": True, "dest_lang": "zh"}
        }

        async def mock_get_snapshot(sid): # noqa: ARG001
            return session_snapshot

        async with WSProtocolManager("test_session") as manager:
            manager.set_session_snapshot_callback(mock_get_snapshot)

            # Phase 1: Initial connection and some events
            ws1 = MockWebSocket()
            await manager.add_connection(ws1)
            ws1.sent_messages.clear()

            # Send some domain events that would be in replay buffer
            await manager.send_domain_event(MessageType.ASR_PARTIAL, {"text": "This is"})  # seq=1
            await manager.send_domain_event(MessageType.ASR_PARTIAL, {"text": "This is newer"})  # seq=2
            await manager.send_domain_event(MessageType.ASR_FINAL, {"text": "This is newer text."})  # seq=3

            # Capture what was sent during initial session
            initial_messages = [json.loads(msg) for msg in ws1.sent_messages]
            initial_seq_numbers = [msg["seq"] for msg in initial_messages if "seq" in msg]

            # Phase 2: Disconnect (simulate network issue)
            await manager.remove_connection(ws1)

            # Phase 3: Reconnect and resume (client sends resume request)
            ws2 = MockWebSocket()
            await manager.add_connection(ws2)
            ws2.sent_messages.clear()

            # Client sends resume request with last received seq
            last_received_seq = max(initial_seq_numbers) if initial_seq_numbers else 0
            resume_request = WSEnvelope(
                t=MessageType.SESSION_RESUME,
                data=SessionResumeData(
                    session_id="test_session",
                    last_seq=last_received_seq,
                    epoch=manager.state.epoch,
                ).model_dump(),
            )
            await manager.handle_message(ws2, resume_request.model_dump_json())

            # Phase 4: Validate resume response
            resume_messages = [json.loads(msg) for msg in ws2.sent_messages]

            # Should have: snapshot, potentially replay messages, ack
            assert len(resume_messages) >= 2  # At least snapshot + ack

            # First message should be snapshot
            snapshot_msg = resume_messages[0]
            assert snapshot_msg["t"] == "session.snapshot"

            # Validate snapshot contains expected data
            snapshot_data = snapshot_msg["data"]
            assert len(snapshot_data["finalized_transcript"]) == 2
            assert snapshot_data["finalized_transcript"][0]["text"] == "Hello world."
            assert snapshot_data["finalized_transcript"][0]["final_seq_range"] == [1, 2, 3]
            assert snapshot_data["finalized_transcript"][1]["text"] == "How are you?"
            assert snapshot_data["finalized_transcript"][1]["final_seq_range"] == [4, 5]

            assert len(snapshot_data["active_partials"]) == 1
            assert snapshot_data["active_partials"][0]["text"] == "I am fine"

            # Validate monotonic timing
            assert snapshot_msg["t_mono_ns"] is not None
            assert snapshot_msg["t_mono_ns"] > 0

            # Last message should be session ack
            ack_msg = resume_messages[-1]
            assert ack_msg["t"] == "session.ack"
            assert ack_msg["data"]["status"] == "resumed"

            # Phase 5: Continue session with new events (ensure sequence continues properly)
            ws2.sent_messages.clear()
            await manager.send_domain_event(MessageType.ASR_FINAL, {"text": "I am fine, thanks."})  # Should get next seq

            new_messages = [json.loads(msg) for msg in ws2.sent_messages]
            assert len(new_messages) == 1

            new_final = new_messages[0]
            assert new_final["t"] == "asr.final"
            assert new_final["seq"] > last_received_seq  # Sequence should continue from where it left off

            # Phase 6: Validate metrics
            telemetry = manager.get_telemetry_summary()
            resume_metrics = telemetry["resume_metrics"]

            assert resume_metrics["attempts"] == 1
            assert resume_metrics["success"] == 1
            assert resume_metrics["miss"] == 0
            assert resume_metrics["success_rate"] == 1.0
            assert resume_metrics["avg_snapshot_size"] > 0  # Should have content in snapshot

    async def test_ordering_guarantees_after_resume(self):
        """Test that sequence ordering is maintained after resume."""

        async def mock_get_snapshot(sid): # noqa: ARG001
            return {
                "finalized_transcript": [],
                "active_partials": [],
                "mt_status": None
            }

        async with WSProtocolManager("test_session") as manager:
            manager.set_session_snapshot_callback(mock_get_snapshot)

            # Initial session
            ws1 = MockWebSocket()
            await manager.add_connection(ws1)

            # Send some events
            await manager.send_domain_event(MessageType.ASR_PARTIAL, {"text": "msg1"})  # seq=1
            await manager.send_domain_event(MessageType.ASR_PARTIAL, {"text": "msg2"})  # seq=2

            # Get sequence numbers
            initial_messages = [json.loads(msg) for msg in ws1.sent_messages if json.loads(msg)["t"] in ["asr.partial"]]
            last_seq = max(msg["seq"] for msg in initial_messages)

            # Disconnect and resume
            await manager.remove_connection(ws1)

            ws2 = MockWebSocket()
            await manager.add_connection(ws2)
            ws2.sent_messages.clear()

            # Resume from last sequence
            resume_request = WSEnvelope(
                t=MessageType.SESSION_RESUME,
                data=SessionResumeData(
                    session_id="test_session",
                    last_seq=last_seq,
                    epoch=manager.state.epoch,
                ).model_dump(),
            )
            await manager.handle_message(ws2, resume_request.model_dump_json())
            ws2.sent_messages.clear()

            # Send new events after resume
            await manager.send_domain_event(MessageType.ASR_PARTIAL, {"text": "msg3"})  # Should be seq=3
            await manager.send_domain_event(MessageType.ASR_FINAL, {"text": "msg3 final"})  # Should be seq=4

            new_messages = [json.loads(msg) for msg in ws2.sent_messages]

            # Check sequence ordering is maintained
            sequences = [msg["seq"] for msg in new_messages if "seq" in msg]
            assert sequences == sorted(sequences)  # Should be in ascending order
            assert min(sequences) > last_seq  # Should continue from where we left off

            # Check all sequences are strictly increasing
            for i in range(1, len(sequences)):
                assert sequences[i] == sequences[i-1] + 1  # Should be consecutive

    async def test_resume_with_expired_window(self):
        """Test graceful handling when resume window has expired."""

        from loquilex.api.ws_types import ResumeWindow

        # Very short resume window (1 second)
        short_window = ResumeWindow(seconds=1)

        async with WSProtocolManager("test_session", resume_window=short_window) as manager:
            ws1 = MockWebSocket()
            await manager.add_connection(ws1)
            await manager.send_domain_event(MessageType.ASR_PARTIAL, {"text": "msg1"})
            await manager.remove_connection(ws1)

            # Wait for window to expire
            await asyncio.sleep(1.1)

            # Try to resume
            ws2 = MockWebSocket()
            await manager.add_connection(ws2)
            ws2.sent_messages.clear()

            resume_request = WSEnvelope(
                t=MessageType.SESSION_RESUME,
                data=SessionResumeData(
                    session_id="test_session",
                    last_seq=1,
                    epoch=manager.state.epoch,
                ).model_dump(),
            )
            await manager.handle_message(ws2, resume_request.model_dump_json())

            # Should get session.new (fresh start) instead of snapshot
            resume_response = json.loads(ws2.sent_messages[0])
            assert resume_response["t"] == "session.new"
            assert resume_response["data"]["reason"] == "resume_expired"

            # Check metrics recorded the miss
            telemetry = manager.get_telemetry_summary()
            resume_metrics = telemetry["resume_metrics"]
            assert resume_metrics["attempts"] == 1
            assert resume_metrics["miss"] == 1
            assert resume_metrics["success"] == 0
"""Integration tests for SessionState with session storage."""

import os
import time
from unittest.mock import patch

from loquilex.api.ws_types import SessionState


class TestSessionStateIntegration:
    """Test SessionState integration with session storage."""

    def test_session_state_storage_initialization(self):
        """Test that SessionState automatically initializes session storage."""
        session_state = SessionState(
            sid="test-session", t0_mono=time.monotonic(), t0_wall="2023-01-01T00:00:00Z"
        )

        # Session storage should be initialized
        assert session_state._session_storage is not None
        assert session_state._session_storage.session_id == "test-session"

    def test_session_state_storage_with_env_config(self):
        """Test that SessionState respects environment configuration."""
        with patch.dict(
            os.environ,
            {
                "LX_SESSION_MAX_COMMITS": "50",
                "LX_SESSION_MAX_SIZE_BYTES": "512000",
                "LX_SESSION_MAX_AGE_SECONDS": "1800.0",
            },
        ):
            session_state = SessionState(
                sid="test-session", t0_mono=time.monotonic(), t0_wall="2023-01-01T00:00:00Z"
            )

            config = session_state._session_storage.config
            assert config.max_commits == 50
            assert config.max_size_bytes == 512000
            assert config.max_age_seconds == 1800.0

    def test_add_session_commit(self):
        """Test adding commits through SessionState."""
        session_state = SessionState(
            sid="test-session", t0_mono=time.monotonic(), t0_wall="2023-01-01T00:00:00Z"
        )

        # Add a transcript commit
        commit = session_state.add_session_commit(
            "transcript", {"text": "hello world", "confidence": 0.95}
        )

        assert commit is not None
        assert commit.commit_type == "transcript"
        assert commit.data["text"] == "hello world"
        assert commit.seq == 0  # Should use current session seq

    def test_get_session_snapshot(self):
        """Test getting session storage snapshot."""
        session_state = SessionState(
            sid="test-session", t0_mono=time.monotonic(), t0_wall="2023-01-01T00:00:00Z"
        )

        # Add some commits
        session_state.add_session_commit("transcript", {"text": "first"})
        session_state.add_session_commit("translation", {"text": "primero"})
        session_state.add_session_commit("status", {"stage": "complete"})

        snapshot = session_state.get_session_snapshot()

        assert snapshot is not None
        assert snapshot["session_id"] == "test-session"
        assert snapshot["total_commits"] == 3
        assert len(snapshot["recent_commits"]) == 3

        # Check that different commit types are present
        commit_types = {c["type"] for c in snapshot["recent_commits"]}
        assert "transcript" in commit_types
        assert "translation" in commit_types
        assert "status" in commit_types

    def test_get_session_storage_stats(self):
        """Test getting session storage statistics."""
        session_state = SessionState(
            sid="test-session", t0_mono=time.monotonic(), t0_wall="2023-01-01T00:00:00Z"
        )

        # Add some commits
        for i in range(5):
            session_state.add_session_commit("transcript", {"text": f"message {i}"})

        stats = session_state.get_session_storage_stats()

        assert stats is not None
        assert stats["session_id"] == "test-session"
        assert stats["total_commits"] == 5
        assert stats["commits_added"] == 5
        assert stats["commits_dropped"] == 0
        assert stats["total_size_bytes"] > 0

    def test_session_state_with_sequence_tracking(self):
        """Test that commits use correct sequence numbers."""
        session_state = SessionState(
            sid="test-session", t0_mono=time.monotonic(), t0_wall="2023-01-01T00:00:00Z"
        )

        # Advance sequence number
        session_state.next_seq()  # seq = 1
        session_state.next_seq()  # seq = 2

        commit = session_state.add_session_commit("transcript", {"text": "test"})

        assert commit.seq == 2  # Should match current session seq

    def test_session_state_storage_capping(self):
        """Test that session storage respects capping limits."""
        # Create session with small storage limits
        with patch.dict(os.environ, {"LX_SESSION_MAX_COMMITS": "3"}):
            session_state = SessionState(
                sid="test-session", t0_mono=time.monotonic(), t0_wall="2023-01-01T00:00:00Z"
            )

            # Add more commits than limit
            for i in range(5):
                session_state.add_session_commit("transcript", {"text": f"message {i}"})

            stats = session_state.get_session_storage_stats()

            # Should be capped at 3 commits
            assert stats["total_commits"] == 3
            assert stats["commits_dropped"] == 2

            # Should keep the most recent commits
            snapshot = session_state.get_session_snapshot()
            texts = [c["data"]["text"] for c in snapshot["recent_commits"]]
            assert "message 4" in texts  # Most recent
            assert "message 3" in texts
            assert "message 2" in texts
            assert "message 0" not in texts  # Oldest dropped
            assert "message 1" not in texts

    def test_session_state_without_storage(self):
        """Test graceful handling when storage is not available."""
        session_state = SessionState(
            sid="test-session", t0_mono=time.monotonic(), t0_wall="2023-01-01T00:00:00Z"
        )

        # Manually disable storage to test fallback
        session_state._session_storage = None

        # Should return None gracefully
        commit = session_state.add_session_commit("transcript", {"text": "test"})
        assert commit is None

        snapshot = session_state.get_session_snapshot()
        assert snapshot is None

        stats = session_state.get_session_storage_stats()
        assert stats is None

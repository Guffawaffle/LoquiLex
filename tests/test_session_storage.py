"""Unit tests for SessionStorage with rolling history and capped storage."""

from unittest.mock import patch
import pytest

from loquilex.api.session_storage import SessionStorage, StorageConfig, SessionCommit


class TestStorageConfig:
    """Test storage configuration validation."""

    def test_default_values(self):
        """Test default configuration values."""
        config = StorageConfig()
        assert config.max_commits == 100
        assert config.max_size_bytes == 1024 * 1024  # 1MB
        assert config.max_age_seconds == 3600.0  # 1 hour

    def test_validation_success(self):
        """Test valid configuration passes validation."""
        config = StorageConfig(max_commits=50, max_size_bytes=512 * 1024, max_age_seconds=1800.0)
        config.validate()  # Should not raise

    def test_validation_negative_commits(self):
        """Test validation fails for negative max_commits."""
        config = StorageConfig(max_commits=0)
        with pytest.raises(ValueError, match="max_commits must be positive"):
            config.validate()

    def test_validation_negative_size(self):
        """Test validation fails for negative max_size_bytes."""
        config = StorageConfig(max_size_bytes=-1)
        with pytest.raises(ValueError, match="max_size_bytes must be positive"):
            config.validate()

    def test_validation_negative_age(self):
        """Test validation fails for negative max_age_seconds."""
        config = StorageConfig(max_age_seconds=0)
        with pytest.raises(ValueError, match="max_age_seconds must be positive"):
            config.validate()


class TestSessionCommit:
    """Test session commit creation and size calculation."""

    def test_default_values(self):
        """Test commit created with default values."""
        commit = SessionCommit()
        assert commit.id  # UUID should be generated
        assert commit.timestamp > 0  # Should have current time
        assert commit.seq == 0
        assert commit.commit_type == "transcript"
        assert commit.data == {}
        assert commit.size_bytes > 0  # Should calculate size

    def test_custom_values(self):
        """Test commit created with custom values."""
        data = {"text": "hello world", "confidence": 0.95}
        commit = SessionCommit(seq=42, commit_type="translation", data=data)
        assert commit.seq == 42
        assert commit.commit_type == "translation"
        assert commit.data == data
        assert commit.size_bytes > 0

    def test_size_calculation(self):
        """Test that size calculation increases with data size."""
        small_commit = SessionCommit(data={"text": "hi"})
        large_commit = SessionCommit(data={"text": "hello world " * 100})

        assert large_commit.size_bytes > small_commit.size_bytes


class TestSessionStorage:
    """Test session storage functionality."""

    def test_initialization(self):
        """Test storage initialization."""
        storage = SessionStorage("test-session")
        assert storage.session_id == "test-session"
        assert storage.config.max_commits == 100  # Default

        stats = storage.get_stats()
        assert stats["total_commits"] == 0
        assert stats["total_size_bytes"] == 0
        assert stats["commits_added"] == 0
        assert stats["commits_dropped"] == 0

    def test_initialization_with_config(self):
        """Test storage initialization with custom config."""
        config = StorageConfig(max_commits=50, max_size_bytes=256 * 1024)
        storage = SessionStorage("test-session", config)
        assert storage.config.max_commits == 50
        assert storage.config.max_size_bytes == 256 * 1024

    def test_add_commit_basic(self):
        """Test adding a basic commit."""
        storage = SessionStorage("test-session")

        data = {"text": "hello world", "confidence": 0.95}
        commit = storage.add_commit("transcript", data, seq=1)

        assert commit.id
        assert commit.seq == 1
        assert commit.commit_type == "transcript"
        assert commit.data == data
        assert commit.timestamp > 0

        stats = storage.get_stats()
        assert stats["total_commits"] == 1
        assert stats["commits_added"] == 1
        assert stats["total_size_bytes"] > 0

    def test_add_multiple_commits(self):
        """Test adding multiple commits."""
        storage = SessionStorage("test-session")

        # Add several commits
        for i in range(5):
            storage.add_commit("transcript", {"text": f"message {i}"}, seq=i)

        stats = storage.get_stats()
        assert stats["total_commits"] == 5
        assert stats["commits_added"] == 5
        assert stats["commits_dropped"] == 0

    def test_get_commits_all(self):
        """Test retrieving all commits."""
        storage = SessionStorage("test-session")

        # Add commits with different timestamps
        with patch("time.monotonic", return_value=100.0):
            storage.add_commit("transcript", {"text": "first"}, seq=1)

        with patch("time.monotonic", return_value=101.0):
            storage.add_commit("transcript", {"text": "second"}, seq=2)

        with patch("time.monotonic", return_value=102.0):
            storage.add_commit("translation", {"text": "third"}, seq=3)

        commits = storage.get_commits()
        assert len(commits) == 3

        # Should be ordered by timestamp (most recent first)
        assert commits[0].data["text"] == "third"
        assert commits[1].data["text"] == "second"
        assert commits[2].data["text"] == "first"

    def test_get_commits_with_limit(self):
        """Test retrieving commits with limit."""
        storage = SessionStorage("test-session")

        # Add 5 commits
        for i in range(5):
            storage.add_commit("transcript", {"text": f"message {i}"}, seq=i)

        commits = storage.get_commits(limit=3)
        assert len(commits) == 3

    def test_get_commits_by_type(self):
        """Test filtering commits by type."""
        storage = SessionStorage("test-session")

        storage.add_commit("transcript", {"text": "transcript1"}, seq=1)
        storage.add_commit("translation", {"text": "translation1"}, seq=2)
        storage.add_commit("transcript", {"text": "transcript2"}, seq=3)
        storage.add_commit("status", {"stage": "processing"}, seq=4)

        transcript_commits = storage.get_commits(commit_type="transcript")
        assert len(transcript_commits) == 2
        assert all(c.commit_type == "transcript" for c in transcript_commits)

        translation_commits = storage.get_commits(commit_type="translation")
        assert len(translation_commits) == 1
        assert translation_commits[0].commit_type == "translation"

    def test_get_commits_since_timestamp(self):
        """Test filtering commits by timestamp."""
        # Create a mock time function
        mock_time = patch("time.monotonic")
        time_mock = mock_time.start()

        try:
            storage = SessionStorage("test-session", now_fn=time_mock)

            time_mock.return_value = 100.0
            storage.add_commit("transcript", {"text": "old"}, seq=1)

            time_mock.return_value = 200.0
            storage.add_commit("transcript", {"text": "new"}, seq=2)

            # Get commits since 150.0 (should only get the new one)
            recent_commits = storage.get_commits(since_timestamp=150.0)
            assert len(recent_commits) == 1
            assert recent_commits[0].data["text"] == "new"
        finally:
            mock_time.stop()

    def test_count_based_capping(self):
        """Test that storage caps by number of commits."""
        config = StorageConfig(max_commits=3)
        storage = SessionStorage("test-session", config)

        # Add more commits than the limit
        for i in range(5):
            storage.add_commit("transcript", {"text": f"message {i}"}, seq=i)

        stats = storage.get_stats()
        assert stats["total_commits"] == 3  # Should be capped
        assert stats["commits_added"] == 5
        assert stats["commits_dropped"] == 2  # 2 oldest dropped

        # Should keep the most recent commits
        commits = storage.get_commits()
        texts = [c.data["text"] for c in commits]
        assert "message 4" in texts  # Most recent
        assert "message 3" in texts
        assert "message 2" in texts
        assert "message 0" not in texts  # Oldest dropped
        assert "message 1" not in texts

    def test_time_based_capping(self):
        """Test that storage caps by commit age."""
        config = StorageConfig(max_age_seconds=5.0)

        # Create a mock time function that we can control
        mock_time = patch("time.monotonic")
        time_mock = mock_time.start()

        try:
            # Create storage with mocked time function
            storage = SessionStorage("test-session", config, now_fn=time_mock)

            # Add old commit
            time_mock.return_value = 100.0
            storage.add_commit("transcript", {"text": "old"}, seq=1)

            # Add recent commit and trigger cleanup (10 seconds later)
            time_mock.return_value = 110.0
            storage.add_commit("transcript", {"text": "new"}, seq=2)

            stats = storage.get_stats()
            assert stats["total_commits"] == 1  # Old commit should be dropped
            assert stats["commits_dropped"] == 1

            commits = storage.get_commits()
            assert len(commits) == 1
            assert commits[0].data["text"] == "new"
        finally:
            mock_time.stop()

    def test_size_based_capping(self):
        """Test that storage caps by total size."""
        # Set a very small size limit
        config = StorageConfig(max_size_bytes=500)
        storage = SessionStorage("test-session", config)

        # Add commits with large data until size limit is exceeded
        large_data = {"text": "x" * 200}  # Large text data

        storage.add_commit("transcript", large_data, seq=1)
        storage.add_commit("transcript", large_data, seq=2)
        storage.add_commit(
            "transcript", large_data, seq=3
        )  # This should trigger size-based dropping

        stats = storage.get_stats()
        assert stats["total_size_bytes"] <= config.max_size_bytes
        assert stats["commits_dropped"] > 0

    def test_get_snapshot(self):
        """Test snapshot generation."""
        storage = SessionStorage("test-session")

        # Add some commits
        storage.add_commit("transcript", {"text": "hello"}, seq=1)
        storage.add_commit("translation", {"text": "hola"}, seq=2)
        storage.add_commit("status", {"stage": "complete"}, seq=3)

        snapshot = storage.get_snapshot(max_commits=10)

        assert snapshot["session_id"] == "test-session"
        assert snapshot["total_commits"] == 3
        assert len(snapshot["recent_commits"]) == 3
        assert "storage_stats" in snapshot

        # Check commit structure in snapshot
        commit = snapshot["recent_commits"][0]  # Most recent
        assert "id" in commit
        assert "timestamp" in commit
        assert "seq" in commit
        assert "type" in commit
        assert "data" in commit

    def test_get_snapshot_with_limit(self):
        """Test snapshot generation with commit limit."""
        storage = SessionStorage("test-session")

        # Add more commits than limit
        for i in range(5):
            storage.add_commit("transcript", {"text": f"message {i}"}, seq=i)

        snapshot = storage.get_snapshot(max_commits=3)

        assert snapshot["total_commits"] == 5
        assert len(snapshot["recent_commits"]) == 3  # Limited by max_commits

    def test_clear_storage(self):
        """Test clearing all commits."""
        storage = SessionStorage("test-session")

        # Add some commits
        for i in range(3):
            storage.add_commit("transcript", {"text": f"message {i}"}, seq=i)

        assert storage.get_stats()["total_commits"] == 3

        cleared_count = storage.clear()
        assert cleared_count == 3

        stats = storage.get_stats()
        assert stats["total_commits"] == 0
        assert stats["total_size_bytes"] == 0

    def test_thread_safety(self):
        """Test basic thread safety of storage operations."""
        import threading
        import time

        storage = SessionStorage("test-session")
        errors = []

        def add_commits():
            try:
                for i in range(10):
                    storage.add_commit("transcript", {"text": f"thread message {i}"}, seq=i)
                    time.sleep(0.001)  # Small delay to increase chance of race conditions
            except Exception as e:
                errors.append(e)

        # Run multiple threads adding commits
        threads = []
        for _ in range(3):
            thread = threading.Thread(target=add_commits)
            threads.append(thread)
            thread.start()

        for thread in threads:
            thread.join()

        # Should not have any errors
        assert len(errors) == 0

        # Should have all commits (3 threads * 10 commits each)
        stats = storage.get_stats()
        assert stats["commits_added"] == 30

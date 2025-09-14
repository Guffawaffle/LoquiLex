"""Unit tests for BoundedQueue utility."""

import time
from unittest.mock import patch

import pytest

from loquilex.api.bounded_queue import BoundedQueue, DropMetrics, ReplayBuffer


class TestDropMetrics:
    """Test drop metrics tracking."""

    def test_initialization(self):
        """Test metrics initialization."""
        metrics = DropMetrics()
        assert metrics.total_dropped == 0
        assert metrics.drop_count_since_last_read == 0
        assert metrics.last_drop_time_mono == 0.0
        assert metrics.drop_reason == ""

    def test_record_drop(self):
        """Test drop recording."""
        metrics = DropMetrics()
        
        with patch('time.monotonic', return_value=123.45):
            metrics.record_drop("capacity")
            
        assert metrics.total_dropped == 1
        assert metrics.drop_count_since_last_read == 1
        assert metrics.last_drop_time_mono == 123.45
        assert metrics.drop_reason == "capacity"

    def test_read_and_reset_recent(self):
        """Test reading and resetting recent drop count."""
        metrics = DropMetrics()
        metrics.record_drop("test")
        metrics.record_drop("test")
        
        # First read should return count and reset
        count = metrics.read_and_reset_recent()
        assert count == 2
        assert metrics.drop_count_since_last_read == 0
        assert metrics.total_dropped == 2  # Total should remain
        
        # Second read should return 0
        count = metrics.read_and_reset_recent()
        assert count == 0


class TestBoundedQueue:
    """Test bounded queue functionality."""

    def test_initialization(self):
        """Test queue initialization."""
        queue = BoundedQueue(maxsize=10, name="test")
        assert queue.maxsize == 10
        assert queue.name == "test"
        assert queue.size() == 0
        assert queue.is_empty()
        assert not queue.is_full()

    def test_invalid_maxsize(self):
        """Test invalid maxsize raises error."""
        with pytest.raises(ValueError, match="maxsize must be positive"):
            BoundedQueue(maxsize=0)
            
        with pytest.raises(ValueError, match="maxsize must be positive"):
            BoundedQueue(maxsize=-1)

    def test_put_get_basic(self):
        """Test basic put/get operations."""
        queue = BoundedQueue(maxsize=3)
        
        # Put items
        assert queue.put_nowait("item1")
        assert queue.put_nowait("item2")
        assert queue.size() == 2
        assert not queue.is_empty()
        assert not queue.is_full()
        
        # Get items (FIFO order)
        assert queue.get_nowait() == "item1"
        assert queue.get_nowait() == "item2"
        assert queue.get_nowait() is None  # Empty queue
        assert queue.is_empty()

    def test_capacity_and_drop_oldest(self):
        """Test capacity limits and drop-oldest behavior."""
        queue = BoundedQueue(maxsize=2)
        
        # Fill to capacity
        queue.put_nowait("item1")
        queue.put_nowait("item2")
        assert queue.is_full()
        assert queue.size() == 2
        
        # Adding third item should drop oldest
        with patch('time.monotonic', return_value=100.0):
            queue.put_nowait("item3")
            
        assert queue.size() == 2  # Still at capacity
        assert queue.metrics.total_dropped == 1
        assert queue.metrics.drop_reason == "capacity"
        assert queue.metrics.last_drop_time_mono == 100.0
        
        # Verify oldest was dropped
        assert queue.get_nowait() == "item2"  # item1 was dropped
        assert queue.get_nowait() == "item3"

    def test_peek(self):
        """Test peek functionality."""
        queue = BoundedQueue(maxsize=5)
        
        # Empty queue
        assert queue.peek() is None
        
        # Add items and peek
        queue.put_nowait("first")
        queue.put_nowait("second")
        
        assert queue.peek() == "first"
        assert queue.size() == 2  # Peek doesn't remove
        
        # Get item and peek again
        assert queue.get_nowait() == "first"
        assert queue.peek() == "second"

    def test_clear(self):
        """Test clear functionality."""
        queue = BoundedQueue(maxsize=5)
        
        # Add items
        queue.put_nowait("item1")
        queue.put_nowait("item2")
        queue.put_nowait("item3")
        
        # Clear and check count
        count = queue.clear()
        assert count == 3
        assert queue.size() == 0
        assert queue.is_empty()

    def test_drain(self):
        """Test drain functionality."""
        queue = BoundedQueue(maxsize=5)
        
        # Add items
        queue.put_nowait("item1")
        queue.put_nowait("item2")
        queue.put_nowait("item3")
        
        # Drain all items
        items = queue.drain()
        assert items == ["item1", "item2", "item3"]
        assert queue.size() == 0
        assert queue.is_empty()

    def test_telemetry(self):
        """Test telemetry data collection."""
        queue = BoundedQueue(maxsize=5, name="test_queue")
        
        # Add some items and cause drops
        queue.put_nowait("item1")  
        queue.put_nowait("item2")
        
        with patch('time.monotonic', return_value=200.0):
            # Fill beyond capacity to cause drops
            for i in range(10):
                queue.put_nowait(f"item{i+3}")
        
        telemetry = queue.get_telemetry()
        
        assert telemetry["name"] == "test_queue"
        assert telemetry["size"] == 5  # At capacity
        assert telemetry["capacity"] == 5
        assert telemetry["utilization"] == 1.0
        assert telemetry["total_dropped"] > 0
        assert telemetry["last_drop_time_mono"] == 200.0
        assert telemetry["last_drop_reason"] == "capacity"

    def test_thread_safety_structure(self):
        """Test that queue has thread safety structure."""
        queue = BoundedQueue(maxsize=5)
        
        # Access should trigger lock initialization
        queue.put_nowait("test")
        assert queue._lock is not None


class TestReplayBuffer:
    """Test replay buffer specialized functionality."""

    def test_initialization(self):
        """Test replay buffer initialization."""
        buffer = ReplayBuffer(maxsize=10, ttl_seconds=5.0)
        assert buffer.maxsize == 10
        assert buffer.ttl_seconds == 5.0
        assert buffer.name == "replay_buffer"

    def test_add_message_with_seq(self):
        """Test adding messages with sequence numbers."""
        buffer = ReplayBuffer(maxsize=5, ttl_seconds=10.0)
        
        # Mock envelope objects
        env1 = {"type": "asr.partial", "text": "hello"}
        env2 = {"type": "asr.final", "text": "hello world"}
        
        with patch('time.monotonic', return_value=100.0):
            buffer.add_message(1, env1)
            buffer.add_message(2, env2)
            
        assert buffer.size() == 2

    def test_get_messages_after(self):
        """Test getting messages after a sequence number."""
        buffer = ReplayBuffer(maxsize=5, ttl_seconds=10.0)
        
        # Add messages with sequence numbers
        env1 = {"seq": 1, "text": "msg1"}
        env2 = {"seq": 2, "text": "msg2"}
        env3 = {"seq": 3, "text": "msg3"}
        
        with patch('time.monotonic', return_value=100.0):
            buffer.add_message(1, env1)
            buffer.add_message(2, env2)
            buffer.add_message(3, env3)
            
            # Get messages after seq 1 (within the patch context)
            messages = buffer.get_messages_after(1)
            assert len(messages) == 2
            assert messages[0]["seq"] == 2
            assert messages[1]["seq"] == 3
            
            # Get messages after seq 2
            messages = buffer.get_messages_after(2)
            assert len(messages) == 1
            assert messages[0]["seq"] == 3
            
            # Get messages after seq 3 (none)
            messages = buffer.get_messages_after(3)
            assert len(messages) == 0

    def test_ttl_cleanup(self):
        """Test TTL-based message cleanup."""
        buffer = ReplayBuffer(maxsize=10, ttl_seconds=2.0)
        
        env1 = {"seq": 1, "text": "old"}
        env2 = {"seq": 2, "text": "new"}
        
        # Add first message at time 100
        with patch('time.monotonic', return_value=100.0):
            buffer.add_message(1, env1)
            
        # Add second message at time 101 (within TTL)
        with patch('time.monotonic', return_value=101.0):
            buffer.add_message(2, env2)
            
        # Query at time 103 (first message expired, second still valid)
        with patch('time.monotonic', return_value=103.0):
            messages = buffer.get_messages_after(0)
            
        assert len(messages) == 1
        assert messages[0]["seq"] == 2
        assert buffer.metrics.total_dropped == 1  # First message dropped due to TTL

    def test_ttl_disabled(self):
        """Test behavior when TTL is disabled."""
        buffer = ReplayBuffer(maxsize=5, ttl_seconds=0.0)  # Disabled TTL
        
        env1 = {"seq": 1, "text": "persistent"}
        
        with patch('time.monotonic', return_value=100.0):
            buffer.add_message(1, env1)
            
        # Much later time should not affect messages when TTL disabled
        with patch('time.monotonic', return_value=1000.0):
            messages = buffer.get_messages_after(0)
            
        assert len(messages) == 1
        assert messages[0]["seq"] == 1
        assert buffer.metrics.total_dropped == 0  # No TTL drops
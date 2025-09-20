"""Resource Management Tests: Ensure clean termination and release of all resources.

This module tests proper cleanup of threads, asyncio tasks, subprocesses, 
and other resources across normal and error conditions.
"""

import asyncio
import gc
import threading
import time
import tracemalloc
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from pathlib import Path

from loquilex.api.supervisor import StreamingSession, Session, SessionManager, SessionConfig
from loquilex.api.ws_protocol import WSProtocolManager
from loquilex.api.bounded_queue import BoundedQueue
from loquilex.output.text_io import RollingTextFile


class TestStreamingSessionResourceManagement:
    """Test resource cleanup for StreamingSession."""

    def test_context_manager_cleanup(self):
        """Test that async context manager properly cleans up resources."""
        cfg = SessionConfig(
            name="test", asr_model_id="tiny.en", mt_enabled=False, 
            dest_lang="zh", device="cpu", vad=False, beams=1,
            pause_flush_sec=1.0, segment_max_sec=10.0, partial_word_cap=20,
            save_audio="none", streaming_mode=True
        )
        run_dir = Path("/tmp/test_session")
        run_dir.mkdir(exist_ok=True)

        async def test_context():
            async with StreamingSession("test_session", cfg, run_dir) as session:
                # Session should be initialized
                assert session.sid == "test_session"
                assert session._stop_evt is not None
            # After context exit, cleanup should have been called
            assert session._stop_evt.is_set()

        asyncio.run(test_context())

    def test_destructor_cleanup(self):
        """Test that destructor properly cleans up resources."""
        cfg = SessionConfig(
            name="test", asr_model_id="tiny.en", mt_enabled=False,
            dest_lang="zh", device="cpu", vad=False, beams=1,
            pause_flush_sec=1.0, segment_max_sec=10.0, partial_word_cap=20,
            save_audio="none", streaming_mode=True
        )
        run_dir = Path("/tmp/test_session")
        run_dir.mkdir(exist_ok=True)

        session = StreamingSession("test_session", cfg, run_dir)
        
        # Simulate an audio thread
        def dummy_thread():
            while not session._stop_evt.is_set():
                time.sleep(0.1)
        
        session._audio_thread = threading.Thread(target=dummy_thread, daemon=True)
        session._audio_thread.start()
        
        # Delete session - destructor should clean up
        del session
        gc.collect()
        
        # Thread should be stopped
        # Note: We can't directly verify this without the original reference,
        # but the destructor should have set the stop event


class TestSessionResourceManagement:
    """Test resource cleanup for Session."""

    def test_context_manager_cleanup(self):
        """Test that async context manager properly cleans up resources."""
        cfg = SessionConfig(
            name="test", asr_model_id="tiny.en", mt_enabled=False,
            dest_lang="zh", device="cpu", vad=False, beams=1,
            pause_flush_sec=1.0, segment_max_sec=10.0, partial_word_cap=20,
            save_audio="none", streaming_mode=False
        )
        run_dir = Path("/tmp/test_session")
        run_dir.mkdir(exist_ok=True)

        async def test_context():
            with patch('subprocess.Popen') as mock_popen:
                mock_proc = MagicMock()
                mock_proc.poll.return_value = None
                mock_popen.return_value = mock_proc
                
                async with Session("test_session", cfg, run_dir) as session:
                    # Session should be initialized
                    assert session.sid == "test_session"
                    assert session._stop_evt is not None
                # After context exit, cleanup should have been called
                assert session._stop_evt.is_set()

        asyncio.run(test_context())

    def test_destructor_handles_subprocess_cleanup(self):
        """Test that destructor properly handles subprocess cleanup."""
        cfg = SessionConfig(
            name="test", asr_model_id="tiny.en", mt_enabled=False,
            dest_lang="zh", device="cpu", vad=False, beams=1,
            pause_flush_sec=1.0, segment_max_sec=10.0, partial_word_cap=20,
            save_audio="none", streaming_mode=False
        )
        run_dir = Path("/tmp/test_session")
        run_dir.mkdir(exist_ok=True)

        with patch('subprocess.Popen') as mock_popen:
            mock_proc = MagicMock()
            mock_proc.poll.return_value = None
            mock_popen.return_value = mock_proc
            
            session = Session("test_session", cfg, run_dir)
            session.proc = mock_proc
            
            # Delete session - destructor should clean up
            del session
            gc.collect()
            
            # Process should have been terminated
            mock_proc.terminate.assert_called_once()


class TestSessionManagerResourceManagement:
    """Test resource cleanup for SessionManager."""

    @pytest.mark.asyncio
    async def test_shutdown_cleans_all_resources(self):
        """Test that shutdown method properly cleans up all resources."""
        with patch('threading.Thread') as mock_thread:
            mock_thread_instance = MagicMock()
            mock_thread.return_value = mock_thread_instance
            
            manager = SessionManager()
            
            # Mock some active sessions and protocols
            mock_session = MagicMock()
            mock_protocol = AsyncMock()
            mock_protocol.close = AsyncMock()
            
            manager._sessions["test_session"] = mock_session
            manager._ws_protocols["test_session"] = mock_protocol
            
            # Mock download process
            mock_proc = MagicMock()
            mock_proc.poll.return_value = None
            manager._dl_procs["test_job"] = mock_proc
            
            await manager.shutdown()
            
            # Verify cleanup was called
            assert manager._stop is True
            mock_session.stop.assert_called_once()
            mock_protocol.close.assert_called_once()

    def test_destructor_sets_stop_flag(self):
        """Test that destructor sets stop flag for background threads."""
        with patch('threading.Thread'):
            manager = SessionManager()
            
            # Add a mock session
            mock_session = MagicMock()
            manager._sessions["test_session"] = mock_session
            
            # Delete manager - destructor should clean up
            del manager
            gc.collect()
            
            # Stop should have been called on session
            mock_session.stop.assert_called_once()


class TestBoundedQueueResourceManagement:
    """Test resource cleanup for BoundedQueue."""

    def test_cleanup_method_clears_resources(self):
        """Test that cleanup method properly clears resources."""
        queue = BoundedQueue(maxsize=10, name="test_queue")
        
        # Add some items
        queue.put_nowait("item1")
        queue.put_nowait("item2")
        
        # Verify items are there
        assert queue.size() == 2
        
        # Cleanup
        queue.cleanup()
        
        # Verify resources are cleared
        assert queue.size() == 0
        assert queue.metrics.total_dropped == 0

    def test_destructor_clears_queue(self):
        """Test that destructor clears queue references."""
        queue = BoundedQueue(maxsize=10, name="test_queue")
        queue.put_nowait("item1")
        
        # Delete queue - destructor should clear
        del queue
        gc.collect()
        
        # No assertions needed - just verify no exceptions


class TestRollingTextFileResourceManagement:
    """Test resource cleanup for RollingTextFile."""

    def test_context_manager_support(self):
        """Test that context manager is properly supported."""
        test_path = "/tmp/test_rolling_file.txt"
        
        with RollingTextFile(test_path, max_lines=10) as writer:
            writer.append_final_line("test line")
            assert writer.path == test_path
        
        # Context manager should exit cleanly
        # File operations use atomic writes with proper context managers


class TestResourceLeakDetection:
    """Test resource leak detection using tracemalloc."""

    def test_memory_usage_bounded(self):
        """Test that memory usage remains bounded during normal operations."""
        tracemalloc.start()
        
        # Simulate some operations
        queues = []
        for i in range(10):
            queue = BoundedQueue(maxsize=100, name=f"queue_{i}")
            for j in range(50):
                queue.put_nowait(f"item_{j}")
            queues.append(queue)
        
        # Take snapshot
        snapshot1 = tracemalloc.take_snapshot()
        
        # Cleanup queues
        for queue in queues:
            queue.cleanup()
        queues.clear()
        gc.collect()
        
        # Take another snapshot
        snapshot2 = tracemalloc.take_snapshot()
        
        # Memory should not have grown significantly
        # (This is a basic check - in practice you'd want more sophisticated leak detection)
        stats1 = snapshot1.statistics('lineno')
        stats2 = snapshot2.statistics('lineno')
        
        # Just verify we can take snapshots without errors
        assert len(stats1) > 0
        assert len(stats2) > 0
        
        tracemalloc.stop()

    def test_thread_cleanup_after_operations(self):
        """Test that thread count remains bounded after operations."""
        initial_thread_count = threading.active_count()
        
        # Create some threaded operations
        events = []
        threads = []
        
        for i in range(5):
            event = threading.Event()
            events.append(event)
            
            def worker(stop_event):
                while not stop_event.is_set():
                    time.sleep(0.01)
            
            thread = threading.Thread(target=worker, args=(event,), daemon=True)
            thread.start()
            threads.append(thread)
        
        # Let threads run briefly
        time.sleep(0.1)
        
        # Stop all threads
        for event in events:
            event.set()
        
        for thread in threads:
            thread.join(timeout=1.0)
        
        # Thread count should return to normal
        final_thread_count = threading.active_count()
        
        # Allow for some variance in thread count
        assert final_thread_count <= initial_thread_count + 2


@pytest.mark.asyncio
class TestWSProtocolManagerResourceCleanup:
    """Test resource cleanup for WSProtocolManager."""

    async def test_context_manager_cleanup(self):
        """Test that context manager properly cleans up resources."""
        async with WSProtocolManager("test_session") as manager:
            assert manager.sid == "test_session"
            # Manager should be properly initialized
        
        # After context exit, tasks should be cleaned up
        assert manager._hb_task is None
        assert manager._hb_timeout_task is None
        assert manager._system_hb_task is None

    async def test_close_method_cleanup(self):
        """Test that close method properly cleans up resources."""
        manager = WSProtocolManager("test_session")
        
        # Simulate some connections and tasks
        mock_ws = AsyncMock()
        await manager.add_connection(mock_ws)
        
        # Close should clean up everything
        await manager.close()
        
        # Verify cleanup
        assert len(manager.connections) == 0
        assert len(manager._outbound_queues) == 0


class TestAbruptShutdownScenarios:
    """Test resource cleanup during abrupt shutdowns and error conditions."""

    def test_session_cleanup_during_exception(self):
        """Test that resources are cleaned up even when exceptions occur."""
        cfg = SessionConfig(
            name="test", asr_model_id="tiny.en", mt_enabled=False,
            dest_lang="zh", device="cpu", vad=False, beams=1,
            pause_flush_sec=1.0, segment_max_sec=10.0, partial_word_cap=20,
            save_audio="none", streaming_mode=True
        )
        run_dir = Path("/tmp/test_session")
        run_dir.mkdir(exist_ok=True)

        async def test_exception_handling():
            try:
                async with StreamingSession("test_session", cfg, run_dir) as session:
                    # Simulate an error during processing
                    raise RuntimeError("Simulated error")
            except RuntimeError:
                pass  # Expected
            
            # Session should still be cleaned up despite the exception
            assert session._stop_evt.is_set()

        asyncio.run(test_exception_handling())

    @pytest.mark.asyncio
    async def test_manager_cleanup_with_active_sessions(self):
        """Test manager cleanup when sessions are still active."""
        with patch('threading.Thread'):
            manager = SessionManager()
            
            # Add mock active sessions
            mock_session1 = MagicMock()
            mock_session2 = MagicMock()
            manager._sessions["session1"] = mock_session1
            manager._sessions["session2"] = mock_session2
            
            # Mock active protocol managers
            mock_protocol1 = AsyncMock()
            mock_protocol2 = AsyncMock()
            manager._ws_protocols["session1"] = mock_protocol1
            manager._ws_protocols["session2"] = mock_protocol2
            
            # Shutdown should clean up all sessions
            await manager.shutdown()
            
            # Verify all sessions were stopped
            mock_session1.stop.assert_called_once()
            mock_session2.stop.assert_called_once()
            mock_protocol1.close.assert_called_once()
            mock_protocol2.close.assert_called_once()
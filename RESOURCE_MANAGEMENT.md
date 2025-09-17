# Resource Management Guidelines

This document outlines the resource management patterns and lifecycle guarantees for LoquiLex components.

## Overview

All resource-managing components in LoquiLex follow consistent patterns for cleanup to prevent memory leaks, dangling threads, and orphaned processes.

## Resource Management Patterns

### 1. Context Managers

All resource-managing classes implement async context managers (`__aenter__` and `__aexit__`) for guaranteed cleanup:

```python
# StreamingSession
async with StreamingSession(sid, config, run_dir) as session:
    # Use session
    pass
# Automatic cleanup when exiting context

# WSProtocolManager  
async with WSProtocolManager(sid) as protocol:
    # Use protocol manager
    pass
# Automatic cleanup of tasks and connections
```

### 2. Destructors

All resource-managing classes implement `__del__` methods as a safety net for cleanup:

```python
def __del__(self):
    """Destructor to ensure cleanup if not already done."""
    # Cancel asyncio tasks
    # Stop threads
    # Close connections
    # Release resources
```

### 3. Explicit Cleanup Methods

Components provide explicit cleanup methods for controlled resource release:

```python
# SessionManager
await session_manager.shutdown()

# BoundedQueue
queue.cleanup()

# WSProtocolManager
await protocol_manager.close()
```

## Resource Types and Cleanup Guarantees

### Threads

**Components**: `StreamingSession`, `Session`, `SessionManager`

**Resources**: Audio processing threads, CLI output reader threads, background processing threads

**Cleanup Guarantees**:
- All threads are created with `daemon=True` to prevent hanging the process
- Stop events are set before attempting joins
- Joins have timeouts (1-3 seconds) to prevent indefinite blocking
- Threads are properly joined in destructors and context managers

**Example**:
```python
# StreamingSession audio thread cleanup
def stop(self) -> None:
    self._stop_evt.set()
    if self._audio_thread:
        try:
            self._audio_thread.join(timeout=2.0)
        except Exception:
            pass
```

### AsyncIO Tasks

**Components**: `WSProtocolManager`

**Resources**: Heartbeat tasks, system heartbeat tasks, timeout monitoring tasks

**Cleanup Guarantees**:
- All tasks are properly cancelled in cleanup methods
- Tasks are awaited for completion where possible
- Task references are cleared after cancellation
- CancelledError exceptions are handled gracefully

**Example**:
```python
async def _stop_heartbeat(self) -> None:
    if self._hb_task:
        self._hb_task.cancel()
        try:
            await self._hb_task
        except asyncio.CancelledError:
            pass
        self._hb_task = None
```

### Subprocesses

**Components**: `Session`, `SessionManager`

**Resources**: CLI subprocess instances, download processes

**Cleanup Guarantees**:
- Process groups are used (`start_new_session=True`) for proper signal handling
- SIGTERM is sent first, followed by SIGKILL if needed
- Process termination has timeouts to prevent hanging
- Both `os.killpg()` and direct process methods are attempted

**Example**:
```python
def stop(self) -> None:
    if self.proc and self.proc.poll() is None:
        try:
            os.killpg(self.proc.pid, signal.SIGTERM)
            self.proc.wait(timeout=3)
        except subprocess.TimeoutExpired:
            os.killpg(self.proc.pid, signal.SIGKILL)
```

### WebSocket Connections

**Components**: `WSProtocolManager`

**Resources**: WebSocket connections, outbound message queues

**Cleanup Guarantees**:
- All connections are explicitly closed
- Connection sets are cleared after closing
- Outbound queues are cleaned up and cleared
- Close operations are wrapped in try/except for error handling

**Example**:
```python
# Close all connections
for ws in list(self.connections):
    try:
        await ws.close()
    except Exception:
        pass
self.connections.clear()
```

### File Handles

**Components**: `RollingTextFile`

**Resources**: File handles for atomic writes

**Cleanup Guarantees**:
- All file operations use context managers (`with open()`)
- Atomic writes prevent partial file states
- Temporary files are properly cleaned up via `os.replace()`
- No persistent file handles are maintained

**Example**:
```python
def _write_atomic(path: str, text: str) -> None:
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)
    os.replace(tmp, path)  # Atomic replacement
```

### Message Queues

**Components**: `BoundedQueue`, `ReplayBuffer`

**Resources**: In-memory queues, threading locks

**Cleanup Guarantees**:
- Queues are explicitly cleared
- Metrics are reset
- Threading locks are released
- References are cleared in destructors

**Example**:
```python
def cleanup(self) -> None:
    with self._lock:
        self._queue.clear()
        self.metrics = DropMetrics()
```

## Testing Resource Management

### Unit Tests

Resource management is tested with:

- Context manager behavior verification
- Destructor cleanup validation  
- Explicit cleanup method testing
- Exception handling during cleanup

### Integration Tests

- Memory leak detection using `tracemalloc`
- Thread count monitoring before/after operations
- Subprocess cleanup verification
- WebSocket connection cleanup testing

### CI Resource Monitoring

The test suite includes automatic resource monitoring:

```python
@pytest.fixture(autouse=True)
def resource_monitoring():
    # Monitor thread counts
    # Track memory usage with tracemalloc
    # Warn about significant resource growth
```

## Error Handling

All cleanup operations follow these patterns:

1. **Best Effort**: Cleanup attempts continue even if individual operations fail
2. **Exception Swallowing**: Cleanup methods catch and log exceptions without re-raising
3. **Multiple Strategies**: Fallback methods are used (e.g., `killpg()` then `terminate()`)
4. **Timeout Protection**: Blocking operations have timeouts to prevent hangs

## Lifecycle Guarantees

### Normal Operation

1. Resources are created on-demand
2. Resources are associated with their managing component
3. Resources are cleaned up when the component is stopped or closed
4. Cleanup is verified through explicit methods and context managers

### Error Conditions

1. Cleanup is attempted in exception handlers
2. Destructors provide safety net cleanup
3. Partial failures in cleanup don't prevent other cleanup operations
4. Resource leaks are logged but don't crash the application

### Shutdown Scenarios

1. **Graceful Shutdown**: All components are stopped in dependency order
2. **Abrupt Shutdown**: Destructors and signal handlers ensure cleanup
3. **Exception During Shutdown**: Best-effort cleanup continues for remaining resources

## Best Practices

### For Developers

1. Always implement context managers for resource-managing classes
2. Provide explicit cleanup methods with clear semantics
3. Implement destructors as a safety net
4. Use timeouts for all blocking cleanup operations
5. Test resource cleanup in both normal and error conditions

### For Users

1. Prefer context managers over manual resource management
2. Call explicit cleanup methods in finally blocks
3. Don't rely solely on garbage collection for cleanup
4. Monitor resource usage in production deployments

## Monitoring and Debugging

### Runtime Monitoring

- Enable resource warnings: `python -W default::ResourceWarning`
- Use tracemalloc for memory profiling
- Monitor thread counts in long-running processes
- Track subprocess lifecycle in logs

### Debugging Resource Leaks

1. Enable comprehensive logging for cleanup operations
2. Use memory profilers (tracemalloc, memory_profiler)
3. Monitor system resources (htop, ps, lsof)
4. Add debugging hooks in destructors and cleanup methods

## Configuration

Resource management behavior can be tuned via environment variables:

- `LX_WS_HEARTBEAT_SEC`: WebSocket heartbeat interval
- `LX_WS_HEARTBEAT_TIMEOUT_SEC`: WebSocket timeout
- `LX_MAX_CUDA_SESSIONS`: Maximum concurrent GPU sessions
- `LX_CLIENT_EVENT_BUFFER`: Client event buffer size

## Migration Guide

### Updating Existing Code

When adding resource management to existing components:

1. Add `__aenter__` and `__aexit__` methods
2. Add `__del__` method for safety net cleanup
3. Add explicit cleanup method (e.g., `close()`, `shutdown()`)
4. Update tests to verify cleanup behavior
5. Add resource monitoring to integration tests

### Breaking Changes

None of the resource management improvements introduce breaking changes to existing APIs. All changes are additive and backward compatible.
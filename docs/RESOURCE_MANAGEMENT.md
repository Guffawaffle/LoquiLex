# Resource Management

This document outlines expectations and contracts for starting, shutting down, and cleaning resources used by LoquiLex services.

## Shutdown Contract

- Threads: All background threads MUST check a shared stop flag and join within a bounded timeout during shutdown.
- Asyncio Tasks: Any background task created with an event loop should be either cancelled explicitly during shutdown or scheduled via a manager that ensures tasks are awaited before exit.
- Subprocesses: When spawning subprocesses from threads, prefer `start_new_session=True` on POSIX and `creationflags=CREATE_NEW_PROCESS_GROUP` on Windows; never use `preexec_fn` in a multithreaded parent. Track subprocess PIDs and ensure termination on shutdown.
- Queues and Buffers: Producers must drain or signal consumers to stop; consumers should handle empty queues gracefully and exit promptly when the stop flag is set.
- Finalizers: Best-effort finalizers (e.g., `weakref.finalize`) should avoid raising and should be idempotent.

## Minimal Checklist for Implementers

- Use a single `stop` flag shared across threads and event loops.
- Ensure `join(timeout=...)` is used for threads during shutdown with a logged warning if a thread fails to stop.
- Schedule coroutine broadcasts using the running event loop (e.g., `loop.create_task(...)`). Avoid creating new event loops from background threads.
- Avoid interpolating untrusted strings into shell commands; prefer passing as argv parameters.

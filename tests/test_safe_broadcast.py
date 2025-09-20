from loquilex.api.supervisor import SessionManager


# NOTE: This test intentionally avoids creating or querying an asyncio
# event loop. On Python 3.12 asyncio's event loop policy will raise a
# RuntimeError when `asyncio.get_event_loop()` is called and no loop has
# been set for the current thread. Previous automated edits reverted the
# defensive check and reintroduced `get_event_loop()` usage which caused
# spurious test failures in CI. Keep this test minimal: it only ensures
# that `_safe_broadcast` is a no-op when there is no running loop.
def test_safe_broadcast_no_loop_does_not_raise():
    mgr = SessionManager()
    # Should not raise even if no event loop is set
    mgr._safe_broadcast("dummy", {"type": "status", "stage": "test"})

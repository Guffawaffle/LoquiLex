import asyncio

from loquilex.api.supervisor import SessionManager


def test_safe_broadcast_no_loop_does_not_raise():
    mgr = SessionManager()
    # Ensure no running loop in this thread
    assert not asyncio.get_event_loop().is_running() if hasattr(asyncio, "get_event_loop") else True
    # Should not raise
    mgr._safe_broadcast("dummy", {"type": "status", "stage": "test"})

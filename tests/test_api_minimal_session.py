import pytest
import time

from loquilex.api.supervisor import SessionConfig, SessionManager


def test_minimal_session_lifecycle():
    cfg = SessionConfig(name="test", mt_enabled=False)
    manager = SessionManager()
    sid = manager.start_session(cfg)
    assert sid in manager._sessions
    # stop session and ensure cleanup
    manager.stop_session(sid)
    time.sleep(0.1)
    assert sid not in manager._sessions

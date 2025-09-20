import pytest
import time

from loquilex.api.supervisor import SessionConfig, SessionManager


def test_minimal_session_lifecycle():
    cfg = SessionConfig(
        name="test",
        asr_model_id="fake-small",
        mt_enabled=False,
        dest_lang="zh",
        device="cpu",
        vad=False,
        beams=1,
        pause_flush_sec=0.2,
        segment_max_sec=2.0,
        partial_word_cap=10,
        save_audio="no",
        streaming_mode=True,
    )
    manager = SessionManager()
    sid = manager.start_session(cfg)
    assert sid in manager._sessions
    # stop session and ensure cleanup
    manager.stop_session(sid)
    time.sleep(0.1)
    assert sid not in manager._sessions

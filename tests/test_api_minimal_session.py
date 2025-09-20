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
    # Poll for session cleanup with timeout to avoid flakiness
    timeout = 2.0  # seconds
    poll_interval = 0.05  # seconds
    start_time = time.time()
    while sid in manager._sessions and (time.time() - start_time) < timeout:
        time.sleep(poll_interval)
    assert (
        sid not in manager._sessions
    ), f"Session {sid} was not cleaned up within {timeout} seconds"

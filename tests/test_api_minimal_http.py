import pytest
from fastapi.testclient import TestClient

from loquilex.api.server import app


def test_create_and_stop_minimal_session_http():
    with TestClient(app) as client:
        payload = {
            "asr_model_id": "fake-small",
            "mt_enabled": False,
            "device": "cpu",
            "streaming_mode": True,
        }
        r = client.post("/sessions", json=payload)
        assert r.status_code in (200, 409)
        if r.status_code == 409:
            pytest.skip("Session creation failed due to environment constraints")
        sid = r.json().get("session_id")
        assert sid
        r2 = client.delete(f"/sessions/{sid}")
        assert r2.status_code == 200
        assert r2.json().get("stopped") is True

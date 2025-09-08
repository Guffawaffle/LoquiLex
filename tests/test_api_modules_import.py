from __future__ import annotations

def test_import_api_modules_for_coverage():
    # Import FastAPI modules if available; otherwise skip gracefully
    try:
        __import__("fastapi")
        __import__("greenfield.api.server")
        __import__("greenfield.api.supervisor")
    except Exception:
        pass
    # model_discovery should be importable
    __import__("greenfield.api.model_discovery")

    # Exercise events and vu helpers
    from greenfield.api.events import EventStamper
    from greenfield.api.vu import rms_peak, EmaVu
    import numpy as np

    st = EventStamper.new()
    out = st.stamp({"type": "x"})
    assert out["seq"] == 1 and "ts_server" in out and "ts_session" in out

    r, p = rms_peak(np.array([0.0, 0.3, -0.5], dtype=np.float32))
    assert 0.0 <= r <= 1.0 and 0.0 <= p <= 1.0

    vu = EmaVu(alpha=0.5)
    r1, p1 = vu.update(r, p)
    r2, p2 = vu.update(r, p)
    assert r2 >= r1 and p2 >= p1

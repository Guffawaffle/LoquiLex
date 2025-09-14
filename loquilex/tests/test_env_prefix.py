import os
from importlib import reload

from loquilex.config import defaults as d


def _reload_defaults(monkeypatch, env):
    for k in list(os.environ.keys()):
        if k.startswith("LX_"):
            monkeypatch.delenv(k, raising=False)
    for k, v in env.items():
        monkeypatch.setenv(k, v)
    reload(d)
    return d


def test_lx_only(monkeypatch):
    dd = _reload_defaults(
        monkeypatch, {"LX_ASR_BEAM": "5", "LX_ASR_NO_SPEECH": "0.9", "LX_ASR_VAD": "yes"}
    )
    assert dd.ASR.beam_size == 5
    assert abs(dd.ASR.no_speech_threshold - 0.9) < 1e-6
    assert dd.ASR.vad_filter is True

import os
import warnings
from importlib import reload
from loquilex.config import defaults as d


def _reload_defaults(monkeypatch, env):
    # clear and set env
    for k in list(os.environ.keys()):
        if k.startswith(("LX_", "GF_")):
            monkeypatch.delenv(k, raising=False)
    for k, v in env.items():
        monkeypatch.setenv(k, v)
    # reload module to re-evaluate dataclasses
    reload(d)
    return d


def test_gf_only_triggers_deprecation(monkeypatch):
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always", DeprecationWarning)
        dd = _reload_defaults(monkeypatch, {"GF_ASR_LANGUAGE": "en-US"})
        assert dd.ASR.language == "en-US"
        assert any(isinstance(x.message, DeprecationWarning) for x in w), "expected deprecation"


def test_lx_wins_over_gf(monkeypatch):
    dd = _reload_defaults(monkeypatch, {"GF_ASR_LANGUAGE": "en-GB", "LX_ASR_LANGUAGE": "en"})
    assert dd.ASR.language == "en"


def test_type_coercion(monkeypatch):
    dd = _reload_defaults(
        monkeypatch, {"LX_ASR_BEAM": "5", "LX_ASR_NO_SPEECH": "0.9", "LX_ASR_VAD": "yes"}
    )
    assert dd.ASR.beam_size == 5
    assert abs(dd.ASR.no_speech_threshold - 0.9) < 1e-6
    assert dd.ASR.vad_filter is True
    dd = _reload_defaults(
        monkeypatch, {"GF_ASR_BEAM": "7", "GF_ASR_NO_SPEECH": "0.8", "GF_ASR_VAD": "no"}
    )
    assert dd.ASR.beam_size == 7
    assert abs(dd.ASR.no_speech_threshold - 0.8) < 1e-6
    assert dd.ASR.vad_filter is False

from __future__ import annotations

import os
import importlib


def test_env_overrides(monkeypatch):
    monkeypatch.setenv("GF_MAX_LINES", "123")
    monkeypatch.setenv("GF_PARTIAL_WORD_CAP", "9")
    monkeypatch.setenv("GF_SAVE_AUDIO", "flac")
    monkeypatch.setenv("GF_SAVE_AUDIO_PATH", "loquilex/out/session.flac")
    # Reload module to pick env
    mod = importlib.import_module("greenfield.config.defaults")
    importlib.reload(mod)
    assert mod.RT.max_lines == 123
    assert mod.RT.partial_word_cap == 9
    assert mod.RT.save_audio == "flac"
    assert mod.RT.save_audio_path.endswith("session.flac")
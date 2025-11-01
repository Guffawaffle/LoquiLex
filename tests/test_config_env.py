from __future__ import annotations

import importlib
from pathlib import Path


def test_env_overrides(monkeypatch):
    monkeypatch.setenv("LX_MAX_LINES", "123")
    monkeypatch.setenv("LX_PARTIAL_WORD_CAP", "9")
    monkeypatch.setenv("LX_SAVE_AUDIO", "flac")
    monkeypatch.setenv("LX_SAVE_AUDIO_PATH", "loquilex/out/session.flac")
    # Reload module to pick env
    from loquilex.config import defaults as mod

    importlib.reload(mod)
    assert mod.RT.max_lines == 123
    assert mod.RT.partial_word_cap == 9
    assert mod.RT.save_audio == "flac"
    assert mod.RT.save_audio_path.endswith("session.flac")


def test_out_dir_is_absolute():
    """Test that out_dir default is always an absolute path."""
    from loquilex.config import defaults as mod

    # RT.out_dir should be absolute even with default relative value
    assert Path(mod.RT.out_dir).is_absolute(), f"out_dir should be absolute, got: {mod.RT.out_dir}"


def test_out_dir_custom_absolute(monkeypatch):
    """Test that custom LX_OUT_DIR is resolved to absolute path."""
    monkeypatch.setenv("LX_OUT_DIR", "/tmp/custom-out")
    from loquilex.config import defaults as mod

    importlib.reload(mod)
    assert Path(mod.RT.out_dir).is_absolute()
    assert mod.RT.out_dir == "/tmp/custom-out"


def test_out_dir_custom_relative(monkeypatch):
    """Test that relative LX_OUT_DIR is resolved to absolute path."""
    monkeypatch.setenv("LX_OUT_DIR", "relative/path")
    from loquilex.config import defaults as mod

    importlib.reload(mod)
    assert Path(mod.RT.out_dir).is_absolute()
    # Should resolve relative to current working directory
    expected = str(Path.cwd() / "relative/path")
    assert mod.RT.out_dir == expected


def test_out_dir_legacy_env_var(monkeypatch):
    """Test that legacy LLX_OUT_DIR is supported."""
    monkeypatch.delenv("LX_OUT_DIR", raising=False)
    monkeypatch.setenv("LLX_OUT_DIR", "/tmp/legacy-out")
    from loquilex.config import defaults as mod

    importlib.reload(mod)
    assert Path(mod.RT.out_dir).is_absolute()
    assert mod.RT.out_dir == "/tmp/legacy-out"


def test_out_dir_prefers_lx_over_llx(monkeypatch):
    """Test that LX_OUT_DIR takes precedence over LLX_OUT_DIR."""
    monkeypatch.setenv("LX_OUT_DIR", "/tmp/new-out")
    monkeypatch.setenv("LLX_OUT_DIR", "/tmp/legacy-out")
    from loquilex.config import defaults as mod

    importlib.reload(mod)
    assert mod.RT.out_dir == "/tmp/new-out"

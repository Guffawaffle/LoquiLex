"""Tests for loquilex.config.paths module."""

from __future__ import annotations

from pathlib import Path


def test_resolve_out_dir_default_is_absolute(monkeypatch):
    """Test that resolve_out_dir returns absolute path with default."""
    # Clear any existing env vars
    monkeypatch.delenv("LX_OUT_DIR", raising=False)
    monkeypatch.delenv("LLX_OUT_DIR", raising=False)

    from loquilex.config.paths import resolve_out_dir

    result = resolve_out_dir()
    assert result.is_absolute(), f"resolve_out_dir should return absolute path, got: {result}"


def test_resolve_out_dir_with_absolute_env(monkeypatch):
    """Test that resolve_out_dir handles absolute path from env."""
    monkeypatch.setenv("LX_OUT_DIR", "/tmp/test-out")

    from loquilex.config.paths import resolve_out_dir

    result = resolve_out_dir()
    assert result.is_absolute()
    assert str(result) == "/tmp/test-out"


def test_resolve_out_dir_with_relative_env(monkeypatch):
    """Test that resolve_out_dir resolves relative path from env."""
    monkeypatch.setenv("LX_OUT_DIR", "relative/test")

    from loquilex.config.paths import resolve_out_dir

    result = resolve_out_dir()
    assert result.is_absolute()
    # Should resolve relative to current working directory
    expected = Path.cwd() / "relative/test"
    assert result == expected


def test_resolve_out_dir_with_tilde(monkeypatch):
    """Test that resolve_out_dir expands ~ in path."""
    monkeypatch.setenv("LX_OUT_DIR", "~/my-loquilex-out")

    from loquilex.config.paths import resolve_out_dir

    result = resolve_out_dir()
    assert result.is_absolute()
    assert "~" not in str(result)
    # Should expand to user home directory
    assert str(result).startswith(str(Path.home()))


def test_resolve_out_dir_legacy_env_var(monkeypatch):
    """Test that resolve_out_dir falls back to LLX_OUT_DIR."""
    monkeypatch.delenv("LX_OUT_DIR", raising=False)
    monkeypatch.setenv("LLX_OUT_DIR", "/tmp/legacy-out")

    from loquilex.config.paths import resolve_out_dir

    result = resolve_out_dir()
    assert result.is_absolute()
    assert str(result) == "/tmp/legacy-out"


def test_resolve_out_dir_prefers_lx_over_llx(monkeypatch):
    """Test that LX_OUT_DIR takes precedence over LLX_OUT_DIR."""
    monkeypatch.setenv("LX_OUT_DIR", "/tmp/new-out")
    monkeypatch.setenv("LLX_OUT_DIR", "/tmp/legacy-out")

    from loquilex.config.paths import resolve_out_dir

    result = resolve_out_dir()
    assert str(result) == "/tmp/new-out"

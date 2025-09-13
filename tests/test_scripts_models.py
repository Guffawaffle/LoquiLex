"""
Tests for scripts.models helper functions.
"""

from __future__ import annotations

import warnings
from pathlib import Path


from scripts.models import prefetch_asr, should_skip_prefetch


class TestShouldSkipPrefetch:
    """Test should_skip_prefetch function behavior."""

    def test_skip_when_lx_env_set(self, monkeypatch):
        monkeypatch.setenv("LX_SKIP_MODEL_PREFETCH", "1")
        assert should_skip_prefetch() is True

    def test_skip_when_legacy_env_set(self, monkeypatch):
        # Clear warning state
        import scripts.env

        scripts.env._warned.clear()

        monkeypatch.delenv("LX_SKIP_MODEL_PREFETCH", raising=False)
        monkeypatch.setenv("GF_SKIP_MODEL_PREFETCH", "true")

        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always", DeprecationWarning)
            result = should_skip_prefetch()

        assert result is True
        assert len(w) == 1
        assert "GF_SKIP_MODEL_PREFETCH" in str(w[0].message)

    def test_no_skip_when_unset(self, monkeypatch):
        monkeypatch.delenv("LX_SKIP_MODEL_PREFETCH", raising=False)
        monkeypatch.delenv("GF_SKIP_MODEL_PREFETCH", raising=False)
        assert should_skip_prefetch() is False

    def test_no_skip_when_false(self, monkeypatch):
        monkeypatch.setenv("LX_SKIP_MODEL_PREFETCH", "0")
        assert should_skip_prefetch() is False

    def test_lx_wins_over_legacy(self, monkeypatch):
        monkeypatch.setenv("LX_SKIP_MODEL_PREFETCH", "0")
        monkeypatch.setenv("GF_SKIP_MODEL_PREFETCH", "1")

        # Should not warn since LX_ var takes precedence
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always", DeprecationWarning)
            result = should_skip_prefetch()

        assert result is False
        assert len(w) == 0


class TestPrefetchAsr:
    """Test prefetch_asr function behavior."""

    def test_skip_when_flag_set(self, monkeypatch, capsys):
        monkeypatch.setenv("LX_SKIP_MODEL_PREFETCH", "1")

        prefetch_asr("tiny.en", Path("/tmp/models"))

        captured = capsys.readouterr()
        assert "LX_SKIP_MODEL_PREFETCH set" in captured.out

    def test_stub_message_when_not_skipped(self, monkeypatch, capsys):
        monkeypatch.delenv("LX_SKIP_MODEL_PREFETCH", raising=False)

        prefetch_asr("tiny.en", Path("/tmp/models"))

        captured = capsys.readouterr()
        assert "Would prefetch ASR model 'tiny.en'" in captured.out
        assert "/tmp/models" in captured.out
        assert "No action taken" in captured.out

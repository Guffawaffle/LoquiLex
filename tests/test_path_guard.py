from __future__ import annotations

import pytest
from pathlib import Path

from loquilex.security import PathGuard, PathSecurityError


def test_ensure_dir_creates_relative(tmp_path: Path):
    guard = PathGuard({"root": tmp_path})
    target = guard.resolve("root", "sessions")
    guard.ensure_dir(target)
    assert target == tmp_path / "sessions"
    assert target.exists()


def test_ensure_dir_rejects_escape(tmp_path: Path):
    guard = PathGuard({"root": tmp_path})
    outside = tmp_path.parent / "other"
    with pytest.raises(PathSecurityError):
        guard.ensure_dir(outside)


def test_open_write_invalid_filename(tmp_path: Path):
    guard = PathGuard({"root": tmp_path})
    with pytest.raises(PathSecurityError):
        p = guard.resolve("root", "../")
        if p.exists():
            p.unlink()

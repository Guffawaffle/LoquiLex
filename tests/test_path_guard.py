from __future__ import annotations

import pytest

from loquilex.security import PathGuard, PathSecurityError


def test_ensure_dir_creates_relative(tmp_path):
    guard = PathGuard([tmp_path])
    safe_dir = guard.ensure_dir("sessions", allow_relative=True, create=True)
    assert safe_dir == tmp_path / "sessions"
    assert safe_dir.exists()


def test_ensure_dir_rejects_escape(tmp_path):
    guard = PathGuard([tmp_path])
    outside = tmp_path.parent / "other"
    with pytest.raises(PathSecurityError):
        guard.ensure_dir(outside, allow_relative=False)


def test_ensure_file_rejects_empty_name(tmp_path):
    guard = PathGuard([tmp_path])
    with pytest.raises(PathSecurityError):
        guard.ensure_file(tmp_path, "../", allow_fallback=False)

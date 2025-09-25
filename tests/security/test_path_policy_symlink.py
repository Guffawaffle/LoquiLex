# -*- coding: utf-8 -*-
"""
Symlink/escape and containment tests for PathPolicy.resolve_under
These run on Unix-like CI. On Windows, test is skipped; see Windows doc addendum.
"""
import os
import sys
import pathlib
import pytest

# Adjust import paths to match your package layout.
# from loquilex.security.path_policy import PathPolicy, PathPolicyConfig, PathSecurityError

pytestmark = pytest.mark.skipif(
    sys.platform.startswith("win"),
    reason="Symlink tests are Unix-focused; Windows handled in docs.",
)


@pytest.fixture()
def sandbox(tmp_path: pathlib.Path):
    root = tmp_path / "allowed"
    root.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    real_file = outside / "secrets.txt"
    real_file.write_text("nope")
    return root, outside, real_file


def test_symlink_escape_rejected(sandbox):
    root, outside, real_file = sandbox
    # Create a symlink *inside* allowed root pointing *outside*
    evil_link = root / "link_out"
    os.symlink(str(outside), str(evil_link))

    # Candidate path attempts to walk through the symlink
    candidate = evil_link / "secrets.txt"

    policy = PathPolicy(config=PathPolicyConfig(allow_follow_symlinks=False))
    with pytest.raises(PathSecurityError):
        policy.resolve_under(root, candidate)


def test_normal_file_allowed(sandbox):
    root, _, _ = sandbox
    safe_dir = root / "safe"
    safe_dir.mkdir()
    safe_file = safe_dir / "ok.txt"
    safe_file.write_text("ok")

    policy = PathPolicy(config=PathPolicyConfig(allow_follow_symlinks=False))
    resolved = policy.resolve_under(root, safe_file.name, base_dir=safe_dir)
    assert resolved.exists()
    assert resolved.read_text() == "ok"


def test_commonpath_containment_even_if_following_symlinks(sandbox):
    root, outside, real_file = sandbox
    # This variant demonstrates the expected behavior if allow_follow_symlinks=True:
    # containment must still be enforced after resolution.
    evil_link = root / "link_out"
    os.symlink(str(outside), str(evil_link))
    candidate = evil_link / "secrets.txt"

    policy = PathPolicy(config=PathPolicyConfig(allow_follow_symlinks=True))
    # Expect rejection because resolved path would escape allowed root
    with pytest.raises(PathSecurityError):
        policy.resolve_under(root, candidate)

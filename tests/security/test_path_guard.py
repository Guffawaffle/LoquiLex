import pytest
from pathlib import Path

from loquilex.security.path_guard import PathGuard, PathSecurityError


@pytest.fixture()
def roots(tmp_path: Path):
    storage = tmp_path / "storage"
    export = tmp_path / "export"
    storage.mkdir(parents=True, exist_ok=True)
    export.mkdir(parents=True, exist_ok=True)
    guard = PathGuard([storage, export], default_root=storage)
    return guard, storage, export


@pytest.mark.parametrize(
    "fragment",
    [
        "../..",
        "/abs",
        "./././../../",
        "sub/..//..//",
        "dir/../../..",
    ],
)
def test_resolve_relative_rejects_traversal(roots, fragment: str):
    guard, storage, _ = roots
    with pytest.raises(PathSecurityError):
        guard.resolve_relative(storage, fragment)


@pytest.mark.parametrize(
    "name,suffix",
    [
        ("file", ".txt"),
        ("sub-file", ".vtt"),
        ("nested_ok", ".json"),
        ("sub__name", ".log"),
    ],
)
def test_ensure_file_accepts_simple_names(roots, name: str, suffix: str):
    guard, storage, _ = roots
    p = guard.ensure_file(storage, name, suffix=suffix, create_parents=True)
    assert p.parent == storage
    expected = f"{guard.sanitise_component(name)}{suffix}"
    assert p.name == expected


@pytest.mark.parametrize(
    "name",
    [
        "../etc/passwd",
        "dir/%2e%2e",
        "dir\\..\\file",
        "..\\",
        "dir/..",
        ".\\.\\..\\..",
    ],
)
def test_ensure_file_sanitizes_and_stays_in_root(roots, name: str):
    guard, storage, _ = roots
    # Even with traversal chars, sanitisation collapses to safe stem in storage
    p = guard.ensure_file(storage, name, suffix=".txt", create_parents=True)
    assert p.parent == storage
    assert p.suffix == ".txt"
    assert guard._is_within_roots(p)


@pytest.mark.parametrize(
    "fragment",
    [
        "dir/%2e%2e",  # literal string, not decoded; stays inside base
        "dir\\..\\file",  # backslashes are not separators on POSIX
        "dir/..",  # reduces to base, still inside allowed root
    ],
)
def test_resolve_relative_allows_non_escaping_cases(roots, fragment: str):
    guard, storage, _ = roots
    p = guard.resolve_relative(storage, fragment)
    assert guard._is_within_roots(p)

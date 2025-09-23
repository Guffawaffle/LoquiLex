import pytest
from pathlib import Path

from loquilex.security.path_guard import PathGuard, PathSecurityError


@pytest.fixture()
def roots(tmp_path: Path):
    storage = tmp_path / "storage"
    export = tmp_path / "export"
    storage.mkdir(parents=True, exist_ok=True)
    export.mkdir(parents=True, exist_ok=True)
    guard = PathGuard({"storage": storage.resolve(), "export": export.resolve()})
    return guard, storage.resolve(), export.resolve()


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
        # We attempt resolution under the storage root
        guard.resolve("storage", fragment)


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
    p = guard.resolve("storage", f"{name}{suffix}")
    guard.ensure_dir(p.parent)
    assert p.parent == storage
    assert p.name.endswith(suffix)


@pytest.mark.parametrize(
    "name",
    [
        "../etc/passwd",
        "dir/%2e%2e",
        "dir\\..\\file",
        "..\\",
        ".\\.\\..\\..",
    ],
)
def test_rejects_traversalish_filenames(roots, name: str):
    guard, storage, _ = roots
    with pytest.raises(PathSecurityError):
        guard.resolve("storage", f"{name}.txt")


@pytest.mark.parametrize(
    "fragment",
    [
        "dir/..",  # reduces to base, still inside allowed root
    ],
)
def test_resolve_allows_non_escaping_cases(roots, fragment: str):
    guard, storage, _ = roots
    p = guard.resolve("storage", fragment)
    assert PathGuard._is_within_root(storage, p)

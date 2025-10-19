import os
import time
from pathlib import Path

from loquilex.storage.retention import RetentionPolicy, enforce_retention


def write_file(p: Path, size_bytes: int):
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, "wb") as f:
        f.write(b"x" * size_bytes)


def test_ttl_removes_old(tmp_path: Path):
    root = tmp_path / "out"
    root.mkdir()

    old = root / "old.txt"
    new = root / "new.txt"
    write_file(old, 100)
    write_file(new, 200)

    # Backdate old file by 2 hours
    now = time.time()
    os.utime(old, (now - 2 * 3600, now - 2 * 3600))

    policy = RetentionPolicy(ttl_seconds=3600, max_bytes=None)
    deleted, remaining = enforce_retention(root, policy)

    assert deleted == 1
    # remaining should reflect new file only
    assert remaining == 200


def test_size_cap_deletes_oldest(tmp_path: Path):
    root = tmp_path / "out2"
    root.mkdir()

    f1 = root / "f1.bin"
    f2 = root / "f2.bin"
    f3 = root / "f3.bin"

    # Create files 2MB each
    mb = 1024 * 1024
    write_file(f1, 2 * mb)
    time.sleep(0.01)
    write_file(f2, 2 * mb)
    time.sleep(0.01)
    write_file(f3, 2 * mb)

    # Cap at 4MB -> should remove oldest (f1) and leave f2+f3 = 4MB
    policy = RetentionPolicy(ttl_seconds=9999999, max_bytes=4 * mb)
    deleted, remaining = enforce_retention(root, policy)

    assert deleted >= 1
    assert remaining <= 4 * mb

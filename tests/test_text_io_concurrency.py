from __future__ import annotations

import threading
from pathlib import Path

from loquilex.output.text_io import RollingTextFile


def test_rolling_text_concurrent_appends_and_rewrites(tmp_path: Path):
    p = tmp_path / "out.txt"
    r = RollingTextFile(str(p), max_lines=50)
    r.reset()

    stop = threading.Event()

    def appender():
        i = 0
        while not stop.is_set() and i < 200:
            r.append_final_line(f"L{i}")
            i += 1

    def rewriter():
        j = 0
        while not stop.is_set() and j < 200:
            r.rewrite_current_line(f"draft {j}")
            j += 1

    t1 = threading.Thread(target=appender)
    t2 = threading.Thread(target=rewriter)
    t1.start(); t2.start()
    t1.join(); t2.join()
    stop.set()

    content = p.read_text(encoding="utf-8")
    # Must end with newline and contain at most max_lines + 1 draft line
    assert content.endswith("\n")
    # Count non-empty lines
    lines = [ln for ln in content.splitlines() if ln]
    assert 1 <= len(lines) <= 51
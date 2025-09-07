from __future__ import annotations

import os

from greenfield.output.text_io import RollingTextFile


def test_rewrite_keeps_single_last_line(tmp_path):
    p = tmp_path / "live.partial.en.txt"
    r = RollingTextFile(str(p))
    r.reset()
    r.rewrite_current_line("hello")
    r.rewrite_current_line("hello world")
    r.rewrite_current_line("final draft")
    txt = p.read_text(encoding="utf-8")
    # Should contain only the latest draft + trailing newline
    assert txt == "final draft\n"


def test_append_enforces_max_lines(tmp_path):
    p = tmp_path / "live.final.en.txt"
    r = RollingTextFile(str(p), max_lines=3)
    r.reset()
    for i in range(1, 7):
        r.append_final_line(f"line {i}")
    txt = p.read_text(encoding="utf-8")
    lines = [ln for ln in txt.split("\n") if ln]
    # Kept last 3 lines only
    assert lines == ["line 4", "line 5", "line 6"]


def test_utf8_and_trailing_newline(tmp_path):
    p = tmp_path / "live.final.zh.txt"
    r = RollingTextFile(str(p), max_lines=2)
    r.reset()
    r.append_final_line("你好，世界")
    r.append_final_line("再见")
    txt = p.read_text(encoding="utf-8")
    assert txt.endswith("\n")
    # Exactly two lines (plus trailing blank from split)
    parts = txt.split("\n")
    assert parts[:-1] == ["你好，世界", "再见"]

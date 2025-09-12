from __future__ import annotations

from pathlib import Path

from loquilex.output.text_io import RollingTextFile
from loquilex.output.vtt import append_vtt_cue
from loquilex.output.srt import append_srt_cue


def test_partial_and_final_files(tmp_path: Path):
    p_en = RollingTextFile(str(tmp_path / "live.partial.en.txt"))
    p_zh = RollingTextFile(str(tmp_path / "live.partial.zh.txt"))
    f_en = RollingTextFile(str(tmp_path / "live.final.en.txt"), max_lines=2)
    f_zh = RollingTextFile(str(tmp_path / "live.final.zh.txt"), max_lines=2)
    for w in (p_en, p_zh, f_en, f_zh):
        w.reset()

    # Partials rewritten
    p_en.rewrite_current_line("hello")
    p_zh.rewrite_current_line("你好")
    p_en.rewrite_current_line("hello world")
    assert (tmp_path / "live.partial.en.txt").read_text(encoding="utf-8").strip() == "hello world"

    # Finalization clears partials and appends finals with max_lines enforced
    p_en.rewrite_current_line("")
    p_zh.rewrite_current_line("")
    for i in range(3):
        f_en.append_final_line(f"en {i}")
        f_zh.append_final_line(f"zh {i}")
    en_lines = [
        ln for ln in (tmp_path / "live.final.en.txt").read_text(encoding="utf-8").splitlines() if ln
    ]
    zh_lines = [
        ln for ln in (tmp_path / "live.final.zh.txt").read_text(encoding="utf-8").splitlines() if ln
    ]
    assert en_lines == ["en 1", "en 2"]
    assert zh_lines == ["zh 1", "zh 2"]


def test_append_vtt_and_srt(tmp_path: Path):
    vtt = tmp_path / "out.vtt"
    srt = tmp_path / "out.srt"

    # Overlapping inputs; append ensures monotonic
    append_vtt_cue(str(vtt), 0.0, 1.0, "a")
    append_vtt_cue(str(vtt), 0.5, 1.2, "b")
    append_vtt_cue(str(vtt), 1.2, 1.2, "c")
    vtt_text = vtt.read_text(encoding="utf-8")
    assert vtt_text.startswith("WEBVTT\n\n")
    lines = [ln for ln in vtt_text.splitlines() if "-->" in ln]
    assert lines == sorted(lines)

    # SRT index increments across appends and monotonic timestamps
    idx = append_srt_cue(str(srt), None, 0.0, 1.0, "one")
    assert idx == 1
    idx = append_srt_cue(str(srt), None, 0.5, 1.3, "two")
    assert idx == 2
    idx = append_srt_cue(str(srt), None, 1.3, 1.3, "three")
    assert idx == 3
    srt_text = srt.read_text(encoding="utf-8")
    blocks = [b for b in srt_text.strip().split("\n\n") if b]
    assert blocks[0].startswith("1\n")
    assert blocks[1].startswith("2\n")
    assert blocks[2].startswith("3\n")

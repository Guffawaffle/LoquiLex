from __future__ import annotations

from pathlib import Path

from loquilex.output.vtt import append_vtt_cue
from loquilex.output.srt import append_srt_cue


def test_vtt_srt_append_order(tmp_path: Path):
    vtt = tmp_path / "t.vtt"
    srt = tmp_path / "t.srt"

    append_vtt_cue(str(vtt), 0.0, 1.0, "one")
    append_vtt_cue(str(vtt), 0.9, 1.1, "two")
    append_vtt_cue(str(vtt), 1.1, 1.1, "three")
    lines = [ln for ln in vtt.read_text(encoding="utf-8").splitlines() if "-->" in ln]
    assert lines == sorted(lines)

    idx = append_srt_cue(str(srt), None, 0.0, 0.5, "a")
    assert idx == 1
    idx = append_srt_cue(str(srt), None, 0.4, 0.6, "b")
    assert idx == 2
    idx = append_srt_cue(str(srt), None, 0.6, 0.6, "c")
    assert idx == 3
    blocks = [b for b in srt.read_text(encoding="utf-8").strip().split("\n\n") if b]
    assert (
        blocks[0].startswith("1\n") and blocks[1].startswith("2\n") and blocks[2].startswith("3\n")
    )

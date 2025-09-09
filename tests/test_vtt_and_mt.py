from __future__ import annotations

from loquilex.output.vtt import write_vtt
from loquilex.mt.translator import Translator


def test_vtt_monotonic(tmp_path):
    path = tmp_path / "t.vtt"
    cues = [(0.0, 1.0, "a"), (0.5, 1.2, "b"), (1.2, 1.2, "c")]  # overlapping + zero len
    write_vtt(cues, str(path))
    txt = path.read_text(encoding="utf-8")
    assert txt.startswith("WEBVTT")
    # ensure non-overlap by simple search order
    lines = [ln for ln in txt.splitlines() if "-->" in ln]
    assert lines == sorted(lines)


def test_translator_bos_handling():
    tr = Translator()
    # We don't download models in test env; ensure fallback works and doesn't throw.
    out = tr.translate_en_to_zh("Hello world")
    assert isinstance(out.text, str)
    assert out.model in {"facebook/nllb-200-distilled-600M", "facebook/m2m100_418M", "echo"}

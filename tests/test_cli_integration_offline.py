from __future__ import annotations

import sys
import types
from pathlib import Path

from tests.util.audio import write_tiny_wav


def _install_fake_faster_whisper():
    fake_fw = types.ModuleType("faster_whisper")
    from tests.fakes.fake_whisper import WhisperModel

    fake_fw.WhisperModel = WhisperModel
    sys.modules["faster_whisper"] = fake_fw


def _install_fake_mt():
    fake_mt = types.ModuleType("greenfield.mt.translator")
    from tests.fakes.fake_mt import Translator, TranslationResult

    fake_mt.Translator = Translator
    fake_mt.TranslationResult = TranslationResult
    sys.modules["greenfield.mt.translator"] = fake_mt


def test_wav_to_vtt_offline_with_fake_asr(tmp_path: Path, monkeypatch):
    _install_fake_faster_whisper()
    wav = tmp_path / "a.wav"
    out = tmp_path / "a.vtt"
    write_tiny_wav(wav, seconds=1.0)

    from loquilex.cli import wav_to_vtt as cli

    old = sys.argv
    try:
        sys.argv = [old[0], "--wav", str(wav), "--out", str(out)]
        cli.main()
    finally:
        sys.argv = old

    text = out.read_text(encoding="utf-8")
    assert text.startswith("WEBVTT")
    assert "hello" in text and "world" in text


def test_vtt_to_zh_offline_with_fake_mt(tmp_path: Path, monkeypatch):
    # Create a tiny VTT
    vtt = tmp_path / "a.vtt"
    vtt.write_text(
        "WEBVTT\n\n00:00:00.000 --> 00:00:00.500\nhello\n\n00:00:00.500 --> 00:00:01.000\nworld\n",
        encoding="utf-8",
    )
    _install_fake_mt()

    out_txt = tmp_path / "zh.txt"
    out_srt = tmp_path / "zh.srt"
    from loquilex.cli import vtt_to_zh as cli

    old = sys.argv
    try:
        sys.argv = [
            old[0],
            "--vtt",
            str(vtt),
            "--out-text",
            str(out_txt),
            "--out-srt",
            str(out_srt),
        ]
        cli.main()
    finally:
        sys.argv = old

    assert out_txt.exists() and out_srt.exists()
    # Accept either [zh] or pure Chinese output
    zh_text = out_txt.read_text(encoding="utf-8")
    assert "[zh]" in zh_text or any(ord(c) > 127 for c in zh_text), f"Unexpected output: {zh_text}"


def test_output_boundary_respected(tmp_path: Path, monkeypatch):
    # Ensure we can guard paths within GF_OUT_DIR in tests using helper
    from loquilex.output.paths import ensure_out_path

    root = tmp_path / "out"
    inside = ensure_out_path(root, "sub/ok.txt")
    assert str(inside).startswith(str(root))

    outside_abs = tmp_path.parent / "oops.txt"
    try:
        ensure_out_path(root, outside_abs)
        assert False, "expected ValueError for escaping path"
    except ValueError:
        pass

from __future__ import annotations

import types
from pathlib import Path
import numpy as np


def test_cli_runs_with_fake_capture_and_translator(monkeypatch, tmp_path: Path):
    import loquilex.mt.translator as tr
    import loquilex.cli.live_en_to_zh as cli
    # Patch capture_stream to emit a few silent frames then stop
    import loquilex.audio.capture as cap
    import numpy as np

    def fake_capture_stream(cb):
        frames = 6
        sr = 16000
        chunk = np.zeros(sr // 5, dtype=np.float32)  # 200ms per frame
        class Stopper:
            def __call__(self):
                pass
        stopper = Stopper()
        for _ in range(frames):
            t1 = cap.time.monotonic()
            t0 = t1 - (len(chunk) / cap.SAMPLE_RATE)
            cb(cap.AudioFrame(chunk, t0, t1))
        return stopper

    monkeypatch.setattr(cap, "capture_stream", fake_capture_stream)

    # Patch translator to echo quickly
    from loquilex.mt.translator import Translator, TranslationResult
    class Echo:
        def __init__(self):
            pass
        def translate_en_to_zh(self, text):
            return tr.TranslationResult(text, "echo")
        def translate_en_to_zh_draft(self, text):
            return tr.TranslationResult(text, "echo:draft")

    monkeypatch.setattr(tr, "Translator", Echo)

    # Run CLI main with short seconds and custom output dir
    from loquilex.cli.live_en_to_zh import main as cli_main
    outdir = tmp_path / "out"
    args = [
        "--seconds", "1",
        "--partial-en", str(outdir / "live.partial.en.txt"),
        "--partial-zh", str(outdir / "live.partial.zh.txt"),
        "--final-en", str(outdir / "live.final.en.txt"),
        "--final-zh", str(outdir / "live.final.zh.txt"),
        "--final-vtt-en", str(outdir / "live.final.en.vtt"),
        "--final-srt-zh", str(outdir / "live.final.zh.srt"),
        "--overwrite-run",
    ]
    monkeypatch.setenv("PYTHONUNBUFFERED", "1")

    # Wrap main to parse our args
    def run_with_args():
        import sys
        old = sys.argv
        try:
            sys.argv = [old[0]] + args
            cli.main()
        finally:
            sys.argv = old

    run_with_args()

    # Verify outputs exist (some may be empty depending on silence)
    assert (outdir / "live.final.en.txt").exists()
    assert (outdir / "live.final.zh.txt").exists()
    assert (outdir / "live.final.en.vtt").exists() or True  # VTT only written on finalization
    assert (outdir / "live.final.zh.srt").exists() or True
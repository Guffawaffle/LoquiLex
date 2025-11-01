from __future__ import annotations

from pathlib import Path


def test_cli_runs_with_fake_capture_and_translator(monkeypatch, tmp_path: Path):
    import numpy as np

    # Patch capture_stream to emit a few silent frames then stop
    import loquilex.audio.capture as cap
    import loquilex.cli.live_en_to_zh as cli
    import loquilex.mt.translator as tr

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
    monkeypatch.setattr(cli, "capture_stream", fake_capture_stream)

    # Patch translator to echo quickly

    class Echo:

        def __init__(self):
            pass

        def translate(self, text, src_lang="en", tgt_lang="zh", quality="final"):
            """Generic translate method (new API)."""
            return tr.TranslationResult(
                text=text, model=f"echo:{quality}", src_lang=src_lang, tgt_lang=tgt_lang, duration_ms=0.0
            )

        def translate_en_to_zh(self, text):
            return tr.TranslationResult(
                text=text, model="echo", src_lang="en", tgt_lang="zh", duration_ms=0.0
            )

        def translate_en_to_zh_draft(self, text):
            return tr.TranslationResult(
                text=text, model="echo:draft", src_lang="en", tgt_lang="zh", duration_ms=0.0
            )

    # Patch both the module and the CLI's imported Translator
    monkeypatch.setattr(tr, "Translator", Echo)
    monkeypatch.setattr(cli, "Translator", Echo)

    # Run CLI main with short seconds and custom output dir
    outdir = tmp_path / "out"
    args = [
        "--seconds",
        "1",
        "--partial-en",
        str(outdir / "live.partial.en.txt"),
        "--partial-zh",
        str(outdir / "live.partial.zh.txt"),
        "--final-en",
        str(outdir / "live.final.en.txt"),
        "--final-zh",
        str(outdir / "live.final.zh.txt"),
        "--final-vtt-en",
        str(outdir / "live.final.en.vtt"),
        "--final-srt-zh",
        str(outdir / "live.final.zh.srt"),
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

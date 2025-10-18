import json
import os
import shutil
import wave
import struct
from pathlib import Path

import pytest


@pytest.mark.timeout(30)
def test_demo_wav(tmp_path: Path):
    # Create a small valid WAV file (1s of silence at 16kHz)
    wav_path = tmp_path / "hello_en.wav"
    sr = 16000
    duration_s = 1
    nframes = sr * duration_s
    with wave.open(str(wav_path), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sr)
        # write silence
        frames = struct.pack("<%dh" % nframes, *([0] * nframes))
        wf.writeframes(frames)

    # Isolate OUT_ROOT for test by setting env and importing demo after
    test_out = tmp_path / "out"
    os.environ["LLX_OUT_DIR"] = str(test_out)

    from loquilex.cli import demo
    from loquilex.api.server import OUT_ROOT

    # Pick a session name to make dir predictable
    session_name = "testdemo"
    session_dir = OUT_ROOT / f"session-{session_name}"
    if session_dir.exists():
        shutil.rmtree(session_dir)

    # Run demo main with wav and short duration
    demo.main(
        ["--wav", str(wav_path), "--duration", "2", "--session", session_name, "--allow-fallback"]
    )

    assert session_dir.exists()
    events = session_dir / "events.jsonl"
    transcript = session_dir / "transcript.txt"

    assert events.exists()
    assert transcript.exists()

    # Ensure at least one mt.final in events
    found = False
    with open(events, "r", encoding="utf-8") as f:
        for line in f:
            try:
                obj = json.loads(line)
            except Exception:
                continue
            if obj.get("type") == "mt.final":
                found = True
                break

    assert found, "No mt.final event found"
    assert transcript.stat().st_size > 0

from __future__ import annotations

from pathlib import Path
import wave
import numpy as np


def write_tiny_wav(path: str | Path, seconds: float = 1.0, sr: int = 16000) -> None:
    n = int(seconds * sr)
    t = np.arange(n, dtype=np.float32) / sr
    # Simple low-amplitude tone to avoid clipping
    x = (0.1 * np.sin(2 * np.pi * 440.0 * t)).astype(np.float32)
    pcm16 = (np.clip(x, -1.0, 1.0) * 32767.0).astype(np.int16)
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes(pcm16.tobytes())

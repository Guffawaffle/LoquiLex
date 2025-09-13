from __future__ import annotations

import shutil
import subprocess
import tempfile

import numpy as np


def ffmpeg_resample_wav_to_16k_mono(in_path: str) -> np.ndarray:
    if shutil.which("ffmpeg") is None:
        raise RuntimeError("ffmpeg not available")
    with tempfile.NamedTemporaryFile(suffix=".f32", delete=True) as tmp:
        cmd = [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-i",
            in_path,
            "-ac",
            "1",
            "-ar",
            "16000",
            "-f",
            "f32le",
            tmp.name,
        ]
        subprocess.check_call(cmd)
        data = np.fromfile(tmp.name, dtype=np.float32)
    return data


def linear_resample(x: np.ndarray, sr_in: int, sr_out: int = 16000) -> np.ndarray:
    if sr_in == sr_out:
        return x.astype(np.float32, copy=False)
    t = np.linspace(0, len(x) / sr_in, num=len(x), endpoint=False)
    t2 = np.linspace(0, len(x) / sr_out, num=int(len(x) * sr_out / sr_in), endpoint=False)
    return np.interp(t2, t, x).astype(np.float32)

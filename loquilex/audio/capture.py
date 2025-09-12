from __future__ import annotations

import queue
import shutil
import subprocess
import threading
import time
from dataclasses import dataclass
from typing import Callable

import numpy as np

"""Microphone capture with sounddevice; ffmpeg pulse/alsa fallback.

Produces 16 kHz mono float32 frames. Never writes files. No side effects on import.
"""

SAMPLE_RATE = 16000
CHANNELS = 1
FRAME_SAMPLES = 1600  # 100 ms frames


@dataclass
class AudioFrame:
    data: np.ndarray  # shape (n,), float32 mono at 16kHz
    t0: float  # capture start time (monotonic)
    t1: float  # capture end time (monotonic)


def _log(msg: str) -> None:
    print(f"[audio] {msg}")


def available(cmd: str) -> bool:
    return shutil.which(cmd) is not None


def capture_stream(callback: Callable[[AudioFrame], None]) -> Callable[[], None]:
    """Start capturing audio and call callback for each frame.

    Returns a stop() function. Tries sounddevice -> ffmpeg pulse -> ffmpeg alsa.
    """

    # Try sounddevice first
    try:
        import sounddevice as sd  # type: ignore

        q: queue.Queue[np.ndarray] = queue.Queue(maxsize=10)

        def on_audio(indata: np.ndarray, frames: int, time_info, status) -> None:  # type: ignore
            if status:
                _log(f"sounddevice status: {status}")
            q.put(indata.copy())

        stream = sd.InputStream(
            samplerate=SAMPLE_RATE,
            channels=CHANNELS,
            dtype="float32",
            blocksize=FRAME_SAMPLES,
            callback=on_audio,
        )
        stream.start()
        _log("path=sounddevice")

        stop_flag = threading.Event()

        def worker() -> None:
            while not stop_flag.is_set():
                try:
                    block = q.get(timeout=0.2)
                except queue.Empty:
                    continue
                t1 = time.monotonic()
                t0 = t1 - (len(block) / SAMPLE_RATE)
                mono = block.reshape(-1).astype(np.float32)
                callback(AudioFrame(mono, t0, t1))

        th = threading.Thread(target=worker, daemon=True)
        th.start()

        def stop() -> None:
            stop_flag.set()
            th.join(timeout=1.0)
            stream.stop()
            stream.close()

        return stop
    except Exception as e:
        _log(f"sounddevice unavailable: {e}")

    # Fallback to ffmpeg pulse then alsa
    if not available("ffmpeg"):
        raise RuntimeError("ffmpeg not available, cannot capture audio")

    for dev in ("pulse", "alsa"):
        cmd = [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-f",
            dev,
            "-i",
            "default",
            "-ac",
            str(CHANNELS),
            "-ar",
            str(SAMPLE_RATE),
            "-vn",
            "-f",
            "f32le",
            "-",
        ]
        try:
            proc = subprocess.Popen(cmd, stdout=subprocess.PIPE)
        except Exception as e:
            _log(f"ffmpeg {dev} failed to start: {e}")
            continue

        if not proc.stdout:
            proc.kill()
            continue

        _log(f"path=ffmpeg/{dev}")
        stop_flag = threading.Event()

        def reader() -> None:
            bufsize = FRAME_SAMPLES * 4  # float32 bytes
            while not stop_flag.is_set():
                assert proc.stdout is not None  # Already checked above
                chunk = proc.stdout.read(bufsize)
                if not chunk:
                    break
                t1 = time.monotonic()
                arr = np.frombuffer(chunk, dtype=np.float32)
                if arr.size == 0:
                    continue
                t0 = t1 - (arr.size / SAMPLE_RATE)
                callback(AudioFrame(arr, t0, t1))

        th = threading.Thread(target=reader, daemon=True)
        th.start()

        def stop() -> None:
            stop_flag.set()
            try:
                if proc.stdout:
                    proc.stdout.close()
            except Exception:
                pass
            proc.terminate()
            th.join(timeout=1.0)

        return stop

    raise RuntimeError("No audio capture path available (sounddevice/ffmpeg)")

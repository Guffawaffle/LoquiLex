"""Fake audio capture for testing."""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass
from typing import Callable

import numpy as np

__all__ = ["FakeAudioFrame", "fake_capture_stream"]


@dataclass
class FakeAudioFrame:
    """Fake audio frame for testing."""

    data: np.ndarray
    timestamp: float = 0.0


def fake_capture_stream(callback: Callable[[FakeAudioFrame], None]) -> Callable[[], None]:
    """
    Fake audio capture that generates synthetic audio frames.

    Returns a stop function to halt the capture.
    """
    stop_event = threading.Event()

    def audio_worker():
        """Generate fake audio frames at regular intervals."""
        frame_count = 0
        while not stop_event.is_set():
            # Generate 0.1 second of fake audio at 16kHz
            samples_per_frame = 1600  # 0.1s * 16000 Hz

            # Generate low-level noise to simulate microphone input
            audio_data = np.random.uniform(-0.01, 0.01, samples_per_frame).astype(np.float32)

            frame = FakeAudioFrame(
                data=audio_data,
                timestamp=frame_count * 0.1,
            )

            try:
                callback(frame)
            except Exception as e:
                print(f"[FakeAudio] Callback error: {e}")
                break

            frame_count += 1

            # Sleep for frame duration
            time.sleep(0.1)

    # Start the worker thread
    thread = threading.Thread(target=audio_worker, daemon=True)
    thread.start()

    # Return stop function
    def stop():
        stop_event.set()
        try:
            thread.join(timeout=1.0)
        except Exception:
            pass

    return stop

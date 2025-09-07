from __future__ import annotations

"""faster-whisper runner with VAD and segmentation.

Emits partial text quickly and final segments on end-of-speech or max length.
"""

from dataclasses import dataclass
from typing import Callable, Iterable, Iterator, Optional
import time

import numpy as np

from greenfield.config.defaults import ASR, RT, pick_device


@dataclass
class Segment:
    start: float
    end: float
    text: str
    is_final: bool


def _log(msg: str) -> None:
    print(f"[asr] {msg}")


class WhisperEngine:
    def __init__(self) -> None:
        device, dtype = pick_device()
        self.device = device
        self.dtype = dtype
        self.buf = np.zeros(0, dtype=np.float32)
        self._last_partial = ""
        self._last_partial_at = 0.0
        self._last_decode_at = 0.0
        self._last_seg_end: Optional[float] = None
        self._last_seg_end_wall: float = time.time()
        try:
            from faster_whisper import WhisperModel  # type: ignore
        except Exception as e:
            raise RuntimeError("faster-whisper not installed") from e

        compute_type = ASR.compute_type if device == "cuda" else "int8"
        self.model_name = ASR.model
        self.model = WhisperModel(
            self.model_name,
            device=device,
            compute_type=compute_type,
            cpu_threads=ASR.cpu_threads,
        )
        _log(f"device={device} dtype={dtype} model={self.model_name} compute={compute_type}")

    def warmup(self) -> None:
        """Run a tiny inference to load weights and kernels."""
        z = np.zeros(ASR.sample_rate, dtype=np.float32)  # ~1s
        try:
            res = self.model.transcribe(
                z,
                language=ASR.language,
                vad_filter=False,
                beam_size=1,
                temperature=0.0,
                word_timestamps=False,
            )
            # exhaust generator quickly
            list(res[0])
        except Exception:
            pass

    def feed(
        self,
        samples_iter: Iterable[np.ndarray],
        on_partial: Callable[[str], None],
        on_segment: Callable[[Segment], None],
    ) -> None:
        """Stateful streaming with ring buffer, debounced partials, and EoS heuristic.

        Emits partials frequently and finalizes when segment end hasn't advanced for RT.pause_flush_sec.
        """
        max_keep = int(ASR.sample_rate * RT.max_buffer_sec)
        for chunk in samples_iter:
            ch = np.asarray(chunk, dtype=np.float32).reshape(-1)
            if ch.size == 0:
                continue
            np.clip(ch, -1.0, 1.0, out=ch)
            self.buf = np.concatenate([self.buf, ch])
            if self.buf.size > max_keep:
                self.buf = self.buf[-max_keep:]

            now = time.time()
            if now - self._last_decode_at < RT.decode_interval_sec:
                continue
            self._last_decode_at = now

            segments, info = self.model.transcribe(
                self.buf,
                language=ASR.language,
                vad_filter=ASR.vad_filter,
                beam_size=ASR.beam_size,
                no_speech_threshold=ASR.no_speech_threshold,
                log_prob_threshold=ASR.log_prob_threshold,
                condition_on_previous_text=ASR.condition_on_previous_text,
                temperature=0.0,
                word_timestamps=False,
            )
            segs = list(segments)
            partial_text = " ".join((s.text or "").strip() for s in segs if (s.text or "").strip()).strip()

            # Debounced partials
            if partial_text and partial_text != self._last_partial:
                if now - self._last_partial_at >= RT.partial_debounce_sec:
                    on_partial(partial_text)
                    self._last_partial = partial_text
                    self._last_partial_at = now

            # Track last end
            if segs:
                last_end = float(segs[-1].end or 0.0)
                if self._last_seg_end is None or last_end > self._last_seg_end + 1e-3:
                    self._last_seg_end = last_end
                    self._last_seg_end_wall = now

            # Finalize on pause
            if partial_text and (now - self._last_seg_end_wall) >= RT.pause_flush_sec:
                start_t = float(segs[0].start or 0.0) if segs else 0.0
                end_t = float(segs[-1].end or 0.0) if segs else 0.0
                on_segment(Segment(start_t, end_t, partial_text, True))
                # reset buffer/state for next clause
                self.buf = np.zeros(0, dtype=np.float32)
                self._last_partial = ""
                self._last_seg_end = None
                self._last_seg_end_wall = now

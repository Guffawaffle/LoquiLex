from __future__ import annotations

"""faster-whisper runner with VAD and segmentation.

Emits partial text quickly and final segments on end-of-speech or max length.
"""

from dataclasses import dataclass
from typing import Callable, Iterable, Optional, List
import time

import numpy as np

from loquilex.config.defaults import ASR, RT, SEG, pick_device


@dataclass
class Segment:
    start: float
    end: float
    text: str
    is_final: bool


@dataclass
class Word:
    start: float
    end: float
    text: str


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
        # Use monotonic clock for durations/latency math
        self._last_seg_end_wall: float = time.monotonic()
        # word-level tracking
        self._words_emitted: int = 0
        try:
            from faster_whisper import WhisperModel  # type: ignore
        except Exception as e:
            raise RuntimeError("faster-whisper not installed") from e

        # Prefer int8_float32 on CPU (weights int8, activations fp32) for better quality; fallback to int8
        requested_compute = ASR.compute_type if device == "cuda" else "int8_float32"
        self.model_name = ASR.model
        try:
            self.model = WhisperModel(
                self.model_name,
                device=device,
                compute_type=requested_compute,
                cpu_threads=ASR.cpu_threads,
            )
            effective_compute = requested_compute
        except Exception:
            if device == "cpu" and requested_compute == "int8_float32":
                # Fallback if build doesn't support int8_float32
                self.model = WhisperModel(
                    self.model_name,
                    device=device,
                    compute_type="int8",
                    cpu_threads=ASR.cpu_threads,
                )
                effective_compute = "int8"
            else:
                raise
        _log(f"device={device} dtype={dtype} model={self.model_name} compute={effective_compute}")

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
        on_words: Optional[Callable[[List[Word]], None]] = None,
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

            now = time.monotonic()
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
                word_timestamps=ASR.word_timestamps,
            )
            segs = list(segments)
            partial_text = " ".join((s.text or "").strip() for s in segs if (s.text or "").strip()).strip()

            # Optional word-level callbacks (rolling window support)
            if ASR.word_timestamps and on_words is not None:
                # Flatten words across segments in order
                flat_words: List[Word] = []
                for s in segs:
                    ws = getattr(s, "words", None)
                    if not ws:
                        continue
                    for w in ws:
                        # faster-whisper uses .word for text
                        txt = getattr(w, "word", None) or getattr(w, "text", "")
                        try:
                            a = float(getattr(w, "start", 0.0) or 0.0)
                            b = float(getattr(w, "end", 0.0) or 0.0)
                        except Exception:
                            a, b = 0.0, 0.0
                        flat_words.append(Word(a, b, (txt or "").strip()))
                if self._words_emitted < len(flat_words):
                    new_ws = flat_words[self._words_emitted:]
                    # update before callback to avoid reentrancy issues
                    self._words_emitted = len(flat_words)
                    # filter empty
                    new_ws = [w for w in new_ws if w.text]
                    if new_ws:
                        on_words(new_ws)

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

            # Finalize on pause or segment max length (engine is the single source of truth for finals)
            max_len_hit = False
            start_t = float(segs[0].start or 0.0) if segs else 0.0
            end_t = float(segs[-1].end or 0.0) if segs else 0.0
            if segs and (end_t - start_t) >= SEG.segment_max_sec:
                max_len_hit = True
            if partial_text and ((now - self._last_seg_end_wall) >= RT.pause_flush_sec or max_len_hit):
                on_segment(Segment(start_t, end_t, partial_text, True))
                # reset buffer/state for next clause
                self.buf = np.zeros(0, dtype=np.float32)
                self._last_partial = ""
                self._last_seg_end = None
                self._last_seg_end_wall = now
                self._words_emitted = 0

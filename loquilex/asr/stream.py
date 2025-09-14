"""Streaming ASR pipeline using CTranslate2/faster-whisper with rich partial/final events."""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

import numpy as np

from loquilex.config.defaults import ASR, RT, pick_device

__all__ = [
    "StreamingASR",
    "ASRWord",
    "ASRSegment",
    "ASRPartialEvent",
    "ASRFinalEvent",
    "ASRSnapshotEvent",
]


@dataclass
class ASRWord:
    """Word-level timing and confidence information."""

    w: str  # word text
    t0: float  # start time in seconds
    t1: float  # end time in seconds
    conf: float  # confidence score 0.0-1.0


@dataclass
class ASRSegment:
    """Segment for snapshot events."""

    segment_id: str
    text: str
    t0: float
    t1: float


@dataclass
class ASRPartialEvent:
    """Partial transcription event sent during active speech."""

    type: str = "asr.partial"
    stream_id: str = ""
    segment_id: str = ""
    seq: int = 0
    text: str = ""
    words: List[ASRWord] = field(default_factory=list)
    stable: bool = False  # partials are always provisional
    ts_monotonic: float = 0.0


@dataclass
class ASRFinalEvent:
    """Final transcription event sent at end-of-utterance."""

    type: str = "asr.final"
    stream_id: str = ""
    segment_id: str = ""
    text: str = ""
    words: List[ASRWord] = field(default_factory=list)
    ts_monotonic: float = 0.0
    eou_reason: str = ""  # silence|punctuation|timeout


@dataclass
class ASRSnapshotEvent:
    """Snapshot event for reconnect scenarios."""

    type: str = "asr.snapshot"
    stream_id: str = ""
    recent_finals: List[ASRSegment] = field(default_factory=list)
    live_partial: Optional[Dict[str, Any]] = None
    ts_monotonic: float = 0.0


class StreamingASR:
    """Enhanced streaming ASR with rich partial/final events using faster-whisper."""

    def __init__(self, stream_id: Optional[str] = None) -> None:
        """Initialize streaming ASR engine."""
        self.stream_id = stream_id or f"sess{uuid.uuid4().hex[:8]}"

        # Initialize whisper model
        device, dtype = pick_device()
        self.device = device
        self.dtype = dtype

        try:
            from faster_whisper import WhisperModel
        except Exception as e:
            raise RuntimeError("faster-whisper not installed") from e

        # Prefer int8_float32 on CPU for better quality; fallback to int8
        requested_compute = ASR.compute_type if device == "cuda" else "int8_float32"
        self.model_name = ASR.model

        try:
            self.model = WhisperModel(
                self.model_name,
                device=device,
                compute_type=requested_compute,
                cpu_threads=ASR.cpu_threads,
            )
            self.effective_compute = requested_compute
        except Exception:
            if device == "cpu" and requested_compute == "int8_float32":
                # Fallback if build doesn't support int8_float32
                self.model = WhisperModel(
                    self.model_name,
                    device=device,
                    compute_type="int8",
                    cpu_threads=ASR.cpu_threads,
                )
                self.effective_compute = "int8"
            else:
                raise

        # Streaming state
        self.audio_buffer = np.zeros(0, dtype=np.float32)
        self.current_segment_id: Optional[str] = None
        self.last_decode_time = 0.0
        self.last_partial_time = 0.0
        self.last_segment_end: Optional[float] = None
        self.last_segment_end_wall = time.monotonic()

        # Event sequence tracking
        self.seq_counter = 0

        # Recent finals for snapshots (keep last 10)
        self.recent_finals: List[ASRSegment] = []
        self.max_recent_finals = 10

        print(
            f"[StreamingASR] Initialized: device={device} model={self.model_name} compute={self.effective_compute}"
        )

    def warmup(self) -> None:
        """Run a tiny inference to load weights and kernels."""
        dummy_audio = np.zeros(ASR.sample_rate, dtype=np.float32)  # ~1s
        try:
            segments, _ = self.model.transcribe(
                dummy_audio,
                language=ASR.language,
                vad_filter=False,
                beam_size=1,
                temperature=0.0,
                word_timestamps=False,
            )
            # Exhaust generator quickly
            list(segments)
        except Exception:
            pass

    def _extract_words(self, segments: List[Any]) -> List[ASRWord]:
        """Extract word-level information from segments."""
        words: List[ASRWord] = []

        if not ASR.word_timestamps:
            return words

        for seg in segments:
            seg_words = getattr(seg, "words", None)
            if not seg_words:
                continue

            for word_obj in seg_words:
                # faster-whisper uses .word for text
                word_text = getattr(word_obj, "word", None) or getattr(word_obj, "text", "")
                if not word_text:
                    continue

                try:
                    start_time = float(getattr(word_obj, "start", 0.0) or 0.0)
                    end_time = float(getattr(word_obj, "end", 0.0) or 0.0)
                    confidence = float(
                        getattr(word_obj, "probability", 0.8) or 0.8
                    )  # default confidence
                except Exception:
                    start_time, end_time, confidence = 0.0, 0.0, 0.8

                words.append(
                    ASRWord(w=word_text.strip(), t0=start_time, t1=end_time, conf=confidence)
                )

        return words

    def _detect_eou(self, segments: List[Any], current_time: float) -> Optional[str]:
        """Detect end-of-utterance based on various heuristics."""
        if not segments:
            return None

        # Get the last segment's text for punctuation detection
        last_text = ""
        last_end = 0.0

        for seg in segments:
            if hasattr(seg, "text") and seg.text:
                last_text = seg.text.strip()
            if hasattr(seg, "end") and seg.end:
                last_end = float(seg.end)

        # Check for punctuation-based EOU
        if last_text and any(last_text.endswith(p) for p in ASR.punctuation):
            return "punctuation"

        # Check for silence-based EOU
        silence_threshold = ASR.silence_ms / 1000.0
        if (current_time - self.last_segment_end_wall) >= silence_threshold:
            return "silence"

        # Check for timeout-based EOU
        if self.current_segment_id and segments:
            first_start = float(getattr(segments[0], "start", 0.0) or 0.0)
            segment_duration = last_end - first_start
            max_segment_duration = ASR.max_seg_ms / 1000.0
            if segment_duration >= max_segment_duration:
                return "timeout"

        return None

    def process_audio_chunk(
        self,
        audio_chunk: np.ndarray,
        on_partial: Callable[[ASRPartialEvent], None],
        on_final: Callable[[ASRFinalEvent], None],
    ) -> None:
        """Process a chunk of audio and emit partial/final events as needed."""

        current_time = time.monotonic()

        # Append to buffer
        chunk = np.asarray(audio_chunk, dtype=np.float32).reshape(-1)
        if chunk.size == 0:
            return

        np.clip(chunk, -1.0, 1.0, out=chunk)
        self.audio_buffer = np.concatenate([self.audio_buffer, chunk])

        # Keep buffer bounded
        max_buffer_samples = int(ASR.sample_rate * RT.max_buffer_sec)
        if self.audio_buffer.size > max_buffer_samples:
            self.audio_buffer = self.audio_buffer[-max_buffer_samples:]

        # Rate limit decoding
        if current_time - self.last_decode_time < RT.decode_interval_sec:
            return

        self.last_decode_time = current_time

        # Run transcription
        try:
            segments, info = self.model.transcribe(
                self.audio_buffer,
                language=ASR.language,
                vad_filter=ASR.vad_filter,
                beam_size=ASR.beam_size,
                no_speech_threshold=ASR.no_speech_threshold,
                log_prob_threshold=ASR.log_prob_threshold,
                condition_on_previous_text=ASR.condition_on_previous_text,
                temperature=0.0,
                word_timestamps=ASR.word_timestamps,
            )

            segment_list = list(segments)

        except Exception as e:
            print(f"[StreamingASR] Transcription error: {e}")
            return

        if not segment_list:
            return

        # Extract text and words
        text = " ".join(
            (seg.text or "").strip() for seg in segment_list if (seg.text or "").strip()
        ).strip()

        if not text:
            return

        words = self._extract_words(segment_list)

        # Generate or reuse segment ID
        if self.current_segment_id is None:
            self.current_segment_id = f"seg{uuid.uuid4().hex[:8]}"

        # Update segment end tracking
        last_end = 0.0
        for seg in segment_list:
            if hasattr(seg, "end") and seg.end:
                last_end = max(last_end, float(seg.end))

        if self.last_segment_end is None or last_end > self.last_segment_end + 1e-3:
            self.last_segment_end = last_end
            self.last_segment_end_wall = current_time

        # Check for EOU
        eou_reason = self._detect_eou(segment_list, current_time)

        if eou_reason:
            # Emit final event
            self.seq_counter += 1
            final_event = ASRFinalEvent(
                stream_id=self.stream_id,
                segment_id=self.current_segment_id,
                text=text,
                words=words,
                ts_monotonic=current_time,
                eou_reason=eou_reason,
            )

            on_final(final_event)

            # Add to recent finals for snapshots
            first_start = 0.0
            if segment_list:
                first_start = float(getattr(segment_list[0], "start", 0.0) or 0.0)

            recent_segment = ASRSegment(
                segment_id=self.current_segment_id,
                text=text,
                t0=first_start,
                t1=last_end,
            )

            self.recent_finals.append(recent_segment)
            if len(self.recent_finals) > self.max_recent_finals:
                self.recent_finals = self.recent_finals[-self.max_recent_finals :]

            # Reset for next segment
            self._reset_segment_state()

        else:
            # Emit partial event (with debouncing)
            if current_time - self.last_partial_time >= RT.partial_debounce_sec:
                self.seq_counter += 1
                partial_event = ASRPartialEvent(
                    stream_id=self.stream_id,
                    segment_id=self.current_segment_id,
                    seq=self.seq_counter,
                    text=text,
                    words=words,
                    ts_monotonic=current_time,
                )

                on_partial(partial_event)
                self.last_partial_time = current_time

    def _reset_segment_state(self) -> None:
        """Reset state for a new segment."""
        self.audio_buffer = np.zeros(0, dtype=np.float32)
        self.current_segment_id = None
        self.last_segment_end = None
        self.last_segment_end_wall = time.monotonic()

    def get_snapshot(self) -> ASRSnapshotEvent:
        """Get current snapshot for reconnect scenarios."""
        live_partial = None

        if self.current_segment_id and self.audio_buffer.size > 0:
            # Try to get current partial state
            try:
                segments, _ = self.model.transcribe(
                    self.audio_buffer,
                    language=ASR.language,
                    vad_filter=ASR.vad_filter,
                    beam_size=ASR.beam_size,
                    no_speech_threshold=ASR.no_speech_threshold,
                    log_prob_threshold=ASR.log_prob_threshold,
                    condition_on_previous_text=ASR.condition_on_previous_text,
                    temperature=0.0,
                    word_timestamps=ASR.word_timestamps,
                )

                segment_list = list(segments)
                text = " ".join(
                    (seg.text or "").strip() for seg in segment_list if (seg.text or "").strip()
                ).strip()

                if text:
                    words = self._extract_words(segment_list)
                    live_partial = {
                        "segment_id": self.current_segment_id,
                        "text": text,
                        "words": [
                            {"w": w.w, "t0": w.t0, "t1": w.t1, "conf": w.conf} for w in words
                        ],
                        "seq": self.seq_counter,
                    }

            except Exception:
                pass  # Live partial is optional

        return ASRSnapshotEvent(
            stream_id=self.stream_id,
            recent_finals=self.recent_finals.copy(),
            live_partial=live_partial,
            ts_monotonic=time.monotonic(),
        )

    def force_finalize(self, on_final: Callable[[ASRFinalEvent], None]) -> None:
        """Force finalization of current segment."""
        if self.current_segment_id is None or self.audio_buffer.size == 0:
            return

        try:
            segments, _ = self.model.transcribe(
                self.audio_buffer,
                language=ASR.language,
                vad_filter=ASR.vad_filter,
                beam_size=ASR.beam_size,
                no_speech_threshold=ASR.no_speech_threshold,
                log_prob_threshold=ASR.log_prob_threshold,
                condition_on_previous_text=ASR.condition_on_previous_text,
                temperature=0.0,
                word_timestamps=ASR.word_timestamps,
            )

            segment_list = list(segments)
            text = " ".join(
                (seg.text or "").strip() for seg in segment_list if (seg.text or "").strip()
            ).strip()

            if text:
                words = self._extract_words(segment_list)

                self.seq_counter += 1
                final_event = ASRFinalEvent(
                    stream_id=self.stream_id,
                    segment_id=self.current_segment_id,
                    text=text,
                    words=words,
                    ts_monotonic=time.monotonic(),
                    eou_reason="forced",
                )

                on_final(final_event)

                # Add to recent finals
                first_start = 0.0
                last_end = 0.0
                if segment_list:
                    first_start = float(getattr(segment_list[0], "start", 0.0) or 0.0)
                    for seg in segment_list:
                        if hasattr(seg, "end") and seg.end:
                            last_end = max(last_end, float(seg.end))

                recent_segment = ASRSegment(
                    segment_id=self.current_segment_id,
                    text=text,
                    t0=first_start,
                    t1=last_end,
                )

                self.recent_finals.append(recent_segment)
                if len(self.recent_finals) > self.max_recent_finals:
                    self.recent_finals = self.recent_finals[-self.max_recent_finals :]

        except Exception as e:
            print(f"[StreamingASR] Force finalize error: {e}")

        # Always reset after force finalize
        self._reset_segment_state()

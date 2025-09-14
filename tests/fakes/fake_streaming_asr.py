"""Fake streaming ASR for offline testing."""

from __future__ import annotations

import time
import uuid
from typing import Any, Callable, Dict, List, Optional

import numpy as np

from loquilex.asr.stream import ASRWord, ASRSegment, ASRPartialEvent, ASRFinalEvent, ASRSnapshotEvent


class FakeStreamingASR:
    """Fake streaming ASR that produces deterministic events for testing."""
    
    def __init__(self, stream_id: Optional[str] = None) -> None:
        self.stream_id = stream_id or f"sess{uuid.uuid4().hex[:8]}"
        self.current_segment_id: Optional[str] = None
        self.seq_counter = 0
        self.audio_buffer_size = 0
        self.recent_finals: List[ASRSegment] = []
        self.chunk_count = 0
        self.max_recent_finals = 10
        
        # Predefined test data
        self.test_words = [
            ASRWord(w="Hello", t0=0.0, t1=0.3, conf=0.95),
            ASRWord(w="world", t0=0.3, t1=0.6, conf=0.92),
            ASRWord(w="this", t0=0.7, t1=0.9, conf=0.88),
            ASRWord(w="is", t0=0.9, t1=1.0, conf=0.91),
            ASRWord(w="a", t0=1.0, t1=1.1, conf=0.85),
            ASRWord(w="test.", t0=1.1, t1=1.4, conf=0.93),
        ]
        
        print(f"[FakeStreamingASR] Initialized: stream_id={self.stream_id}")

    def warmup(self) -> None:
        """No-op warmup for fake ASR."""
        pass

    def process_audio_chunk(
        self,
        audio_chunk: np.ndarray,
        on_partial: Callable[[ASRPartialEvent], None],
        on_final: Callable[[ASRFinalEvent], None],
    ) -> None:
        """Process fake audio chunk and emit deterministic events."""
        
        chunk = np.asarray(audio_chunk, dtype=np.float32).reshape(-1)
        if chunk.size == 0:
            return
            
        self.audio_buffer_size += chunk.size
        self.chunk_count += 1
        current_time = time.monotonic()
        
        # Generate segment ID if needed
        if self.current_segment_id is None:
            self.current_segment_id = f"seg{uuid.uuid4().hex[:8]}"
        
        # Deterministic behavior based on chunk count
        if self.chunk_count <= 3:
            # Emit partials for first 3 chunks
            num_words = min(self.chunk_count + 1, len(self.test_words))
            words = self.test_words[:num_words]
            text = " ".join(w.w for w in words)
            
            self.seq_counter += 1
            partial = ASRPartialEvent(
                stream_id=self.stream_id,
                segment_id=self.current_segment_id,
                seq=self.seq_counter,
                text=text,
                words=words,
                ts_monotonic=current_time,
            )
            on_partial(partial)
            
        elif self.chunk_count == 4:
            # Emit final on 4th chunk (punctuation EOU)
            words = self.test_words
            text = " ".join(w.w for w in words)
            
            final = ASRFinalEvent(
                stream_id=self.stream_id,
                segment_id=self.current_segment_id,
                text=text,
                words=words,
                ts_monotonic=current_time,
                eou_reason="punctuation",
            )
            on_final(final)
            
            # Add to recent finals
            segment = ASRSegment(
                segment_id=self.current_segment_id,
                text=text,
                t0=0.0,
                t1=1.4,
            )
            self.recent_finals.append(segment)
            if len(self.recent_finals) > self.max_recent_finals:
                self.recent_finals = self.recent_finals[-self.max_recent_finals:]
                
            # Reset state
            self._reset_segment_state()
            
        # Reset chunk count after finalization for repeatable behavior
        if self.chunk_count >= 5:
            self.chunk_count = 0

    def _reset_segment_state(self) -> None:
        """Reset state for a new segment."""
        self.audio_buffer_size = 0
        self.current_segment_id = None

    def get_snapshot(self) -> ASRSnapshotEvent:
        """Get fake snapshot."""
        live_partial = None
        
        if self.current_segment_id:
            # Generate fake live partial
            live_partial = {
                "segment_id": self.current_segment_id,
                "text": "Hello world",
                "words": [{"w": "Hello", "t0": 0.0, "t1": 0.3, "conf": 0.95}],
                "seq": self.seq_counter,
            }
            
        return ASRSnapshotEvent(
            stream_id=self.stream_id,
            recent_finals=self.recent_finals.copy(),
            live_partial=live_partial,
            ts_monotonic=time.monotonic(),
        )

    def force_finalize(self, on_final: Callable[[ASRFinalEvent], None]) -> None:
        """Force finalize current segment."""
        if self.current_segment_id is None:
            return
            
        # Create minimal final event
        final = ASRFinalEvent(
            stream_id=self.stream_id,
            segment_id=self.current_segment_id,
            text="Forced finalization",
            words=[ASRWord(w="Forced", t0=0.0, t1=0.5, conf=0.8)],
            ts_monotonic=time.monotonic(),
            eou_reason="forced",
        )
        on_final(final)
        
        # Add to recent finals
        segment = ASRSegment(
            segment_id=self.current_segment_id,
            text="Forced finalization",
            t0=0.0,
            t1=0.5,
        )
        self.recent_finals.append(segment)
        if len(self.recent_finals) > self.max_recent_finals:
            self.recent_finals = self.recent_finals[-self.max_recent_finals:]
            
        self._reset_segment_state()
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Optional
import time

from greenfield.config.defaults import SEG


@dataclass
class CaptionState:
    start_time: float
    last_update: float
    text: str


class Aggregator:
    """Simple caption state machine.

    - Debounces partials (sends at most every partial_debounce_ms)
    - Finalizes on pause >= pause_flush_sec or length >= segment_max_sec
    """

    def __init__(self, now: Callable[[], float] | None = None) -> None:
        self.now = now or time.monotonic
        self.state: Optional[CaptionState] = None
        self.last_partial_emit = 0.0

    def on_partial(self, text: str, emit_partial: Callable[[str], None]) -> None:
        t = self.now()
        if self.state is None:
            self.state = CaptionState(t, t, text)
        else:
            self.state.text = text
            self.state.last_update = t

        if t - self.last_partial_emit >= SEG.partial_debounce_ms / 1000.0:
            if text.strip():
                emit_partial(text.strip())
                self.last_partial_emit = t

    def maybe_finalize(self, emit_final: Callable[[float, float, str], None]) -> None:
        if self.state is None:
            return
        t = self.now()
        st = self.state
        if not st.text.strip():
            return

        paused = t - st.last_update >= SEG.pause_flush_sec
        long = t - st.start_time >= SEG.segment_max_sec
        if paused or long:
            # finalize current text
            emit_final(st.start_time, t, st.text.strip())
            self.state = None

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any, Dict

"""Event stamping helpers: add seq, ts_server, ts_session to outbound WS messages."""


@dataclass
class EventStamper:
    t0_mono: float
    seq: int = 0

    @classmethod
    def new(cls) -> "EventStamper":
        return cls(t0_mono=time.monotonic(), seq=0)

    def stamp(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        self.seq += 1
        now = time.time()
        now_mono = time.monotonic()
        stamped = dict(payload)
        stamped.update(
            {
                "seq": self.seq,
                "ts_server": now,
                "ts_session": max(0.0, now_mono - self.t0_mono),
            }
        )
        return stamped

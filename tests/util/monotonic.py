from __future__ import annotations

from typing import Iterator


def step_times(start: float, step: float, count: int) -> Iterator[float]:
    t = start
    for _ in range(count):
        yield t
        t += step

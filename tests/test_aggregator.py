from __future__ import annotations

import time

from loquilex.segmentation.aggregator import Aggregator


def test_aggregator_partial_debounce():
    t = [0.3]

    def now():
        return t[0]

    agg = Aggregator(now=now)
    emitted: list[str] = []
    # Rapid partials inside debounce window should collapse to one emit
    agg.on_partial("hello", emitted.append)
    for _ in range(5):
        agg.on_partial("hello world", emitted.append)
    assert emitted == ["hello"]
    # Advance time beyond debounce and new text should emit
    t[0] += 0.5
    agg.on_partial("how are you", emitted.append)
    assert emitted[-1] == "how are you"


def test_aggregator_force_finalize():
    t = [100.0]

    def now():
        return t[0]

    agg = Aggregator(now=now)
    finals: list[tuple[float, float, str]] = []
    agg.on_partial("partial", lambda s: None)
    t[0] += 1.0
    agg.force_finalize(lambda a, b, s: finals.append((a, b, s)))
    assert len(finals) == 1
    a, b, s = finals[0]
    assert 0.0 <= a <= b
    assert s == "partial"
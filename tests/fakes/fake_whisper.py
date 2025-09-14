from __future__ import annotations

from typing import Iterable, Tuple


class _Seg:
    def __init__(self, start: float, end: float, text: str):
        self.start = start
        self.end = end
        self.text = text


class WhisperModel:
    def __init__(self, *args, **kwargs):
        pass

    def transcribe(self, _data, **_kwargs) -> Tuple[Iterable[_Seg], dict]:
        # Return two tiny deterministic segments
        segs = [_Seg(0.0, 0.5, "hello"), _Seg(0.5, 1.0, "world")]
        return segs, {"lang": "en"}

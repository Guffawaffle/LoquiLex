from __future__ import annotations

from dataclasses import dataclass
from typing import List, Tuple
import os


EPS = 0.001


def _ts(sec: float) -> str:
    ms = int(round(sec * 1000))
    h = ms // 3_600_000
    ms %= 3_600_000
    m = ms // 60_000
    ms %= 60_000
    s = ms // 1000
    ms %= 1000
    return f"{h:02d}:{m:02d}:{s:02d}.{ms:03d}"


def write_vtt(cues: List[Tuple[float, float, str]], path: str) -> None:
    d = os.path.dirname(path)
    if d:
        os.makedirs(d, exist_ok=True)
    clean: List[Tuple[float, float, str]] = []
    last_end = 0.0
    for (a, b, t) in cues:
        t = t.strip()
        if not t:
            continue
        a = max(a, last_end + EPS)
        if b <= a:
            b = a + EPS
        clean.append((a, b, t))
        last_end = b

    with open(path, "w", encoding="utf-8") as f:
        f.write("WEBVTT\n\n")
        for a, b, t in clean:
            f.write(f"{_ts(a)} --> {_ts(b)}\n{t}\n\n")

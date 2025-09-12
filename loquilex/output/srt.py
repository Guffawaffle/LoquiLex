from __future__ import annotations

import os
from typing import List, Tuple

EPS = 0.001


def _ts(sec: float) -> str:
    ms = int(round(sec * 1000))
    h = ms // 3_600_000
    ms %= 3_600_000
    m = ms // 60_000
    ms %= 60_000
    s = ms // 1000
    ms %= 1000
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def write_srt(cues: List[Tuple[float, float, str]], path: str) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    clean: List[Tuple[float, float, str]] = []
    last_end = 0.0
    for a, b, t in cues:
        if not t.strip():
            continue
        a = max(a, last_end)
        if b <= a:
            b = a + EPS
        clean.append((a, b, t.strip()))
        last_end = b

    with open(path, "w", encoding="utf-8") as f:
        for i, (a, b, t) in enumerate(clean, start=1):
            f.write(f"{i}\n{_ts(a)} --> {_ts(b)}\n{t}\n\n")


def append_srt_cue(path: str, index: int | None, start: float, end: float, text: str) -> int:
    """Append a single SRT cue. If index is None, determine next index from file.

    Returns the index used for this cue.
    """
    os.makedirs(os.path.dirname(path), exist_ok=True)

    # Determine next index
    next_idx = 1
    last_end = 0.0
    if os.path.exists(path):
        try:
            with open(path, "rb") as f:
                f.seek(0, os.SEEK_END)
                size = f.tell()
                chunk = 8192
                data = b""
                while size > 0 and (b"-->" not in data or b"\n\n" not in data):
                    step = min(chunk, size)
                    size -= step
                    f.seek(size)
                    data = f.read(step) + data
            txt = data.decode("utf-8", errors="ignore")
            # Find the last complete cue block
            blocks = [b for b in txt.split("\n\n") if "-->" in b]
            if blocks:
                last = blocks[-1].splitlines()
                try:
                    next_idx = int(last[0]) + 1
                except Exception:
                    next_idx = 1
                try:
                    tsline = [ln for ln in last if "-->" in ln][0]
                    right = tsline.split("-->")[1].strip().split(" ")[0]
                    hh, mm, ss_ms = right.split(":")
                    ss, ms = ss_ms.split(",")
                    last_end = int(hh) * 3600 + int(mm) * 60 + int(ss) + int(ms) / 1000.0
                except Exception:
                    last_end = 0.0
        except Exception:
            next_idx = 1
            last_end = 0.0
    if index is not None:
        next_idx = index

    a = max(start, last_end + EPS)
    b = end
    if b <= a:
        b = a + EPS
    cue = f"{next_idx}\n{_ts(a)} --> {_ts(b)}\n{text.strip()}\n\n"
    with open(path, "a", encoding="utf-8") as f:
        f.write(cue)
    return next_idx

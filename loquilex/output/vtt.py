from __future__ import annotations

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


def append_vtt_cue(path: str, start: float, end: float, text: str) -> None:
    """Append a single VTT cue, creating file+header if needed.

    Applies epsilon bump and monotonic enforcement by checking the last cue in file if present.
    """
    d = os.path.dirname(path)
    if d:
        os.makedirs(d, exist_ok=True)

    # Ensure file exists with header
    if not os.path.exists(path):
        with open(path, "w", encoding="utf-8") as f:
            f.write("WEBVTT\n\n")

    # Read last end time by scanning backwards a bit (cheap for typical files)
    last_end = 0.0
    try:
        with open(path, "rb") as f:
            f.seek(0, os.SEEK_END)
            size = f.tell()
            chunk = 4096
            data = b""
            while size > 0 and b"-->" not in data:
                step = min(chunk, size)
                size -= step
                f.seek(size)
                data = f.read(step) + data
        text_data = data.decode("utf-8", errors="ignore")
        lines = [ln for ln in text_data.splitlines() if "-->" in ln]
        if lines:
            last = lines[-1]
            try:
                parts = last.split("-->")
                right = parts[1].strip().split(" ")[0]
                hh, mm, ss_ms = right.split(":")
                ss, ms = ss_ms.split(".")
                last_end = int(hh) * 3600 + int(mm) * 60 + int(ss) + int(ms) / 1000.0
            except Exception:
                last_end = 0.0
    except Exception:
        last_end = 0.0

    a = max(start, last_end + EPS)
    b = end
    if b <= a:
        b = a + EPS

    cue = f"{_ts(a)} --> {_ts(b)}\n{text.strip()}\n\n"
    # Append atomically: write tmp then concatenate with existing file content would be heavy; instead
    # for appends we can open in append mode which is atomic at OS-level for writes.
    with open(path, "a", encoding="utf-8") as f:
        f.write(cue)

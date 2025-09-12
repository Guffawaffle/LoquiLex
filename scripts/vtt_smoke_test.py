from __future__ import annotations

import os
from typing import List, Tuple


def parse_vtt(path: str) -> List[Tuple[float, float, str]]:
    cues: List[Tuple[float, float, str]] = []
    import re

    def ts(s: str) -> float:
        h, m, rest = s.split(":")
        if "," in rest:
            s2, ms = rest.split(",")
        else:
            s2, ms = rest.split(".")
        return int(h) * 3600 + int(m) * 60 + int(s2) + int(ms) / 1000.0

    with open(path, "r", encoding="utf-8") as f:
        lines = [ln.strip() for ln in f]
    i = 0
    while i < len(lines):
        line = lines[i]
        if "-->" in line:
            a, b = [x.strip() for x in line.split("-->")]
            i += 1
            text = []
            while i < len(lines) and lines[i] != "":
                text.append(lines[i])
                i += 1
            cues.append((ts(a), ts(b), " ".join(text)))
        i += 1
    return cues


def main() -> None:
    path = "loquilex/out/asr_en.vtt"
    assert os.path.exists(path), f"missing {path}"
    cues = parse_vtt(path)
    last = 0.0
    for i, (a, b, t) in enumerate(cues, 1):
        assert a >= last - 1e-6, f"non-monotonic at {i}"
        assert b > a, f"non-positive duration at {i}"
        last = b
    print(f"OK {len(cues)} cues monotonic")


if __name__ == "__main__":
    main()

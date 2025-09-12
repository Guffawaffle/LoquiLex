from __future__ import annotations

import argparse
import os
from typing import List, Tuple

from loquilex.mt.translator import Translator
from loquilex.output.srt import write_srt
from loquilex.post.zh_text import post_process


def parse_vtt(path: str) -> List[Tuple[float, float, str]]:
    cues: List[Tuple[float, float, str]] = []

    def parse_ts(s: str) -> float:
        h, m, rest = s.split(":")
        if "," in rest:
            s2, ms = rest.split(",")
        else:
            s2, ms = rest.split(".")
        return int(h) * 3600 + int(m) * 60 + int(s2) + int(ms) / 1000.0

    with open(path, "r", encoding="utf-8") as f:
        lines = [ln.rstrip("\n") for ln in f]
    i = 0
    while i < len(lines):
        line = lines[i]
        if "-->" in line:
            a, b = [x.strip() for x in line.split("-->")]
            i += 1
            text = []
            while i < len(lines) and lines[i].strip() != "":
                text.append(lines[i])
                i += 1
            txt = " ".join(text).strip()
            if txt:
                cues.append((parse_ts(a), parse_ts(b), txt))
        i += 1
    return cues


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--vtt", required=True)
    ap.add_argument("--out-text", required=True)
    ap.add_argument("--out-srt", required=True)
    args = ap.parse_args()

    cues = parse_vtt(args.vtt)
    tr = Translator()

    zh_lines: List[str] = []
    zh_cues: List[Tuple[float, float, str]] = []
    for a, b, t in cues:
        zh = tr.translate_en_to_zh(t)
        txt = post_process(zh.text)
        zh_lines.append(txt)
        zh_cues.append((a, b, txt))

    d = os.path.dirname(args.out_text)
    if d:
        os.makedirs(d, exist_ok=True)
    with open(args.out_text, "w", encoding="utf-8") as f:
        for line in zh_lines:
            if line:
                f.write(line + "\n")

    write_srt(zh_cues, args.out_srt)
    print(f"[cli] wrote {args.out_text} and {args.out_srt} ({len(zh_cues)} cues)")


if __name__ == "__main__":
    main()

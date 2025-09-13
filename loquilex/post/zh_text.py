from __future__ import annotations

import re
from typing import Iterable, Set

PUNCT_MAP = {
    ",": "，",
    ".": "。",
    "?": "？",
    "!": "！",
    ":": "：",
    ";": "；",
}


def normalize_punctuation(s: str) -> str:
    out = []
    for ch in s:
        out.append(PUNCT_MAP.get(ch, ch))
    s2 = "".join(out)
    # Collapse spaces around CJK
    s2 = re.sub(r"\s+", " ", s2).strip()
    s2 = re.sub(r"\s*([，。！？：；])\s*", r"\1", s2)
    return s2


def apply_glossary(s: str, dont_translate: Iterable[str] | None = None) -> str:
    if not dont_translate:
        return s
    # Replace with same token to prevent later MT (in our pipeline, MT already done).
    # Here it's mainly for consistent casing/spaces cleanup.
    st: Set[str] = set(dont_translate)
    for term in sorted(st, key=len, reverse=True):
        s = re.sub(re.escape(term), term, s, flags=re.IGNORECASE)
    return s


def post_process(s: str, glossary: Iterable[str] | None = None) -> str:
    return apply_glossary(normalize_punctuation(s), glossary)

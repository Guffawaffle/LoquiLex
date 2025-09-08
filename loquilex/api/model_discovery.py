from __future__ import annotations

"""Local model discovery for ASR (whisper) and MT (NLLB/M2M).

We scan common cache locations:
- HF cache (HF_HOME or HF_DATASETS_CACHE) for Transformers models (MT)
- whisper.cpp GGUF files under third_party/whisper.cpp/models and repo root models/
- CTranslate2 directories (faster-whisper converted) under ~/.cache/ or project models/
"""

import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional


def _env_paths() -> List[Path]:
    paths: List[Path] = []
    for key in ("HF_HOME", "HF_DATASETS_CACHE", "TRANSFORMERS_CACHE"):
        v = os.getenv(key)
        if v:
            paths.append(Path(v))
    # Add user caches
    paths.extend([Path.home() / ".cache" / "huggingface", Path("~/.cache").expanduser()])
    return [p for p in paths if p.exists()]


def _project_paths() -> List[Path]:
    root = Path(__file__).resolve().parents[2]
    return [root / "models", root / "third_party" / "whisper.cpp" / "models"]


def list_asr_models() -> List[Dict]:
    out: List[Dict] = []
    seen: set[str] = set()

    # GGUF files (whisper.cpp)
    for base in _project_paths():
        if not base.exists():
            continue
        for p in base.rglob("*.gguf"):
            size = p.stat().st_size
            name = p.stem
            quant = None
            m = re.search(r"-(Q\d+_\w+)", p.name)
            if m:
                quant = m.group(1)
            rec = {
                "id": name,
                "name": name,
                "source": "gguf",
                "quant": quant,
                "path": str(p),
                "size_bytes": size,
                "language": "en",
            }
            if rec["id"] not in seen:
                out.append(rec)
                seen.add(rec["id"])

    # faster-whisper by model id (names only) — we don't enumerate CT2 dirs reliably
    # Provide a minimal list of common models as present if HF cache has them
    common = [
        "tiny.en",
        "base.en",
        "small.en",
        "medium.en",
        "large-v3",
    ]
    caches = _env_paths()
    for mid in common:
        for c in caches:
            # Transformers cache layout varies; attempt a heuristic presence check
            hits = list(c.rglob(f"**/{mid}*"))
            if hits:
                rec = {
                    "id": mid,
                    "name": mid,
                    "source": "hf",
                    "quant": None,
                    "path": str(hits[0].parent),
                    "size_bytes": 0,
                    "language": "en",
                }
                if rec["id"] not in seen:
                    out.append(rec)
                    seen.add(rec["id"])
                break

    return out


def list_mt_models() -> List[Dict]:
    out: List[Dict] = []
    seen: set[str] = set()
    caches = _env_paths()
    candidates = [
        "facebook/nllb-200-distilled-600M",
        "facebook/m2m100_418M",
    ]
    for cid in candidates:
        parts = cid.split("/")
        leaf = parts[-1]
        present = False
        for c in caches:
            hits = list(c.rglob(f"**/{leaf}*"))
            if hits:
                present = True
                path = str(hits[0].parent)
                break
        if present:
            rec = {"id": cid, "name": leaf, "langs": ["zho_Hans"], "path": path}
            if rec["id"] not in seen:
                out.append(rec)
                seen.add(rec["id"])
    return out


def mt_supported_languages(model_id: str) -> List[str]:
    # Minimal mapping for defaults; can be extended in future
    if model_id.endswith("nllb-200-distilled-600M"):
        return [
            "zho_Hans",
            "zho_Hant",
            "jpn_Jpan",
            "kor_Hang",
            "fra_Latn",
            "spa_Latn",
        ]
    if "m2m" in model_id:
        return ["zh", "ja", "ko", "fr", "es"]
    return ["zho_Hans"]

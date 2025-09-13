#!/usr/bin/env python3
"""
Prefetch only the smallest models for local dev to avoid large downloads.
 - Whisper tiny.en via faster-whisper (CTRANSLATE2)

Environment:
  LX_ASR_MODEL      (default: "tiny.en", legacy: GF_ASR_MODEL)
  LX_MODEL_DIR      (default: ".models", legacy: LLX_MODEL_DIR)

This script is safe to run repeatedly; it only ensures the local cache exists.
"""
from __future__ import annotations
import sys
from pathlib import Path

try:
    from .env import getenv
    from .models import should_skip_prefetch
except ImportError:
    # Handle direct execution
    import sys

    sys.path.insert(0, str(Path(__file__).parent))
    from env import getenv
    from models import should_skip_prefetch

ASR_MODEL = getenv("LX_ASR_MODEL", "tiny.en", aliases=("GF_ASR_MODEL",))
DOWNLOAD_ROOT = Path(getenv("LX_MODEL_DIR", ".models", aliases=("LLX_MODEL_DIR",))).resolve()
DOWNLOAD_ROOT.mkdir(parents=True, exist_ok=True)

print(f"[dev] Prefetching ASR model: {ASR_MODEL} -> {DOWNLOAD_ROOT}")

if should_skip_prefetch():
    print("[dev] LX_SKIP_MODEL_PREFETCH set — skipping model prefetch.")
    sys.exit(0)

try:
    # Force online just for this fetch (call-site can also set envs)
    # We do not mutate global env here to respect caller's choice.
    from faster_whisper import WhisperModel

    # CPU-only, int8 is fine for dev verification
    model = WhisperModel(
        ASR_MODEL,
        device="cpu",
        compute_type="int8",
        download_root=str(DOWNLOAD_ROOT),
    )
    # Touch the model once to ensure artifacts are present
    # (No actual transcription run to keep execution fast.)
    print("[dev] Model cache prepared.")
except Exception as e:
    print(f"[dev] Skipped ASR prefetch due to error: {e}")

print("[dev] Done.")

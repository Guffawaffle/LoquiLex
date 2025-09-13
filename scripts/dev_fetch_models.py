#!/usr/bin/env python3
"""
Prefetch only the smallest models for local dev to avoid large downloads.
 - Whisper tiny.en via faster-whisper (CTRANSLATE2)

Environment:
  GF_ASR_MODEL      (default: "tiny.en")
  LLX_MODEL_DIR     (default: ".models")

This script is safe to run repeatedly; it only ensures the local cache exists.
"""
from __future__ import annotations
import os
from pathlib import Path

ASR_MODEL = os.getenv("GF_ASR_MODEL", "tiny.en")
DOWNLOAD_ROOT = Path(os.getenv("LLX_MODEL_DIR", ".models")).resolve()
DOWNLOAD_ROOT.mkdir(parents=True, exist_ok=True)

print(f"[dev] Prefetching ASR model: {ASR_MODEL} -> {DOWNLOAD_ROOT}")

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
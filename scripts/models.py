"""
Centralized model prefetch helpers.

Behavior:
- Obey LX_SKIP_MODEL_PREFETCH (or legacy aliases if we add them later).
- Provide a no-op prefetch stub so call-sites are stable offline.

CLI:
  python -m scripts.models prefetch-asr --model tiny.en --dir ./models
"""
from __future__ import annotations
import argparse
from pathlib import Path
from .env import getenv_bool

def should_skip_prefetch() -> bool:
    # Extend aliases=() if you want to accept GF_* here too.
    return getenv_bool("LX_SKIP_MODEL_PREFETCH", default=False, aliases=("GF_SKIP_MODEL_PREFETCH",))

def prefetch_asr(model: str, download_root: Path) -> None:
    """
    Placeholder for ASR model prefetching.
    Currently, this is a no-op to stay offline-first in minimal flows.
    """
    if should_skip_prefetch():
        print("[models] LX_SKIP_MODEL_PREFETCH set — skipping model prefetch.")
        return
    # TODO: implement actual download (honor offline-first by making this opt-in)
    print(f"[models] (stub) Would prefetch ASR model '{model}' into '{download_root}'. No action taken.")

def _cli(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="scripts.models", description="Model helper CLI")
    sub = parser.add_subparsers(dest="cmd", required=True)
    p_asr = sub.add_parser("prefetch-asr", help="Prefetch ASR model (no-op stub if skip flag set)")
    p_asr.add_argument("--model", required=True, help="ASR model name, e.g., tiny.en")
    p_asr.add_argument("--dir", default="./.cache/models", help="Download root directory")
    args = parser.parse_args(argv)

    if args.cmd == "prefetch-asr":
        prefetch_asr(args.model, Path(args.dir))
        return 0
    return 2

if __name__ == "__main__":
    raise SystemExit(_cli())

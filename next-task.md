Finish Migration to LoquiLex (from greenfield)

Role: You are a senior developer joining mid-migration. The repo may be in a partially moved state. Finish the rename/migration cleanly and make the project runnable end-to-end.

Hard rules

✅ Touch only the LoquiLex/ project (this folder).

✅ Keep all current functionality; no removals.

✅ Prefer additive, reversible changes; commit in small steps with clear messages.

❌ Do not modify anything outside this folder.

0) Snapshot & quick audit (read-only first)

Print a concise tree (depth 3) and surface any places that still reference the old name greenfield or GF_:

Search patterns: greenfield, GF_, Greenfield, green-field, from greenfield., python -m greenfield, greenfield/out.

Note any half-migrated artifacts (e.g., loquilex_egg-info/, mismatched package names, missing pyproject.toml fields, broken imports, failing tests).

Output a short bullet list of suspicions to fix before making changes.

1) Canonical package name & imports

Canonical Python package name: loquilex
Project display name: LoquiLex

Tasks

Ensure the top-level package directory is loquilex/ with these subpackages (create if missing and move files as needed):

loquilex/
  api/
  asr/
  audio/
  cli/
  config/
  mt/
  output/
  post/
  segmentation/
  scripts/
  tests/
  __init__.py


Update all imports and module references from greenfield.* → loquilex.*.

Update any python -m greenfield... invocations to python -m loquilex....

Update static/output paths: greenfield/out/... → out/... (rooted at repo’s out/).

Keep a small compatibility shim: if a module path greenfield.* is imported accidentally, raise a helpful error telling users the new name.

2) Env prefix & configuration

New env prefix: LX_
(Keep backward compatibility by reading GF_ if LX_ is missing, with LX_ taking precedence.)

Update loquilex/config/defaults.py to:

Read LX_* first, then fallback to GF_*.

Keep existing defaults identical.

Ensure pick_device() behavior unchanged.

Update README/docs and any CLI help strings to mention LX_... variables.

Examples (retain behavior, change names):

GF_ASR_MODEL → LX_ASR_MODEL

GF_DEVICE → LX_DEVICE

GF_OUT_DIR → LX_OUT_DIR (default remains out/)

3) Packaging & entry points

Create/align pyproject.toml with:

project.name = "loquilex"

requires-python = ">=3.10"

Runtime deps (mirror current requirements): faster-whisper, ctranslate2 (indirect via faster-whisper), transformers, sentencepiece, numpy, sounddevice, torch, accelerate, webvtt-py, fastapi, uvicorn, huggingface_hub, plus any existing ones in the repo.

Optional extras:

api = ["fastapi", "uvicorn", "huggingface_hub"]

dev = ["pytest", "ruff", "black", "mypy", "types-requests"]

Console scripts (keep behavior, rename to brand):

loquilex-live = loquilex.cli.live_en_to_zh:main

loquilex-wav2vtt = loquilex.cli.wav_to_vtt:main

loquilex-vtt2zh = loquilex.cli.vtt_to_zh:main

loquilex-api = loquilex.api.server:main

Remove stale *-egg-info if auto-generated and re-generated on build.

4) API & static paths

In loquilex/api/server.py:

Update imports to loquilex.*.

Keep static mount to a resolved out/ directory inside this repo; forbid traversal/symlinks.

Keep CORS allowlist via env (LX_ALLOWED_ORIGINS, fallback to http://localhost:5173).

Ensure WS origin checks reference the new env variable.

Ensure supervisor spawns python -m loquilex.cli.live_en_to_zh with per-session out/<sid>/.

5) Tests & smoke

Ensure tests/ import loquilex.* and pass.

Add/adjust a smoke test that:

Generates a tiny WAV (or uses the existing test asset).

Runs python -m loquilex.cli.wav_to_vtt --wav tests/assets/short.wav --out out/test_en.vtt.

Runs python -m loquilex.cli.vtt_to_zh --vtt out/test_en.vtt --out-text out/test_zh.txt --out-srt out/test_zh.srt.

Asserts the 3 files exist, are non-empty, and VTT is monotonic.

Keep existing unit tests; just fix imports/paths.

6) Tooling & env

.venv: keep project-scoped venv in this folder; add/update Makefile targets:

make venv

make dev (installs dev extras)

make test

make build (wheel + sdist)

make api (runs uvicorn with loquilex.api.server:app)

direnv: provide .envrc that activates .venv and loads .env if present. Provide .env.example with new LX_ keys.

.gitignore: ensure it ignores .venv/, out/, model caches, and build artifacts.

7) Rename in docs & strings

Update README.md, comments, and any user-visible strings from “Greenfield” to “LoquiLex”.

Keep a short migration note section explaining the rename and env prefix change (GF_ → LX_ with fallback).

8) Build & run checklist (scriptable)

Provide a scripted set of commands (as comments at the end of the PR) that you validate locally:

# 1) Create venv & install
python3 -m venv .venv && source .venv/bin/activate
pip install --upgrade pip
pip install -e .[dev]

# 2) Quick smoke
python -m loquilex.cli.wav_to_vtt --wav tests/assets/short.wav --out out/asr_en.vtt
python -m loquilex.cli.vtt_to_zh --vtt out/asr_en.vtt --out-text out/asr_zh.txt --out-srt out/asr_zh.srt
pytest -q

# 3) API
python -m loquilex.api.server  # or: uvicorn loquilex.api.server:app --port 8000
# (manually hit /models, /self-test, start a session, verify /out/<sid>/ artifacts)

9) Acceptance criteria

All imports/paths renamed to loquilex.*; no lingering greenfield or python -m greenfield.

Env uses LX_ with GF_ fallback (documented).

pip install -e . works; console scripts exist and run.

Tests & smoke pass; VTT monotonicity preserved.

API and WS flow operational; artifacts land in out/<sid>/ under this repo.

.venv and direnv scoped to the project folder; no external path bleed.

10) Deliverables

A single PR/commit series with:

Updated code, tests, docs, and tooling per steps above.

A short MIGRATION.md summarizing rename and env changes.

A final “How I verified” section (commands + brief outputs).

If anything is ambiguous or blocked (e.g., missing files in this folder), list the blockers at the top and proceed with the rest.

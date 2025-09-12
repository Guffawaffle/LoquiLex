# Task: Fix Ruff E402/F811 in `tests/conftest.py` while preserving offline stubs

Our current `tests/conftest.py` trips Ruff with:
- **E402**: imports not at top of file (imports appear after executable code)
- **F811**: duplicate imports of `os`/`pytest`

We must make the file Ruff-clean **without** losing the offline-first testing behavior (fake `faster_whisper`, fake `transformers`, and patched `Translator`).

## Goals
- Resolve all **E402** and **F811** in `tests/conftest.py`.
- Keep tests fully offline and deterministic (no network calls).
- Maintain green `pytest` and green `ruff`.

## Approach
- Move *all* imports to the top of the module (stdlib → third-party → local).
- Eliminate duplicate imports.
- Defer all executable patching to a `pytest_sessionstart()` hook so imports remain at top-level and we still install fakes before any test code runs.
- Keep environment variables enforced in the same hook (or via an autouse fixture if preferred) — but avoid mid-file imports.

## Required Changes

### 1) Replace `tests/conftest.py` with this Ruff-clean version
```python
# tests/conftest.py
# Enforce offline, install fake modules, and patch translator deterministically.

from __future__ import annotations

import os
import sys
import types
import pytest

from tests.fakes import fake_mt, fake_whisper


def _install_fakes() -> None:
    """Install fake modules into sys.modules before app code imports them."""

    # Fake faster_whisper
    fake_faster_whisper = types.ModuleType("faster_whisper")
    fake_faster_whisper.WhisperModel = fake_whisper.WhisperModel
    # Do not overwrite if a real/other stub already exists
    sys.modules.setdefault("faster_whisper", fake_faster_whisper)

    # Fake transformers
    fake_transformers = types.ModuleType("transformers")

    class DummyModel:
        def __init__(self, *args, **kwargs) -> None: ...
        def to(self, *args, **kwargs):
            return self
        def eval(self):
            return self
        def generate(self, *args, **kwargs):
            # Return deterministic token ids
            return [[1, 2, 3]]

    class DummyTokenizer:
        src_lang = "eng_Latn"
        def __init__(self, *args, **kwargs) -> None: ...
        def __call__(self, text, **kwargs):
            return {"input_ids": [[1, 2, 3]], "attention_mask": [[1, 1, 1]]}

    # Minimal surface used by our code/tests
    fake_transformers.AutoModelForSeq2SeqLM = DummyModel
    fake_transformers.AutoTokenizer = DummyTokenizer
    fake_transformers.M2M100ForConditionalGeneration = DummyModel
    fake_transformers.M2M100Tokenizer = DummyTokenizer

    sys.modules.setdefault("transformers", fake_transformers)


def _set_offline_env() -> None:
    """Force offline behavior for tests."""
    os.environ.setdefault("HF_HUB_OFFLINE", "1")
    os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")
    os.environ.setdefault("HF_HUB_DISABLE_TELEMETRY", "1")
    os.environ.setdefault("LOQUILEX_OFFLINE", "1")


def _patch_translator() -> None:
    """Patch our Translator to the fake implementation after fakes are installed."""
    # Import after fakes are installed so downstream imports see our stubs.
    import loquilex.mt.translator as mt  # noqa: WPS433 (allowed here intentionally)
    mt.Translator = fake_mt.Translator


def pytest_sessionstart(session: pytest.Session) -> None:
    """
    Pytest lifecycle hook that runs before any tests are collected.
    We:
      1) enforce offline env
      2) install fake modules (faster_whisper, transformers)
      3) patch the Translator to the fake
    """
    _set_offline_env()
    _install_fakes()
    _patch_translator()
Why this fixes Ruff:

All imports are at the very top (E402 resolved).

No duplicate import os/import pytest lines (F811 resolved).

Executable changes (sys.modules edits, env mutations) happen inside functions
called by the pytest_sessionstart hook, not at module top level.

2) Keep CI env (already added)
Ensure CI jobs still export:

ini
Copy code
HF_HUB_OFFLINE=1
TRANSFORMERS_OFFLINE=1
HF_HUB_DISABLE_TELEMETRY=1
LOQUILEX_OFFLINE=1
Verification
Run Ruff:

bash
Copy code
ruff check .
Expect 0 errors.

Run tests (no network):

bash
Copy code
pytest -v
Expect all tests green; no firewall warnings; no external downloads.

Acceptance Criteria
ruff check . returns no E402/F811 (or other new) errors.

pytest -v passes entirely in a hermetic environment.

No external DNS or HTTP calls are observed in CI logs.

Deliverables
Updated tests/conftest.py (as above).

.github/copilot/current-task-deliverables.md including:

Ruff output before/after.

Full pytest logs.

Confirmation of no external calls.

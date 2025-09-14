# tests/conftest.py
# Enforce offline, install fake modules, and patch translator deterministically.

from __future__ import annotations

import os
import socket
import sys
import types
import pytest

from tests.fakes import fake_mt, fake_whisper
from tests.fakes.fake_streaming_asr import FakeStreamingASR
from tests.fakes.fake_audio import fake_capture_stream


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
        def __init__(self, *_args, **_kwargs) -> None: ...
        def to(self, *_args, **_kwargs):
            return self

        def eval(self):
            return self

        def generate(self, *_args, **_kwargs):
            # Return deterministic token ids
            return [[1, 2, 3]]

    class DummyTokenizer:
        src_lang = "eng_Latn"

        def __init__(self, *_args, **_kwargs) -> None: ...
        def __call__(self, _text, **_kwargs):
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
    import loquilex.mt.translator as mt  # (allowed here intentionally)

    mt.Translator = fake_mt.Translator


def _patch_streaming_asr() -> None:
    """Patch StreamingASR to use fake for offline testing."""
    try:
        import loquilex.asr.stream as asr_stream

        asr_stream.StreamingASR = FakeStreamingASR
    except ImportError:
        # Module might not exist yet during early tests
        pass


def _patch_audio_capture() -> None:
    """Patch audio capture to use fake for offline testing."""
    try:
        import loquilex.audio.capture as audio_capture

        audio_capture.capture_stream = fake_capture_stream
    except ImportError:
        # Module might not exist yet during early tests
        pass


@pytest.fixture
def forbid_network(monkeypatch):
    real_create_connection = socket.create_connection

    def guarded(address, *args, **kwargs):
        host = address[0] if isinstance(address, tuple) else address
        if host not in {"127.0.0.1", "::1", "localhost"}:
            raise RuntimeError(f"Blocked outbound connection to {host}")
        return real_create_connection(address, *args, **kwargs)

    monkeypatch.setattr(socket, "create_connection", guarded, raising=True)


def pytest_sessionstart(session: pytest.Session) -> None:  # noqa: ARG001
    """
    Pytest lifecycle hook that runs before any tests are collected.
    We:
      1) enforce offline env
      2) install fake modules (faster_whisper, transformers)
      3) patch the Translator to the fake
      4) patch StreamingASR to the fake
      5) patch audio capture to the fake
    """
    _set_offline_env()
    _install_fakes()
    _patch_translator()
    _patch_streaming_asr()
    _patch_audio_capture()

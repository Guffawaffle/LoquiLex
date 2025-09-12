import sys
from pathlib import Path

# Add project root to sys.path so `import greenfield` works even if pytest
# sets the working dir to the tests package.
ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# Install fake modules to prevent network access
import types
from tests.fakes import fake_mt, fake_whisper

# Fake faster_whisper
fake_faster_whisper = types.ModuleType("faster_whisper")
fake_faster_whisper.WhisperModel = fake_whisper.WhisperModel
sys.modules["faster_whisper"] = fake_faster_whisper

# Fake transformers
fake_transformers = types.ModuleType("transformers")
# Add dummy classes to prevent import errors
class DummyModel:
    def __init__(self, *args, **kwargs):
        pass
    def to(self, *args, **kwargs):
        return self
    def eval(self):
        return self
    def generate(self, *args, **kwargs):
        return [[1, 2, 3]]  # dummy tokens

class DummyTokenizer:
    def __init__(self, *args, **kwargs):
        pass
    def __call__(self, text, **kwargs):
        return {"input_ids": [[1, 2, 3]], "attention_mask": [[1, 1, 1]]}
    src_lang = "eng_Latn"

fake_transformers.AutoModelForSeq2SeqLM = DummyModel
fake_transformers.AutoTokenizer = DummyTokenizer
fake_transformers.M2M100ForConditionalGeneration = DummyModel
fake_transformers.M2M100Tokenizer = DummyTokenizer
sys.modules["transformers"] = fake_transformers

# Also patch the Translator class
import loquilex.mt.translator
loquilex.mt.translator.Translator = fake_mt.Translator

import os
import pytest

import os
import pytest
from tests.fakes import fake_mt, fake_whisper


@pytest.fixture(autouse=True)
def offline_env():
    """Set environment variables to enforce offline mode during tests."""
    original_env = {}
    env_vars = {
        'HF_HUB_OFFLINE': '1',
        'TRANSFORMERS_OFFLINE': '1',
        'HF_HUB_DISABLE_TELEMETRY': '1',
        'LOQUILEX_OFFLINE': '1',
    }
    for key, value in env_vars.items():
        original_env[key] = os.environ.get(key)
        os.environ[key] = value
    yield
    # Restore original values
    for key, value in original_env.items():
        if value is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = value

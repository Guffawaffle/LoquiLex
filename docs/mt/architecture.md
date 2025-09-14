# MT Architecture: Modular Design

**Issue:** MT: NLLB/M2M CTranslate2 integration for EN↔ZH (#30)
**Scope:** Modular, extensible, and tracked with a compatibility matrix. No new models added here—this defines how we expand safely later.

---

## Design Goals

- **Plug-and-Play Providers:** Add/replace MT engines without touching call sites.
- **Tokenizer Abstraction:** Swap tokenizers (HF/NLLB/M2M) independently of provider runtime.
- **Language Variants:** Clean handling of `en`, `zh-Hans` (Simplified), `zh-Hant` (Traditional).
- **Offline-First:** Lazy-import heavy deps (e.g., `ctranslate2`) so base code loads offline.
- **Single-Source-of-Truth:** Machine-readable compatibility data + human-readable table.
- **Contract Tests:** Every provider must pass the same behavior suite.

---

## Package Layout (proposed)

```
loquilex/
  mt/
    core/
      __init__.py
      types.py              # Lang, QualityMode, Errors
      protocol.py           # MTProvider, TokenizerAdapter Protocols
      registry.py           # Provider registry + factories
      util.py               # small helpers (lang mapping, timing)
    tokenizers/
      __init__.py
      nllb.py               # NLLBTokenizerAdapter
      m2m.py                # M2MTokenizerAdapter
    providers/
      __init__.py
      ct2_nllb.py           # CT2 provider using NLLB tokenizer
      ct2_m2m.py            # CT2 provider using M2M tokenizer
    tests/
      test_contract_provider.py  # shared contract tests for all providers
docs/
  mt/
    compatibility.md
    compatibility.yaml
```

- `api/server.py` depends only on `loquilex.mt.core.protocol` and the `registry`, never on provider internals.
- `ctranslate2` is **only** imported inside `providers/ct2_*.py` (lazy import on first use).

---

## Core Protocols (contract)

```python
# loquilex/mt/core/protocol.py
from __future__ import annotations
from typing import Iterable, Iterator, Protocol, TypedDict, Literal, runtime_checkable

Lang = Literal["en", "zh-Hans", "zh-Hant"]
QualityMode = Literal["realtime", "quality"]

class ProviderCapabilities(TypedDict):
    family: str                # "nllb" | "m2m" | "custom"
    model_name: str            # e.g., "nllb-200-d600M"
    directions: list[tuple[Lang, Lang]]
    requires_target_prefix: bool
    device_types: list[str]    # ["cpu","cuda"]
    compute_types: list[str]   # ["int8","int8_float16","float16","float32"]
    supports_chunked: bool
    supports_streaming_partials: bool

@runtime_checkable
class TokenizerAdapter(Protocol):
    def encode(self, text: str, src: Lang) -> list[str]: ...
    def target_prefix(self, tgt: Lang) -> list[str]: ...
    def decode(self, tokens: list[str]) -> str: ...

@runtime_checkable
class MTProvider(Protocol):
    def translate_text(self, text: str, src: Lang, tgt: Lang, *, quality: QualityMode = "realtime") -> str: ...
    def translate_chunked(self, chunks: Iterable[str], src: Lang, tgt: Lang, *, quality: QualityMode = "realtime") -> Iterator[str]: ...
    def capabilities(self) -> ProviderCapabilities: ...
```

**Notes**
- `Lang` is explicit (no free-form strings). JSON config may accept `"zh"` and map to `"zh-Hans"` by default.
- `TokenizerAdapter` is a hard boundary. Providers must not rely on HF specifics outside the adapter.

---

## Registry (factory pattern)

```python
# loquilex/mt/core/registry.py
from typing import Callable, Dict
from .protocol import MTProvider

ProviderFactory = Callable[[], MTProvider]
_registry: Dict[str, ProviderFactory] = {}

def register_provider(name: str, factory: ProviderFactory) -> None:
    _registry[name] = factory

def available() -> list[str]:
    return sorted(_registry.keys())

def create(name: str) -> MTProvider:
    try:
        return _registry[name]()
    except KeyError:
        raise ValueError(f"Unknown MT provider: {{name}}")
```

- CT2 providers call `register_provider("ct2-nllb", factory)` / `register_provider("ct2-m2m", factory)` at import time.
- `api/server.py` asks `create(os.getenv("LX_MT_PROVIDER", "ct2-nllb"))` and never imports CT2 directly.

---

## Tokenizer Adapters (examples)

```python
# loquilex/mt/tokenizers/m2m.py
from .common import Lang
from transformers import AutoTokenizer

class M2MTokenizerAdapter:
    def __init__(self, name: str = "facebook/m2m100_418M"):
        self._tok = AutoTokenizer.from_pretrained(name)

    def encode(self, text: str, src: Lang) -> list[str]:
        self._tok.src_lang = "en" if src == "en" else "zh"
        return self._tok.convert_ids_to_tokens(self._tok.encode(text))

    def target_prefix(self, tgt: Lang) -> list[str]:
        code = "en" if tgt == "en" else "zh"
        return [self._tok.lang_code_to_token[code]]

    def decode(self, tokens: list[str]) -> str:
        # strip possible target lang token at position 0
        ids = self._tok.convert_tokens_to_ids(tokens[1:] if tokens and tokens[0].startswith("__") else tokens)
        return self._tok.decode(ids, skip_special_tokens=True)
```

```python
# loquilex/mt/tokenizers/nllb.py
from .common import Lang
from transformers import AutoTokenizer

FLORES = {"en": "eng_Latn", "zh-Hans": "zho_Hans", "zh-Hant": "zho_Hant"}

class NLLBTokenizerAdapter:
    def __init__(self, name: str = "facebook/nllb-200-distilled-600M"):
        self._tok = AutoTokenizer.from_pretrained(name)

    def encode(self, text: str, src: Lang) -> list[str]:
        self._tok.src_lang = FLORES[src]
        return self._tok.convert_ids_to_tokens(self._tok.encode(text))

    def target_prefix(self, tgt: Lang) -> list[str]:
        return [FLORES[tgt]]

    def decode(self, tokens: list[str]) -> str:
        # NLLB may emit the language tag as first token; drop if present
        if tokens and tokens[0] in FLORES.values():
            tokens = tokens[1:]
        ids = self._tok.convert_tokens_to_ids(tokens)
        return self._tok.decode(ids, skip_special_tokens=True)
```

> These adapters wrap HF details so providers can stay clean.

---

## Config Surface (stable, extensible)

- `LX_MT_PROVIDER` = `ct2-nllb` | `ct2-m2m` (provider key registered in `registry.py`)
- `LX_MT_MODEL_DIR` = path to CT2 artifacts
- `LX_MT_DEVICE` = `auto` | `cpu` | `cuda`
- `LX_MT_COMPUTE_TYPE` = `int8_float16` | `int8` | `float16` | `float32`
- `LX_MT_WORKERS` = int (default 2)
- `LX_LANG_VARIANT_ZH` = `Hans` | `Hant` (default `Hans`)

No breaking changes needed to add future providers/models/tokenizers.

---

## Contract Tests (shared across providers)

- **API parity:** `translate_text`, `translate_chunked` behavior identical across providers.
- **Lang routing:** en↔zh-Hans/zh-Hant round-trips through adapters (prefix injected, BOS stripped).
- **Offline safety:** importing `loquilex.mt` must not import heavy deps.
- **Timing budget:** smoke test asserts upper bounds for small chunks (skipped in CI by default).

---

## Notes

- Streaming-partials are a later concern; `translate_chunked` yields finals per chunk now.
- Compatibility data is the audit trail for “what works with what.” CI will gate on schema validity later.

---

_Last updated: 2025-09-14 18:26_

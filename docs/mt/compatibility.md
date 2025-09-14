# MT Compatibility Matrix

> Source of truth: keep this table in `docs/mt/compatibility.md` and mirror the data in `docs/mt/compatibility.yaml`.

| Family | Model | Tokenizer Adapter | Directions | Target Prefix | Device Types | Compute Types | GPU Mem (approx) | CPU Viable | Notes | Status |
|---|---|---|---|---|---|---|---:|:---:|---|---|
| NLLB | nllb-200-distilled-600M | NLLBTokenizerAdapter | en↔zh-Hans/zh-Hant | Yes (FLORES) | cpu,cuda | int8, int8_float16, float16, float32 | ~2–3 GB | Yes | Good baseline; fast on 8GB GPUs | ✅ Working (Phase 1) |
| M2M100 | m2m100_418M | M2MTokenizerAdapter | en↔zh-Hans/zh-Hant* | Yes (BOS code) | cpu,cuda | int8, int8_float16, float16, float32 | ~1.5–2 GB | Yes | Uses zh code (maps to Hans) | ✅ Working (Phase 1) |

\* For Traditional (`zh-Hant`) with M2M100, we may apply a post-conversion step or detok mapping; mark as experimental at first.

---

_Last updated: 2025-09-14 18:26_

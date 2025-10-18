LoquiLex demo: mic -> ASR -> MT pipeline

Overview
--------
This small demo streams audio from your microphone (or a WAV file) through the local StreamingASR and MT provider, then writes event logs and a translated transcript under the configured OUT_ROOT.

Environment knobs
-----------------
- LX_ASR_LANG: language code for ASR (default: en). Use `auto` if supported by your ASR model.
- LX_MT_SOURCE_LANG: source language for MT (default: en)
- LX_MT_TARGET_LANG: target language for MT (default: zh_Hans)
- LX_MT_PROVIDER: MT provider name (default from config; e.g., ct2-nllb)
- LX_MT_MODEL_DIR / LX_MT_MODEL: provider-specific model location knobs
- LLX_OUT_DIR: root output directory (default: loquilex/out)

Quickstart
----------
Mic demo (30s):

```bash
source .venv/bin/activate
loquilex-demo --duration 30
```

WAV demo (headless, CI-friendly):

```bash
source .venv/bin/activate
loquilex-demo --wav tests/fixtures/hello_en.wav --duration 3
```

Outputs
-------
For a session created at runtime, files will be written to:

- $OUT_ROOT/session-<ts>-<id>/events.jsonl  # one JSON event per line (asr.* and mt.*)
- $OUT_ROOT/session-<ts>-<id>/transcript.txt  # plain text translated finals (one per line)

JSONL schema (mt.final example):

```json
{
  "type": "mt.final",
  "seq": 1,
  "segment_id": "segabcd12",
  "text_src": "Hello world",
  "text_tgt": "你好，世界",
  "provider": "ct2-nllb",
  "src_lang": "en",
  "tgt_lang": "zh_Hans",
  "t0_ms": 1697040000000,
  "t1_ms": 1697040000310,
  "latency_ms": 310.2
}
```

Notes
-----
- Local-first only: demo uses local faster-whisper/CTranslate2 and local MT providers. No network calls.
- If `sounddevice` is not installed or no input device is available, use `--wav`.
- Retention sweeper applies to the OUT_ROOT directory and will clean old sessions per configured TTL.

# LoquiLex

History-preserving extraction of the `greenfield` module from rt-whisper, renamed to `loquilex`.

## Quickstart


```bash
python -m venv .venv
source .venv/bin/activate
pip install -U pip build
pip install -e .

# Run tests (ensure loquilex is discoverable):

## Environment Variables

LoquiLex uses `LX_*` as the canonical environment prefix. Legacy `GF_*` variables are supported as a silent fallback until v0.3.0 (with a one-time deprecation warning).

**Migration note:**
GF_* envs will be removed in v0.3. Use LX_* going forward. If only GF_* is set, a one-time DeprecationWarning will be issued.

### Supported LX_ variables
- LX_ASR_LANGUAGE, LX_ASR_MODEL, LX_ASR_COMPUTE, LX_ASR_BEAM, LX_ASR_VAD, LX_ASR_NO_SPEECH, LX_ASR_LOGPROB, LX_ASR_COND_PREV, LX_ASR_SAMPLE_RATE, LX_ASR_CPU_THREADS
- LX_PAUSE_FLUSH_SEC, LX_SEGMENT_MAX_SEC, LX_PARTIAL_DEBOUNCE_MS
- LX_NLLB_MODEL, LX_M2M_MODEL, LX_MT_BEAMS, LX_MT_NO_REPEAT, LX_MT_MAX_INPUT, LX_MT_MAX_NEW
- LX_OUT_DIR, LX_DEVICE, LX_DECODE_INTERVAL_SEC, LX_PARTIAL_DEBOUNCE_SEC, LX_MAX_BUFFER_SEC, LX_MAX_LINES, LX_PARTIAL_WORD_CAP, LX_SAVE_AUDIO, LX_SAVE_AUDIO_PATH

### Legacy GF_ → LX_ mapping
| GF_*                | LX_*                 |
GF_ is deprecated; use LX_ going forward. If only GF_ is set, a one-time DeprecationWarning will be issued.

Supported environment variables (prefix LX_):
- LX_ASR_LANGUAGE, LX_ASR_MODEL, LX_ASR_COMPUTE, LX_ASR_BEAM, LX_ASR_VAD, LX_ASR_NO_SPEECH, LX_ASR_LOGPROB, LX_ASR_COND_PREV, LX_ASR_SAMPLE_RATE, LX_ASR_CPU_THREADS
- LX_PAUSE_FLUSH_SEC, LX_SEGMENT_MAX_SEC, LX_PARTIAL_DEBOUNCE_MS
- LX_NLLB_MODEL, LX_M2M_MODEL, LX_MT_BEAMS, LX_MT_NO_REPEAT, LX_MT_MAX_INPUT, LX_MT_MAX_NEW
- LX_OUT_DIR, LX_DEVICE, LX_DECODE_INTERVAL_SEC, LX_PARTIAL_DEBOUNCE_SEC, LX_MAX_BUFFER_SEC, LX_MAX_LINES, LX_PARTIAL_WORD_CAP, LX_SAVE_AUDIO, LX_SAVE_AUDIO_PATH

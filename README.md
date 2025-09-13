# LoquiLex

History-preserving extraction of the `greenfield` module from rt-whisper, renamed to `loquilex`.

## Quickstart

```bash
make dev-minimal  # Lightweight, offline-first setup
make run-ci-mode  # Fast, lightweight checks (mirrors CI-lite)
make run-local-ci # Full dependencies for local development
```

### Offline-first Development

Set LX_SKIP_MODEL_PREFETCH=1 to prevent any model downloads during setup. This ensures a fully offline-friendly environment.

#### Environment flags

| Variable              | Purpose                              | Default |
|-----------------------|--------------------------------------|---------|
| LX_SKIP_MODEL_PREFETCH | Skip any model prefetch during setup | unset   |

See CI-TESTING.md for details on run-ci-mode vs run-local-ci.

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
## Development

### Quick CI Testing

For fast local testing without heavy ML dependencies (saves 1.5GB+ bandwidth):

```bash
make run-ci-mode  # Uses lightweight deps, same as GitHub Actions
```

For full local development with all ML packages:

```bash
make run-local-ci  # Full dependencies for local development
```

See [CI-TESTING.md](CI-TESTING.md) for detailed testing documentation.

### Environment Variable Migration

| GF_*                | LX_*                 |
GF_ is deprecated; use LX_ going forward. If only GF_ is set, a one-time DeprecationWarning will be issued.

Supported environment variables (prefix LX_):
- LX_ASR_LANGUAGE, LX_ASR_MODEL, LX_ASR_COMPUTE, LX_ASR_BEAM, LX_ASR_VAD, LX_ASR_NO_SPEECH, LX_ASR_LOGPROB, LX_ASR_COND_PREV, LX_ASR_SAMPLE_RATE, LX_ASR_CPU_THREADS
- LX_PAUSE_FLUSH_SEC, LX_SEGMENT_MAX_SEC, LX_PARTIAL_DEBOUNCE_MS
- LX_NLLB_MODEL, LX_M2M_MODEL, LX_MT_BEAMS, LX_MT_NO_REPEAT, LX_MT_MAX_INPUT, LX_MT_MAX_NEW
- LX_OUT_DIR, LX_DEVICE, LX_DECODE_INTERVAL_SEC, LX_PARTIAL_DEBOUNCE_SEC, LX_MAX_BUFFER_SEC, LX_MAX_LINES, LX_PARTIAL_WORD_CAP, LX_SAVE_AUDIO, LX_SAVE_AUDIO_PATH

### CI / Docker Parity

The repository includes a minimal, cache-friendly CI image definition in `Dockerfile.ci` for reproducing GitHub Actions locally without copying the full source into the image.

Build the CI image (expect a very small build context thanks to `.dockerignore`):

```bash
DOCKER_BUILDKIT=1 docker build -f Dockerfile.ci -t loquilex-ci . --progress=plain
```

Run the full CI parity sequence (lint, format check, type check, unit/integration, e2e):

```bash
docker run --rm -v "$(pwd)":/app loquilex-ci ./scripts/ci-gh-parity.sh
```

If you need an interactive shell inside the container:

```bash
docker run --rm -it -v "$(pwd)":/app loquilex-ci bash
```

The container sets offline-friendly environment flags (`HF_HUB_OFFLINE`, `TRANSFORMERS_OFFLINE`, etc.) to avoid unintended network access during tests.

Tooling (ruff, black, mypy, pytest) is always installed even if not explicitly pinned in requirements files.

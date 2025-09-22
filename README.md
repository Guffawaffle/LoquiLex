# LoquiLex

## Quickstart

### Local Development
```bash
make dev-minimal  # Lightweight, offline-first setup
make run-ci-mode  # Fast, lightweight checks (mirrors CI-lite)
make run-local-ci # Full dependencies for local development
```

### Docker Deployment
```bash
# CPU-only deployment
make docker-run

# GPU-enabled deployment (WSL2/Docker Desktop)
make docker-gpu
```

FastAPI + UI available at http://localhost:8000

For detailed Docker setup instructions, see [Docker Deployment Guide](docs/DOCKER.md).

### Offline-first Development

Set LX_SKIP_MODEL_PREFETCH=1 to prevent any model downloads during setup. This ensures a fully offline-friendly environment.

#### Environment flags

| Variable              | Purpose                              | Default |
|-----------------------|--------------------------------------|---------|
| LX_SKIP_MODEL_PREFETCH | Skip any model prefetch during setup | unset   |

See CI-TESTING.md for details on run-ci-mode vs run-local-ci.

# Run tests (ensure loquilex is discoverable):

## Environment Variables

LoquiLex uses `LX_*` as the canonical environment prefix.

### Supported LX_ variables
- LX_ASR_LANGUAGE, LX_ASR_MODEL, LX_ASR_COMPUTE, LX_ASR_BEAM, LX_ASR_VAD, LX_ASR_NO_SPEECH, LX_ASR_LOGPROB, LX_ASR_COND_PREV, LX_ASR_SAMPLE_RATE, LX_ASR_CPU_THREADS
- LX_PAUSE_FLUSH_SEC, LX_SEGMENT_MAX_SEC, LX_PARTIAL_DEBOUNCE_MS
- LX_NLLB_MODEL, LX_M2M_MODEL, LX_MT_BEAMS, LX_MT_NO_REPEAT, LX_MT_MAX_INPUT, LX_MT_MAX_NEW
- LX_MT_PROVIDER, LX_MT_MODEL_DIR, LX_MT_DEVICE, LX_MT_COMPUTE_TYPE, LX_MT_WORKERS, LX_LANG_VARIANT_ZH
- LX_OUT_DIR, LX_DEVICE, LX_DECODE_INTERVAL_SEC, LX_PARTIAL_DEBOUNCE_SEC, LX_MAX_BUFFER_SEC, LX_MAX_LINES, LX_PARTIAL_WORD_CAP, LX_SAVE_AUDIO, LX_SAVE_AUDIO_PATH

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

### Environment Variables

Supported environment variables (prefix LX_ only):
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

## Development Workflow

LoquiLex uses a structured GitHub Copilot/Codex workflow for development tasks:

- **Task Management**: Tasks initiated via prompts in `.github/prompts/` or maintainer directives
- **Quality Gates**: Automated linting, formatting, type checking, and testing
- **Deliverables**: Live log in `docs/deliverables/.live.md` (gitignored) with archived copies tracked under `docs/deliverables/ARCHIVE/PR-<number>-<YYYYMMDD>-<shortsha>.md`
- **Branch Strategy**: Feature branches with imperative commit messages

See `AGENTS.md` for complete workflow documentation.

We’re prompt-driven (Codex/Copilot). See `AGENTS.md` and `.github/prompts/*`. The live working log is `docs/deliverables/.live.md` (ignored), archived under `docs/deliverables/ARCHIVE/` on merge.

## Documentation

### Quick Start
- **[Quick Start Guide](./docs/quickstart.md)** - Get running in under 5 minutes
- **[MVP User Guide](./docs/mvp-user-guide.md)** - Complete workflows and production setup
- **[Troubleshooting Guide](./docs/troubleshooting.md)** - Common issues, offline-first behavior, and solutions

### Architecture & Development

LoquiLex follows a **JS-first architecture** where JavaScript orchestrates workflows and Python executes ML tasks:

- **[JS-First Architecture Guide](./docs/architecture/js-first.md)** - Core principles, patterns, and implementation guidelines
- **[API Contracts Reference](./docs/contracts/README.md)** - Comprehensive WebSocket, REST, and data type contracts
- **[Orchestration Module](./loquilex/ui/web/src/orchestration/README.md)** - Client-side utilities and patterns
- **[Resource Management](./docs/RESOURCE_MANAGEMENT.md)** - Expectations for clean shutdown of threads, tasks, and subprocesses

### API Contracts & Integration

Detailed contracts for all JS ↔ Python communication:

- **[WebSocket Protocol](./docs/contracts/websocket.md)** - Message envelope format, session management
- **[ASR Streaming](./docs/contracts/asr-streaming.md)** - Audio streaming and transcription events
- **[Translation Events](./docs/contracts/translation.md)** - Real-time translation message types
- **[Downloads API](./docs/contracts/downloads-api.md)** - Model download orchestration
- **[Device Testing](./docs/contracts/device-testing.md)** - Audio device validation endpoints
- **[Export Operations](./docs/contracts/exports.md)** - Caption export and file generation
- **[Session Management](./docs/contracts/session-management.md)** - Connection lifecycle and recovery
- **[Models API](./docs/contracts/models-api.md)** - Model management and configuration

### Key Features

- **Event Throttling**: 2-10 Hz frequency capping prevents UI jank
- **Resilient WebSockets**: Automatic reconnection with bounded queues
- **Web Workers**: Background processing for progress smoothing and ETA calculations
- **Type Safety**: End-to-end TypeScript contracts for all JS ↔ Python communication
- **Offline-First**: Works without internet once models are cached locally

## Versioning & Releases

### Versioning Strategy

LoquiLex uses **Semantic Versioning (SemVer)**:

- **MAJOR.MINOR.PATCH** (e.g., `1.2.3`)
- **MAJOR**: Breaking changes, API incompatibilities
- **MINOR**: New features, backward compatible
- **PATCH**: Bug fixes, backward compatible

Current version: **0.1.0** (initial development release)

### Release Process

1. **Version Bump**: Update version in `pyproject.toml`
2. **CHANGELOG**: Document changes in `CHANGELOG.md` using format:
   ```markdown
   ## [VERSION] - YYYY-MM-DD

   ### Added
   - New features

   ### Changed
   - Changes in existing functionality

   ### Fixed
   - Bug fixes

   ### Removed
   - Removed features
   ```

3. **Tag Release**: Create git tag `v[VERSION]`
4. **Publish**: Build and publish to PyPI (future)

### CHANGELOG Maintenance

- Keep `CHANGELOG.md` updated with every PR that affects functionality
- Use imperative mood for change descriptions
- Group changes by type (Added, Changed, Fixed, Removed)
- Reference issue/PR numbers when applicable

## Security

LoquiLex is maintained with an automated security posture:
- **CodeQL** (advanced workflow) for static analysis
- **Dependabot** + **Dependency Review** for supply-chain changes
- **gitleaks** for CI secret sweeps (with Push Protection enabled in GitHub)
- **OpenSSF Scorecards** for repo hygiene and best practices

See [SECURITY.md](./SECURITY.md) for how to report vulnerabilities.

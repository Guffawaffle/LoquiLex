# LoquiLex Quick Start

Get up and running with LoquiLex in under 5 minutes.

## Installation

### Prerequisites
- Python 3.10+ 
- Git
- 2GB+ free disk space (for ML models)

### Quick Setup

```bash
# Clone the repository
git clone https://github.com/Guffawaffle/LoquiLex.git
cd LoquiLex

# Lightweight setup (offline-first, no model downloads)
make dev-minimal

# OR full setup with ML models
make dev-ml-cpu
```

### Environment Configuration

Set key environment variables:

```bash
# Offline development (skip model downloads)
export LX_SKIP_MODEL_PREFETCH=1

# Output directory
export LX_OUT_DIR="./output"

# ASR settings
export LX_ASR_MODEL="tiny.en"    # Or base.en, small.en
export LX_ASR_LANGUAGE="en"
```

## Basic Usage

### 1. Audio File to Captions

Convert a WAV file to VTT captions:

```bash
loquilex-wav-to-vtt --wav input.wav --out captions.vtt
```

### 2. Captions to Chinese Translation

Translate VTT captions to Chinese:

```bash
loquilex-vtt-to-zh --vtt captions.vtt --out-text chinese.txt --out-srt chinese.srt
```

### 3. Live Captioning (CLI)

Real-time English to Chinese captioning:

```bash
loquilex-live --out-prefix ./output/session
```

Press `Ctrl+C` to stop and save files.

### 4. WebSocket Server (for JS apps)

Start the FastAPI server for web applications:

```bash
# Install with web server support
python -m pip install -e .

# Start server
python -m loquilex.api.server
```

Access at: http://localhost:8000

## Architecture Overview

LoquiLex follows a **JS-first architecture**:

- **JavaScript orchestrates** - Controls workflows, UI, and user interactions
- **Python executes** - Handles ML inference, audio processing, and compute tasks
- **Clear boundaries** - Well-defined WebSocket/REST contracts

See [JS-First Architecture Guide](./architecture/js-first.md) for details.

## Offline Mode

LoquiLex is designed to work offline-first:

```bash
# Skip all model downloads during setup
export LX_SKIP_MODEL_PREFETCH=1
make dev-minimal

# Run tests without network access
make test
```

Perfect for:
- Development in constrained environments
- CI/CD pipelines with bandwidth limits
- Air-gapped deployments

## What's Next?

- **[MVP User Guide](./mvp-user-guide.md)** - Complete workflows and advanced usage
- **[Architecture Guide](./architecture/js-first.md)** - Technical deep-dive
- **[API Contracts](./contracts/README.md)** - WebSocket and REST API reference

## Getting Help

- Check [Troubleshooting](./mvp-user-guide.md#troubleshooting) section in the MVP User Guide
- Review [CI-TESTING.md](../CI-TESTING.md) for development environment issues
- Open an issue on GitHub for bugs or feature requests

---

**Next: [MVP User Guide](./mvp-user-guide.md)** for comprehensive workflows.
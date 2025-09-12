# Testing in CI-Identical Environment

This document explains how to test LoquiLex in the exact same environment as the CI pipeline.

## Quick Start

The easiest way is to use the Make target:

```bash
make run-local-ci
```

This runs all CI checks locally with identical environment variables and commands.

## Available Methods

### 1. Make Targets (Recommended)

```bash
# Run all CI checks locally (lint, typecheck, tests)
make run-local-ci

# Run just the tests with CI environment (backward-compatible alias)
make test-ci
```

### 2. Bash Script

```bash
# Run the comprehensive CI replication script
./scripts/run-local-ci.sh
```

### 3. Docker Container (Most Exact)

```bash
# Build CI-identical container
docker build -f Dockerfile.ci -t loquilex-ci .

# Run all CI checks
docker run --rm loquilex-ci

# Interactive debugging
docker run --rm -it loquilex-ci bash
```

### 4. Act (GitHub Actions Runner)

```bash
# Install act first (see script for instructions)
./scripts/run-with-act.sh

# Or manually:
act                    # Run all jobs
act -j unit           # Run just unit tests
act -j e2e            # Run just e2e tests
```

## CI Environment Details

### Exact Configuration:
- **OS**: `ubuntu-latest` (Ubuntu 22.04)
- **Python**: `3.12.3` (exact version)
- **Dependencies**: Installed via `requirements.txt` + `requirements-dev.txt`

### Environment Variables:
```bash
HF_HUB_OFFLINE=1
TRANSFORMERS_OFFLINE=1
HF_HUB_DISABLE_TELEMETRY=1
LOQUILEX_OFFLINE=1
```

### Test Commands:
```bash
# Unit/Integration tests (excludes e2e by default)
pytest -m "not e2e" -vv -rA --maxfail=1 --disable-warnings

# E2E tests (explicit opt-in)
pytest -q --maxfail=1 -m e2e --disable-warnings --no-header --no-summary
```

### Lint Commands:
```bash
ruff check .           # Code linting
black --check .        # Code formatting check
mypy loquilex || true  # Type checking (allowed to fail)
```

## Key Differences from Development

1. **Test Separation**: CI runs unit tests separately from e2e tests
2. **Offline Mode**: All external network calls are blocked
3. **Verbose Output**: CI uses different pytest flags for better CI logging
4. **Dependency Management**: Uses both `requirements.txt` and `requirements-dev.txt`

## Troubleshooting

### Python Version Mismatch
If you don't have Python 3.12.3 exactly:
```bash
# Install with pyenv
pyenv install 3.12.3
pyenv local 3.12.3

# Or use Docker method for exact match
```

### Network Issues
The CI environment is completely offline. If tests fail locally but pass in CI:
```bash
# Check for network calls by running with network guard
pytest -v  # Should block any external connections
```

### Dependency Issues
CI installs dependencies in a specific order:
```bash
python -m pip install -U pip
pip install -r requirements.txt      # Core dependencies
pip install -r requirements-dev.txt  # Dev dependencies (includes httpx for e2e)
```

## Files Created

- `scripts/run-local-ci.sh` - Comprehensive CI replication script
- `scripts/ci-local.sh` - Hardened CI script (legacy)
- `scripts/run-with-act.sh` - GitHub Actions local runner
- `Dockerfile.ci` - Exact CI environment container
- `Makefile` (updated) - Added `run-local-ci` and `test-ci` targets

All methods should produce identical results to the CI pipeline.
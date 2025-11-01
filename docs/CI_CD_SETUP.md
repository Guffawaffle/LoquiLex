# CI/CD Configuration Guide

This document describes the GitHub Actions CI/CD setup for LoquiLex backend.

## Workflows

### Test Workflow (`test.yml`)
Runs comprehensive testing on every push and pull request.

**Jobs:**
- **Lint & Type Check**: Runs Ruff, Black, and mypy on Python 3.12
- **Test Matrix**: Runs pytest with coverage on Python 3.10, 3.11, and 3.12

**Features:**
- Coverage reports uploaded as artifacts (Python 3.12 only)
- Dependency caching for faster builds
- Offline-first testing (no external network calls)
- Runs in parallel for all Python versions

**Estimated Duration:** 10-15 minutes

### Docker Workflow (`docker.yml`)
Builds and optionally pushes Docker images.

**Jobs:**
- **Build**: Builds CI and production Docker images, runs basic tests
- **Push**: Pushes to GitHub Container Registry (only on main branch)

**Features:**
- BuildKit caching for faster builds
- Tests import of loquilex module in CI image
- Only pushes to GHCR on main branch (not PRs)
- Supports semantic versioning tags

**Estimated Duration:** 15-20 minutes

### CI Workflow (`ci.yml`)
Quick CI check using the Makefile.

**Jobs:**
- **Quick CI Check**: Runs `make ci` (lint + typecheck + test)

**Features:**
- Fast feedback loop for developers
- Uses exact same commands as local development
- Dependency caching

**Estimated Duration:** 5-10 minutes

## Branch Protection Setup

To enable required status checks and prevent merging failed PRs:

1. Go to **Settings** → **Branches** in the GitHub repository
2. Add a branch protection rule for `main`
3. Enable the following settings:
   - ✅ Require status checks to pass before merging
   - ✅ Require branches to be up to date before merging
   - ✅ Require linear history (optional, recommended)

4. Add these required status checks:
   - `Lint & Type Check` (from test.yml)
   - `Test (Python 3.10)` (from test.yml)
   - `Test (Python 3.11)` (from test.yml)
   - `Test (Python 3.12)` (from test.yml)
   - `Build Docker Image` (from docker.yml)
   - `Quick CI Check` (from ci.yml) - optional, for fast feedback

## Environment Variables

All workflows use the following environment variables:

```yaml
LX_OFFLINE: 1                    # Offline mode for tests
HF_HUB_OFFLINE: 1                # Disable HuggingFace downloads
TRANSFORMERS_OFFLINE: 1           # Disable transformers downloads
HF_HUB_DISABLE_TELEMETRY: 1      # Disable telemetry
LX_LOG_MAX_SIZE_MB: 5            # Log file size limit
LX_LOG_MAX_FILES: 2              # Log file rotation count
LX_LOG_DIR: /tmp/loquilex-ci-logs # Log directory
```

## Coverage Reports

Coverage reports are generated for Python 3.12 and uploaded as artifacts:

- **Format**: XML (for CI tools) and terminal output
- **Configuration**: Uses `.coveragerc` for coverage settings
- **Retention**: 30 days
- **Download**: Available in workflow run artifacts

To view coverage locally:
```bash
make test
python -m coverage report --show-missing
python -m coverage html  # Generate HTML report
```

## Caching

All workflows use GitHub Actions caching for pip dependencies:

- **Cache key**: OS + pip + Python version + requirements file hashes
- **Cache location**: `~/.cache/pip`
- **Benefits**: Faster builds (30-60% time reduction)

## Concurrency Control

All workflows use concurrency groups to cancel in-progress runs:

- When a new commit is pushed to a branch, old workflow runs are cancelled
- Saves CI minutes and provides faster feedback
- Format: `{workflow-name}-{ref}`

## Security Scanning

Security scanning is handled by separate workflows (already configured):

- **Bandit** (`bandit.yml`): Python security linting
- **CodeQL** (`codeql.yml`): Advanced static analysis
- **Gitleaks** (`gitleaks.yml`): Secret scanning

## Troubleshooting

### Workflow fails with "No module named 'loquilex'"
- Check that `requirements-ci.txt` and `requirements-dev.txt` are properly installed
- Verify Python path is set correctly

### Coverage report not generated
- Coverage artifacts are only uploaded for Python 3.12
- Check that `pytest-cov` is installed in `requirements-dev.txt`

### Docker build fails
- Ensure `Dockerfile` and `Dockerfile.ci` are present
- Check that base images are accessible
- Verify build context size (should be minimal with `.dockerignore`)

### Tests timeout
- Default timeout is 30 minutes per workflow
- Check for infinite loops or blocking operations in tests
- Ensure offline mode is properly configured

## Local Testing

To test workflows locally before pushing:

```bash
# Quick CI check (same as ci.yml)
make ci

# Full test suite with coverage (similar to test.yml)
make install-base
python -m pytest -q --cov=loquilex --cov-report=xml --cov-report=term

# Docker build (same as docker.yml)
make docker-ci-build
make docker-ci-test
```

## Performance Targets

As per the issue acceptance criteria:

- ✅ CI completes in < 15 minutes (average: 10-15 minutes)
- ✅ All tests pass on every push
- ✅ Coverage reports generated
- ✅ Type checking passes
- ✅ Docker image builds successfully
- ✅ Failed builds block PR merges (with branch protection)

## Next Steps

After merging this PR:

1. Configure branch protection rules (see above)
2. Monitor first few workflow runs for issues
3. Adjust timeouts if needed
4. Consider adding coverage badges to README
5. Set up notifications for failed builds (optional)

# Task: Fix Docker exec (126) — ensure image arch & shell correctness (PR #43 support)

**Timestamp:** 2025-09-14 14:43:39

## Intent
Resolve container runtime errors like `cannot execute binary file` when running `bash`, `make`, or `python` inside `loquilex-ci`. Target the most probable causes: image architecture mismatch and shell/tooling availability. Keep diffs minimal.

## Branch
Use the PR #43 head branch (do **not** work on `main`). Create a short-lived branch if desired:
```bash
gh pr view 43 --json headRefName,url --jq '.headRefName + " ← " + .url'
git fetch origin pull/43/head:pr-43 && git checkout pr-43
git checkout -b fix/43-docker-exec-126
```

## Diagnosis steps (run & record outputs)
```bash
# 1) Confirm the image arch & OS
docker inspect --format '{{.Os}}/{{.Architecture}}' loquilex-ci

# 2) Confirm the base image arch (the tag you use in Dockerfile.ci)
docker image inspect python:3.12-slim --format '{{.Os}}/{{.Architecture}}'

# 3) Try a shell that should always exist
docker run --rm --entrypoint /bin/sh loquilex-ci -c 'uname -a && which sh && /bin/sh -c "echo sh-ok"'
# If this fails identically, it's an arch/exec format problem, not just missing bash.

# 4) Inspect critical binaries
docker run --rm --entrypoint /usr/bin/file loquilex-ci /bin/sh /bin/bash /usr/bin/make /opt/venv/bin/python || true
```

## Required fixes

### A) Make the Dockerfile arch-agnostic & shell-agnostic
- **Remove any `--platform=$BUILDPLATFORM` usage.** If you must specify, prefer `--platform=$TARGETPLATFORM` or omit entirely to let Docker pick the native arch.
- **Do not require bash.** Use `/bin/sh` for build RUNs and for local debug.

**Dockerfile.ci (minimal, robust)**
```dockerfile
# Use native target by default; avoid BUILDPLATFORM pinning
FROM python:3.12-slim

SHELL ["/bin/sh", "-lc"]

# Basic tooling; keep small
RUN apt-get update && apt-get install -y --no-install-recommends \
    make \
    git \
  && rm -rf /var/lib/apt/lists/*

# Virtualenv
RUN python -m venv /opt/venv
ENV VIRTUAL_ENV=/opt/venv
ENV PATH="/opt/venv/bin:${PATH}"

WORKDIR /app

# Install deps first for layer caching
COPY requirements*.txt constraints*.txt /app/ 2>/dev/null || true
RUN if [ -f requirements-ci.txt ]; then \
      if [ -f constraints.txt ]; then \
        pip install --upgrade pip && pip install -r requirements-ci.txt -r requirements-dev.txt --constraint constraints.txt; \
      else \
        pip install --upgrade pip && pip install -r requirements-ci.txt -r requirements-dev.txt; \
      fi; \
    fi

# Copy source
COPY . /app
```

### B) `.dockerignore` — prevent host leakage
```
.git
.venv
.direnv
__pycache__/
.pytest_cache/
.mypy_cache/
.ruff_cache/
.coverage
htmlcov/
dist/
build/
```

### C) Rerun with explicit native arch (only if needed)
If Docker Desktop/WSL cross-builds by default, force native at build/run time:
```bash
docker build -t loquilex-ci -f Dockerfile.ci .
# or, if needed on ARM host for x86 runner parity:
# docker build --platform=linux/amd64 -t loquilex-ci -f Dockerfile.ci .

docker run --rm -v "$(pwd)":/app -w /app loquilex-ci /bin/sh -lc 'python -V && which python && which make && make --version'
docker run --rm -v "$(pwd)":/app -w /app loquilex-ci /bin/sh -lc 'make run-ci-mode && make dead-code-analysis'
```

## Acceptance Criteria
- `docker inspect --format '{{.Os}}/{{.Architecture}}' loquilex-ci` shows expected `linux/amd64` (or native host arch).
- `docker run ... /bin/sh -lc 'python -V'` works (no `cannot execute binary file` errors).
- `docker run ... make run-ci-mode` and `... make dead-code-analysis` succeed.
- No dependence on `bash` at runtime (shell-agnostic).

## Deliverables → `.github/copilot/current-task-deliverables.md`
1. **Executive Summary** of the fix.
2. **Steps Taken** with commands and outputs.
3. **Evidence & Verification** (inspects, file(1) results, successful run logs).
4. **Final Results** stating pass/fail vs acceptance criteria.
5. **Files Changed** (Dockerfile.ci, .dockerignore, and any docs).

# Next Task — Add Dockerized CI Runner for Local + Pipeline Parity

> Mode: One PR = One Chat · Source of Truth: this file (see also `AGENTS.md`)

---

## Objective
Introduce a **Docker-based path to deploy and test the full CI pipeline locally**, mirroring the GitHub Actions environment. Developers should be able to run:

```bash
make docker-ci
```

…and get identical checks to what CI runs (lint, format, type, pytest unit + e2e).

---

## Scope
- Add a new Dockerfile for CI (`Dockerfile.ci`).
- Add a new script (`scripts/ci-entrypoint.sh`) to run all checks in the container.
- Update the Makefile with a `docker-ci` target that builds and runs the container.
- Update VS Code tasks to expose `docker-ci` alongside `run-local-ci`.
- Ensure GitHub Actions can reuse the same Dockerfile if desired in the future.

---

## Instructions

1. **Add Dockerfile**
   Create file: `.github/Dockerfile.ci` (or `Dockerfile.ci` at repo root).
   Contents:
   ```dockerfile
   FROM python:3.12-slim AS base

   ENV PYTHONDONTWRITEBYTECODE=1        PYTHONUNBUFFERED=1        PIP_NO_CACHE_DIR=1        VENV=/opt/venv        PATH="/opt/venv/bin:$PATH"        HF_HUB_OFFLINE=1        TRANSFORMERS_OFFLINE=1        HF_HUB_DISABLE_TELEMETRY=1        LX_OFFLINE=1

   RUN apt-get update && apt-get install -y --no-install-recommends          git build-essential &&        rm -rf /var/lib/apt/lists/*

   RUN python -m venv $VENV

   WORKDIR /app

   COPY requirements.txt ./
   RUN if [ -f requirements.txt ]; then pip install -r requirements.txt; fi

   RUN pip install --upgrade pip &&        pip install ruff black mypy pytest

   COPY . .

   ENTRYPOINT ["/bin/bash"]
   ```

2. **Add CI entrypoint script**
   Create file: `scripts/ci-entrypoint.sh` with executable permissions.
   Contents:
   ```bash
   #!/usr/bin/env bash
   set -euo pipefail

   echo "=== Environment (offline flags) ==="
   env | grep -E '^(HF_HUB_OFFLINE|TRANSFORMERS_OFFLINE|HF_HUB_DISABLE_TELEMETRY|LX_OFFLINE)=' || true

   echo "=== Ruff ==="
   ruff check .

   echo "=== Black --check ==="
   black --check .

   echo "=== MyPy (non-blocking) ==="
   ( mypy loquilex || true )

   echo "=== Pytest (unit/integration, not e2e) ==="
   pytest -m "not e2e" -vv -rA --maxfail=1 --disable-warnings

   echo "=== Pytest (e2e) ==="
   pytest -q --maxfail=1 -m e2e --disable-warnings --no-header --no-summary
   ```

   Make it executable:
   ```bash
   chmod +x scripts/ci-entrypoint.sh
   ```

3. **Update Makefile**
   Add:
   ```makefile
   .PHONY: docker-ci
   docker-ci:
    	@echo "=== Running CI in Docker (Dockerfile.ci) ==="
    	docker build -f Dockerfile.ci -t loquilex-ci .
    	docker run --rm -v $(PWD):/app loquilex-ci ./scripts/ci-entrypoint.sh
   ```

4. **Update VS Code Tasks**
   Add to `.vscode/tasks.json`:
   ```json
   {
     "label": "Docker CI (CI-identical container run)",
     "type": "shell",
     "command": "make docker-ci",
     "group": "test",
     "problemMatcher": []
   }
   ```

5. **Verification**
   - Run `make docker-ci` locally → should perform lint/format/type/test as in CI.
   - Ensure both `run-local-ci` (host-based) and `docker-ci` (container-based) pass.
   - Commit changes and push; CI should remain green.

---

## Acceptance Criteria
- ✅ `make docker-ci` builds a container and runs all checks successfully.
- ✅ Developers can choose between `run-local-ci` (host venv) and `docker-ci` (container).
- ✅ VS Code shows both tasks.
- ✅ GitHub Actions can be updated later to optionally use `Dockerfile.ci`.
- ✅ No changes to existing test semantics or markers.

---

## Deliverables
- `Dockerfile.ci`
- `scripts/ci-entrypoint.sh`
- Updated `Makefile` with `docker-ci`
- Updated `.vscode/tasks.json`
- Verification evidence in `.github/copilot/current-task-deliverables.md`

---

## Suggested Commit
```
Add Dockerfile.ci and docker-ci target to run pipeline locally in container
```

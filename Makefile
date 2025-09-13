### Makefile is the canonical interface for local, CI, and IDE tasks.
### Update commands ONLY here (do not hand-edit CI workflow or VS Code tasks).
### Targets: fmt, lint, typecheck, unit, e2e, ci (aggregates), plus legacy/util extras.

VENV?=.venv
PY=$(VENV)/bin/python
PIP=$(VENV)/bin/pip

.PHONY: venv install dev fmt lint typecheck unit e2e ci test run-local-ci run-ci-mode test-ci run-wav run-zh clean docker-ci docker-ci-test docker-ci-build docker-ci-run docker-ci-shell

venv:
	python3 -m venv $(VENV)
	$(PIP) install -U pip

install: venv
	$(PIP) install -r requirements.txt

dev: install
	$(PIP) install -r requirements-dev.txt

fmt:
	$(VENV)/bin/black loquilex tests

lint:
	$(VENV)/bin/ruff check loquilex tests

typecheck:
	$(VENV)/bin/mypy loquilex

# Unit tests (non-e2e) quick mode; add extra flags via PYTEST_ADDOPTS if needed
unit:
	$(PY) -m pytest -q -m "not e2e"

# E2E tests (verbose). Timeout override applied by invoking: make e2e PYTEST_ADDOPTS=--timeout=45
e2e:
	$(PY) -m pytest -m e2e -vv -rA

# Aggregate CI-style sequence
ci: fmt lint typecheck unit e2e

# --- CI-identical local run (canonical) ---
.PHONY: run-local-ci run-ci-mode test-ci
OFFLINE_ENV = HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 HF_HUB_DISABLE_TELEMETRY=1 LOQUILEX_OFFLINE=1

run-local-ci:
	@echo "=== Running ALL CI checks locally with full ML dependencies ==="
	@CI_MODE=local scripts/run-local-ci.sh

run-ci-mode:
	@echo "=== Running CI checks with lightweight dependencies (CI simulation) ==="
	@CI_MODE=ci scripts/run-local-ci.sh

# Back-compat alias (uses full local mode by default)
test-ci: run-local-ci

run-wav:
	$(PY) -m loquilex.cli.wav_to_vtt --wav ../../test.wav --out loquilex/out/asr_en.vtt

run-zh:
	$(PY) -m loquilex.cli.vtt_to_zh --vtt loquilex/out/asr_en.vtt --out-text loquilex/out/live_zh.txt --out-srt loquilex/out/live_zh.srt

clean:
	rm -rf .pytest_cache out .coverage

.PHONY: docker-ci
docker-ci:
	@echo "=== Running CI in Docker (Dockerfile.ci) ==="
	docker build -f Dockerfile.ci -t loquilex-ci .
	docker run --rm -v $(PWD):/app loquilex-ci ./scripts/ci-entrypoint.sh
# --- CI-parity via Docker (canonical: docker-ci-test) ---
.PHONY: docker-ci-test docker-ci-build docker-ci-run docker-ci-shell
DOCKER_IMAGE ?= loquilex-ci
PWD_SHELL := $(shell pwd)

docker-ci-build:
	@echo "=== Building CI-parity image ==="
	DOCKER_BUILDKIT=1 docker build -f Dockerfile.ci -t $(DOCKER_IMAGE) . --progress=plain

docker-ci-run:
	@echo "=== Running CI-parity test sequence in container ==="
	docker run --rm -v "$(PWD_SHELL)":/app $(DOCKER_IMAGE) ./scripts/ci-gh-parity.sh

docker-ci-test: docker-ci-build docker-ci-run

docker-ci-shell: docker-ci-build
	@echo "=== Opening interactive shell in CI-parity container (repo mounted at /app) ==="
	docker run --rm -it -v "$(PWD_SHELL)":/app $(DOCKER_IMAGE)

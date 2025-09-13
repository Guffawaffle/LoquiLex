# Lightweight dev profile: installs only base+dev deps and prefetches tiny model.

## ------------------------------
## Config
VENV        ?= .venv
USE_VENV    ?= 1                  # set to 0 in CI to use system python
ASR_MODEL   ?= tiny.en            # override: make dev-minimal ASR_MODEL=base.en

## ------------------------------
## Interpreter/PIP selection (prefer venv if present)
VENV_PY     := $(VENV)/bin/python
VENV_PIP    := $(VENV)/bin/pip
SYS_PY      := $(shell command -v python3 || command -v python || echo python)
SYS_PIP     := $(shell command -v pip3 || command -v pip || echo pip)
PY          := $(if $(wildcard $(VENV_PY)),$(VENV_PY),$(SYS_PY))
PIP         := $(if $(wildcard $(VENV_PIP)),$(VENV_PIP),$(SYS_PIP))

## ------------------------------
## Phony targets
.PHONY: help install-venv install-base install-ml-minimal install-ml-cpu \
        prefetch-asr models-tiny dev dev-minimal dev-ml-cpu \
        lint fmt fmt-check typecheck test unit test-e2e e2e ci clean \
        docker-ci docker-ci-build docker-ci-run docker-ci-test docker-ci-shell

help:
	@echo "Targets:"
	@echo "  dev-minimal      - base+dev deps + minimal ML (no torch/CUDA) + tiny model prefetch"
	@echo "  dev              - alias of dev-minimal"
	@echo "  dev-ml-cpu       - add CPU-only ML stack and prefetch tiny model"
	@echo "  lint / fmt / typecheck / test / e2e / ci"
	@echo "Vars:"
	@echo "  USE_VENV=0       - use system Python instead of creating .venv (good for CI)"
	@echo "  ASR_MODEL=...    - model to prefetch (default: tiny.en)"

## ------------------------------
## Bootstrap / installs

# Create venv if requested and missing; otherwise ensure system Python has pip
install-venv:
	@echo ">> Ensuring Python environment is ready"
	@if [ "$(USE_VENV)" = "0" ]; then \
		echo "Using system Python: $(SYS_PY)"; \
		"$(SYS_PY)" -m pip --version >/dev/null || { echo "ERROR: pip not available for $(SYS_PY)"; exit 1; }; \
	else \
		if [ ! -x "$(VENV_PY)" ]; then \
			echo "Creating venv at $(VENV)"; \
			"$(SYS_PY)" -m venv "$(VENV)"; \
		fi; \
		"$(VENV_PY)" -m pip install -U pip setuptools wheel; \
	fi

# Install dev/test deps used by lint/format/typecheck/test
install-base: install-venv
	@echo ">> Installing base dev/test dependencies"
	@if [ "$(USE_VENV)" = "0" ] || [ ! -x "$(VENV_PIP)" ]; then PIP_CMD="$(SYS_PIP)"; else PIP_CMD="$(VENV_PIP)"; fi; \
	$$PIP_CMD install -r requirements-ci.txt -r requirements-dev.txt -c constraints.txt

# Minimal ML stack (no torch/CUDA) to keep Codespaces lightweight
install-ml-minimal: install-venv
	@if [ "$(USE_VENV)" = "0" ] || [ ! -x "$(VENV_PIP)" ]; then PIP_CMD="$(SYS_PIP)"; else PIP_CMD="$(VENV_PIP)"; fi; \
	$$PIP_CMD install -r requirements-ml-minimal.txt -c constraints.txt

# Optional: CPU ML additions (still no heavy GPU wheels)
install-ml-cpu: install-venv
	@if [ "$(USE_VENV)" = "0" ] || [ ! -x "$(VENV_PIP)" ]; then PIP_CMD="$(SYS_PIP)"; else PIP_CMD="$(VENV_PIP)"; fi; \
	$$PIP_CMD install -r requirements-ml-cpu.txt -c constraints.txt

## ------------------------------
## Model prefetch (tiny by default)

# Prefetch a specific ASR model (default tiny.en) to avoid on-demand downloads
prefetch-asr:
    @echo "[prefetch-asr] Downloading ASR model: $(ASR_MODEL)"
    @ASR_MODEL="$(ASR_MODEL)" $(PY) -c ' \
import os; \
from faster_whisper import WhisperModel; \
model = os.environ.get("ASR_MODEL") or os.environ.get("GF_ASR_MODEL") or "tiny.en"; \
print(f"Downloading {model}..."); \
WhisperModel(model, device="cpu", compute_type="int8"); \
print(f"[prefetch-asr] downloaded/prepared: {model}")'


# Prefetch only the tiny model unless explicitly skipped
models-tiny:
	@if [ "$${LX_SKIP_MODEL_PREFETCH:-0}" = "1" ]; then \
		echo "[dev] Skipping tiny model prefetch (LX_SKIP_MODEL_PREFETCH=1)"; \
	else \
		$(MAKE) prefetch-asr ASR_MODEL=tiny.en; \
	fi

## ------------------------------
## Dev presets

# Lightweight developer setup (safe for Codespaces)
dev-minimal: install-base
	@if [ -f "requirements-dev.txt" ]; then \
		. .venv/bin/activate; pip install -r requirements-dev.txt -c constraints.txt; \
	else \
		echo "[dev-minimal] requirements-dev.txt not found; skipping dev deps."; \
	fi
	@echo "[dev-minimal] Skipping model prefetch (offline-first)."
	@echo "[dev-minimal] Development environment ready."

# Keep `dev` as the default developer entrypoint
dev: dev-minimal
	@true

# Opt-in CPU ML stack (no torch/CUDA)
dev-ml-cpu: install-base install-ml-cpu models-tiny
	@echo "✅ dev-ml-cpu ready."

## ------------------------------
## Quality gates & tests

lint: install-base
	$(PY) -m ruff check loquilex tests

fmt: install-base
	$(PY) -m black loquilex tests

fmt-check: install-base
	$(PY) -m black --check --diff loquilex tests

typecheck: install-base
	$(PY) -m mypy loquilex

test: install-base
	$(PY) -m pytest -q

unit: test

test-e2e: install-base
	$(PY) -m pytest -m e2e -q

# Verbose E2E (add extra flags via: make e2e PYTEST_FLAGS="--timeout=45")
e2e: install-base
	$(PY) -m pytest -m e2e -vv -rA $(PYTEST_FLAGS)

ci: lint typecheck test
	@echo "✓ CI checks passed locally"

## ------------------------------
## Cleanup

clean:
	rm -rf .pytest_cache .coverage $(VENV) dist build

## ------------------------------
## Docker CI parity (optional)

DOCKER_IMAGE ?= loquilex-ci
PWD_SHELL := $(shell pwd)

docker-ci:
	@echo "=== Running CI in Docker (Dockerfile.ci) ==="
	docker build -f Dockerfile.ci -t $(DOCKER_IMAGE) .
	docker run --rm -v "$(PWD_SHELL)":/app $(DOCKER_IMAGE) ./scripts/ci-entrypoint.sh

docker-ci-build:
	@echo "=== Building CI-parity image ==="
	DOCKER_BUILDKIT=1 docker build -f Dockerfile.ci -t $(DOCKER_IMAGE) . --progress=plain

docker-ci-run:
	@echo "=== Running CI-parity test sequence in container ==="
	docker run --rm -v "$(PWD_SHELL)":/app $(DOCKER_IMAGE) ./scripts/ci-gh-parity.sh

docker-ci-test: docker-ci-build docker-ci-run

docker-ci-shell: docker-ci-build
	@echo "=== Shell in CI-parity container (repo mounted at /app) ==="
	docker run --rm -it -v "$(PWD_SHELL)":/app $(DOCKER_IMAGE) bash

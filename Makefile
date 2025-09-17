# Alias used by GitHub Actions to run the full CI pipeline
.PHONY: run-ci-mode
run-ci-mode: ci
# Lightweight dev profile: installs only base+dev deps and prefetches tiny model.

## ------------------------------
## Config
VENV        ?= .venv
USE_VENV    ?= 1                  # set to 0 in CI to use system python
ASR_MODEL   ?= tiny.en            # override: make dev-minimal ASR_MODEL=base.en
PYTEST_FLAGS ?=                   # extra flags for `make e2e`, e.g. --timeout=45

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
        docker-ci docker-ci-build docker-ci-run docker-ci-test docker-ci-shell \
        docker-build docker-run docker-gpu docker-stop docker-clean \
        sec-scan dead-code-analysis dead-code-report clean-artifacts \
        ui-setup ui-dev ui-build ui-start ui-test ui-e2e

help:
	@echo "Targets:"
	@echo "  dev-minimal      - base+dev deps only; no model prefetch (offline-first)"
	@echo "  dev              - alias of dev-minimal"
	@echo "  dev-ml-cpu       - add CPU-only ML stack and prefetch tiny model"
	@echo "  lint / fmt / typecheck / test / e2e / ci"
	@echo "  ui-setup         - install UI dependencies"
	@echo "  ui-dev           - start dev server with proxy to FastAPI"
	@echo "  ui-build         - build UI for production"
	@echo "  ui-start         - start FastAPI serving built UI"
	@echo "  ui-test          - run UI unit tests"
	@echo "  ui-e2e           - run UI end-to-end tests"
	@echo "  docker-build     - build production Docker image (CPU-only)"
	@echo "  docker-run       - run LoquiLex in Docker (CPU-only)"
	@echo "  docker-gpu       - run LoquiLex in Docker with GPU support"
	@echo "  docker-stop      - stop running Docker containers"
	@echo "  docker-clean     - remove Docker containers and images"
	@echo "  dead-code-analysis - run comprehensive dead code detection tools"
	@echo "  dead-code-report   - generate reports locally (no CI gating)"
	@echo "  clean-artifacts    - remove all generated artifacts"
	@echo "Vars:"
	@echo "  USE_VENV=0       - use system Python instead of creating .venv (good for CI)"
	@echo "  ASR_MODEL=...    - model to prefetch (default: tiny.en)"
	@echo "  LX_SKIP_MODEL_PREFETCH=1 - skip model prefetch (for faster CI runs)"
	@echo "  LX_SKIP_DEAD_CODE_REPORT=1 - skip dead code report generation (for faster CI runs)"


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
	if [ -f "constraints.txt" ]; then \
		$$PIP_CMD install -r requirements-ci.txt -r requirements-dev.txt -c constraints.txt; \
	else \
		echo "[install-base] constraints.txt not found; installing without constraints"; \
		$$PIP_CMD install -r requirements-ci.txt -r requirements-dev.txt; \
	fi

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
model = os.environ.get("ASR_MODEL") or os.environ.get("LX_ASR_MODEL") or "tiny.en"; \
print(f"Downloading {model}..."); \
WhisperModel(model, device="cpu", compute_type="int8"); \
print(f"[prefetch-asr] downloaded/prepared: {model}")'


# Prefetch only the tiny model unless explicitly skipped
models-tiny:
	@if echo "$${LX_SKIP_MODEL_PREFETCH:-0}" | grep -Eiq '^(1|true|yes|on)$'; then \
		echo "[dev] Skipping tiny model prefetch (LX_SKIP_MODEL_PREFETCH set to truthy value)"; \
	else \
		$(MAKE) prefetch-asr ASR_MODEL=tiny.en; \
	fi

## ------------------------------
## Dev presets

# Lightweight developer setup (safe for Codespaces)
dev-minimal: install-base
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

test:
	LX_OFFLINE=${LX_OFFLINE:-1} HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 HF_HUB_DISABLE_TELEMETRY=1 pytest -q

test-online:
	HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 HF_HUB_DISABLE_TELEMETRY=1 LX_OFFLINE=0 pytest -q

unit: test

test-e2e: install-base
	$(PY) -m pytest -m e2e -q

# Verbose E2E (add extra flags via: make e2e PYTEST_FLAGS="--timeout=45")
e2e: install-base
	$(PY) -m pytest -m e2e -vv -rA $(PYTEST_FLAGS)

ci: lint typecheck test
	@echo "✓ CI checks passed locally"

.PHONY: run-ci-mode
run-ci-mode: ci

## ------------------------------
## Cleanup

clean:
	rm -rf .pytest_cache .coverage $(VENV) dist build
	cd ui/app && rm -rf node_modules dist .vite || true

## ------------------------------
## UI targets

# Install UI dependencies
ui-setup:
	@echo "[ui-setup] Installing UI dependencies (npm ci)"
	cd ui/app && npm ci

# Start development server with proxy to FastAPI
ui-dev: ui-setup
	@echo "[ui-dev] Starting development servers"
	@echo "Starting FastAPI server in background..."
	@LX_API_PORT=$${LX_API_PORT:-8000} LX_UI_PORT=$${LX_UI_PORT:-5173} \
	$(PY) -m loquilex.api.server &
	@echo "Waiting for FastAPI to start..."
	@sleep 3
	@echo "Starting Vite dev server..."
	@cd ui/app && LX_API_PORT=$${LX_API_PORT:-8000} LX_UI_PORT=$${LX_UI_PORT:-5173} npm run dev

# Build UI for production
ui-build: ui-setup
	@echo "[ui-build] Building UI for production"
	cd ui/app && npm run build

# Start FastAPI serving built UI
ui-start: ui-build
	@echo "[ui-start] Starting FastAPI with built UI"
	LX_API_PORT=$${LX_API_PORT:-8000} $(PY) -m loquilex.api.server

# Run UI unit tests
ui-test: ui-setup
	@echo "[ui-test] Running UI unit tests"
	cd ui/app && npm run test

# Run UI end-to-end tests
ui-e2e: ui-build
	@echo "[ui-e2e] Running UI end-to-end tests"
	@echo "Starting FastAPI server for e2e tests..."
	@LX_API_PORT=$${LX_API_PORT:-8000} $(PY) -m loquilex.api.server &
	@SERVER_PID=$$!; \
	sleep 5; \
	cd ui/app && npm run e2e; \
	E2E_EXIT=$$?; \
	kill $$SERVER_PID 2>/dev/null || true; \
	exit $$E2E_EXIT

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

# Secret scanning using Gitleaks
sec-scan:
	@docker run --rm -v "$(PWD_SHELL)":/repo zricethezav/gitleaks:latest detect -s /repo --no-git --redact

## ------------------------------
## Docker local runtime (production)

DOCKER_IMAGE_PROD ?= loquilex
DOCKER_CONTAINER_NAME ?= loquilex-app

docker-build:
	@echo "=== Building production Docker image (CPU-only) ==="
	@echo "First building UI..."
	$(MAKE) ui-build
	@echo "Building Docker image..."
	DOCKER_BUILDKIT=1 docker build -t $(DOCKER_IMAGE_PROD):latest . --progress=plain

docker-build-gpu:
	@echo "=== Building production Docker image with GPU support ==="
	@echo "First building UI..."
	$(MAKE) ui-build
	@echo "Building Docker image with GPU support..."
	DOCKER_BUILDKIT=1 docker build --build-arg INSTALL_GPU_SUPPORT=true -t $(DOCKER_IMAGE_PROD):gpu . --progress=plain

docker-run: docker-build
	@echo "=== Starting LoquiLex (CPU-only) ==="
	@echo "FastAPI + UI will be available at http://localhost:8000"
	docker-compose up -d
	@echo "Use 'make docker-logs' to view logs, 'make docker-stop' to stop"

docker-gpu: docker-build-gpu
	@echo "=== Starting LoquiLex with GPU support ==="
	@echo "FastAPI + UI will be available at http://localhost:8000"
	@echo "Requires: Docker with nvidia-container-runtime"
	INSTALL_GPU_SUPPORT=true docker-compose -f docker-compose.yml -f docker-compose.gpu.yml up -d
	@echo "Use 'make docker-logs' to view logs, 'make docker-stop' to stop"

docker-logs:
	@echo "=== Viewing LoquiLex container logs ==="
	docker-compose logs -f

docker-stop:
	@echo "=== Stopping LoquiLex containers ==="
	docker-compose down

docker-clean: docker-stop
	@echo "=== Removing LoquiLex containers and images ==="
	docker-compose down -v --rmi all --remove-orphans
	docker rmi $(DOCKER_IMAGE_PROD):latest $(DOCKER_IMAGE_PROD):gpu 2>/dev/null || true

docker-shell:
	@echo "=== Opening shell in running LoquiLex container ==="
	docker exec -it $(DOCKER_CONTAINER_NAME) /bin/bash

# Dead code analysis using multiple detection tools
dead-code-analysis: install-base
	@echo "=== Running comprehensive dead code analysis (WARN-ONLY) ==="
	- ./scripts/dead-code-analysis.sh || echo "[warn] dead code found (non-blocking)"
	@echo "== done =="

.PHONY: dead-code-report
dead-code-report:
	@bash scripts/dead-code-analysis.sh --report-only
	@echo "✅ Dead code reports generated in .artifacts/dead-code-reports/"

.PHONY: clean-artifacts
clean-artifacts:
	@rm -rf .artifacts || true

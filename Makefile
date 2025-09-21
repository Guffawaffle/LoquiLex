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
# Prefer venv when present unless USE_VENV=0 (explicitly request system Python)
PY          := $(if $(filter 0,$(USE_VENV)),$(SYS_PY),$(if $(wildcard $(VENV_PY)),$(VENV_PY),$(SYS_PY)))
PIP         := $(if $(filter 0,$(USE_VENV)),$(SYS_PIP),$(if $(wildcard $(VENV_PIP)),$(VENV_PIP),$(SYS_PIP)))

## ------------------------------
## PID Management Helpers
define pid_start
	@mkdir -p .pids
	@echo "[pid_start] Starting $(1) with PID file $(2)"
	@$(3) & echo $$! > $(2)
	@sleep 2
	@if [ -f "$(2)" ] && kill -0 $$(cat "$(2)") 2>/dev/null; then \
		echo "[pid_start] ✓ $(1) started (PID: $$(cat $(2)))"; \
	else \
		echo "[pid_start] ✗ Failed to start $(1)"; \
		rm -f "$(2)"; \
		exit 1; \
	fi
endef

define pid_stop
	@if [ -f "$(2)" ]; then \
		PID=$$(cat "$(2)"); \
		echo "[pid_stop] Stopping $(1) (PID: $$PID)"; \
		if kill -0 "$$PID" 2>/dev/null; then \
			kill "$$PID" 2>/dev/null || true; \
			sleep 1; \
			if kill -0 "$$PID" 2>/dev/null; then \
				echo "[pid_stop] Force killing $(1)"; \
				kill -9 "$$PID" 2>/dev/null || true; \
			fi; \
		fi; \
		rm -f "$(2)"; \
		echo "[pid_stop] ✓ $(1) stopped"; \
	else \
		echo "[pid_stop] No PID file for $(1), trying fallback..."; \
		$(3); \
	fi
endef

define pid_status
	@if [ -f "$(2)" ]; then \
		PID=$$(cat "$(2)"); \
		if kill -0 "$$PID" 2>/dev/null; then \
			echo "$(1): ✓ running (PID: $$PID)"; \
		else \
			echo "$(1): ✗ stale PID file (PID: $$PID not found)"; \
		fi; \
	else \
		echo "$(1): - no PID file"; \
	fi
endef

## ------------------------------
## Phony targets
.PHONY: help install-venv install-base install-ml-minimal install-ml-cpu \
        prefetch-asr models-tiny dev dev-minimal dev-ml-cpu \
        lint fmt fmt-check typecheck link-check test unit test-e2e e2e ci clean clean-logs \
        docker-ci docker-ci-build docker-ci-run docker-ci-test docker-ci-shell \
        docker-build docker-run docker-gpu docker-stop docker-clean docker-test \
        sec-scan dead-code-analysis dead-code-report clean-artifacts \
        ui-setup ui-dev ui-build ui-start ui-test ui-e2e ui-verify \
        api-start-bg ui-dev-bg ui-start-bg \
        stop-ui stop-api stop-ws stop-all stop-all-force \
        pids-status pids-clean-stale \
        install test-all qual-all

help:
	@echo "=== LoquiLex Make Targets ==="
	@echo ""
	@echo "Install:"
	@echo "  dev-minimal      - base+dev deps only; no model prefetch (offline-first)"
	@echo "  dev              - alias of dev-minimal"
	@echo "  dev-ml-cpu       - add CPU-only ML stack and prefetch tiny model"
	@echo "  lint / fmt / typecheck / link-check / test / e2e / ci"
	@echo "  ui-setup         - install UI dependencies"
	@echo "  ui-dev           - start dev server with proxy to FastAPI"
	@echo "  ui-dev-bg        - start UI dev server in background"
	@echo "  ui-build         - build UI for production"
	@echo "  ui-start         - start FastAPI serving built UI"
	@echo "  ui-start-bg      - start UI preview server in background"
	@echo "  ui-test          - run UI unit tests"
	@echo "  ui-e2e           - run UI end-to-end tests"
	@echo "  ui-verify        - run UI tests (unit + e2e when online)"
	@echo ""
	@echo "Services:"
	@echo "  api-start-bg     - start FastAPI server in background"
	@echo "  stop-ui          - stop UI servers"
	@echo "  stop-api         - stop API server"
	@echo "  stop-all         - stop all tracked services"
	@echo "  stop-all-force   - force stop all services"
	@echo "  pids-status      - show status of tracked processes"
	@echo "  pids-clean-stale - clean up stale PID files"
	@echo ""
	@echo "Clean:"
	@echo "  clean            - remove build artifacts and venv"
	@echo "  clean-artifacts  - remove generated artifacts"
	@echo ""
	@echo "Docker:"
	@echo "  docker-build     - build production Docker image (CPU-only)"
	@echo "  docker-run       - run LoquiLex in Docker (CPU-only)"
	@echo "  docker-gpu       - run LoquiLex in Docker with GPU support"
	@echo "  docker-stop      - stop running Docker containers"
	@echo "  docker-clean     - remove Docker containers and images"
	@echo ""
	@echo "Analysis:"
	@echo "  dead-code-analysis - run comprehensive dead code detection tools"
	@echo "  dead-code-report   - generate reports locally (no CI gating)"
	@echo ""
	@echo "=== Environment Variables ==="
	@echo "  LX_OFFLINE=1           - enable offline mode (skip network calls, e2e tests)"
	@echo "  LX_API_PORT=8000       - FastAPI server port"
	@echo "  clean-logs         - cleanup old log files (uses LX_LOG_DIR)"
	@echo "  LX_UI_PORT=5173        - Vite dev server port (4173 for preview)"
	@echo "  USE_VENV=0             - use system Python instead of creating .venv"
	@echo "  LX_ASR_MODEL=tiny.en   - ASR model to prefetch (preferred; falls back to ASR_MODEL if unset)"
	@echo "  ASR_MODEL=tiny.en      - (legacy) ASR model to prefetch"
	@echo "  LX_SKIP_MODEL_PREFETCH=1  - skip model prefetch (for faster CI)"
	@echo "  PYTEST_FLAGS=...       - extra flags for e2e tests"


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

link-check:
	@echo "=== Checking links in README.md and docs/ ==="
	@if ! command -v npm >/dev/null 2>&1; then \
		echo "❌ npm (Node.js) not found. Please install Node.js (https://nodejs.org/) and ensure 'npm' is in your PATH."; \
		exit 1; \
	fi; \
	if [ ! -f package.json ]; then \
		echo "Installing markdown-link-check (no package.json found)..."; \
		npm install --no-save markdown-link-check; \
	elif ! npm list markdown-link-check >/dev/null 2>&1; then \
		echo "Installing markdown-link-check..."; \
		npm install --no-save markdown-link-check; \
	fi; \
	FAILED=0; \
	for file in README.md $$(find docs -name "*.md"); do \
		echo "Checking $$file..."; \
		output=$$(npx markdown-link-check "$$file" --config .markdown-link-check.json 2>&1); \
		echo "$$output"; \
		if echo "$$output" | grep -q "ERROR:.*dead links found"; then \
			FAILED=1; \
		fi; \
	done; \
	if [ $$FAILED -eq 1 ]; then \
		echo "❌ Link check failed: dead links found"; \
		exit 1; \
	else \
		echo "✅ All links are valid"; \
	fi

test:
	LX_OFFLINE=${LX_OFFLINE:-1} HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 HF_HUB_DISABLE_TELEMETRY=1 $(PY) -m pytest -q

test-online:
	HF_HUB_OFFLINE=0 TRANSFORMERS_OFFLINE=0 HF_HUB_DISABLE_TELEMETRY=1 LX_OFFLINE=0 $(PY) -m pytest -q

unit: test

test-e2e: install-base
	$(PY) -m pytest -m e2e -q

# Verbose E2E (add extra flags via: make e2e PYTEST_FLAGS="--timeout=45")
e2e: install-base
	$(PY) -m pytest -m e2e -vv -rA $(PYTEST_FLAGS)

ci: lint typecheck test

# Resource leak testing
test-resource-leaks: install-base
	$(PY) -m pytest tests/test_resource_management.py -v --tb=short

# Comprehensive testing with resource monitoring
test-comprehensive: install-base
	$(PY) -W default::ResourceWarning -m pytest -v --tb=short
	@echo "✓ CI checks passed locally"

.PHONY: run-ci-mode
run-ci-mode: ci

## ------------------------------
## Cleanup

clean:
	rm -rf .pytest_cache .coverage $(VENV) dist build
	cd ui/app && rm -rf node_modules dist .vite || true

## ------------------------------
## Background Service Management

# Start FastAPI server in background with PID tracking
api-start-bg: install-base
	$(call pid_start,FastAPI server,.pids/api.pid,LX_API_PORT=$${LX_API_PORT:-8000} $(PY) -m loquilex.api.server)

# Start UI dev server in background with PID tracking
ui-dev-bg: ui-setup
	$(call pid_start,UI dev server,.pids/ui-dev.pid,cd ui/app && LX_API_PORT=$${LX_API_PORT:-8000} LX_UI_PORT=$${LX_UI_PORT:-5173} npm run dev)

# Start UI preview server in background with PID tracking
ui-start-bg: ui-build
	$(call pid_start,UI preview server,.pids/ui-preview.pid,cd ui/app && LX_UI_PORT=$${LX_UI_PORT:-4173} npm run preview)

# Stop UI services
stop-ui:
	$(call pid_stop,UI dev server,.pids/ui-dev.pid,pids="$$(lsof -ti:$${LX_UI_PORT:-5173})"; [ -n "$$pids" ] && kill $$pids 2>/dev/null || true)
	$(call pid_stop,UI preview server,.pids/ui-preview.pid,pids="$$(lsof -ti:$${LX_UI_PORT:-4173})"; [ -n "$$pids" ] && kill $$pids 2>/dev/null || true)

# Stop API server
stop-api:
	$(call pid_stop,FastAPI server,.pids/api.pid,pids="$$(lsof -ti:$${LX_API_PORT:-8000})"; [ -n "$$pids" ] && kill $$pids 2>/dev/null || true)

# Stop WebSocket server (placeholder for future)
stop-ws:
	@echo "[stop-ws] No WebSocket server configured yet"

# Stop all tracked services
stop-all: stop-ui stop-api stop-ws
	@echo "[stop-all] All services stopped"

# Force stop all services (fallback to port-based killing)
stop-all-force:
	@echo "[stop-all-force] Force stopping all services..."
	@pids="$$(lsof -ti:$${LX_API_PORT:-8000})"; [ -n "$$pids" ] && kill -9 $$pids 2>/dev/null || true
	@pids="$$(lsof -ti:$${LX_UI_PORT:-5173})"; [ -n "$$pids" ] && kill -9 $$pids 2>/dev/null || true
	@pids="$$(lsof -ti:4173)"; [ -n "$$pids" ] && kill -9 $$pids 2>/dev/null || true
	@rm -f .pids/*.pid
	@echo "[stop-all-force] ✓ Force stop complete"

# Show status of all tracked PIDs
pids-status:
	@echo "=== PID Status ==="
	$(call pid_status,FastAPI server,.pids/api.pid)
	$(call pid_status,UI dev server,.pids/ui-dev.pid)
	$(call pid_status,UI preview server,.pids/ui-preview.pid)
	$(call pid_status,E2E backend,.backend.pid)

# Clean up stale PID files
pids-clean-stale:
	@echo "[pids-clean-stale] Cleaning stale PID files..."
	@for pidfile in .pids/*.pid .backend.pid; do \
		if [ -f "$$pidfile" ]; then \
			if ! kill -0 $$(cat "$$pidfile") 2>/dev/null; then \
				echo "Removing stale PID file: $$pidfile"; \
				rm -f "$$pidfile"; \
			fi; \
		fi; \
	done
	@echo "[pids-clean-stale] ✓ Cleanup complete"

clean-logs:
	@echo "=== Cleaning old log files ==="
	@if [ -n "$$LX_LOG_DIR" ] && [ -d "$$LX_LOG_DIR" ]; then \
		if [ -n "$$LX_LOG_MAX_AGE_HOURS" ]; then \
			$(PY) -c "from loquilex.logging import cleanup_old_logs; print(f'Deleted {cleanup_old_logs(\"$$LX_LOG_DIR\", max_age_hours=int(\"$$LX_LOG_MAX_AGE_HOURS\"))} log files')"; \
		else \
			$(PY) -c "from loquilex.logging import cleanup_old_logs; print(f'Deleted {cleanup_old_logs(\"$$LX_LOG_DIR\")} log files')"; \
		fi; \
	else \
		echo "No LX_LOG_DIR set or directory not found"; \
	fi
	@rm -rf .artifacts/logs || true

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
	@if [ "$${LX_OFFLINE:-1}" != "1" ]; then \
		echo "[ui-e2e] Installing Chromium for Playwright (online mode)"; \
		cd ui/app && PLAYWRIGHT_BROWSERS_PATH=$${PLAYWRIGHT_BROWSERS_PATH:-0} npx playwright install chromium --with-deps >/dev/null 2>&1 || true; \
	else \
		echo "[ui-e2e] Skipping Chromium install (offline mode)"; \
	fi
	@echo "Starting FastAPI server for e2e tests..."
	@LX_API_PORT=$${LX_API_PORT:-8000} $(PY) -m loquilex.api.server & echo $$! > .backend.pid
	@echo "Waiting for FastAPI to become available on port $${LX_API_PORT:-8000}..."
	E2E_EXIT=$$?; \
	if [ -f ".backend.pid" ]; then \
		kill $$(cat .backend.pid) 2>/dev/null || true; \
		rm -f .backend.pid; \
	fi; \
	exit $$E2E_EXIT

# UI verification (combines unit tests + e2e, skips e2e when offline)
ui-verify: ui-test
	@if [ "$${LX_OFFLINE:-1}" != "1" ]; then \
		echo "[ui-verify] Running e2e tests (online mode)"; \
		$(MAKE) ui-e2e; \
	else \
		echo "[ui-verify] Skipping e2e tests (offline mode)"; \
	fi

## ------------------------------
## Bucketed Commands

# Install bucket
install:
	@if $(PY) -c "import pytest" 2>/dev/null; then \
		echo "✓ Dependencies already installed"; \
	else \
		$(MAKE) install-base; \
	fi

# Test bucket
test-all: test
	@if [ "$${LX_OFFLINE:-1}" != "1" ]; then \
		echo "[test-all] Running e2e tests (online mode)"; \
		$(MAKE) test-e2e; \
	else \
		echo "[test-all] Skipping e2e tests (offline mode)"; \
	fi
	@echo "✓ All tests complete"

# Quality bucket
qual-all: lint fmt-check typecheck
	@echo "✓ Quality checks complete"

## Pattern rules for command discovery
test-%:
	@if [ "$*" = "all" ]; then $(MAKE) test-all; \
	elif [ "$*" = "online" ]; then $(MAKE) test-online; \
	elif [ "$*" = "e2e" ]; then $(MAKE) test-e2e; \
	else echo "Unknown test target: test-$*"; exit 1; fi

qual-%:
	@if [ "$*" = "all" ]; then $(MAKE) qual-all; \
	elif [ "$*" = "lint" ]; then $(PY) -m ruff check loquilex tests; \
	elif [ "$*" = "fmt" ]; then $(PY) -m black loquilex tests; \
	elif [ "$*" = "fmt-check" ]; then $(PY) -m black --check --diff loquilex tests; \
	elif [ "$*" = "typecheck" ]; then $(PY) -m mypy loquilex; \
	else echo "Unknown quality target: qual-$*"; exit 1; fi

ui-%:
	@if [ "$*" = "verify" ]; then $(MAKE) ui-verify; \
	elif [ "$*" = "dev-bg" ]; then $(MAKE) ui-dev-bg; \
	elif [ "$*" = "start-bg" ]; then $(MAKE) ui-start-bg; \
	else echo "Unknown UI target: ui-$*"; exit 1; fi

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

docker-test:
	@echo "=== Testing Docker setup ==="
	./scripts/test-docker.sh

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
	@echo "=== Cleaned build and test artifacts ==="

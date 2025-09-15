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
        lint fmt fmt-check typecheck test test-online unit test-e2e e2e ci clean \
        docker-ci docker-ci-build docker-ci-run docker-ci-test docker-ci-shell \
        sec-scan dead-code-analysis dead-code-report clean-artifacts \
        stop-ui stop-ui-force stop-api stop-api-force stop-ws stop-ws-force stop-all stop-all-force \
        ui-setup ui-dev ui-build ui-start ui-test ui-test-watch ui-e2e ui-verify

help:
	@echo "Targets:"
	@echo "  dev-minimal      - base+dev deps only; no model prefetch (offline-first)"
	@echo "  dev              - alias of dev-minimal"
	@echo "  dev-ml-cpu       - add CPU-only ML stack and prefetch tiny model"
	@echo "  lint / fmt / typecheck / test / e2e / ci"
	@echo "  ui-setup / ui-dev / ui-build / ui-start / ui-test / ui-e2e / ui-verify"
	@echo "  stop-ui / stop-api / stop-ws / stop-all (and *-force variants)"
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
	@ASR_MODEL="$(ASR_MODEL)" $(PY) -c 'import os; \
from faster_whisper import WhisperModel; \
model = os.environ.get("ASR_MODEL") or os.environ.get("LX_ASR_MODEL") or "tiny.en"; \
print(f"Downloading {model}..."); \
WhisperModel(model, device="cpu", compute_type="int8"); \
print(f\"[prefetch-asr] downloaded/prepared: {model}\")'

# Prefetch only the tiny model unless explicitly skipped
models-tiny:
	@if echo "$${LX_SKIP_MODEL_PREFETCH:-0}" | grep -Eiq '^(1|true|yes|on)$$'; then \
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
	LX_OFFLINE=${LX_OFFLINE:-1} HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 HF_HUB_DISABLE_TELEMETRY=1 $(PY) -m pytest -q

test-online:
	HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 HF_HUB_DISABLE_TELEMETRY=1 LX_OFFLINE=0 $(PY) -m pytest -q

unit: test

test-e2e: install-base
	$(PY) -m pytest -m e2e -q

# Verbose E2E (add extra flags via: make e2e PYTEST_FLAGS="--timeout=45")
e2e: install-base
	$(PY) -m pytest -m e2e -vv -rA $(PYTEST_FLAGS)

ci: lint typecheck test
	@echo "✓ CI checks passed locally"

## ------------------------------
## Stop config (graceful & force)

PIDS_DIR           ?= .pids
STOP_TIMEOUT       ?= 5

UI_DEV_PORT        ?= 5173
UI_PREVIEW_PORT    ?= $(UI_DEV_PORT)

API_PORT           ?= 8000
WS_PORT            ?= 0            # set if WS is on a distinct port; 0 = skip

UI_DEV_PID         ?= $(PIDS_DIR)/ui-dev.pid
UI_PREVIEW_PID     ?= $(PIDS_DIR)/ui-preview.pid
API_PID            ?= $(PIDS_DIR)/api.pid
# Also clean up temp backend started by ui-e2e:
E2E_API_PID        ?= .backend.pid
WS_PID             ?= $(PIDS_DIR)/ws.pid

# -------------- Helpers
define _kill_from_pid
	@if [ -f $(1) ]; then \
		PID=$$(cat $(1)); \
		if kill -0 $$PID >/dev/null 2>&1; then \
			echo ">> Stopping $$PID ($(1)) with SIGTERM"; \
			kill $$PID; \
			for i in $$(seq $(STOP_TIMEOUT)); do \
				if kill -0 $$PID >/dev/null 2>&1; then sleep 1; else DONE=1; break; fi; \
			done; \
			if [ "$$DONE" != "1" ]; then echo "!! Timeout; still alive $$PID after $(STOP_TIMEOUT)s"; fi; \
		else \
			echo ">> Stale PID file $(1) (no process $$PID)"; \
		fi; \
		rm -f $(1); \
	else \
		echo ">> No PID file: $(1)"; \
	fi
endef

define _kill_by_port
	@PORT=$(1); \
	if [ "$$PORT" = "0" ] || [ -z "$$PORT" ]; then exit 0; fi; \
	if command -v lsof >/dev/null 2>&1; then \
		PIDS=$$(lsof -tiTCP:$$PORT -sTCP:LISTEN || true); \
	elif command -v fuser >/dev/null 2>&1; then \
		PIDS=$$(fuser -n tcp $$PORT 2>/dev/null | tr ' ' '\n'); \
	else \
		echo ">> Neither lsof nor fuser found; cannot kill by port $$PORT"; \
		PIDS=""; \
	fi; \
	for PID in $$PIDS; do \
		echo ">> Stopping $$PID listening on :$$PORT with SIGTERM"; \
		kill $$PID || true; \
		for i in $$(seq $(STOP_TIMEOUT)); do \
			if kill -0 $$PID >/dev/null 2>&1; then sleep 1; else break; fi; \
		done; \
	done
endef

define _kill_from_pid_force
	@if [ -f $(1) ]; then \
		PID=$$(cat $(1)); \
		if kill -0 $$PID >/dev/null 2>&1; then echo ">> Force killing $$PID ($(1))"; kill -9 $$PID || true; fi; \
		rm -f $(1); \
	fi
endef

define _kill_by_port_force
	@PORT=$(1); \
	if [ "$$PORT" = "0" ] || [ -z "$$PORT" ]; then exit 0; fi; \
	if command -v lsof >/dev/null 2>&1; then \
		PIDS=$$(lsof -tiTCP:$$PORT -sTCP:LISTEN || true); \
	elif command -v fuser >/dev/null 2>&1; then \
		PIDS=$$(fuser -n tcp $$PORT 2>/dev/null | tr ' ' '\n'); \
	else \
		PIDS=""; \
	fi; \
	for PID in $$PIDS; do echo ">> Force killing $$PID on :$$PORT"; kill -9 $$PID || true; done
endef

## UI (dev + preview) — graceful
stop-ui:
	@mkdir -p "$(PIDS_DIR)"
	$(call _kill_from_pid,$(UI_DEV_PID))
	$(call _kill_from_pid,$(UI_PREVIEW_PID))
	$(call _kill_by_port,$(UI_DEV_PORT))
	$(call _kill_by_port,$(UI_PREVIEW_PORT))

## UI — force
stop-ui-force:
	@mkdir -p "$(PIDS_DIR)"
	$(call _kill_from_pid_force,$(UI_DEV_PID))
	$(call _kill_from_pid_force,$(UI_PREVIEW_PID))
	$(call _kill_by_port_force,$(UI_DEV_PORT))
	$(call _kill_by_port_force,$(UI_PREVIEW_PORT))

## Backend API (includes temp PID from ui-e2e) — graceful
stop-api:
	@mkdir -p "$(PIDS_DIR)"
	$(call _kill_from_pid,$(API_PID))
	$(call _kill_from_pid,$(E2E_API_PID))
	$(call _kill_by_port,$(API_PORT))

## Backend API — force
stop-api-force:
	@mkdir -p "$(PIDS_DIR)"
	$(call _kill_from_pid_force,$(API_PID))
	$(call _kill_from_pid_force,$(E2E_API_PID))
	$(call _kill_by_port_force,$(API_PORT))

## WebSocket endpoint (set WS_PORT if distinct) — graceful
stop-ws:
	@mkdir -p "$(PIDS_DIR)"
	$(call _kill_from_pid,$(WS_PID))
	$(call _kill_by_port,$(WS_PORT))

## WebSocket endpoint — force
stop-ws-force:
	@mkdir -p "$(PIDS_DIR)"
	$(call _kill_from_pid_force,$(WS_PID))
	$(call _kill_by_port_force,$(WS_PORT))

## Everything — graceful
stop-all: stop-ui stop-api stop-ws
	@echo ">> stop-all complete"

## Everything — force
stop-all-force: stop-ui-force stop-api-force stop-ws-force
	@echo ">> stop-all-force complete"

## ------------------------------
## Cleanup

help:
	@echo "Targets:"
	@echo "  dev-minimal      - base+dev deps only; no model prefetch (offline-first)"
	@echo "  dev              - alias of dev-minimal"
	@echo "  dev-ml-cpu       - add CPU-only ML stack and prefetch tiny model"
	@echo "  lint / fmt / typecheck / test / e2e / ci"
	@echo "  ui-verify        - run UI unit/component and e2e tests (see below)"
	@echo "  ui-e2e           - run Playwright E2E tests (see below)"
	@echo "  dead-code-analysis - run comprehensive dead code detection tools"
	@echo "  dead-code-report   - generate reports locally (no CI gating)"
	@echo "  clean-artifacts    - remove all generated artifacts"
	@echo ""
	@echo "UI E2E/Verify Behavior:"
	@echo "  - ui-e2e and ui-verify will conditionally install Playwright Chromium browser only when LX_OFFLINE!=1."
	@echo "  - When LX_OFFLINE=1, browser install and E2E are skipped for deterministic offline runs."
	@echo "  - When LX_OFFLINE=0, browser is installed and E2E tests are executed."
	@echo "  - See scripts/ui_e2e.sh for details."
	@echo ""
	@echo "Vars:"
	@echo "  USE_VENV=0       - use system Python instead of creating .venv (good for CI)"
	@echo "  ASR_MODEL=...    - model to prefetch (default: tiny.en)"
	@echo "  LX_SKIP_MODEL_PREFETCH=1 - skip model prefetch (for faster CI runs)"
	@echo "  LX_SKIP_DEAD_CODE_REPORT=1 - skip dead code report generation (for faster CI runs)"
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

# Dead code analysis using multiple detection tools
dead-code-analysis: install-base
	@echo "=== Running comprehensive dead code analysis (WARN-ONLY) ==="
	- ./scripts/dead-code-analysis.sh || echo "[warn] dead code found (non-blocking)"
	@echo "== done =="

dead-code-report:
	@bash scripts/dead-code-analysis.sh --report-only
	@echo "✅ Dead code reports generated in .artifacts/dead-code-reports/"

clean-artifacts:
	@rm -rf .artifacts || true

## ------------------------------
## UI config
UI_DIR      ?= ui
PKG_MGR     := $(shell if [ -f $(UI_DIR)/pnpm-lock.yaml ]; then echo pnpm; elif [ -f $(UI_DIR)/yarn.lock ]; then echo yarn; else echo npm; fi)
UI_DEV_PORT ?= 5173
UI_BASE_URL ?= http://localhost:$(UI_DEV_PORT)

# If set to 1, `make ui-e2e` will start a local backend automatically.
UI_E2E_START_BACKEND ?= 1
# Override this to your project’s backend entrypoint if different.
UI_E2E_BACKEND_CMD ?= $(PY) -m loquilex.api.server --host 127.0.0.1 --port 8000
UI_E2E_BACKEND_URL ?= http://127.0.0.1:8000

ui-setup:
	@echo ">> Installing UI deps with $(PKG_MGR)"
	@if [ "$(PKG_MGR)" = "pnpm" ]; then cd "$(UI_DIR)" && pnpm install; \
	elif [ "$(PKG_MGR)" = "yarn" ]; then cd "$(UI_DIR)" && yarn install --frozen-lockfile; \
	else cd "$(UI_DIR)" && if [ -f package-lock.json ]; then npm ci; else echo "(package-lock.json missing; using npm install)"; npm install; fi; fi

ui-dev: ui-setup
	@echo ">> Starting UI dev server (port $(UI_DEV_PORT))"
	@cd "$(UI_DIR)" && \
	if [ "$(PKG_MGR)" = "pnpm" ]; then pnpm run dev; \
	elif [ "$(PKG_MGR)" = "yarn" ]; then yarn dev; \
	else npm run dev; fi

ui-build: ui-setup
	@echo ">> Building UI"
	@cd "$(UI_DIR)" && \
	if [ "$(PKG_MGR)" = "pnpm" ]; then pnpm run build; \
	elif [ "$(PKG_MGR)" = "yarn" ]; then yarn build; \
	else npm run build; fi

ui-start: ui-build
	@echo ">> Serving production build"
	@cd "$(UI_DIR)" && \
	if [ "$(PKG_MGR)" = "pnpm" ]; then pnpm run preview; \
	elif [ "$(PKG_MGR)" = "yarn" ]; then yarn preview; \
	else npm run preview; fi

ui-test: ui-setup
	@echo ">> Running UI unit/component tests"
	@cd "$(UI_DIR)" && \
	if [ "$(PKG_MGR)" = "pnpm" ]; then pnpm run test -- --run; \
	elif [ "$(PKG_MGR)" = "yarn" ]; then yarn test --run; \
	else npm run test -- --run; fi

ui-test-watch: ui-setup
	@cd "$(UI_DIR)" && \
	if [ "$(PKG_MGR)" = "pnpm" ]; then pnpm run test; \
	elif [ "$(PKG_MGR)" = "yarn" ]; then yarn test; \
	else npm run test; fi

ui-e2e: ui-setup
	@UI_E2E_START_BACKEND=$(UI_E2E_START_BACKEND) \
	UI_E2E_BACKEND_CMD='$(UI_E2E_BACKEND_CMD)' \
	UI_E2E_BACKEND_URL='$(UI_E2E_BACKEND_URL)' \
	UI_BASE_URL='$(UI_BASE_URL)' \
	bash scripts/ui_e2e.sh

ui-verify: ui-test ui-e2e
	@echo ">> UI verify complete"

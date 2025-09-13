# Lightweight dev profile: installs only base+dev deps and prefetches tiny model.

# ------------------------------
# Vars
VENV ?= .venv
PY   ?= $(VENV)/bin/python
PIP := .venv/bin/python -m pip

# ---------------------------------------------------------------------------
# Bootstrap / installs
.PHONY: install-venv install-base

# Create venv if missing; idempotent
install-venv:
	@echo ">> Ensuring .venv exists"
	@test -x $(PY) || python3 -m venv .venv
	@$(PY) -m pip install -U pip setuptools wheel

# Install dev/test deps used by lint/format/typecheck/test
install-base: install-venv
	@echo ">> Installing base dev/test dependencies"
	@$(PIP) install -r requirements-ci.txt -r requirements-dev.txt -c constraints.txt

install-ml-cpu:
	$(PIP) install -r requirements-ml-cpu.txt -c constraints.txt

# Prefetch only the tiny Whisper model; temporarily allow network for the fetch.
models-tiny:
	@if [ "$${LLX_SKIP_MODEL_PREFETCH:-0}" = "1" ]; then \
	  echo "[dev] Skipping tiny model prefetch (LLX_SKIP_MODEL_PREFETCH=1)"; \
	else \
	  HF_HUB_OFFLINE=0 LOQUILEX_OFFLINE=0 GF_ASR_MODEL=tiny.en $(PY) scripts/dev_fetch_models.py; \
	fi

# Default dev is LIGHT (CPU-only): install minimal ML libs then prefetch tiny model.
# This keeps downloads to ~100–150MB vs multi-GB when torch/CUDA is pulled.
dev: venv install-base install-ml-cpu models-tiny
	@echo "Dev (light) ready. (CPU-only, tiny.en cached)"

# Opt-in: add CPU ML libs (still light; no torch)
dev-ml-cpu: venv install-base install-ml-cpu models-tiny
	@echo "Dev (ml-cpu) ready."

# Opt-in: GPU ML libs — WARNING: huge downloads. Uncomment in requirements-ml-gpu.txt first.
dev-ml-gpu: dev
	@echo ">>> Skipping GPU install by default. Edit requirements-ml-gpu.txt and run:"
	@echo "    pip install -r requirements-ml-gpu.txt -c constraints.txt"

.PHONY: test unit
test: install-base
	$(PY) -m pytest -q
unit: test

.PHONY: test-e2e
test-e2e: install-base
	$(PY) -m pytest -m e2e -q

.PHONY: lint
lint: install-base
	.venv/bin/ruff check loquilex tests

.PHONY: fmt
fmt: install-base
	.venv/bin/black loquilex tests

.PHONY: fmt-check
fmt-check: install-base
	.venv/bin/black --check --diff loquilex tests

.PHONY: typecheck
typecheck: install-base
	.venv/bin/mypy loquilex

.PHONY: ci
ci: lint typecheck test
	@echo "✓ CI checks passed locally"

# Unit tests (non-e2e) quick mode; add extra flags via PYTEST_FLAGS if needed

# E2E tests (verbose). Timeout override applied by invoking: make e2e PYTEST_ADDOPTS=--timeout=45
e2e:
	$(PY) -m pytest -m e2e -vv -rA $(PYTEST_FLAGS)

# Aggregate CI-style sequence

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

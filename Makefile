VENV?=.venv
PY=$(VENV)/bin/python
PIP=$(VENV)/bin/pip

.PHONY: venv install dev lint fmt test run-local-ci run-ci-mode test-ci run-wav run-zh clean

venv:
	python3 -m venv $(VENV)
	$(PIP) install -U pip

install: venv
	$(PIP) install -r requirements.txt

dev: install
	$(PIP) install -r requirements-dev.txt

lint:
	$(VENV)/bin/ruff check .

fmt:
	$(VENV)/bin/black .

test:
	$(PY) -m pytest -q --maxfail=1 --disable-warnings -ra --cov=loquilex --cov-report=term-missing

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

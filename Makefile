VENV?=.venv
PY=$(VENV)/bin/python
PIP=$(VENV)/bin/pip

.PHONY: venv install dev lint fmt test run-wav run-zh clean

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

# CI-identical testing
test-ci:
	@echo "=== Running tests in CI-identical environment ==="
	@export HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 HF_HUB_DISABLE_TELEMETRY=1 LOQUILEX_OFFLINE=1 && \
	env | grep -E '^(HF_HUB_OFFLINE|TRANSFORMERS_OFFLINE|HF_HUB_DISABLE_TELEMETRY|LOQUILEX_OFFLINE)=' && \
	$(VENV)/bin/pytest -m "not e2e" -vv -rA --maxfail=1 --disable-warnings && \
	$(VENV)/bin/pytest -q --maxfail=1 -m e2e --disable-warnings --no-header --no-summary

# All CI checks locally
ci-local:
	@echo "=== Running all CI checks locally ==="
	@export HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 HF_HUB_DISABLE_TELEMETRY=1 LOQUILEX_OFFLINE=1 && \
	$(VENV)/bin/ruff check . && \
	$(VENV)/bin/black --check . && \
	($(VENV)/bin/mypy loquilex || true) && \
	$(VENV)/bin/pytest -m "not e2e" -vv -rA --maxfail=1 --disable-warnings && \
	$(VENV)/bin/pytest -q --maxfail=1 -m e2e --disable-warnings --no-header --no-summary

run-wav:
	$(PY) -m loquilex.cli.wav_to_vtt --wav ../../test.wav --out loquilex/out/asr_en.vtt

run-zh:
	$(PY) -m loquilex.cli.vtt_to_zh --vtt loquilex/out/asr_en.vtt --out-text loquilex/out/live_zh.txt --out-srt loquilex/out/live_zh.srt

clean:
	rm -rf .pytest_cache out .coverage

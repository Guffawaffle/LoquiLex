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

run-wav:
	$(PY) -m loquilex.cli.wav_to_vtt --wav ../../test.wav --out loquilex/out/asr_en.vtt

run-zh:
	$(PY) -m loquilex.cli.vtt_to_zh --vtt loquilex/out/asr_en.vtt --out-text loquilex/out/live_zh.txt --out-srt loquilex/out/live_zh.srt

clean:
	rm -rf .pytest_cache out .coverage

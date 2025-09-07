VENV?=.venv
PY=$(VENV)/bin/python
PIP=$(VENV)/bin/pip

.PHONY: venv install lint test run-wav run-zh

venv:
	python3 -m venv $(VENV)

install: venv
	$(PIP) install -U pip
	$(PIP) install -r requirements.txt

lint:
	@echo "(ruff/black suggested, kept minimal)"

test:
	$(PY) -m pytest -q

run-wav:
	$(PY) -m greenfield.cli.wav_to_vtt --wav ../../test.wav --out greenfield/out/asr_en.vtt

run-zh:
	$(PY) -m greenfield.cli.vtt_to_zh --vtt greenfield/out/asr_en.vtt --out-text greenfield/out/live_zh.txt --out-srt greenfield/out/live_zh.srt

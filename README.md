# LoquiLex

History-preserving extraction of the `greenfield` module from rt-whisper, renamed to `loquilex`.

## Quickstart

```bash
python -m venv .venv
source .venv/bin/activate
pip install -U pip build
pip install -e .

loquilex-wav-to-vtt --help
loquilex-vtt-to-zh --help
# loquilex-live --seconds 5 --out-prefix loquilex/out/live
```

Environment variables now prefer `LLX_*` with fallback to legacy `GF_*` and a DeprecationWarning on use.

from __future__ import annotations

import importlib
import types

from loquilex.output.vtt import _ts as _vtt_ts
from loquilex.output.srt import _ts as _srt_ts
from loquilex.mt.translator import _dtype_kwargs, Translator
from loquilex.config import defaults as cfg_defaults
from loquilex.config.defaults import pick_device
from loquilex.post.zh_text import normalize_punctuation, post_process


def test_timestamp_formatting_helpers():
    assert _vtt_ts(12.345).endswith("12.345")
    assert _srt_ts(1.2).endswith(",200")


def test_dtype_kwargs_version_switch(monkeypatch):
    fake_tr = types.SimpleNamespace(__version__="4.56.0")
    monkeypatch.setitem(importlib.sys.modules, "transformers", fake_tr)
    kw = _dtype_kwargs(torch_mod=None, device_str="cpu")
    assert kw == {}

    class T:
        float16 = "f16"
        float32 = "f32"

    kw2 = _dtype_kwargs(torch_mod=T, device_str="cuda")
    assert "dtype" in kw2 and kw2["dtype"] == "f16"


def test_pick_device_cpu(monkeypatch):
    # Force cpu path
    monkeypatch.setenv("GF_DEVICE", "cpu")
    # Reload defaults to pick up env
    import importlib

    importlib.reload(cfg_defaults)
    dev, dt = cfg_defaults.pick_device()
    assert dev == "cpu" and dt == "float32"


def test_post_processing():
    s = normalize_punctuation("Hello, world !")
    assert "，" in s and s.endswith("！")
    s2 = post_process("GPU with RTX 4090, great!")
    assert s2.endswith("！")

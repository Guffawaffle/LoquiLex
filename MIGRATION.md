# Migration Guide: Language-Agnostic API

This guide helps you migrate from the hardcoded EN→ZH API to the new language-agnostic API introduced in version 0.2.0.

## Overview

LoquiLex now supports **any language pair** supported by the underlying translation models (NLLB-200 or M2M-100), not just English→Chinese. All APIs, CLIs, and configuration have been updated to use generic `src_lang` and `tgt_lang` parameters.

## Quick Migration

### CLI Usage

**Old (deprecated, but still works):**
```bash
loquilex-live --zh-partial-debounce-sec 0.5
```

**New (recommended):**
```bash
loquilex-live --src-lang en --tgt-lang zh --tgt-partial-debounce-sec 0.5

# Other language pairs:
loquilex-live --src-lang zh --tgt-lang en  # Chinese to English
loquilex-live --src-lang en --tgt-lang es  # English to Spanish
loquilex-live --src-lang es --tgt-lang en  # Spanish to English
```

### Python API

**Old (deprecated, but still works):**
```python
from loquilex.mt.translator import Translator

tr = Translator()
result = tr.translate_en_to_zh("Hello, world!")
draft = tr.translate_en_to_zh_draft("Quick update")
```

**New (recommended):**
```python
from loquilex.mt.translator import Translator

tr = Translator()

# Final quality (beam search, slower but better)
result = tr.translate("Hello, world!", src_lang="en", tgt_lang="zh", quality="final")

# Draft quality (fast, single beam)
draft = tr.translate("Quick update", src_lang="en", tgt_lang="zh", quality="draft")

# Other language pairs:
result = tr.translate("你好", src_lang="zh", tgt_lang="en", quality="final")
result = tr.translate("Hola", src_lang="es", tgt_lang="en", quality="final")
```

### Post-Processing

**Old (language assumed from context):**
```python
from loquilex.post.zh_text import post_process

cleaned = post_process("测试 文本 。")
```

**New (explicit language parameter):**
```python
from loquilex.post import post_process

cleaned = post_process("测试 文本 。", lang="zh")
cleaned = post_process("Hello world", lang="en")
```

### Environment Variables

**Old:**
```bash
export LX_LANG_VARIANT_ZH=zh-Hans
```

**New (additional variables):**
```bash
export LX_SRC_LANG=en
export LX_TGT_LANG=zh
export LX_TGT_PARTIAL_DEBOUNCE_SEC=0.5
export LX_LANG_VARIANT_ZH=zh-Hans  # Still supported for backward compatibility
```

### Module Imports

**Old (still works with deprecation warning):**
```python
from loquilex.cli.live_en_to_zh import main
```

**New (recommended):**
```python
from loquilex.cli.live import main
```

## Language Codes

Use **FLORES-200** codes for language specification:

| Language | Code | FLORES Code (NLLB) | M2M Code |
|----------|------|-------------------|----------|
| English | `en` | `eng_Latn` | `en` |
| Chinese (Simplified) | `zh` | `zho_Hans` | `zh` |
| Chinese (Traditional) | `zh-Hant` | `zho_Hant` | - |
| Spanish | `es` | `spa_Latn` | `es` |
| French | `fr` | `fra_Latn` | `fr` |
| German | `de` | `deu_Latn` | `de` |
| Japanese | `ja` | `jpn_Jpan` | `ja` |
| Korean | `ko` | `kor_Hang` | `ko` |

See the [FLORES-200 documentation](https://github.com/facebookresearch/flores/blob/main/flores200/README.md) for the complete list.

## Supported Language Pairs

### NLLB-200 (Default)
Supports **200 languages** with any-to-any translation. Examples:
- EN ↔ ZH, EN ↔ ES, EN ↔ FR, EN ↔ DE, EN ↔ JA, EN ↔ KO
- ZH ↔ ES, ZH ↔ FR, ES ↔ FR (any combination)

### M2M-100 (Alternative)
Supports **100 languages** with any-to-any translation. Enable with:
```bash
export LX_MT_PROVIDER=m2m
```

## Breaking Changes

### None (Fully Backward Compatible)

All old APIs remain functional with deprecation warnings. You can migrate at your own pace. The deprecated APIs will be removed in version **1.0.0**.

## Deprecation Timeline

| Version | Status | Notes |
|---------|--------|-------|
| 0.2.0 | Deprecated | Old APIs emit `DeprecationWarning` |
| 0.x.x | Grace Period | Both old and new APIs work |
| 1.0.0 | Removed | Old APIs removed, only new APIs available |

## Testing Your Migration

Run your existing code with Python warnings enabled to catch deprecated usage:

```bash
python -W default::DeprecationWarning your_script.py
```

Or in your code:

```python
import warnings
warnings.simplefilter('default', DeprecationWarning)
```

## Need Help?

- **Issues**: [GitHub Issues](https://github.com/Guffawaffle/LoquiLex/issues)
- **Discussions**: [GitHub Discussions](https://github.com/Guffawaffle/LoquiLex/discussions)
- **Documentation**: [docs/](https://github.com/Guffawaffle/LoquiLex/tree/main/docs)

## Example: Complete Migration

**Before:**
```python
from loquilex.cli.live_en_to_zh import main as cli_main
from loquilex.mt.translator import Translator
from loquilex.post.zh_text import post_process

tr = Translator()
result = tr.translate_en_to_zh("Hello")
cleaned = post_process(result.text)
```

**After:**
```python
from loquilex.cli.live import main as cli_main
from loquilex.mt.translator import Translator
from loquilex.post import post_process

tr = Translator()
result = tr.translate("Hello", src_lang="en", tgt_lang="zh", quality="final")
cleaned = post_process(result.text, lang="zh")
```

That's it! Your code is now future-proof and supports any language pair. 🎉

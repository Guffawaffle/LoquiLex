# Migration Guide: Language-Agnostic API (v0.2.0)

This guide helps you migrate from the hardcoded EN→ZH API to the new language-agnostic API.

## Overview

LoquiLex now supports **any language pair** supported by the underlying translation models (NLLB-200 or M2M-100), not just English→Chinese. All APIs, CLIs, and configuration have been updated to use generic `src_lang` and `tgt_lang` parameters.

## Breaking Changes

### CLI Module Renamed

**Old:**
```python
from loquilex.cli.live_en_to_zh import main
```

**New:**
```python
from loquilex.cli.live import main
```

**Command stays the same:**
```bash
loquilex-live  # Entry point updated internally
```

### CLI Flags

**Old flag removed:**
- `--zh-partial-debounce-sec` ❌

**New flags:**
```bash
loquilex-live --src-lang en --tgt-lang zh --tgt-partial-debounce-sec 0.5

# Other language pairs:
loquilex-live --src-lang zh --tgt-lang en  # Chinese to English
loquilex-live --src-lang en --tgt-lang es  # English to Spanish
```

### Python API

**Old methods removed:**
- `Translator.translate_en_to_zh()` ❌
- `Translator.translate_en_to_zh_draft()` ❌

**New unified method:**
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

**Old (implicit language):**
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

**New:**
```bash
export LX_SRC_LANG=en
export LX_TGT_LANG=zh
export LX_TGT_PARTIAL_DEBOUNCE_SEC=0.5
export LX_LANG_VARIANT_ZH=zh-Hans  # Chinese variant (Simplified/Traditional)
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

## Quick Reference

**Example: Complete Update**

```python
# Import from new location
from loquilex.cli.live import main as cli_main
from loquilex.mt.translator import Translator
from loquilex.post import post_process

tr = Translator()
result = tr.translate("Hello", src_lang="en", tgt_lang="zh", quality="final")
cleaned = post_process(result.text, lang="zh")
```

## Need Help?

- **Issues**: [GitHub Issues](https://github.com/Guffawaffle/LoquiLex/issues)
- **Discussions**: [GitHub Discussions](https://github.com/Guffawaffle/LoquiLex/discussions)
- **Documentation**: [docs/](https://github.com/Guffawaffle/LoquiLex/tree/main/docs)


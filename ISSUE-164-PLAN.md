# Language-Agnostic Refactoring Plan (Issue #164)

**Issue:** [#164](https://github.com/Guffawaffle/LoquiLex/issues/164)
**Branch:** `feature/lang-agnostic-cli-164`
**Goal:** Remove all hardcoded EN→ZH assumptions, make runtime language pair selection possible

## Problem Statement

Currently hardcoded everywhere:
- CLI: `live_en_to_zh.py`, `--zh-partial-debounce-sec`
- API: `translate_en_to_zh()`, `translate_en_to_zh_draft()`
- Config: `LX_LANG_VARIANT_ZH`

**Desired state:**
```bash
loquilex live --src-lang en --tgt-lang zh --partial-debounce-sec 0.5
loquilex live --src-lang zh --tgt-lang en --partial-debounce-sec 0.3
```

## Implementation Plan

### Phase 1: Translation Layer
- [ ] Add `Translator.translate(text, src, tgt, quality)` generic method
- [ ] Deprecate `translate_en_to_zh()` (keep as wrapper with warning)
- [ ] Create post-processor registry for language-specific cleanup

### Phase 2: CLI Refactoring
- [ ] Rename flags: `--zh-partial-debounce-sec` → `--partial-debounce-sec`
- [ ] Add `--src-lang` and `--tgt-lang` arguments
- [ ] Add `--list-language-pairs` discovery flag
- [ ] Update output file naming (generic, not hardcoded `*-en.txt`, `*-zh.txt`)

### Phase 3: API & Discovery
- [ ] Add `GET /api/models/mt/current/pairs` endpoint
- [ ] Return language pair capabilities from models
- [ ] Validate src/tgt pair before translation

### Phase 4: Config Updates
- [ ] Generic variant system: `LX_LANG_VARIANTS` JSON map
- [ ] Default language pair: `LX_SRC_LANG`, `LX_TGT_LANG`
- [ ] Backward compat: map old `LX_LANG_VARIANT_ZH` to new system

### Phase 5: Testing & Documentation
- [ ] Add ZH→EN reverse tests
- [ ] Add EN→ES tests (if model supports)
- [ ] Update CLI help text
- [ ] Write migration guide
- [ ] Update API documentation

## Preserved Features

✅ **Word-count cadence gating** (3-word default) remains language-agnostic
✅ **Backward compatibility** for legacy commands/methods (with deprecation warnings)
✅ **All existing tests pass** (411/411)

## Success Criteria

1. CLI works with any model-supported language pair
2. Model capabilities discoverable via API
3. No hardcoded language pairs in core logic
4. Backward compatibility maintained
5. Tests pass for EN→ZH, ZH→EN, and EN→ES (if available)

=== Dead Code Analysis Report ===
Generated: Sat Sep 13 11:16:23 UTC 2025

## 1. Ruff Analysis (unused imports/variables/arguments)

✅ No unused code detected by Ruff

## 2. Vulture Analysis (dead code detection, min-confidence 70%)

✅ No dead code detected by Vulture

## 3. Coverage Analysis (files with 0% coverage)

Running coverage analysis...
Files with 0% coverage:
```
✅ No files with 0% coverage found
```

Files with <25% coverage:
```
✅ No files with <25% coverage found
```

## 4. Multi-Signal Analysis (flagged by ≥2 tools)

Analyzing overlap between tools...
### Files/functions mentioned by multiple tools:
```
No overlap analysis possible (insufficient data from tools)
```

## 5. Summary & Recommendations

- **Ruff findings**: 1 unused imports/variables/arguments
- **Vulture findings**: 0 dead code items
- **Zero coverage files**: 0 files

**Next Steps:**
1. Review items flagged by multiple tools for removal
2. Unused function parameters can often be prefixed with _ if they're required by interface
3. Dead code items with high confidence (>90%) are safe candidates for removal
4. Low/zero coverage files should be examined for actual usage vs dead code

Full reports saved to: .artifacts/dead-code-reports/

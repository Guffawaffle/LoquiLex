# Merge-Weave Session: LoquiLex PR Consolidation

**Session UUID:** `merge-weave-kickoff`
**Umbrella Branch:** `merge-weave-{UUID}` (to be generated)
**Default Branch:** `main`
**Total PRs:** 4
**Expected Duration:** ~30 minutes (gates + merges)

## PR Summary

| # | Title | Branch | Status |
|---|-------|--------|--------|
| 158 | Add centralized loquilex.config | `copilot/add-centralized-config-module` | Pending |
| 161 | Deprecate legacy orchestration | `copilot/cleanup-remove-legacy-orchestration` | Pending |
| 159 | Fix base_directory paths | `copilot/fix-base-directory-path` | Pending |
| 160 | Fix hard-coded test paths | `copilot/fix-hard-coded-path-in-tests` | Pending |

## Merge Topology

```
Level 0 (Independent)
├─ PR #158: centralized config ────┐
│                                   ├─→ Level 1: PR #159 ─→ Level 2: PR #160
└─ PR #161: deprecate orchestration ┘
```

**Merge Strategy:**
- Level 0: Merge both PRs in any order (can parallelize)
- Level 1: Merge PR #159 (depends on PR #158)
- Level 2: Merge PR #160 (depends on PR #159)

## Gates (Required)

1. **lint** — `make lint` (ruff)
2. **typecheck** — `make typecheck` (mypy)
3. **test** — `make unit` (pytest)
4. **determinism** — `git diff --exit-code` (no stray changes)

**Gate Policy:**
- All gates must pass after each fold-in
- Blocking gate: determinism (prevents accidental uncommitted state)
- Proceed-with-siblings: true (Level 0 can fold independently)

## Next Steps

1. ✅ Plan created and saved to `.smartergpt.local/deliverables/_session/`
2. ⏳ Create umbrella branch and PR
3. ⏳ Fold PR #158 (Level 0, step 1)
4. ⏳ Fold PR #161 (Level 0, step 2)
5. ⏳ Fold PR #159 (Level 1, after Level 0 gates pass)
6. ⏳ Fold PR #160 (Level 2, after Level 1 gates pass)
7. ⏳ Verify all gates pass on umbrella branch
8. ⏳ Mark umbrella PR as ready for review
9. ⏳ Merge umbrella PR to main

---

## Dry-Run Artifacts

All merge dry-runs and gate logs will be saved to:
```
.smartergpt.local/deliverables/_session/
├── dryrun-pr-*.log          (dry-run merge attempts)
├── gates-pr-*.json          (gate execution results)
├── fold-ins.ndjson          (append-only fold-in log)
└── summary.md               (final integration summary)
```

## Issue Closure

After collecting all linked issues, umbrella PR body will include:
```
Closes #issue1
Closes #issue2
...
```

These will auto-close when the umbrella PR merges to main.

---

**Ready to proceed?** Say "Begin fold-in sequence" and I will:
1. Generate umbrella branch and PR
2. Execute Level 0 merges
3. Run gates
4. Proceed to Level 1 & 2 as gates pass

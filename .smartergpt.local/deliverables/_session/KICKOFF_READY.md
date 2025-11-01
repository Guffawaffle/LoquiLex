# Merge-Weave Session: Plan & Ready State

**Session ID:** `merge-weave-kickoff`
**Repo:** LoquiLex
**Default Branch:** `main` (at `870e0b0`)
**Created:** 2025-11-01

---

## Executive Summary

A **merge-weave** infrastructure consolidation session is planned to fold 4 targeted improvements into a single cohesive branch:

1. **Centralized config** (PR #158) — hardware thresholds in one place
2. **Deprecate legacy orchestration** (PR #161) — align with JS-first mandate
3. **Fix base directory paths** (PR #159) — absolute path resolution
4. **Portable test paths** (PR #160) — no hard-coded `/root` directory

**Topology:** Linear dependency chain with one parallel opportunity (Level 0: PRs #158 & #161 can merge independently).

**Gates:** lint, typecheck, test, determinism (all required).

---

## Merge Pyramid

```
LEVEL 0 (Independent, can parallelize)
├─ PR #158 → Config consolidation
└─ PR #161 → Deprecate orchestration
        ↓
LEVEL 1 (depends on Level 0)
└─ PR #159 → Absolute path resolution
        ↓
LEVEL 2 (depends on Level 1)
└─ PR #160 → Portable test paths
        ↓
        ✓ All gates pass
        ↓
    MERGE to main
```

---

## Artifacts Generated

```
.smartergpt.local/deliverables/_session/
├── plan.json                 ✅ (4 nodes, 3 levels)
├── merge-order.json          ✅ (merge sequence + timing)
├── gate-definitions.json     ✅ (lint, typecheck, test, determinism)
├── policy.json               ✅ (merge strategy: --no-ff, gates required)
├── dryrun.md                 ✅ (this plan)
└── umbrella-body.md          ✅ (PR body template, issue closure placeholders)
```

---

## What Happens Next (Automated)

### Phase 1: Umbrella Setup
```bash
# Generate umbrella branch and create draft PR
UMB_BRANCH="merge-weave-$(uuidgen | tr 'A-Z' 'a-z')"
git checkout main && git pull --ff-only
git checkout -b "$UMB_BRANCH"
git push -u origin "$UMB_BRANCH"
gh pr create --base main --head "$UMB_BRANCH" --title "Merge-weave: Config & Path Infrastructure" --body-file ... --draft
```

### Phase 2: Level 0 Merge (Parallel)
```bash
# Merge PR #158 with gates
git merge --no-commit --no-ff origin/copilot/add-centralized-config-module
# (run gates: lint, typecheck, test, determinism)
git commit -m "merge-weave: fold PR #158 into umbrella (no-ff)"
git push

# Merge PR #161 with gates (can happen in parallel)
git merge --no-commit --no-ff origin/copilot/cleanup-remove-legacy-orchestration
# (run gates)
git commit -m "merge-weave: fold PR #161 into umbrella (no-ff)"
git push
```

### Phase 3: Level 1 Merge
```bash
# After Level 0 gates pass, merge PR #159
git merge --no-commit --no-ff origin/copilot/fix-base-directory-path
# (run gates)
git commit -m "merge-weave: fold PR #159 into umbrella (no-ff)"
git push
```

### Phase 4: Level 2 Merge
```bash
# After Level 1 gates pass, merge PR #160
git merge --no-commit --no-ff origin/copilot/fix-hard-coded-path-in-tests
# (run gates)
git commit -m "merge-weave: fold PR #160 into umbrella (no-ff)"
git push
```

### Phase 5: Finalization
```bash
# Mark draft PR as ready, merge to main with normal merge (no squash/rebase)
gh pr ready <umbrella_pr_number>
gh pr merge <umbrella_pr_number> --merge --delete-branch=false

# Auto-close linked issues via "Closes #…" lines in umbrella body
```

---

## Dry-Run Results (Empty — Ready to Execute)

| PR | Branch | Dry-Run | Status |
|----|--------|---------|--------|
| 158 | copilot/add-centralized-config-module | ⏳ Pending | Ready |
| 161 | copilot/cleanup-remove-legacy-orchestration | ⏳ Pending | Ready |
| 159 | copilot/fix-base-directory-path | ⏳ Pending | Ready |
| 160 | copilot/fix-hard-coded-path-in-tests | ⏳ Pending | Ready |

---

## Environment & Gates

**Python:** 3.12.3
**Venv:** Active (.venv/bin/activate)
**Main baseline:** `870e0b0`

**Gates to run after each fold-in:**
```bash
source .venv/bin/activate
make lint          # ruff
make typecheck     # mypy
make unit          # pytest
git diff --exit-code  # determinism
```

Each gate must pass before proceeding to the next fold-in.

---

## Guardrails & Policy

✅ **No force-push:** All merges use `--no-ff` for auditability
✅ **No squash/rebase:** Merge commits preserve history
✅ **Workspace-only mode:** No network beyond PR fetch/push
✅ **Secrets/CI:** No changes to CI, secrets, or deployment
✅ **Determinism:** `git diff --exit-code` after each merge
✅ **Proceed-with-siblings:** Level 0 PRs can merge independently if gates pass

---

## Ready to Begin?

Confirm by saying **"Begin fold-in sequence"** and I will:

1. ✅ Generate umbrella branch with UUID
2. ✅ Create draft umbrella PR
3. ✅ Execute Level 0 fold-ins (PRs #158 & #161)
4. ✅ Run gates; proceed to Level 1 on pass
5. ✅ Execute Level 1 fold-in (PR #159)
6. ✅ Run gates; proceed to Level 2 on pass
7. ✅ Execute Level 2 fold-in (PR #160)
8. ✅ Run final gates and determinism check
9. ✅ Mark umbrella PR ready and merge to main
10. ✅ Close folded PRs with umbrella reference
11. ✅ Generate final summary & recovery documentation

All logs, diffs, and evidence will be saved to `.smartergpt.local/deliverables/_session/`.

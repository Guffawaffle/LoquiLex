# Epic #16 — Complete Security Posture (Parts 2–4)
**Branch:** `security/epic16-parts2-4`
**Scope:** Dependabot hygiene & PR gating (Part 2), Secret scanning & push protection (Part 3), Supply-chain posture / Scorecards + docs (Part 4).
**Pre-req:** Part 1 (CodeQL advanced setup) is merged and Default CodeQL setup is **disabled**.

---

## Mission / Acceptance Criteria
- **Dependabot**:
  - `.github/dependabot.yml` exists and is tuned for **pip**, **github-actions**, and **npm** (if `/ui` exists).
  - Weekly cadence, PR cap, labels, optional reviewers, and **groups** for low-noise batching.
  - Dependency Review workflow remains active and **fails on high** severity.
- **Secret scanning**:
  - GitHub **Secret scanning** and **Push protection** verified enabled in repo settings.
  - CI secret sweep via **gitleaks** runs on PRs, `main`, and nightly schedule.
  - Local parity: `make sec-scan` runs gitleaks against workspace (no git history by default).
  - Findings (if any) triaged: fixed, accepted risk (short rationale), or follow-up ticket.
- **Supply chain posture**:
  - **OpenSSF Scorecard** workflow runs weekly and uploads SARIF to Code scanning.
- **Docs & policy**:
  - `SECURITY.md` present with PVR (private vulnerability reporting) link and 72h acknowledge target.
  - README contains a brief **Security** section referencing CodeQL, Dependabot, gitleaks, Scorecards, and links to `SECURITY.md`.
- **Branch protection (manual)**:
  - Required checks include: Build/Test, **CodeQL**, **Dependency Review**, **Secret Scan (gitleaks)**.
- **Green CI** for all new workflows on the PR. Deliverables logged to `.github/copilot/current-task-deliverables.md`.

---

## Working Rules (LoquiLex)
- Commit messages use **imperative mood** (e.g., `chore:`, `build:`, `docs:`).
- Offline-first tests remain unchanged.
- Keep workflow `permissions` minimal; grant `security-events: write` only where needed.

---

## Plan of Action

### 0) Create and switch to the feature branch
```bash
git switch -c security/epic16-parts2-4
```

### 1) Dependabot hygiene (Part 2)
**File:** `.github/dependabot.yml` (create or update)

```yaml
version: 2
updates:
  - package-ecosystem: "pip"
    directory: "/"
    schedule: { interval: "weekly" }
    open-pull-requests-limit: 5
    labels: ["deps", "pip"]
    reviewers: ["Guffawaffle"]
    groups:
      prod-deps:
        applies-to: version-updates
        update-types: ["minor", "patch"]
      security-updates:
        applies-to: security-updates

  - package-ecosystem: "github-actions"
    directory: "/"
    schedule: { interval: "weekly" }
    labels: ["deps", "gha"]

  - package-ecosystem: "npm"
    directory: "/ui"
    schedule: { interval: "weekly" }
    open-pull-requests-limit: 5
    labels: ["deps", "npm"]
```

**Ensure Dependency Review gate is present (create if missing):**
**File:** `.github/workflows/dependency-review.yml`
```yaml
name: Dependency Review
on:
  pull_request:
    branches: [ main ]
permissions:
  contents: read
jobs:
  review:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/dependency-review-action@v4
        with:
          fail-on-severity: high
          comment-summary-in-pr: true
```

> _Note_: If `/ui/package.json` does not exist, Dependabot will report no manifests found for npm — acceptable.

### 2) Secret scanning posture (Part 3)
**A) Verify GitHub settings (manual):**
- Settings → **Code security and analysis** → ensure **Secret scanning** and **Push protection** are enabled.

**B) Add CI secret sweep with gitleaks**
**File:** `.github/workflows/gitleaks.yml`
```yaml
name: Secret Scan (gitleaks)

on:
  pull_request:
  push:
    branches: [ main ]
  schedule:
    - cron: "0 3 * * *"  # nightly

permissions:
  contents: read
  security-events: write

jobs:
  scan:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0  # repo history for broader detection
      - name: Gitleaks scan
        uses: gitleaks/gitleaks-action@v2
        with:
          config-path: .gitleaks.toml
          args: --redact
```

**File:** `.gitleaks.toml`
```toml
title = "LoquiLex gitleaks config"

[allowlist]
description = "Allow common non-secret test/placeholder patterns"
paths = [
  '''^\.artifacts/''',
  '''^tests/''',
  '''^\.env\.example$''',
]
regexes = [
  '''dummy[_-]?key''',
  '''example[_-]?secret''',
]
```

**C) Local parity (developer convenience)**
Add a make target for local sweeps (no git history by default).
**Patch:** `Makefile` (append)
```make
.PHONY: sec-scan
sec-scan:
	@docker run --rm -v "$$(pwd)":/repo zricethezav/gitleaks:latest 		detect -s /repo --no-git --redact
```

### 3) OpenSSF Scorecards (Part 4)
**File:** `.github/workflows/scorecards.yml`
```yaml
name: OSSF Scorecard

on:
  schedule:
    - cron: "0 6 * * 1"   # weekly Monday
  workflow_dispatch:

permissions:
  contents: read
  security-events: write

jobs:
  scorecard:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: ossf/scorecard-action@v2.3.3
        with:
          results_file: results.sarif
          results_format: sarif
      - name: Upload SARIF to code scanning
        uses: github/codeql-action/upload-sarif@v3
        with:
          sarif_file: results.sarif
```

### 4) Docs: SECURITY.md & README
**File:** `SECURITY.md` (create or update)
```markdown
# Security Policy

## Supported Versions
LoquiLex is pre-1.0; we support the latest commit on `main` and the most recent tagged release (if any).

## Reporting a Vulnerability
- Prefer **Private Vulnerability Reporting** via GitHub:
  - https://github.com/Guffawaffle/LoquiLex/security/advisories/new
- If that is unavailable, open a minimal **Security** issue without PoC details and request a maintainer contact, or use the contact info on the maintainer’s GitHub profile.
- We aim to acknowledge within **72 hours** and will coordinate a fix and disclosure window as appropriate.

## Security Posture
- Automated checks: CodeQL (code scanning), Dependabot & Dependency Review (supply chain), gitleaks (secrets), OpenSSF Scorecards (posture).
- We welcome hardening suggestions via issues or PRs.
```

**File:** `README.md` — add/update section
```markdown
## Security

LoquiLex is maintained with an automated security posture:
- **CodeQL** (advanced workflow) for static analysis
- **Dependabot** + **Dependency Review** for supply-chain changes
- **gitleaks** for CI secret sweeps (with Push Protection enabled in GitHub)
- **OpenSSF Scorecards** for repo hygiene and best practices

See [SECURITY.md](./SECURITY.md) for how to report vulnerabilities.
```

### 5) Branch protection (manual)
- In **Settings → Branches → Branch protection rules** for `main`, ensure **Required status checks** include:
  - Build/Test (your standard CI),
  - **CodeQL**,
  - **Dependency Review**,
  - **Secret Scan (gitleaks)**.
- Enable **Require pull request reviews** and **Dismiss stale approvals** (optional).

---

## Verification / Definition of Done
- All new workflows pass on the PR (pull_request) and schedule triggers are configured.
- Security tab shows:
  - Code Scanning: CodeQL and Scorecards SARIF (if any findings).
  - Secret Scanning: push protection enabled; no new secrets in CI scans.
  - Dependency Review: continues to gate **high** severity.
- Deliverables file `.github/copilot/current-task-deliverables.md` includes:
  1. **Executive Summary** — what changed and why.
  2. **Steps Taken** — branch, commits, files added/modified.
  3. **Evidence & Verification** — links to workflow runs, Security tab screenshots/log excerpts.
  4. **Final Results** — confirm green CI; list findings and dispositions (fixed/accepted risk/follow-up ticket).
  5. **Files Changed** — list of added/updated files.

---

## Commit Plan (examples)
- `chore(deps): tune dependabot (pip/gha/npm) with groups and labels`
- `ci(security): add gitleaks workflow + make sec-scan`
- `ci(security): add OpenSSF Scorecard workflow (weekly + SARIF upload)`
- `docs(security): add/update SECURITY.md and README Security section`

---

## Finish & PR
```bash
git add -A
git commit -m "ci(security): add gitleaks + scorecards; tune dependabot; update docs (epic16 parts 2–4)"
git push -u origin security/epic16-parts2-4
# open PR targeting main; title should follow commit style
```

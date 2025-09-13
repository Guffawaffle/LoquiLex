# Epic #16 — Align LoquiLex with GitHub Security Scanning (CodeQL, Dependabot, Secret Scanning)

## Title
Epic #16 — Align LoquiLex with GitHub Security Scanning (CodeQL, Dependabot, Secret Scanning)

## Background
Issue #16 requires aligning the repo with GitHub’s security surfaces (code scanning, dependency scanning, secret scanning) and documenting a disclosure path. Current repo state shows no SECURITY.md present.

## Goals (Acceptance Criteria)
- **Code scanning:** CodeQL workflow runs on PRs to `main`, pushes to `main`, and weekly schedule, covering **Python** and **JavaScript/TypeScript**.
- **Dependency controls:**
  - Dependabot enabled for **pip** and **GitHub Actions** at repo root, and **npm** under `/ui` (if present).
  - Dependency Review action gates PRs on **high** severity or worse.
- **Secret scanning posture:**
  - Add a CI secret scan using **gitleaks** on PRs, pushes to `main`, and a nightly schedule.
  - Provide a local `make sec-scan` target for devs.
- **Security policy:** Add `SECURITY.md` with clear vuln-report path.
- **Docs:** README “Security” section briefly explains our posture and links to `SECURITY.md`.
- **Green CI:** All workflows pass in CI. Any found alerts are listed in `current-task-deliverables.md` with dispositions (fixed, ignored-with-rationale, or follow-up ticket created).

## Non-Goals
- Changing runtime architecture or test behavior.
- Turning off offline-first testing. New security jobs run in GitHub Actions; local dev remains offline-friendly.

---

## Changes to Make

### 1) Add CodeQL
Create `.github/workflows/codeql.yml`:

```yaml
name: CodeQL

on:
  push:
    branches: [ "main" ]
  pull_request:
    branches: [ "main" ]
  schedule:
    - cron: "0 4 * * 0"  # weekly Sunday 04:00 UTC

permissions:
  contents: read

jobs:
  analyze:
    name: Analyze (${{ matrix.language }})
    runs-on: ubuntu-latest
    permissions:
      actions: read
      contents: read
      security-events: write
    strategy:
      fail-fast: false
      matrix:
        language: [ "python", "javascript" ]
    steps:
      - name: Checkout
        uses: actions/checkout@v4
      - name: Initialize CodeQL
        uses: github/codeql-action/init@v3
        with:
          languages: ${{ matrix.language }}
      - name: Autobuild
        uses: github/codeql-action/autobuild@v3
      - name: Perform CodeQL Analysis
        uses: github/codeql-action/analyze@v3
        with:
          category: "/language:${{ matrix.language }}"
```

### 2) Dependency Review gate
Create `.github/workflows/dependency-review.yml`:

```yaml
name: Dependency Review

on:
  pull_request:
    branches: [ "main" ]

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

### 3) Dependabot updates
Create `.github/dependabot.yml`:

```yaml
version: 2
updates:
  - package-ecosystem: "pip"
    directory: "/"
    schedule:
      interval: "weekly"
    open-pull-requests-limit: 5

  - package-ecosystem: "github-actions"
    directory: "/"
    schedule:
      interval: "weekly"

  - package-ecosystem: "npm"
    directory: "/ui"
    schedule:
      interval: "weekly"
    open-pull-requests-limit: 5
```

> Note: If `/ui/package.json` is absent, Dependabot will simply report no manifests found—this is acceptable.

### 4) Secret scanning via gitleaks (CI)
Create `.github/workflows/gitleaks.yml`:

```yaml
name: Secret Scan (gitleaks)

on:
  pull_request:
  push:
    branches: [ "main" ]
  schedule:
    - cron: "0 3 * * *"  # nightly 03:00 UTC

permissions:
  contents: read
  security-events: write

jobs:
  scan:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0
      - name: Gitleaks scan
        uses: gitleaks/gitleaks-action@v2
        with:
          config-path: .gitleaks.toml
          args: --redact
```

Create `.gitleaks.toml` (tune as needed):

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

### 5) Makefile convenience target
Append to `Makefile`:

```make
.PHONY: sec-scan
sec-scan:
	@docker run --rm -v "$$(pwd)":/repo zricethezav/gitleaks:latest \
		detect -s /repo --no-git --redact
```

### 6) SECURITY.md
Create `SECURITY.md`:

```markdown
# Security Policy

## Supported Versions
LoquiLex is pre-1.0; we support the latest commit on `main` and the most recent tagged release (if any).

## Reporting a Vulnerability
- Prefer **Private Vulnerability Reporting** via GitHub:
  - https://github.com/Guffawaffle/LoquiLex/security/advisories/new
- If that is unavailable, please open a minimal **Security** issue without PoC details and request a maintainer contact, or use the contact info on the maintainer’s GitHub profile.
- We aim to acknowledge within 72 hours and will coordinate a fix and disclosure window as appropriate.

## Security Posture
- Automated checks: CodeQL (code scanning), Dependabot & Dependency Review (supply chain), gitleaks (secrets).
- We welcome hardening suggestions via issues or PRs.
```

### 7) README patch
Add a short “Security” section linking to `SECURITY.md` and mentioning CodeQL/Dependabot/Secret scan.

---

## Definition of Done (Verification)
- **Security tab shows**:
  - “Security policy detected” after merging (from `SECURITY.md`).
  - CodeQL workflow present and green on a PR against `main`.
  - Dependency Review leaves a PR comment summary and blocks high-severity.
  - Gitleaks job runs on PR and schedule; no secrets reported (or findings triaged).
- **Dependabot PRs** appear (if updates available).
- **Deliverables file** lists:
  - Workflow run links, any alerts found, and actions taken (fixes or follow-ups).
  - Diffs for all added files and the README patch.

## Commit Style
Use imperative mood:
- `chore(security): add CodeQL, Dependabot, gitleaks, and SECURITY.md`
- `docs: add security section to README`
- `build: add make sec-scan target`

## Output
Write the full report to `.github/copilot/current-task-deliverables.md` with:
- Executive summary
- Steps taken
- Evidence (workflow URLs, logs, screenshots if useful)
- Final results and remaining items
- Files changed list

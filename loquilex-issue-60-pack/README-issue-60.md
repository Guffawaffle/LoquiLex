# LoquiLex Issue #60 — Sub-Issues Pack

This pack creates child issues under **#60** (“JS-first architecture”) using GitHub CLI.

## Contents
- `create-sub-issues-60.sh` — Bash script that reads Markdown files and creates issues.
- `issues/60/*.md` — Full sub-issue descriptions (titles pulled from the first `# H1`).

## Requirements
- GitHub CLI: `gh` (authenticated with appropriate repo scope).
- Bash shell.

## Usage (from your project root)
```bash
# Unzip this pack in the repo root, then:
bash create-sub-issues-60.sh Guffawaffle/LoquiLex --dry-run  # preview
bash create-sub-issues-60.sh Guffawaffle/LoquiLex            # create for real
```

Notes:
- Each created issue is labeled: `epic-child`, `architecture`, `ui`, `offline-first`.
- The script comments on parent **#60** for traceability after each creation.
- You can edit the Markdown files in `issues/60/` before running to tweak details.

## Cleanup
After running and verifying, delete the pack:
```bash
rm -rf loquilex-issue-60-pack*
```

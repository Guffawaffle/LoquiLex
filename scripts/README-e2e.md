# CI e2e Artifact Triage Kit

This small kit helps you pull e2e logs & artifacts from GitHub Actions and summarize failing tests.

## Quick Start

```bash
# Authenticate GH CLI first (one time)
gh auth login

# Fetch a specific run/job (example IDs you provided)
bash scripts/ci_fetch_e2e_artifacts.sh --repo Guffawaffle/LoquiLex --run-id 17691185152 --job-id 50284888074

# Inspect outputs
ls -la .artifacts/e2e-17691185152/
cat .artifacts/e2e-17691185152/e2e-failures-summary.txt
```

## Outputs
- `e2e-job.log` — raw job log
- `e2e-failures-summary.txt` — parsed JUnit failures (or FAILED lines from log)

## Notes
- Downloads **all** artifacts for the run into the chosen output directory.
- The parser looks for typical pytest JUnit XML naming patterns; it falls back to scanning the job log if none are found.

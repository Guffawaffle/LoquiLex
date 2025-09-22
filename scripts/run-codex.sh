#!/usr/bin/env bash
set -euo pipefail

# Ensure the GitHub CLI has active auth configured
if ! gh auth status >/dev/null 2>&1; then
  echo "error: gh auth login is required before launching Codex" >&2
  exit 1
fi

# Pull the token from the GitHub CLI keychain without echoing it to the console
GITHUB_TOKEN=$(gh auth token 2>/dev/null)
if [[ -z "${GITHUB_TOKEN}" ]]; then
  echo "error: unable to read GitHub token from gh" >&2
  exit 1
fi

export GITHUB_TOKEN

# Hand execution to Codex with the authenticated environment
exec codex "$@"

#!/usr/bin/env bash
set -euo pipefail

# Create sub-issues under the given repo, linking to parent epic #60.
# Requirements: GitHub CLI (gh) authenticated with repo scope.
# Usage: ./create-sub-issues-60.sh [owner/repo] [--dry-run]
# Defaults to repo: Guffawaffle/LoquiLex

REPO="${1:-Guffawaffle/LoquiLex}"
DRY="${2:-}"
BASE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/60"
PARENT_NUM=60

if ! command -v gh >/dev/null 2>&1; then
  echo "Error: gh (GitHub CLI) not found in PATH." >&2
  exit 1
fi

create_issue() {
  local file="$1"
  local title
  title="$(grep -m1 '^# ' "$file" | sed 's/^# \s*//')"
  if [[ -z "${title// /}" ]]; then
    echo "Skipping $file: no H1 title found" >&2
    return 1
  fi
  echo "Creating issue from: $file"
  if [[ "$DRY" == "--dry-run" ]]; then
    echo "gh issue create --repo "$REPO" --title "$title" --body-file "$file" "
    return 0
  fi

  url="$(gh issue create --repo "$REPO"     --title "$title"     --body-file "$file")"
  echo "Created: $url"
  # Link in parent by leaving a comment for traceability
  num="$(echo "$url" | sed -E 's#.*/issues/([0-9]+).*#\1#')"
  if [[ "$num" =~ ^[0-9]+$ ]]; then
    gh issue comment "$PARENT_NUM" --repo "$REPO" --body "Tracking: created child issue #$num — $title"
  fi
}

main() {
  if [[ ! -d "$BASE_DIR" ]]; then
    echo "Error: sub-issues directory not found: $BASE_DIR" >&2
    exit 1
  fi
  shopt -s nullglob
  for f in "$BASE_DIR"/*.md; do
    create_issue "$f"
  done
  echo "Done."
}

main "$@"

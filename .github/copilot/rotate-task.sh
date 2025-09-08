#!/usr/bin/env bash
set -euo pipefail
BASE=".github/copilot"
ARCHIVE="$BASE/archive"
mkdir -p "$ARCHIVE"
case "${1:-}" in
  promote)
    if [ -f "$BASE/current-task-deliverables.md" ]; then
      mv "$BASE/current-task-deliverables.md" "$ARCHIVE/$(date +%F)-current.md"
    fi
    if [ -f "$BASE/new-task-deliverables.md" ]; then
      mv "$BASE/new-task-deliverables.md" "$BASE/current-task-deliverables.md"
      echo "Promoted new → current"
    else
      echo "No new task to promote"
    fi
    ;;
  advance)
    if [ -f "$BASE/next-task-deliverables.md" ]; then
      mv "$BASE/next-task-deliverables.md" "$BASE/new-task-deliverables.md"
      echo "Advanced next → new"
    else
      echo "No next task to advance"
    fi
    ;;
  *)
    echo "Usage: $0 {promote|advance}"
    ;;
esac

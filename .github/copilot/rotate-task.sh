#!/usr/bin/env bash
set -euo pipefail

BASE=".github/copilot"
ARCHIVE="$BASE/archive"
mkdir -p "$ARCHIVE"

timestamp="$(date +%F-%H%M%S)"
logfile="$ARCHIVE/resets.log"

case "${1:-}" in
  promote)
    # Promote new → current
    if [ -f "$BASE/new-task-deliverables.md" ]; then
      mv "$BASE/new-task-deliverables.md" "$BASE/current-task-deliverables.md"
      echo "Promoted new → current"
    else
      echo "No new task to promote"
    fi
    ;;

  advance)
    # Advance next → new
    if [ -f "$BASE/next-task-deliverables.md" ]; then
      mv "$BASE/next-task-deliverables.md" "$BASE/new-task-deliverables.md"
      echo "Advanced next → new"
    else
      echo "No next task to advance"
    fi
    ;;

  complete)
    # Archive current task and deliverables, then remove them
    if [ -f "$BASE/current-task.md" ]; then
      mv "$BASE/current-task.md" "$ARCHIVE/${timestamp}-task.md"
      echo "Archived current-task.md"
    fi
    if [ -f "$BASE/current-task-deliverables.md" ]; then
      mv "$BASE/current-task-deliverables.md" "$ARCHIVE/${timestamp}-deliverables.md"
      echo "Archived current-task-deliverables.md"
    fi

    rm -f "$BASE/current-task.md" "$BASE/current-task-deliverables.md"
    echo "Cleared active task state"
    ;;

  --reset)
    # Just remove current task files without archiving, and log the action
    rm -f "$BASE/current-task.md" "$BASE/current-task-deliverables.md"
    {
      echo "[$(date -u +'%Y-%m-%dT%H:%M:%SZ')] reset: removed current-task.md and current-task-deliverables.md"
      if [ -n "${RESET_NOTE:-}" ]; then
        echo "  note: ${RESET_NOTE}"
      fi
    } >> "$logfile"
    echo "Reset: removed current task files without archiving (logged to $logfile)"
    ;;

  *)
    echo "Usage: $0 {promote|advance|complete|--reset}"
    ;;
esac

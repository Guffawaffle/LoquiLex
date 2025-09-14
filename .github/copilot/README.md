# Copilot Workflow Documentation

## Overview

This directory contains the GitHub Copilot Coding Agent workflow for LoquiLex. The agent follows a structured task-based development process with clear deliverables and quality gates.

## Files

- `current-task.md` - **Active task** (authoritative source of truth)
- `current-task-deliverables.md` - **Task execution log** (detailed output)
- `next-task.md` - **Upcoming task** (queued)
- `main.prompt.md` - **Agent instructions** (workflow rules)
- `rotate-task.sh` - **Task management script**

## Workflow

### 1. Task Assignment
- Tasks are defined in `current-task.md`
- Contains objectives, patch sketches, commands, and acceptance criteria
- **Source of truth** - agent must follow exactly

### 2. Execution
- Agent reads `current-task.md` and follows `AGENTS.md` guidelines
- Applies patches, runs quality gates, verifies acceptance criteria
- Records all steps in `current-task-deliverables.md`

### 3. Quality Gates
```bash
make fmt-check && make lint && make typecheck && make test
```

### 4. Deliverables
- **Executive Summary** - What was attempted/changed/outcome
- **Steps Taken** - Detailed execution log
- **Evidence & Verification** - Full command outputs, diffs, logs
- **Final Results** - Success confirmation, follow-ups
- **Files Changed** - Complete list with change types

### 5. Task Rotation
Use the rotation script to manage task lifecycle:

```bash
# Complete current task and archive deliverables
.github/copilot/rotate-task.sh complete

# Promote next task to current
.github/copilot/rotate-task.sh promote

# Advance queued task to next
.github/copilot/rotate-task.sh advance
```

## Task States

- **current-task.md** - Active task being worked on
- **next-task.md** - Queued task (promote to make current)
- **archive/** - Completed tasks with deliverables

## Branch Strategy

- Tasks specify target branch (never work on `main` directly)
- Agent creates feature branches as needed
- All changes committed with imperative mood messages

## Quality Standards

- **Minimal diffs** - Only touch files in scope
- **Green CI** - All tests, lint, type checks pass
- **Offline-first** - No network dependencies in tests
- **Security** - Gitleaks, CodeQL, Scorecards all pass
- **Documentation** - Updates when behavior changes

## Example Task

See archived tasks in `archive/` for examples of completed work with full deliverables.
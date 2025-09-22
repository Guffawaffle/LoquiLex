# LoquiLex Project Overview

This document captures the brand, vision, goals, principles, and workflow of the LoquiLex project, consolidating information from all recent project chats and decisions. It is intended as a living reference so that individual PR-specific chats can be pruned without losing context.

---

## Brand Statement

**LoquiLex** is an open-source live captioning and translation app designed to make conversations accessible, multilingual, and beautifully human. Inspired by Jessie—whose voice reminds us that every word matters—it's built for travelers, collaborators, and communities who believe understanding should never be out of reach.

---

## Vision

- **Realtime Bridge**: Enable seamless, sub-second EN ↔ ZH captioning and translation.
- **Local-first**: No reliance on SaaS — models run locally (Whisper, NLLB/M2M).
- **Accessible for All**: Lower the barrier to multilingual communication in personal, professional, and community contexts.
- **Trust & Transparency**: Users see what’s happening, what’s cached, what’s clipped, and what’s queued.

---

## Goals

### Short-term (current cycle)
- ✅ CI separation: unit vs. e2e tests (`@pytest.mark.e2e` enforced).
- ✅ Lint & format standardization: Ruff + Black at 100 chars, Flake8 removed.
- ✅ Type checking: Mypy integrated in **warn-only mode**; last 4 errors resolved; incremental strictness plan in place.
- ✅ Copilot/Codex agents integrated: prompts in `.github/prompts/` drive execution, `.github/copilot/current-task-deliverables.md` captures the log.
- ✅ Repo cleanup: prune historical artifacts with git-filter-repo, harden `.gitignore`.

### Mid-term (next cycle)
- 🔄 Incrementally tighten mypy (per-module strictness).
- 🔄 Prune unused dev dependencies (`pytest-mock`, `pytest-timeout`, `freezegun`) after usage audit.
- 🔄 Harden E2E tests to cover stop/start lifecycle, env var handling, failure cases.
- 🔄 Polish developer experience (VSCode config, Makefile targets, consistent CI jobs).

### Long-term (stretch)
- 🌐 Add Mandarin TTS for reverse captions.
- 📞 WebRTC bridge for real-time call captioning/translation.
- 🎛 GPU passthrough experiments under WSL2/Docker.
- 🧪 Fine-tuned colloquial models.

---

## Core Principles

- **Offline-first**: All functionality must work without network access.
- **Resilient Comms**: WebSockets with reconnect, monotonic time, bounded queues, snapshot rehydrate.
- **Transparency**: Clear UI + logs of latency, device, compute load.
- **Minimal, focused diffs**: Every PR is scoped; no sprawl.
- **Imperative commit messages**: e.g., `Fix tests…`, `Add type annotations…`.
- **CI Green**: PRs must pass lint, format, unit, e2e, and typecheck gates.

---

## Workflow

- **One PR = One Chat**
  - Each PR has a dedicated chat tied to its prompt or maintainer instructions.
  - Deliverables are written to `.github/copilot/current-task-deliverables.md` on that branch.

- **Meta Chat**
  - This planning chat exists for pruning, creating new tasks, and setting direction.
  - Can be deleted once its insights are captured here.

- **Copilot/Codex Agent Rules**
  - Defined in `AGENTS.md`.
  - Agents execute tasks from the active prompt/spec and must log full evidence in `.github/copilot/current-task-deliverables.md`.

---

## Roadmap

1. **Types**
   - Incrementally enforce strictness in `api/`, `audio/`, and `cli/` modules.
   - Eventually flip global mypy to error mode (no `|| true`).

2. **Dependencies**
   - Audit test plugins (`pytest-mock`, `pytest-timeout`, `freezegun`).
   - Remove unused packages from dev dependencies.

3. **Testing**
   - Expand E2E coverage (stop/start lifecycle, server env vars).
   - Add unit tests for corner cases (e.g., `stop_fn is None`).

4. **Infrastructure**
   - Finalize repo pruning (filter-repo, .gitignore hardening).
   - Keep `.vscode/settings.json` minimal but enforce Ruff + Black.

5. **Stretch**
   - Investigate GPU passthrough under WSL2/Docker.
   - Explore TTS and WebRTC integration.

---

## Status Summary

- **Repo Health**: Clean, focused, passing CI.
- **Linting**: Ruff + Black at 100 chars, unified.
- **Typing**: Mypy integrated; 0 errors; incremental strictness plan ready.
- **Testing**: Unit + e2e separated; 25 tests passing.
- **Agent Workflow**: Proven successful with PRs; deliverables captured.
- **Next Steps**: Tighten types, prune dev deps, expand tests.

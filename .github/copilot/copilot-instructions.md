# Copilot Instructions (Repo-wide)

Stable guidance for Copilot Chat/Review/Agent:
- Commit style: imperative ("Add...", "Fix...", "Update...").
- Prefer minimal, composable changes.
- Always prepend a Model Header in prompts.
- Use the 7-section task template:
  1) Model Header
  2) Context Recap
  3) Goals
  4) Changes to Implement
  5) Deliverables
  6) Acceptance Criteria / Test Checklist
  7) Notes / Caveats

**Active task:** prefer ./.github/copilot/current-task-deliverables.md
Fallback: ./.github/copilot/new-task-deliverables.md

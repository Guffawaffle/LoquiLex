# Copilot Instructions (Repo-wide)

Stable guidance for Copilot Chat / Review / Agent.
For detailed workflow rules, **always refer to [`AGENTS.md`](../../AGENTS.md)**.

---

## Core Rules
- **Commit style**: imperative (`Add...`, `Fix...`, `Update...`).
- **Changes**: minimal, composable, and scoped to the current task.
- **Model header**: prepend in prompts (role + task context).

---

## Task Source of Truth
- **Active**: `.github/copilot/current-task.md`
- **Fallback**: `.github/copilot/new-task-deliverables.md`

---

## Task Template (7 sections)
1. **Model Header**
2. **Context Recap**
3. **Goals**
4. **Changes to Implement**
5. **Deliverables**
6. **Acceptance Criteria / Test Checklist**
7. **Notes / Caveats**

---

## Notes
- Follow **AGENTS.md** for step-by-step execution, quality gates, and CI requirements.
- All outputs and logs go into the deliverables file defined in the current task.

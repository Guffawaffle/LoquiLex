# instruction
Implement and finish **UI: dual panels (source/target), timestamps toggle, dark theme** (#34) on top of PR #54. Make minimal diffs to land the acceptance criteria below. Follow **AGENTS.md** and repo conventions (offline-first, small commits, imperative messages).

# branch
ONLY work on branch copilot/fix-34. If the user is currently on anothe branch stop immediately and report to the user. If this is agent mode then ignore this file if you are not working on that branch

# context
- Phase 1 realtime bridge: dual transcript panels with partial/final separation; transparent state; dark theme default.
- Resilient comms (#32/#52) provide reconnect and snapshot; streaming ASR (#43) supplies partial/final with monotonic timestamps.
- We will:
  1) Add **autoscroll pause + “Jump to live”**,
  2) Ensure **partial→final replacement** is stable,
  3) Make **timestamps toggle** layout-stable,
  4) Solidify **dark theme** via CSS variables (WCAG AA),
  5) Add **a11y roles/labels**,
  6) Persist **theme/timestamps** in `localStorage`,
  7) Add unit/component/a11y **tests**.

# constraints
- No new runtime deps unless essential. Prefer standard React/testing libs already in repo.
- Keep changes scoped to `ui/web/` plus minimal docs.
- Escape user text (no `dangerouslySetInnerHTML`).
- Keyboard shortcuts must not hijack input fields.
- Commit messages: **imperative mood** (“Add…”, “Fix…”).
- Offline-first: do not introduce network telemetry.

# tasks
1. **Autoscroll pause & Jump to live**
   - Add `useAutoScroll(ref)` hook:
     - Detect “near bottom” (`< 16px` threshold). When the user scrolls up, set `paused=true`.
     - Expose `jumpToLive()` to scroll to bottom and set `paused=false`.
   - In `TranscriptPanel`, wire the hook; in `StatusBar`, show a compact **“Jump to live”** chip/button when `paused=true`.

2. **Partial→Final replacement (stable keys)**
   - Ensure each rendered row key is **`utterance_id + ':' + segment_seq`**.
   - When a **final** arrives for an existing partial, **replace in place** (no append) to avoid jitter.

3. **Timestamps toggle (layout-stable)**
   - Add global toggle **Timestamps (T)**. Persist to `localStorage` as `ui.showTimestamps`.
   - Format: `mm:ss.mmm` (use `hh:mm:ss.mmm` if ≥ 1h).
   - Reserve a monospace, fixed-width column for timestamps (e.g., `ch` units) so ON/OFF doesn’t shift text.

4. **Dark theme via CSS variables**
   - Dark default; support **Dark / Light / System** with shortcut **D**. Persist `ui.theme`.
   - Implement tokens in `:root` and `[data-theme="dark"]`:
     - `--lx-bg`, `--lx-fg`, `--lx-muted`, `--lx-accent`, `--lx-panel`, `--lx-border`, focus/hover states.
   - Respect `prefers-color-scheme` when `System` is chosen.
   - Verify **WCAG AA** contrast for text and interactive elements.

5. **A11y & status**
   - `StatusBar` uses `role="status"` with polite updates for **Connected / Reconnecting / Offline**.
   - Panels labeled and landmarked: e.g., `aria-labelledby="source-panel"` / `"target-panel"`.
   - Ensure visible focus outlines in dark mode; keyboard access to toggles and “Jump to live”.

6. **Types & state**
   - Add/confirm in `ui/web/src/types.ts`:
     ```ts
     export type TranscriptKind = 'partial' | 'final';
     export interface TranscriptLine {
       utterance_id: string;
       segment_seq: number;
       kind: TranscriptKind;
       text: string;
       t_start_ms: number; // session-monotonic or wall; UI formats
     }
     ```
   - Keep separate source/target stores; align by `(utterance_id, segment_seq)`.

7. **Performance guards (lightweight)**
   - Coalesce rapid partial re-renders via `requestAnimationFrame` (≤ ~30fps).
   - Add soft memory bound (e.g., keep last N=5000 lines; drop oldest).
   - Leave virtualization behind a tiny adapter (no new dep required now).

8. **Docs**
   - Create/update `docs/ui-basics.md`: toggles (T/D), timestamps, “Jump to live”, connection states.

9. **Tests**
   - **Unit**
     - `utils/time`: formatting incl. hour rollover.
     - Reducer: partial→final replacement keeps order and key stability.
     - Prefs: read/write `ui.showTimestamps`, `ui.theme`.
   - **Component**
     - Autoscroll pauses on manual scroll; resumes via “Jump to live”.
     - Panels render partial (subtle style) vs final (normal).
     - Timestamps toggle does not change line wrapping or cause thrash.
   - **A11y**
     - `role="status"` announces state; no critical Axe violations in dark theme.

# acceptance-criteria
- Dual panels render and append at bottom with autoscroll; if user scrolls up, autoscroll pauses and a **“Jump to live”** control appears and works.
- Partial→final swaps occur **in place** without scroll jumps or layout jitter.
- Timestamps toggle (T) instantly affects both panels, persists, and **does not** shift text layout.
- Dark theme is default; **Dark/Light/System** options (D) persist and meet **WCAG AA** contrast.
- Screen-reader and keyboard navigation work for toggles and “Jump to live”.
- Text content is escaped; no unsafe HTML injection.
- Tests pass and cover the above (unit + component + a11y).

# file-map (expected touch points)
- `ui/web/src/App.tsx`
- `ui/web/src/components/DualPanelView.tsx`
- `ui/web/src/components/TranscriptPanel.tsx`
- `ui/web/src/components/StatusBar.tsx`
- `ui/web/src/hooks/useAutoScroll.ts`
- `ui/web/src/utils/time.ts`
- `ui/web/src/types.ts`
- `ui/web/src/styles.css` (or `styles/theme.css`)
- `docs/ui-basics.md`
- `ui/web/tests/unit/time.test.ts`
- `ui/web/tests/unit/reducer.test.ts`
- `ui/web/tests/component/panels.autoscroll.test.tsx`
- `ui/web/tests/a11y/dark-mode.test.tsx`

# implementation-notes
- Timestamp width: render a dedicated `<span class="ts">` with monospace font and fixed width (e.g., `8ch` or computed for `hh:mm:ss.mmm`).
- Keyboard shortcuts: ignore when focus is in text inputs/textareas.
- StatusBar should consume connection state from existing store and expose ARIA-live updates.
- Keep styling tokens minimal and central; avoid hard-coded colors.

# runbook
- Local: `make dev` to run the UI; `make test` for unit/component; `make run-ci-mode` to mirror CI.
- Verify long scrolling sessions (simulate rapid partials) and offline/reconnect behavior.
- Confirm no console errors/warnings remain.

# deliverables
- Code + tests as above.
- `docs/ui-basics.md`.
- Update `CHANGELOG.md` under “Added”.
- Write **.github/copilot/current-task-deliverables.md** with:
  - Summary of changes
  - Test outputs (no truncation)
  - Screenshots or brief notes proving acceptance criteria
  - File list of modified/added files

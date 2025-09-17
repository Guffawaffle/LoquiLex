#instruction
Fix **SPA fallback** so deep routes (e.g., `/settings`, `/sessions`) return **200** with `text/html` (serving `index.html`) without shadowing API/WS routes.

## Do exactly this (tiny diffs)
1) **Static + Fallback**
   - Ensure the built UI directory `ui/app/dist` is served at the site root.
   - Add a **catch‑all GET/HEAD** fallback that returns `ui/app/dist/index.html` with **200** when it exists.
   - Register the fallback **after** API and static routes so it never shadows `/api/*`, `/ws/*`, or `/assets/*`.
   - Remove any reference to dev‑only favicon `vite.svg` in the source HTML if present.

2) **Guardrails**
   - Fallback must trigger **only** for GET and HEAD (not POST/PUT/etc.).
   - Do **not** intercept `/api/*`, `/ws/*`, or `/assets/*` paths.

## Acceptance Criteria
- `GET /settings` → **200** with `content-type: text/html` (index.html).
- `GET /api/health` → **API JSON** (not index.html).
- `GET /ws/{sid}` → **WebSocket** works (unchanged).
- `GET /assets/<built-file>` → **200** with correct `content-type`.
- `ui/app/dist/index.html` (and source) do **not** reference `/vite.svg`.

#requirements
- Branch: continue on your current working branch.
- Minimal diffs; reuse existing patterns; **no new dependencies**.

#deliverable-format
Write `.github/copilot/current-task-deliverables.md` with:
1) **Executive Summary** — one paragraph: what changed, why, outcome.
2) **Steps Taken** — timestamps, key commands, files edited.
3) **Evidence & Verification** — paste outputs for:
   - `curl -sI http://127.0.0.1:8000/settings | grep -E 'HTTP/|content-type'` → `200` + `text/html`.
   - `curl -sI http://127.0.0.1:8000/api/health | head -n1` → shows API status (not HTML).
   - `ASSET=$(ls ui/app/dist/assets | head -n1); curl -sI "http://127.0.0.1:8000/assets/$ASSET" | grep -E 'HTTP/|content-type'` → `200` + correct type.
   - `grep -RIn "vite.svg" ui/app/index.html ui/app/dist/index.html || true` → no matches.
4) **Final Results** — pass/fail.
5) **Files Changed** — each file and purpose.

#output
Write only the deliverables file into `.github/copilot/current-task-deliverables.md`.

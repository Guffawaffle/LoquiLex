
# LoquiLex — Product Goals (Phase‑1)
**Last Updated:** 2025-09-14  
**Status:** Living document (update as scope evolves)  
**Owners:** Lex × Guff

> LoquiLex is a local‑first, privacy‑focused live captioning & translation app.  
> This doc captures the high‑level goals we treat as product truths for Phase‑1.

---

## Pillars (canonical)
- **CLI‑first**: Full pipeline runnable from CLI (live + batch).
- **Model‑agnostic**:
  - **ASR** pluggable (default: faster‑whisper/CTranslate2).
  - **MT** pluggable (default: NLLB/M2M).
  - **Exporters** (VTT/SRT/TXT/JSON) are **model‑independent**.
- **Model management**: Install / list / remove / switch via **CLI and UI**.
- **Privacy / offline‑first**: No network by default; explicit opt‑ins only.
- **Simple vs Advanced UI**: Clean defaults for most users; expert controls for power users.

---

## Product Goals
- **Realtime Bridge** (ASR → MT) with sub‑second experience.
- **Word‑count gated partials (EN→ZH)**: default **3 words**, with punctuation/silence/debounce triggers to avoid awkward running Chinese.
- **Pluggable VAD/segmentation**: swap silence heuristics vs `webrtcvad` without changing higher layers.
- **Headless Server Mode**: `loquilex serve` (FastAPI + WebSockets) using same engine as CLI.
- **Cross‑platform packaging**: Windows (incl. WSL2), Linux, macOS; Docker image; `pipx` route for devs.
- **Config layering**: `LX_*` env → profile file → CLI flags; user profiles export/import.
- **Diagnostics**: `loquilex doctor` (GPU/CPU detection, paths, permissions, model sanity).
- **Resilience**: reconnect + snapshot rehydrate; idempotent finals; bounded queues/backpressure.
- **Performance budgets** (p50/p95): ASR partial cadence, finalization latency, MT turnaround.
- **Session lifecycle**: start/stop, local transcript store, optional audio capture (off by default), retention policy.
- **Exports**: TXT/JSON + VTT/SRT; bilingual option; rolling rotation by size/lines.
- **Accessibility**: caption scaling, high‑contrast, keyboard shortcuts.
- **Docs**: CLI reference, offline quickstart, model table, troubleshooting, privacy statement.
- **Plugin API (lightweight)**: stable adapters for **ASR/MT/VAD/Exporter** backends.

---

## Non‑Negotiables (Phase‑1)
1. **EN→ZH word‑count cadence** (default 3) with punctuation/silence/debounce guards.  
2. **Snapshot rehydrate** with stable `segment_id`; **never duplicate finals**.  
3. **Deterministic offline CI** (fake ASR/MT, golden exporters).  
4. **Bounded queues**: drop oldest **partials** only; finals preserved.  
5. **Monotonic timestamps** for ordering; wall‑clock only for display.

---

## CLI Surface (reference)
- `loquilex live en-zh` — mic → captions/translation (TTY/WS).  
- `loquilex transcribe <audio>` — batch to TXT/VTT/SRT/JSON.  
- `loquilex models [list|install|remove|set-default]` — manage models.  
- `loquilex serve` — start WS/API for the UI (headless server).  
- `loquilex export <json>` — regenerate VTT/SRT from saved transcripts.  
- `loquilex doctor` — diagnostics & environment checks.

---

## Testing & CI (offline)
- **Unit**: cadence triggers, punctuation/silence, debounce, idempotency.
- **Integration**: ASR → aggregator → cadence on synthetic audio (fixed seeds).
- **E2E**: WS stream → UI → exporters; golden VTT/SRT fixtures.
- **Quality gates**: ruff/mypy green; security scanners (gitleaks/scorecards) pass.
- **Zero network** in CI; model paths stubbed; fake modules for ASR/MT.

---

## Privacy Pledge (Phase‑1)
- No telemetry or network calls by default.  
- All data stays local unless the user explicitly exports.  
- Clear, human‑readable settings explaining what’s on/off.

---

## Compatibility & Versioning
- **SemVer** for releases; document config migrations across minor versions.
- Preserve exporter formats (VTT/SRT/TXT/JSON) stability; changes require a migration note and tests.

---

*Keep this file short and decisive. For in‑depth architecture and schemas, see `docs/ARCHITECTURE.md` and `docs/PROTOCOL.md` (to be added).*

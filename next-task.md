# Copilot Task: File Types & Live Outputs — Greenfield EN→ZH

**You are an expert in ASR, live captioning, and MT.** You are working **inside `greenfield/` only** (do not modify files outside this directory). Implement *file-type* behavior for **two concurrent outputs**:

1) **Realtime partial TT (transcription & translation)** — *text-only*, no timestamps, a single “current line” that **keeps getting rewritten** until a breakpoint (finalization) is reached.
2) **Finalized TT** — always export **TXT**, with optional **VTT** and/or **SRT** outputs on each finalization event.

Each run **overwrites** previous run outputs. Add an **optional “max lines”** cap for text files that trims the oldest lines as new ones are appended. Add an option to **save full audio** of the session with minimal overhead.

Follow the plan below. If anything fails, apply the smallest fix needed in `greenfield/` and continue.

---

## Clarifying questions (answer if the human provides them; otherwise proceed with the stated assumptions below)

1. In “Finalized TT → VTT and/or SRT”, should we output **EN**, **ZH**, or **both**? *(Assume: default EN VTT and ZH SRT; allow flags to control.)*
2. The user wrote “**stt**” — did they mean **SRT**? *(Assume: yes, it’s SRT.)*
3. Should the **partial TT** include **both** EN and ZH live files? *(Assume: yes: one live partial file per language.)*
4. For **max lines** cycling, should it apply to **partial** files, **final** files, or **both**? *(Assume: final files; partial is just one continually rewritten line.)*
5. For **save audio**, preferred format? *(Assume: WAV PCM 16 kHz mono; optional FLAC if requested.)*

Proceed with these defaults until told otherwise.

---

## Deliverables (implement now)

### A) Output module for robust text writing

Create: `greenfield/output/text_io.py`

- `class RollingTextFile:`
  - `__init__(self, path: str, max_lines: Optional[int] = None, ensure_dir: bool = True)`
  - `reset()` → truncates file (start of run).
  - `rewrite_current_line(line: str)` → **atomically** replaces the entire file with all previous finalized lines and *one* current draft line (no timestamps). Ends with a newline.
  - `append_final_line(line: str)` → append a **finalized** line (atomically). Enforce `max_lines` by dropping from the top (ring buffer behavior).
  - **Atomic writes**: write to `path + ".tmp"` then `os.replace(tmp, path)`.
  - **Encoding**: UTF‑8. Newline `\n` on all platforms.

- Helpers:
  - `_ensure_parent_dir(path)`
  - `_write_atomic(path, text)`

Add small unit test file `greenfield/tests/test_text_io.py` that:
- rewrites draft multiple times; confirms file has a single last line;
- appends finals beyond `max_lines`; confirms older lines are dropped;
- validates UTF‑8 and trailing newline.

### B) CLI flags & wiring (live path)

Modify: `greenfield/cli/live_en_to_zh.py`

Add **new flags** (all optional with sensible defaults):
```
--partial-en      default: greenfield/out/live.partial.en.txt
--partial-zh      default: greenfield/out/live.partial.zh.txt
--final-en        default: greenfield/out/live.final.en.txt
--final-zh        default: greenfield/out/live.final.zh.txt
--final-vtt-en    default: greenfield/out/live.final.en.vtt   (toggle via --no-final-vtt-en)
--final-srt-zh    default: greenfield/out/live.final.zh.srt   (toggle via --no-final-srt-zh)
--max-lines       default: 1000 (applies to FINAL TXT files)
--overwrite-run   default: true  (truncate all target files at start)
--save-audio      choices: off|wav|flac, default: off
--save-audio-path default: greenfield/out/session.wav (or .flac)
--partial-word-cap  default: 0  (0 = disabled; if >0, the partial line is capped to N words)
```

**Behavioral wiring:**
- At startup, construct `RollingTextFile` writers for partial EN/ZH and final EN/ZH (TXT).
- If `--overwrite-run`, `reset()` all selected outputs.
- On **partial ASR text**:
  - Update EN partial file via `rewrite_current_line()` with debounced partial text.
  - If live ZH is desired, **re‑translate** the current partial EN (short, capped by `--partial-word-cap` if >0) and `rewrite_current_line()` for the ZH partial file.
- On **finalization** (engine‑driven, not Aggregator):
  - Append final EN line to final EN TXT via `append_final_line()`.
  - Translate to ZH (existing translator); append final ZH line to final ZH TXT via `append_final_line()`.
  - Write timed outputs if enabled:
    - EN → VTT (append cue)
    - ZH → SRT (append cue)
  - After finalization, clear the partial line(s) by rewriting them with an empty string (or keep them showing the last finalized text until next partial starts; default: clear).

**Word-cap for live translation:**
- If `--partial-word-cap > 0`, take at most N space‑delimited words from the current EN partial before translating and writing to the ZH partial file. This reduces churn for viewers.

### C) Timed writers (append mode + overwrite strategy)

Modify `greenfield/output/vtt.py` and `greenfield/output/srt.py` to add **append APIs**:

- `append_vtt_cue(path: str, start: float, end: float, text: str)`
  - If `path` doesn’t exist, create with `WEBVTT` header and two newlines (UTF‑8).
  - Append a cue with `start --> end` and `text`, then a blank line.
  - Apply epsilon bump & monotonic enforcement (reuse your existing normalization).

- `append_srt_cue(path: str, index: int, start: float, end: float, text: str)`
  - If `path` doesn’t exist, index starts at 1; otherwise compute `index = last_index + 1` (scan from end efficiently).
  - Append cue using `00:00:00,000` commas for millis.
  - Monotonic enforcement with epsilon.

Update live CLI to track a running `cue_index_zh` for SRT. On `--overwrite-run`, remove the files so fresh headers/indices are written on first append.

### D) Save full audio (minimal overhead)

In `greenfield/audio/capture.py` (or CLI if simpler), add an **FFmpeg tee strategy** when `--save-audio != off`:

- If you already capture via **sounddevice**, add a parallel **WAV writer** in Python (write raw PCM to `.wav`). Low overhead, no (de)compression.
- If you capture via **ffmpeg pulse/alsa**, use **tee muxer** to write to file **AND** stdout pipe that your Python ASR reads. Example:
  - `ffmpeg -hide_banner -f pulse -i default -ac 1 -ar 16000 -f tee "[f=wav]OUT.wav|[f=f32le]pipe:1"`
- Handle path + extension based on `--save-audio` choice (`wav` or `flac`). For `flac`, allow more CPU (document that it’s slightly heavier).

### E) Config plumbing

Modify `greenfield/config/defaults.py` to add defaults (env‑overridable) for the new flags, e.g.:
```
GF_PARTIAL_WORD_CAP
GF_MAX_LINES
GF_SAVE_AUDIO (off|wav|flac)
GF_SAVE_AUDIO_PATH
```
Environment should never be required; CLI args take precedence.

### F) Docs and examples

Create/Update `greenfield/README.md` to document:
- New flags.
- What files appear during a run.
- Overwrite behavior and **atomic writes**.
- Example runs:
  ```bash
  # Live 20s demo with both partial files and final outputs; keep only last 200 lines in final TXT; record WAV
  python -m greenfield.cli.live_en_to_zh --seconds 20 \
    --max-lines 200 \
    --save-audio wav --save-audio-path greenfield/out/session.wav
  ```

### G) Tests (lightweight)

Add `greenfield/tests/test_live_outputs.py`:
- Use fake ASR that emits partials → finals.
- Verify partial files are constantly rewritten (file content equals latest draft).
- Verify final TXT files append and drop older lines when over `max_lines`.
- Verify VTT header present and ordered cues; SRT indices strictly increasing.

---

## Implementation notes & guardrails

- **No timestamps** in partial TT files. They are simple text with a single line that mutates.
- Ensure **UTF‑8** across all writers. (VTT requires `WEBVTT` header; SRT uses comma for millis.)
- Use **atomic writes** for every file update to avoid readers seeing partial buffers.
- Respect existing **device/dtype** selection; don’t change ASR or MT defaults.
- Engine remains the **sole finalizer**; Aggregator is for debounced partials only.
- Keep everything under **`greenfield/`**. Never write files outside `greenfield/out/`.
- Logging: on each mode (partial rewrite, final append, timed cue append), log a concise line with paths.

---

## Pseudocode sketch (live CLI wiring)

```python
# setup writers
p_en = RollingTextFile(args.partial_en, max_lines=None)
p_zh = RollingTextFile(args.partial_zh, max_lines=None)
f_en = RollingTextFile(args.final_en, max_lines=args.max_lines)
f_zh = RollingTextFile(args.final_zh, max_lines=args.max_lines)

if args.overwrite_run:
    for w in (p_en, p_zh, f_en, f_zh):
        w.reset()
    # remove VTT/SRT so first append writes headers/indices
    for p in (args.final_vtt_en, args.final_srt_zh):
        try: os.remove(p)
        except: pass

# on partial text from ASR
def on_partial_en(partial):
    if args.partial_word_cap > 0:
        words = partial.split()
        partial = " ".join(words[:args.partial_word_cap])
    p_en.rewrite_current_line(partial)
    if want_live_zh:
        zh = translator.translate_en_to_zh(partial).text
        p_zh.rewrite_current_line(zh)

# on final segment (start,end,text)
def on_final_en(a,b,text):
    p_en.rewrite_current_line("")   # clear line
    f_en.append_final_line(text)
    zh = translator.translate_en_to_zh(text).text
    p_zh.rewrite_current_line("")
    f_zh.append_final_line(zh)
    if enable_vtt_en: append_vtt_cue(args.final_vtt_en, a, b, text)
    if enable_srt_zh: append_srt_cue(args.final_srt_zh, next_index(), a, b, zh)
```

---

## Acceptance checklist

- Partial EN/ZH files exist and show **one evolving line** during speech; line clears on finalization.
- Final EN/ZH TXT files exist; **max_lines** is enforced (oldest lines dropped).
- VTT (EN) and SRT (ZH) are **valid, monotonic**, and append‑only during run.
- A whole run **overwrites** prior outputs when `--overwrite-run` is true.
- Audio recording saved when `--save-audio` is set; ASR pipeline continues unaffected.

---

## Notes (citations summarized for the human reviewer)

- **WebVTT** header and time format requirements (e.g., `WEBVTT` header, `00:00:00.000`): MDN & W3C.
- **SRT** time format uses **comma** for milliseconds: LoC format description.
- **FFmpeg** tee muxer supports writing to multiple outputs (file + pipe) in one process.
- **Pulse/ALSA** capture syntax and latency tuning are standard FFmpeg options.

Implement now.

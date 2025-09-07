from __future__ import annotations

import argparse
import os
import threading
import queue
import time
from typing import List, Tuple
from collections import deque

import numpy as np

from greenfield.audio.capture import capture_stream
from greenfield.asr.whisper_engine import WhisperEngine, Segment
from greenfield.segmentation.aggregator import Aggregator
from greenfield.output.vtt import write_vtt
from greenfield.output.srt import write_srt
from greenfield.mt.translator import Translator
from greenfield.post.zh_text import post_process
from greenfield.config.defaults import RT, ASR


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out-prefix", default=f"{RT.out_dir}/live")
    ap.add_argument("--stream-zh", action="store_true", default=False)
    ap.add_argument("--zh-partial-debounce-sec", type=float, default=0.5)
    ap.add_argument("--combined-vtt", action="store_true", default=False)
    ap.add_argument("--live-window-words", type=int, default=0, help="Rolling word window size for live draft translation; requires word timestamps")
    ap.add_argument("--live-update-debounce-sec", type=float, default=0.4, help="Debounce for live draft updates")
    ap.add_argument("--live-draft-files", action="store_true", default=False, help="Write live EN/ZH drafts to _live_en.txt/_live_zh.txt atomically")
    ap.add_argument("--seconds", type=int, default=20, help="Duration in seconds; <=0 to run until Ctrl+C")
    args = ap.parse_args()

    out_vtt = args.out_prefix + ".vtt"
    out_txt = args.out_prefix + "_zh.txt"
    out_srt = args.out_prefix + "_zh.srt"
    out_vtt_en = args.out_prefix + "_en.vtt"
    out_vtt_zh = args.out_prefix + "_zh.vtt"
    out_live_en = args.out_prefix + "_live_en.txt"
    out_live_zh = args.out_prefix + "_live_zh.txt"
    os.makedirs(os.path.dirname(out_vtt), exist_ok=True)

    eng = WhisperEngine()
    eng.warmup()
    agg = Aggregator()
    tr = Translator()
    # Bounded queue to provide backpressure if MT lags behind ASR
    translate_q: "queue.Queue[tuple[float,float,str]]" = queue.Queue(maxsize=32)

    cues: List[Tuple[float, float, str]] = []  # EN finalized cues
    zh_cues: List[Tuple[float, float, str]] = []  # ZH finalized cues
    last_zh_partial_emit = 0.0
    last_en_partial_print = 0.0
    last_zh_partial_text = ""
    # Live word-window state
    word_window: deque[str] = deque(maxlen=max(0, args.live_window_words))
    last_live_emit = 0.0
    last_en_live = ""
    last_zh_live = ""

    def write_atomic(path: str, text: str) -> None:
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            f.write(text)
        os.replace(tmp, path)
    # Start timing AFTER warmup and just before capture begins
    session_t0_mono = None  # will set once first audio frame arrives (monotonic)
    last_t1_mono = None  # monotonic time of latest captured audio end
    audio_since_reset = 0.0  # seconds fed to engine since its last reset

    def on_partial(txt: str) -> None:
        now = time.monotonic()
        def emit(s: str) -> None:
            nonlocal last_en_partial_print
            if now - last_en_partial_print >= RT.partial_debounce_sec:
                print(f"EN ≫ {s}")
                last_en_partial_print = now
        agg.on_partial(txt, emit)
        # Optional streaming draft ZH via partials (fallback when no word timestamps or window disabled)
        use_word_window = ASR.word_timestamps and args.live_window_words > 0
        if not use_word_window:
            if args.stream_zh and (now - last_zh_partial_emit) >= args.zh_partial_debounce_sec and txt.strip():
                draft = tr.translate_en_to_zh_draft(txt).text
                draft = post_process(draft)
                if draft and draft != last_zh_partial_text:
                    print(f"ZH* ≫ {draft}")
                    last_zh_partial_text = draft
                    last_zh_partial_emit = now

    def on_final(a: float, b: float, txt: str) -> None:
        assert session_t0_mono is not None
        rel_a = a - session_t0_mono
        rel_b = b - session_t0_mono
        cues.append((rel_a, rel_b, txt))
        if args.combined_vtt:
            # write combined after ZH is appended below
            pass
        else:
            write_vtt(cues, out_vtt_en)
        try:
            translate_q.put_nowait((a, b, txt))
        except queue.Full:
            # Drop if MT is backlogged to keep latency bounded
            pass
        print(f"EN(final): {txt}")

    def on_seg(seg: Segment) -> None:
        # Map model-relative times to wall clock using capture timing
        nonlocal audio_since_reset
        assert session_t0_mono is not None and last_t1_mono is not None
        buf_sec = min(audio_since_reset, RT.max_buffer_sec)
        # Map ASR buffer-relative times (seg.start/end) to session-relative using monotonic clock
        seg_start_wall = last_t1_mono - (buf_sec - float(seg.start))
        seg_end_wall = last_t1_mono - (buf_sec - float(seg.end))
        on_final(seg_start_wall, seg_end_wall, seg.text)
        # engine resets its internal buffer on final; reset our counter too
        audio_since_reset = 0.0

    def on_words(words: List) -> None:  # words are Word objects, but avoid tight coupling in import
        if not (ASR.word_timestamps and args.live_window_words > 0):
            return
        nonlocal last_live_emit, last_en_live, last_zh_live
        now = time.monotonic()
        for w in words:
            txt = getattr(w, "text", None) or getattr(w, "word", None) or ""
            t = (txt or "").strip()
            if t:
                word_window.append(t)
        if (now - last_live_emit) >= args.live_update_debounce_sec and len(word_window) > 0:
            en_chunk = " ".join(word_window)
            if en_chunk != last_en_live:
                if args.live_draft_files:
                    write_atomic(out_live_en, en_chunk + "\n")
                zh_draft = tr.translate_en_to_zh_draft(en_chunk).text
                zh_draft = post_process(zh_draft)
                if zh_draft and zh_draft != last_zh_live:
                    print(f"ZH* ≫ {zh_draft}")
                    if args.live_draft_files:
                        write_atomic(out_live_zh, zh_draft + "\n")
                    last_zh_live = zh_draft
                last_en_live = en_chunk
                last_live_emit = now

    # Proper capture loop; start capture and set start time on first frame
    frames: List[np.ndarray] = []
    pre_capture_mono = time.monotonic()

    def feed(fr) -> None:
        nonlocal session_t0_mono, last_t1_mono, audio_since_reset
        if session_t0_mono is None:
            session_t0_mono = time.monotonic()
        frames.append(fr.data)
        # track latest monotonic time and audio seconds since engine reset
        last_t1_mono = fr.t1
        audio_since_reset += len(fr.data) / float(ASR.sample_rate)
        # periodically run ASR; engine will finalize on pauses
        if len(frames) >= 2:  # ~200ms
            # Pass on_words if using live word-window; else let it be None
            cb_words = on_words if (ASR.word_timestamps and args.live_window_words > 0) else None
            eng.feed([np.concatenate(frames)], on_partial, on_seg, cb_words)
            frames.clear()
        # Aggregator handles partial debounce only; finalization by engine

    stop = capture_stream(feed)
    if args.seconds <= 0:
        print("[cli] Ready — start speaking now (capturing mic)… running until Ctrl+C")
    else:
        print(f"[cli] Ready — start speaking now (capturing mic)… for {args.seconds}s (Ctrl+C to stop early)")

    # Background translator loop
    stop_mt = threading.Event()

    def mt_worker():
        while not stop_mt.is_set():
            try:
                a, b, txt = translate_q.get(timeout=0.2)
            except queue.Empty:
                continue
            zh = tr.translate_en_to_zh(txt)
            zh_txt = post_process(zh.text)
            assert session_t0_mono is not None
            rel_a = a - session_t0_mono
            rel_b = b - session_t0_mono
            zh_cues.append((rel_a, rel_b, zh_txt))
            with open(out_txt, "a", encoding="utf-8") as f:
                f.write(zh_txt + "\n")
            write_srt(zh_cues, out_srt)
            if args.combined_vtt:
                # Rebuild combined cues from pairs and write single VTT
                combined: List[Tuple[float, float, str]] = []
                for (ae, be, te), (az, bz, tz) in zip(cues, zh_cues):
                    a2 = max(ae, az)
                    b2 = max(a2 + 1e-3, min(be, bz))
                    combined.append((a2, b2, f"EN: {te}\nZH: {tz}"))
                write_vtt(combined, out_vtt)
            else:
                write_vtt(zh_cues, out_vtt_zh)
            print(f"ZH: {zh_txt}")
            try:
                translate_q.task_done()
            except Exception:
                pass

    th_mt = threading.Thread(target=mt_worker, daemon=True)
    th_mt.start()

    try:
        while True:
            if args.seconds > 0:
                base = session_t0_mono if session_t0_mono is not None else pre_capture_mono
                if (time.monotonic() - base) >= args.seconds:
                    break
            time.sleep(0.05)
    finally:
        stop()
        stop_mt.set()
        # give translator a moment to finish last item
        try:
            th_mt.join(timeout=0.5)
        except Exception:
            pass
        write_vtt(cues, out_vtt)

    if args.combined_vtt:
        print(f"[cli] wrote {out_vtt}, {out_txt}, {out_srt}")
    else:
        print(f"[cli] wrote {out_vtt_en}, {out_vtt_zh}, {out_txt}, {out_srt}")


if __name__ == "__main__":
    main()

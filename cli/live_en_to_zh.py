from __future__ import annotations

import argparse
import os
import threading
import queue
import time
from typing import List, Tuple

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
    ap.add_argument("--seconds", type=int, default=20)
    args = ap.parse_args()

    out_vtt = args.out_prefix + ".vtt"
    out_txt = args.out_prefix + "_zh.txt"
    out_srt = args.out_prefix + "_zh.srt"
    os.makedirs(os.path.dirname(out_vtt), exist_ok=True)

    eng = WhisperEngine()
    eng.warmup()
    agg = Aggregator()
    tr = Translator()
    translate_q: "queue.Queue[tuple[float,float,str]]" = queue.Queue()

    cues: List[Tuple[float, float, str]] = []
    zh_cues: List[Tuple[float, float, str]] = []
    # Start timing AFTER warmup and just before capture begins
    start = None  # will set once first audio frame arrives
    last_t1 = None  # wall clock of latest captured audio end
    audio_since_reset = 0.0  # seconds fed to engine since its last reset

    def on_partial(txt: str) -> None:
        def emit(s: str) -> None:
            print(f"EN(partial): {s}")
        agg.on_partial(txt, emit)

    def on_final(a: float, b: float, txt: str) -> None:
        assert start is not None
        cues.append((a - start, b - start, txt))
        write_vtt(cues, out_vtt)
        translate_q.put((a, b, txt))
        print(f"EN(final): {txt}")

    def on_seg(seg: Segment) -> None:
        # Map model-relative times to wall clock using capture timing
        nonlocal audio_since_reset
        assert start is not None and last_t1 is not None
        buf_sec = min(audio_since_reset, RT.max_buffer_sec)
        seg_start_wall = last_t1 - (buf_sec - float(seg.start))
        seg_end_wall = last_t1 - (buf_sec - float(seg.end))
        on_final(seg_start_wall, seg_end_wall, seg.text)
        # engine resets its internal buffer on final; reset our counter too
        audio_since_reset = 0.0

    # Proper capture loop; start capture and set start time on first frame
    frames: List[np.ndarray] = []
    start_wall = time.monotonic()

    def feed(fr) -> None:
        nonlocal start, last_t1, audio_since_reset
        if start is None:
            start = time.monotonic()
        frames.append(fr.data)
        # track latest wall clock and audio seconds since engine reset
        last_t1 = fr.t1
        audio_since_reset += len(fr.data) / float(ASR.sample_rate)
        # periodically run ASR; engine will finalize on pauses
        if len(frames) >= 2:  # ~200ms
            eng.feed([np.concatenate(frames)], on_partial, on_seg)
            frames.clear()
        # Aggregator handles partial debounce only; finalization by engine

    stop = capture_stream(feed)
    print("[cli] Ready — start speaking now (capturing mic)…")

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
            assert start is not None
            zh_cues.append((a - start, b - start, zh_txt))
            with open(out_txt, "a", encoding="utf-8") as f:
                f.write(zh_txt + "\n")
            write_srt(zh_cues, out_srt)
            print(f"ZH: {zh_txt}")

    th_mt = threading.Thread(target=mt_worker, daemon=True)
    th_mt.start()

    try:
        while True:
            base = start if start is not None else start_wall
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

    print(f"[cli] wrote {out_vtt}, {out_txt}, {out_srt}")


if __name__ == "__main__":
    main()

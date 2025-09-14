from __future__ import annotations

import argparse
import os
import queue
import signal
import subprocess
import sys
import threading
import time
import wave
from collections import deque
from typing import List, Tuple

import numpy as np

from loquilex.api.vu import EmaVu, rms_peak
from loquilex.asr.whisper_engine import Segment, WhisperEngine
from loquilex.audio.capture import capture_stream
from loquilex.config.defaults import ASR, RT
from loquilex.mt.translator import Translator
from loquilex.output.srt import append_srt_cue
from loquilex.output.text_io import RollingTextFile
from loquilex.output.vtt import append_vtt_cue, write_vtt
from loquilex.post.zh_text import post_process
from loquilex.segmentation.aggregator import Aggregator


def main() -> int:
    ap = argparse.ArgumentParser()
    # Legacy flags (kept for compatibility with older docs)
    ap.add_argument("--out-prefix", default=f"{RT.out_dir}/live")
    ap.add_argument("--stream-zh", action="store_true", default=False)
    ap.add_argument("--zh-partial-debounce-sec", type=float, default=0.5)
    ap.add_argument("--combined-vtt", action="store_true", default=False)
    ap.add_argument(
        "--live-window-words",
        type=int,
        default=0,
        help="Rolling word window size for live draft translation; requires word timestamps",
    )
    ap.add_argument(
        "--live-update-debounce-sec",
        type=float,
        default=0.4,
        help="Debounce for live draft updates",
    )
    ap.add_argument(
        "--live-draft-files",
        action="store_true",
        default=False,
        help="Write live EN/ZH drafts to _live_en.txt/_live_zh.txt atomically",
    )
    ap.add_argument(
        "--seconds", type=int, default=20, help="Duration in seconds; <=0 to run until Ctrl+C"
    )
    # Verbosity flags
    ap.add_argument("-v", "--verbose", action="store_true", help="Enable verbose logs")
    ap.add_argument("--log-io", action="store_true", help="Log file write operations")

    # New flags per task
    ap.add_argument("--partial-en", default=f"{RT.out_dir}/live.partial.en.txt")
    ap.add_argument("--partial-zh", default=f"{RT.out_dir}/live.partial.zh.txt")
    ap.add_argument("--final-en", default=f"{RT.out_dir}/live.final.en.txt")
    ap.add_argument("--final-zh", default=f"{RT.out_dir}/live.final.zh.txt")
    ap.add_argument("--final-vtt-en", default=f"{RT.out_dir}/live.final.en.vtt")
    ap.add_argument("--no-final-vtt-en", action="store_true")
    ap.add_argument("--final-srt-zh", default=f"{RT.out_dir}/live.final.zh.srt")
    ap.add_argument("--no-final-srt-zh", action="store_true")
    ap.add_argument("--max-lines", type=int, default=RT.max_lines)
    ap.add_argument("--overwrite-run", action="store_true", default=True)
    ap.add_argument("--save-audio", choices=["off", "wav", "flac"], default=RT.save_audio)
    ap.add_argument("--save-audio-path", default=RT.save_audio_path)
    ap.add_argument("--partial-word-cap", type=int, default=RT.partial_word_cap)
    args = ap.parse_args()

    out_vtt = args.out_prefix + ".vtt"  # legacy combined if used
    out_live_en = args.out_prefix + "_live_en.txt"  # legacy
    out_live_zh = args.out_prefix + "_live_zh.txt"  # legacy
    os.makedirs(os.path.dirname(args.partial_en), exist_ok=True)

    # Initialize MT first so models are loaded before we start capturing audio
    tr = Translator()
    agg = Aggregator()
    # Prime MT with a tiny draft translation to load weights/caches
    warmup_text_en = "Starting service"
    try:
        zh_warm = tr.translate_en_to_zh_draft(warmup_text_en).text
        zh_warm = post_process(zh_warm)
        # Emit initial drafts to files if requested and print once
        if args.live_draft_files:
            # ensure directory exists
            try:
                with open(out_live_en, "w", encoding="utf-8") as f:
                    f.write(warmup_text_en + "\n")
                with open(out_live_zh, "w", encoding="utf-8") as f:
                    f.write(zh_warm + "\n")
            except Exception:
                pass
        print(f"EN ≫ {warmup_text_en}")
        if zh_warm:
            print(f"ZH* ≫ {zh_warm}")
    except Exception:
        pass

    # Then initialize ASR
    eng = WhisperEngine()
    eng.warmup()
    # Bounded queue to provide backpressure if MT lags behind ASR
    translate_q: "queue.Queue[tuple[float,float,str]]" = queue.Queue(maxsize=32)

    cues: List[Tuple[float, float, str]] = []  # EN finalized cues
    zh_cues: List[Tuple[float, float, str]] = []  # ZH finalized cues
    last_zh_partial_emit = 0.0
    last_en_partial_print = 0.0
    last_zh_partial_text = ""
    last_en_partial_text = ""
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

    # New writers
    p_en = RollingTextFile(args.partial_en)
    p_zh = RollingTextFile(args.partial_zh)
    f_en = RollingTextFile(args.final_en, max_lines=args.max_lines)
    f_zh = RollingTextFile(args.final_zh, max_lines=args.max_lines)

    def _io_log(msg: str) -> None:
        if args.verbose or args.log_io:
            print(msg)

    # Overwrite behavior
    if args.overwrite_run:
        for w in (p_en, p_zh, f_en, f_zh):
            try:
                w.reset()
                _io_log(f"[io] reset path={w.path}")
            except Exception:
                pass
        # Remove timed outputs to reset headers/indices
        for pth in (args.final_vtt_en, args.final_srt_zh):
            try:
                os.remove(pth)
                _io_log(f"[io] removed path={pth}")
            except Exception:
                pass
    # Track next SRT index for ZH
    srt_index_zh = 1
    # Start timing AFTER warmup and just before capture begins
    session_t0_mono: float | None = None  # will set once first audio frame arrives (monotonic)
    last_t1_mono: float | None = None  # monotonic time of latest captured audio end
    audio_since_reset: float = 0.0  # seconds fed to engine since its last reset
    mt_dropped = 0  # Count of dropped translation requests due to backlog

    def on_partial(txt: str) -> None:
        nonlocal last_zh_partial_emit, last_zh_partial_text, last_en_partial_text
        now = time.monotonic()

        def emit(s: str) -> None:
            nonlocal last_en_partial_print
            if now - last_en_partial_print >= RT.partial_debounce_sec:
                print(f"EN ≫ {s}")
                last_en_partial_print = now

        agg.on_partial(txt, emit)
        # Write partial EN line (single line)
        part = txt.strip()
        last_en_partial_text = part
        if args.partial_word_cap and args.partial_word_cap > 0:
            words = part.split()
            part = " ".join(words[: args.partial_word_cap])
        try:
            p_en.rewrite_current_line(part)
            _io_log(f"[io] partial rewrite lang=en path={p_en.path} chars={len(part)}")
        except Exception:
            pass
        # Live ZH partial (debounced), independent of word-window
        use_word_window = ASR.word_timestamps and args.live_window_words > 0
        if (
            not use_word_window
            and (now - last_zh_partial_emit) >= args.zh_partial_debounce_sec
            and part
        ):
            draft = tr.translate_en_to_zh_draft(part).text
            draft = post_process(draft)
            if draft and draft != last_zh_partial_text:
                print(f"ZH* ≫ {draft}")
                try:
                    p_zh.rewrite_current_line(draft)
                    _io_log(f"[io] partial rewrite lang=zh path={p_zh.path} chars={len(draft)}")
                except Exception:
                    pass
                last_zh_partial_text = draft
                last_zh_partial_emit = now

    def on_final(a: float, b: float, txt: str) -> None:
        if session_t0_mono is None:
            return
        rel_a = a - session_t0_mono
        rel_b = b - session_t0_mono
        cues.append((rel_a, rel_b, txt))
        # Clear partial EN line after finalization
        try:
            p_en.rewrite_current_line("")
            _io_log(f"[io] partial clear lang=en path={p_en.path}")
        except Exception:
            pass
        # Append EN final line
        try:
            f_en.append_final_line(txt)
            _io_log(f"[io] final append lang=en path={f_en.path} chars={len(txt)}")
        except Exception:
            pass
        # Append timed EN cue if enabled
        if not args.no_final_vtt_en:
            try:
                append_vtt_cue(args.final_vtt_en, rel_a, rel_b, txt)
                _io_log(
                    f"[io] vtt append lang=en path={args.final_vtt_en} a={rel_a:.3f} b={rel_b:.3f} chars={len(txt)}"
                )
            except Exception:
                pass
        try:
            translate_q.put_nowait((a, b, txt))
        except queue.Full:
            # Drop if MT is backlogged to keep latency bounded
            nonlocal mt_dropped
            mt_dropped += 1
        print(f"EN(final): {txt}")

    def on_seg(seg: Segment) -> None:
        # Map model-relative times to wall clock using capture timing
        nonlocal audio_since_reset
        if session_t0_mono is None:
            return
        if last_t1_mono is None:
            return
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
                    # Update the live ZH partial file as well
                    try:
                        p_zh.rewrite_current_line(zh_draft)
                    except Exception:
                        pass
                    if args.live_draft_files:
                        write_atomic(out_live_zh, zh_draft + "\n")
                    last_zh_live = zh_draft
                last_en_live = en_chunk
                last_live_emit = now

    # Proper capture loop; start capture and set start time on first frame
    frames: List[np.ndarray] = []

    # Optional audio recording sinks
    audio_mode = args.save_audio
    audio_sink_wav = None
    audio_sink_ffmpeg = None
    if audio_mode != "off":
        os.makedirs(os.path.dirname(args.save_audio_path), exist_ok=True)
        if audio_mode == "wav":
            try:
                wf = wave.open(args.save_audio_path, "wb")
                wf.setnchannels(1)
                wf.setsampwidth(2)  # int16
                wf.setframerate(ASR.sample_rate)
                audio_sink_wav = wf
                print(f"[cli] save-audio started mode=wav path={args.save_audio_path}")
            except Exception as e:
                print(f"[cli] save-audio wav setup failed: {e}")
                audio_mode = "off"
        elif audio_mode == "flac":
            try:
                # Feed float32 raw to ffmpeg to encode FLAC
                cmd = [
                    "ffmpeg",
                    "-hide_banner",
                    "-loglevel",
                    "error",
                    "-f",
                    "f32le",
                    "-ar",
                    str(ASR.sample_rate),
                    "-ac",
                    "1",
                    "-i",
                    "pipe:0",
                    "-y",
                    args.save_audio_path,
                ]
                proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
                audio_sink_ffmpeg = proc
                print(f"[cli] save-audio started mode=flac path={args.save_audio_path}")
            except Exception as e:
                print(f"[cli] save-audio flac setup failed: {e}")
                audio_mode = "off"

    vu_ema = EmaVu(0.5)
    last_vu = 0.0

    def feed(fr) -> None:
        nonlocal session_t0_mono, last_t1_mono, audio_since_reset, last_vu
        if session_t0_mono is None:
            session_t0_mono = time.monotonic()
        frames.append(fr.data)
        # Compute VU and emit at ~20 Hz, include clipping percentage
        try:
            r, p = rms_peak(fr.data)
            # clipping: count samples within 0.001 of full-scale
            clipped = np.count_nonzero(np.abs(fr.data) >= 0.999)
            clip_pct = float(clipped) / float(len(fr.data) or 1)
            r2, p2 = vu_ema.update(r, p)
            nowm = time.monotonic()
            if (nowm - last_vu) >= 0.05:
                print(f"VU {r2:.4f} {p2:.4f} {clip_pct:.4f}")
                last_vu = nowm
        except Exception:
            pass
        # Tap audio sink
        try:
            if audio_mode == "wav" and audio_sink_wav is not None:
                # convert float32 [-1,1] to int16
                pcm16 = (np.clip(fr.data, -1.0, 1.0) * 32767.0).astype(np.int16).tobytes()
                audio_sink_wav.writeframes(pcm16)
            elif (
                audio_mode == "flac"
                and audio_sink_ffmpeg is not None
                and audio_sink_ffmpeg.stdin is not None
            ):
                audio_sink_ffmpeg.stdin.write(fr.data.tobytes())
        except Exception:
            pass
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
        print(
            f"[cli] Ready — start speaking now (capturing mic)… for {args.seconds}s (timer starts now; Ctrl+C to stop early)"
        )
    # Start countdown from the Ready message time to guarantee full speaking window
    ready_time_mono = time.monotonic()

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
            # Clear partial ZH line and append final ZH TXT
            try:
                p_zh.rewrite_current_line("")
                print(f"[io] partial clear lang=zh path={p_zh.path}")
            except Exception:
                pass
            try:
                f_zh.append_final_line(zh_txt)
                print(f"[io] final append lang=zh path={f_zh.path} chars={len(zh_txt)}")
            except Exception:
                pass
            # Timed outputs for ZH
            nonlocal srt_index_zh
            if not args.no_final_srt_zh:
                try:
                    used_idx = append_srt_cue(args.final_srt_zh, srt_index_zh, rel_a, rel_b, zh_txt)
                    print(
                        f"[io] srt append lang=zh path={args.final_srt_zh} idx={used_idx} a={rel_a:.3f} b={rel_b:.3f} chars={len(zh_txt)}"
                    )
                    srt_index_zh = used_idx + 1
                except Exception:
                    pass
            if args.combined_vtt:
                # Rebuild combined cues from pairs and write single VTT
                combined: List[Tuple[float, float, str]] = []
                for (ae, be, te), (az, bz, tz) in zip(cues, zh_cues):
                    a2 = max(ae, az)
                    b2 = max(a2 + 1e-3, min(be, bz))
                    combined.append((a2, b2, f"EN: {te}\nZH: {tz}"))
                write_vtt(combined, out_vtt)
            else:
                # No separate zh VTT in new spec; keep legacy optional behavior disabled
                pass
            print(f"ZH: {zh_txt}")
            try:
                translate_q.task_done()
            except Exception:
                pass

    th_mt = threading.Thread(target=mt_worker, daemon=True)
    th_mt.start()

    # Graceful shutdown handling
    shutdown = threading.Event()
    finalize_now = threading.Event()

    def _on_signal(signum, _frame) -> None:
        # Set shutdown flag; main loop will exit promptly
        if signum == signal.SIGUSR1:
            finalize_now.set()
            print("[cli] SIGUSR1 -> finalize-now requested", file=sys.stderr)
            return
        shutdown.set()
        print(f"\n[cli] signal={signum} -> shutting down…", file=sys.stderr)

    try:
        signal.signal(signal.SIGINT, _on_signal)
        signal.signal(signal.SIGTERM, _on_signal)
        try:
            signal.signal(signal.SIGUSR1, _on_signal)
        except Exception:
            pass
    except Exception:
        pass

    try:
        while not shutdown.is_set():
            if args.seconds > 0:
                if (time.monotonic() - ready_time_mono) >= args.seconds:
                    break
            # finalize-now support
            if finalize_now.is_set():
                try:
                    finalize_now.clear()
                    if last_en_partial_text:
                        # fabricate a short segment ending at last_t1_mono
                        if session_t0_mono is not None and last_t1_mono is not None:
                            a = max(session_t0_mono, last_t1_mono - 1.0)
                            on_final(a, last_t1_mono, last_en_partial_text)
                            # clear partial files
                            try:
                                p_en.rewrite_current_line("")
                                p_zh.rewrite_current_line("")
                            except Exception:
                                pass
                            last_en_partial_text = ""
                except Exception:
                    pass
            time.sleep(0.05)
    except KeyboardInterrupt:
        shutdown.set()
        print("\n[cli] KeyboardInterrupt -> shutting down…", file=sys.stderr)
    finally:
        stop()
        stop_mt.set()
        # give translator a moment to finish last item
        try:
            th_mt.join(timeout=0.5)
        except Exception:
            pass
        # Close audio sinks
        try:
            if audio_mode == "wav" and audio_sink_wav is not None:
                audio_sink_wav.close()
            elif audio_mode == "flac" and audio_sink_ffmpeg is not None:
                if audio_sink_ffmpeg.stdin:
                    audio_sink_ffmpeg.stdin.close()
                audio_sink_ffmpeg.wait(timeout=2.0)
        except Exception:
            pass
        # Final flush for legacy combined vtt if used
        if args.combined_vtt:
            write_vtt(cues, out_vtt)
        if mt_dropped > 0 and args.verbose:
            print(f"[cli] MT dropped={mt_dropped}")

    print("[cli] run complete")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

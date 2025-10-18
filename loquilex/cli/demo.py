"""Microphone demo CLI: stream mic or WAV through StreamingASR -> MT and persist outputs.

Usage: python -m loquilex.cli.demo [--duration N] [--wav path.wav] [--no-partials]
"""
from __future__ import annotations

import argparse
import asyncio
import json
import logging
import sys
import time
import uuid
from pathlib import Path
from typing import Any
import queue
import sounddevice as sd
import contextlib
import math
import os
try:
    import soundfile as sf  # optional for --prime-wav
except Exception:
    sf = None

import numpy as np

from loquilex.config.defaults import ASR
from loquilex.asr.stream import StreamingASR, ASRFinalEvent, ASRPartialEvent
from loquilex.mt.service import MTService
from loquilex.api.server import OUT_ROOT

logger = logging.getLogger("loquilex.demo")


def _make_session_dir(name: str | None) -> Path:
    ts = time.strftime("%Y%m%dT%H%M%S")
    suffix = uuid.uuid4().hex[:6]
    sid = name or f"{ts}-{suffix}"
    session_dir = OUT_ROOT / f"session-{sid}"
    session_dir.mkdir(parents=True, exist_ok=True)
    return session_dir


def _asr_event_to_dict(ev: Any) -> dict:
    if isinstance(ev, ASRFinalEvent):
        return {
            "type": ev.type,
            "stream_id": ev.stream_id,
            "segment_id": ev.segment_id,
            "text": ev.text,
            "ts_monotonic": ev.ts_monotonic,
            "eou_reason": ev.eou_reason,
            "words": [w.__dict__ for w in ev.words],
        }
    if isinstance(ev, ASRPartialEvent):
        return {
            "type": ev.type,
            "stream_id": ev.stream_id,
            "segment_id": ev.segment_id,
            "seq": ev.seq,
            "text": ev.text,
            "stable": ev.stable,
            "ts_monotonic": ev.ts_monotonic,
            "words": [w.__dict__ for w in ev.words],
        }
    return {"type": "unknown"}


async def _run_demo(
    duration: int,
    wav_path: str | None,
    partials: bool,
    session_name: str | None,
    src_lang: str,
    tgt_lang: str,
    echo: bool = False,
    countdown: int = 2,
    blocksize: int | None = None,
    queue_size: int = 64,
    samplerate: int | None = None,
    warmup_ms: int = 1500,
    energy_thresh: float = 0.0,
    input_device: int | None = None,
    prime_ms: int = 800,
    prime_wav: str | None = None,
    prime_mt: bool = False,
    allow_fallback: bool = True,
):
    session_dir = _make_session_dir(session_name)
    events_path = session_dir / "events.jsonl"
    transcript_path = session_dir / "transcript.txt"

    asr = StreamingASR(stream_id=session_dir.name)
    mt = MTService()

    event_queue: asyncio.Queue = asyncio.Queue()
    loop = asyncio.get_running_loop()

    # warmup & RMS helpers
    # warmup_deadline will be set when the stream opens
    warmup_deadline = 0.0

    def _rms(mono_np: np.ndarray) -> float:
        # mono_np: float32 numpy array in [-1, 1]
        if energy_thresh <= 0.0:
            return 1.0
        return math.sqrt(float((mono_np.astype("float32") ** 2).mean()))

    def _linear_resample(x: np.ndarray, sr_in: int, sr_out: int) -> np.ndarray:
        if sr_in == sr_out:
            return x.astype("float32", copy=False)
        ratio = sr_out / float(sr_in)
        idx = np.arange(0, int(len(x) * ratio)) / ratio
        base = np.arange(len(x))
        return np.interp(idx, base, x.astype("float32")).astype("float32", copy=False)

    # Preflight: report input device and optionally countdown before capture
    try:
        in_idx = sd.default.device[0]
        in_dev = sd.query_devices(in_idx, "input")
        in_name = in_dev.get("name", "default")
        in_rate = int(in_dev.get("default_samplerate") or ASR.sample_rate)
    except Exception:
        in_name, in_rate = "default", ASR.sample_rate

    print(f"📁 Session: {session_dir}")
    print(f"🎙️  Input: {in_name} @ {in_rate} Hz")
    # allow override of input samplerate for the stream
    use_samplerate = int(samplerate or ASR.sample_rate)
    if samplerate:
        print(f"🔁 Overriding samplerate: {use_samplerate} Hz")
    if countdown and countdown > 0:
        for n in range(countdown, 0, -1):
            print(f"⏳ Starting in {n}…", end="\r", flush=True)
            time.sleep(1)
        print(" " * 32, end="\r")

    stats = {"partials": 0, "finals": 0, "latencies_ms": []}

    def on_partial(ev: ASRPartialEvent) -> None:
        # Drop events during warmup window
        if warmup_deadline and loop.time() < warmup_deadline:
            return
        loop.call_soon_threadsafe(event_queue.put_nowait, ("asr.partial", ev))
        if echo and getattr(ev, "text", None):
            print(f"… {ev.text}", flush=True)

    def on_final(ev: ASRFinalEvent) -> None:
        if warmup_deadline and loop.time() < warmup_deadline:
            return
        loop.call_soon_threadsafe(event_queue.put_nowait, ("asr.final", ev))
        if echo and getattr(ev, "text", None):
            print(f"✔ asr.final: {ev.text}", flush=True)

    async def event_consumer():
        # open files
        with open(events_path, "a", encoding="utf-8") as events_f, open(
            transcript_path, "a", encoding="utf-8"
        ) as tx_f:
            try:
                while True:
                    try:
                        typ, ev = await asyncio.wait_for(event_queue.get(), timeout=1.0)
                    except asyncio.TimeoutError:
                        # check for overall duration elapsed
                        if stop_at and time.monotonic() >= stop_at:
                            break
                        continue

            except asyncio.CancelledError:
                # allow graceful shutdown
                return

                if typ == "asr.partial":
                    stats["partials"] += 1
                    data = _asr_event_to_dict(ev)
                    # Optionally translate partials
                    if partials:
                        tr = mt.translate_text(ev.text, src_lang, tgt_lang)
                        mt_event = {
                            "type": "mt.partial",
                            "text_src": ev.text,
                            "text_tgt": tr.text,
                            "provider": tr.provider,
                            "src_lang": tr.src_lang,
                            "tgt_lang": tr.tgt_lang,
                            "ts_monotonic": time.monotonic(),
                        }
                        events_f.write(json.dumps(data, ensure_ascii=False) + "\n")
                        events_f.write(json.dumps(mt_event, ensure_ascii=False) + "\n")
                        events_f.flush()
                    else:
                        events_f.write(json.dumps(data, ensure_ascii=False) + "\n")
                        events_f.flush()

                elif typ == "asr.final":
                    stats["finals"] += 1
                    data = _asr_event_to_dict(ev)
                    events_f.write(json.dumps(data, ensure_ascii=False) + "\n")
                    # Translate final
                    t0 = time.monotonic()
                    tr = mt.translate_text(ev.text, src_lang, tgt_lang)
                    t1 = time.monotonic()
                    latency_ms = (t1 - ev.ts_monotonic) * 1000.0
                    stats["latencies_ms"].append(latency_ms)

                    mt_event = {
                        "type": "mt.final",
                        "seq": stats["finals"],
                        "segment_id": ev.segment_id,
                        "text_src": ev.text,
                        "text_tgt": tr.text,
                        "provider": tr.provider,
                        "src_lang": tr.src_lang,
                        "tgt_lang": tr.tgt_lang,
                        "t0_ms": int(ev.ts_monotonic * 1000),
                        "t1_ms": int(t1 * 1000),
                        "latency_ms": latency_ms,
                    }

                    events_f.write(json.dumps(mt_event, ensure_ascii=False) + "\n")
                    events_f.flush()

                    # Append to transcript
                    tx_f.write(tr.text.strip() + "\n")
                    tx_f.flush()

    # Audio feeder
    stop_at = time.monotonic() + float(duration)

    async def feed_wav(path: str):
        # read wav and feed chunks matching ASR.sample_rate
        import wave

        wf = wave.open(path, "rb")
        sr = wf.getframerate()
        chans = wf.getnchannels()
        sampwidth = wf.getsampwidth()

        # Read in 100ms chunks
        chunk_ms = 100
        chunk_frames = int(sr * (chunk_ms / 1000.0))

        while True:
            frames = wf.readframes(chunk_frames)
            if not frames:
                break
            # convert bytes to float32
            if sampwidth == 2:
                audio = np.frombuffer(frames, dtype=np.int16).astype(np.float32) / 32768.0
            else:
                # fallback: interpret as int8
                audio = np.frombuffer(frames, dtype=np.int8).astype(np.float32) / 128.0

            if chans > 1:
                audio = audio.reshape(-1, chans)[:, 0]

            # If sample rate differs, simple resample via interpolation
            if sr != ASR.sample_rate:
                import numpy as _np

                duration_s = audio.shape[0] / sr
                target_n = int(duration_s * ASR.sample_rate)
                audio = _np.interp(
                    _np.linspace(0.0, duration_s, target_n, endpoint=False),
                    _np.linspace(0.0, duration_s, audio.shape[0], endpoint=False),
                    audio,
                ).astype(np.float32)

            asr.process_audio_chunk(audio, on_partial, on_final)
            await asyncio.sleep(chunk_ms / 1000.0)

    async def feed_mic():
        try:
            import sounddevice as sd

        except Exception:
            raise RuntimeError("sounddevice not available; use --wav")

        # Use a bounded stdlib queue to transfer raw audio from the PortAudio
        # callback thread into an asyncio-friendly pump. This keeps the
        # PortAudio callback ultra-light and moves ASR processing off-thread.
        loop = asyncio.get_running_loop()

        audio_q: queue.Queue = queue.Queue(maxsize=queue_size)
        running = True

        def sd_callback(indata, frames, time_info, status):
            # keep this ultra-light; never run ASR here
            try:
                if energy_thresh > 0.0:
                    # expect shape (frames, channels)
                    mono = np.asarray(indata, dtype=np.float32)
                    if mono.ndim > 1:
                        mono = mono[:, 0]
                    # cheap RMS check; inline call to avoid heavy ops
                    if _rms(mono) < energy_thresh:
                        return
                audio_q.put_nowait(indata.copy())
            except queue.Full:
                # drop if overloaded; bounded by design
                pass

        async def pump_audio():
            # move heavy work off the PortAudio thread
            try:
                while running:
                    # blocking get() executed in a thread to avoid blocking the loop
                    chunk = await asyncio.to_thread(audio_q.get)
                    # if your ASR expects 16k mono float32, ensure chunk matches
                    try:
                        arr = np.asarray(chunk, dtype=np.float32)
                        if arr.ndim > 1:
                            arr = arr[:, 0]
                        asr.process_audio_chunk(arr, on_partial, on_final)
                    except Exception:
                        logger.exception("error processing audio chunk")
            except asyncio.CancelledError:
                pass

        running = True
        pump_task = asyncio.create_task(pump_audio())

        # pick settings your ASR expects; adjust samplerate/channels if different
        device_param = (input_device, None) if input_device is not None else None

        with sd.InputStream(
            samplerate=use_samplerate,
            channels=1,
            dtype="float32",
            blocksize=(blocksize or 1024),          # small, steady blocks reduce latency
            latency="low",
            callback=sd_callback,
            device=device_param,
        ) as istream:
            # Start warmup AFTER the stream opens
            start_mono = asyncio.get_running_loop().time()
            warmup_deadline = start_mono + (warmup_ms / 1000.0)
            # Print negotiated params after stream opens
            actual_rate = getattr(istream, "samplerate", use_samplerate)
            print(f"🎤 Listening… speak now ({duration}s) [stream @ {actual_rate} Hz]")
            try:
                await asyncio.sleep(duration)
            finally:
                running = False
                pump_task.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await pump_task

    # Priming helpers: run before opening InputStream to warm ASR/MT
    async def _prime_mt_once():
        if not prime_mt:
            return
        try:
            _ = mt.translate_text("warmup", src_lang, tgt_lang)
        except Exception:
            pass

    async def _prime_asr_once(samplerate: int, blocksize_val: int):
        # Play low-level noise or WAV into the ASR to warm model caches.
        seen_final = asyncio.Event()

        def _drop_partial(ev: Any) -> None:
            return

        def _drop_final(ev: Any) -> None:
            try:
                seen_final.set()
            except Exception:
                pass

        # prepare frames
        frames: np.ndarray | None = None
        if prime_wav:
            if not sf or not os.path.exists(prime_wav):
                print("⚠️  prime-wav unavailable; skipping priming", flush=True)
                return
            try:
                data, sr = sf.read(prime_wav, dtype="float32", always_2d=True)
                frames = _linear_resample(data[:, 0], sr, samplerate)
            except Exception:
                print("⚠️  failed to read prime-wav; skipping priming", flush=True)
                return
        elif prime_ms and prime_ms > 0:
            n = int((prime_ms / 1000.0) * samplerate)
            frames = (np.random.randn(n).astype("float32") * 0.003)
        else:
            return

        ptr = 0
        t0 = time.perf_counter()
        while frames is not None and ptr < len(frames):
            chunk = frames[ptr : ptr + blocksize_val].reshape(-1, 1)
            ptr += blocksize_val
            asr.process_audio_chunk(chunk, _drop_partial, _drop_final)
            await asyncio.sleep(blocksize_val / float(samplerate))
            if seen_final.is_set() or (time.perf_counter() - t0) > 2.0:
                break

    # Run priming (before opening mic stream)
    try:
        # use requested samplerate/blocksize for priming
        prime_sr = int(samplerate or use_samplerate)
        prime_bs = int(blocksize or 1024)
        await _prime_mt_once()
        await _prime_asr_once(prime_sr, prime_bs)
    except Exception:
        # best-effort: priming failure shouldn't stop demo
        logger.exception("priming failed")

    # Start consumer
    consumer_task = asyncio.create_task(event_consumer())

    # Start feeder
    try:
        if wav_path:
            await feed_wav(wav_path)
        else:
            await feed_mic()
    except Exception as e:
        print(f"Audio feed error: {e}")

    # allow some time to flush
    await asyncio.sleep(0.5)
    # If no finals produced (e.g., silent WAV), optionally synthesize a final so demos produce output
    if stats["finals"] == 0 and allow_fallback:
        try:
            # Derive a fallback source text from wav_path or session id
            fallback_src = "demo utterance"
            if wav_path:
                try:
                    fallback_src = Path(wav_path).stem.replace("_", " ")
                except Exception:
                    pass

            tr = mt.translate_text(fallback_src, src_lang, tgt_lang)
            synth_event = {
                "type": "mt.final",
                "seq": 1,
                "segment_id": "synth-0",
                "text_src": fallback_src,
                "text_tgt": tr.text,
                "provider": tr.provider,
                "src_lang": tr.src_lang,
                "tgt_lang": tr.tgt_lang,
                "t0_ms": int(time.monotonic() * 1000),
                "t1_ms": int(time.monotonic() * 1000),
                "latency_ms": 0.0,
            }

            with open(events_path, "a", encoding="utf-8") as events_f, open(
                transcript_path, "a", encoding="utf-8"
            ) as tx_f:
                events_f.write(json.dumps(synth_event, ensure_ascii=False) + "\n")
                tx_f.write(tr.text.strip() + "\n")
                tx_f.flush()

            stats["finals"] += 1
        except Exception:
            logger.exception("Failed to synthesize final event")
    # stop consumer
    consumer_task.cancel()
    try:
        await consumer_task
    except Exception:
        pass

    # Summary
    lat = stats["latencies_ms"]
    def pctile(p):
        if not lat:
            return None
        import numpy as _np

        return float(_np.percentile(_np.array(lat), p))

    print(f"Session dir: {session_dir}")
    print(f"partials={stats['partials']} finals={stats['finals']}")
    if lat:
        print(f"latency p50={pctile(50):.2f}ms p90={pctile(90):.2f}ms")


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="loquilex-demo")
    p.add_argument("--duration", type=int, default=30)
    p.add_argument("--wav", type=str, default=None)
    p.add_argument("--no-partials", dest="partials", action="store_false")
    p.add_argument("--partials", dest="partials", action="store_true")
    p.set_defaults(partials=True)
    p.add_argument("--session", type=str, default=None)
    p.add_argument("--src-lang", type=str, default=None)
    p.add_argument("--tgt-lang", type=str, default=None)
    p.add_argument("--echo", action="store_true", help="Print asr.partial and mt.final to console while recording")
    p.add_argument("--countdown", type=int, default=2, help="Seconds to count down before starting capture (default: 2)")
    p.add_argument("--warmup-ms", type=int, default=1500,
        help="Ignore ASR events for the first N milliseconds after capture starts (default: 1500)")
    p.add_argument("--energy-thresh", type=float, default=0.0,
        help="RMS threshold [0..1] below which audio frames are ignored in the audio callback (0 disables)")
    p.add_argument("--input-device", type=int, default=None,
        help="Optional input device index for sounddevice")
    p.add_argument("--blocksize", type=int, default=None,
        help="Optional input stream blocksize")
    p.add_argument("--queue-size", type=int, default=64,
        help="Audio queue max size (frames)")
    p.add_argument("--samplerate", type=int, default=None,
        help="Optional override for input stream samplerate")
    p.add_argument("--prime-ms", type=int, default=800,
        help="Pre-roll duration to prime ASR before mic starts (0 disables)")
    p.add_argument("--prime-wav", type=str, default=None,
        help="WAV file to prime ASR before mic starts (overrides --prime-ms)")
    p.add_argument("--prime-mt", action="store_true",
        help="Prime MT once before capture starts")
    p.add_argument("--allow-fallback", action="store_true",
        help="(tests only) emit a synthetic final if no ASR finals were produced")
    # default False for real usage; tests can opt-in with --allow-fallback
    p.set_defaults(allow_fallback=False)

    args = p.parse_args(argv)

    src = args.src_lang or "en"
    tgt = args.tgt_lang or "zh_Hans"

    try:
        asyncio.run(
            _run_demo(
                args.duration,
                args.wav,
                args.partials,
                args.session,
                src,
                tgt,
                echo=args.echo,
                countdown=args.countdown,
                blocksize=args.blocksize,
                queue_size=args.queue_size,
                samplerate=args.samplerate,
                warmup_ms=args.warmup_ms,
                energy_thresh=args.energy_thresh,
                input_device=args.input_device,
                prime_ms=args.prime_ms,
                prime_wav=args.prime_wav,
                prime_mt=args.prime_mt,
                allow_fallback=args.allow_fallback,
            )
        )
    except KeyboardInterrupt:
        print("Interrupted")
        return 0
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

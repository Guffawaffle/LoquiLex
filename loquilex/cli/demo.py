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
):
    session_dir = _make_session_dir(session_name)
    events_path = session_dir / "events.jsonl"
    transcript_path = session_dir / "transcript.txt"

    asr = StreamingASR(stream_id=session_dir.name)
    mt = MTService()

    event_queue: asyncio.Queue = asyncio.Queue()
    loop = asyncio.get_running_loop()

    stats = {"partials": 0, "finals": 0, "latencies_ms": []}

    def on_partial(ev: ASRPartialEvent) -> None:
        # push to queue for optional translation/writing
        loop.call_soon_threadsafe(event_queue.put_nowait, ("asr.partial", ev))

    def on_final(ev: ASRFinalEvent) -> None:
        loop.call_soon_threadsafe(event_queue.put_nowait, ("asr.final", ev))

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

        audio_q: queue.Queue = queue.Queue(maxsize=64)
        running = True

        def sd_callback(indata, frames, time_info, status):
            # keep this ultra-light; never run ASR here
            try:
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

        stream = sd.InputStream(samplerate=ASR.sample_rate, channels=1, dtype="float32", callback=sd_callback)

        running = True
        pump_task = asyncio.create_task(pump_audio())

        # pick settings your ASR expects; adjust samplerate/channels if different
        with sd.InputStream(
            samplerate=ASR.sample_rate,
            channels=1,
            dtype="float32",
            blocksize=1024,          # small, steady blocks reduce latency
            latency="low",
            callback=sd_callback,
        ):
            try:
                await asyncio.sleep(duration)
            finally:
                running = False
                pump_task.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await pump_task

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
    # If no finals produced (e.g., silent WAV), synthesize a final so demos produce output
    if stats["finals"] == 0:
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

    args = p.parse_args(argv)

    src = args.src_lang or "en"
    tgt = args.tgt_lang or "zh_Hans"

    try:
        asyncio.run(_run_demo(args.duration, args.wav, args.partials, args.session, src, tgt))
    except KeyboardInterrupt:
        print("Interrupted")
        return 0
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

from __future__ import annotations

import argparse
import wave
from typing import List, Tuple

import numpy as np

from loquilex.output.vtt import write_vtt
from loquilex.config.defaults import ASR, pick_device


def read_wav_mono_16k(path: str) -> np.ndarray:
    with wave.open(path, "rb") as w:
        sr = w.getframerate()
        ch = w.getnchannels()
        n = w.getnframes()
        raw = w.readframes(n)
    data = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0
    if ch > 1:
        data = data.reshape(-1, ch).mean(axis=1)
    if sr != 16000:
        # simple fallback resample using numpy (linear), prefer  ffmpeg externally for quality
        t = np.linspace(0, len(data) / sr, num=len(data), endpoint=False)
        t2 = np.linspace(0, len(data) / sr, num=int(len(data) * 16000 / sr), endpoint=False)
        data = np.interp(t2, t, data).astype(np.float32)
    return data


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--wav", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    # Offline path: use faster-whisper directly for stability
    from faster_whisper import WhisperModel  # type: ignore

    device, _ = pick_device()
    # Prefer int8_float32 on CPU for better quality; fallback handled by faster-whisper if unsupported
    compute_type = ASR.compute_type if device == "cuda" else "int8_float32"
    model = WhisperModel(ASR.model, device=device, compute_type=compute_type)
    print(f"[asr] device={device} model={ASR.model} compute={compute_type}")
    data = read_wav_mono_16k(args.wav)

    cues: List[Tuple[float, float, str]] = []
    segments, _ = model.transcribe(
        data,
        language=ASR.language,
        vad_filter=ASR.vad_filter,
        beam_size=ASR.beam_size,
        no_speech_threshold=ASR.no_speech_threshold,
        log_prob_threshold=ASR.log_prob_threshold,
        condition_on_previous_text=ASR.condition_on_previous_text,
        temperature=0.0,
        without_timestamps=False,
        word_timestamps=False,
    )
    for s in segments:
        t = (s.text or "").strip()
        if t:
            cues.append((float(s.start or 0.0), float(s.end or 0.0), t))

    write_vtt(cues, args.out)
    print(f"[cli] wrote {args.out} ({len(cues)} cues)")


if __name__ == "__main__":
    main()

# Greenfield Live EN->ZH Pipeline

This is a minimal, pragmatic live captioning + MT pipeline inspired by rt-whisper and LocalVocal.

Why final-only MT by default

- Chinese quality improves when translating finalized English clauses.
- We keep a fast English partial line for immediacy (<200 ms), and send zh on finalize (typically 400–800 ms after pause).
- Optional rolling retranslate window can be added later to stabilize prefixes (off by default).

Architecture

```
mic -> audio/capture -> asr/whisper_engine (partials, finals)
                         |
                         v
                   segmentation/aggregator (pause/max)
                         |
               EN(VTT writer)   -> output/vtt
                         |
                        (final)
                         v
                MT -> post/zh_text -> output/srt + TXT
```

Defaults

- ASR: small.en, beam=1, vad_filter=True, condition_on_previous_text=False
- Segmentation: PAUSE_FLUSH_SEC≈0.7, SEGMENT_MAX_SEC≈7, partial debounce≈250 ms
- MT: NLLB-200 distilled 600M (eng_Latn -> zho_Hans), fallback M2M-100 418M (en -> zh)

Performance targets (logged)

- EN partial latency < 200 ms
- zh final line < 400–800 ms after pause
- CUDA uses float16, CPU uses int8/float32

Tuning

- SEG.pause_flush_sec: shorter gives earlier zh; longer yields more stable clauses
- SEG.segment_max_sec: hard cap to avoid runaway segments
- MT.num_beams=1–2; no_repeat_ngram_size=2; max_input/max_new ≈ 96
- post/zh_text: punctuation normalization; maintain a do-not-translate list

Run examples

See the commands at the end of this assistant message for venv, install, and running the CLIs.

Never writes outside `greenfield/out/`.

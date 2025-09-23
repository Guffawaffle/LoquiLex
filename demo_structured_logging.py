#!/usr/bin/env python3
"""
Demonstration of structured logging and performance metrics in LoquiLex.

This script shows the new structured logging system in action across
ASR, MT, and API supervisor components.
"""

import tempfile
import time
from pathlib import Path

from loquilex.logging import create_logger, PerformanceMetrics
from loquilex.asr.metrics import ASRMetrics
from loquilex.mt.translator import TranslationResult


def demo_structured_logging():
    """Demonstrate structured logging with data redaction."""
    print("=== Structured Logging Demo ===")

    # Create logger with file output
    with tempfile.TemporaryDirectory() as tmpdir:
        logger = create_logger(
            component="demo_session",
            session_id="demo123",
            log_dir=tmpdir,
        )

        # Basic logging
        logger.info(
            "Demo session started",
            user_config={
                "model_path": "/home/user/.cache/models/whisper-large.bin",
                "api_token": "sk-abcd1234efgh5678",  # This will be redacted
                "language": "en",  # Safe field
            },
        )

        # Error logging with context
        logger.error(
            "Translation failed",
            error_details={
                "model": "nllb-200-3.3B",
                "input_text": "Hello world",
                "secret_key": "hidden_secret_123",  # This will be redacted
            },
        )

        # Read back logs to show redaction
        # TODO: REMOVE Path()
        log_file = Path(tmpdir) / "demo_session_demo123.jsonl"
        if log_file.exists():
            print(f"\nGenerated log file: {log_file}")
            content = log_file.read_text()
            print("Log content (sensitive data redacted):")
            print(content)

    print("✓ Structured logging demo completed")


def demo_performance_metrics():
    """Demonstrate performance metrics collection."""
    print("\n=== Performance Metrics Demo ===")

    logger = create_logger(component="metrics_demo", session_id="perf123")
    metrics = PerformanceMetrics(logger=logger, component="demo")

    # Set thresholds
    metrics.set_threshold("api_latency", warning=100.0, critical=500.0)

    # Simulate API calls
    print("Simulating API calls...")
    for i in range(5):
        metrics.start_timer("api_call")
        time.sleep(0.01 * (i + 1))  # Simulate varying latency
        duration = metrics.end_timer("api_call", request_id=f"req_{i}")
        print(f"  API call {i+1}: {duration:.2f}ms")

    # Simulate counters and gauges
    metrics.increment_counter("requests_total", 5)
    metrics.set_gauge("cpu_usage", 45.2)
    metrics.set_gauge("memory_mb", 1024)

    # Get metrics summary
    summary = metrics.get_all_metrics()
    print(f"\nMetrics Summary:")
    print(f"  Counters: {summary['counters']}")
    print(f"  Gauges: {summary['gauges']}")

    # Show latency stats
    api_stats = metrics.get_stats("api_call")
    if api_stats:
        print(f"  API Latency Stats:")
        print(f"    Count: {api_stats.count}")
        print(f"    Average: {api_stats.avg:.2f}ms")
        print(f"    Min/Max: {api_stats.min:.2f}ms / {api_stats.max:.2f}ms")
        print(f"    P95: {api_stats.p95:.2f}ms")

    print("✓ Performance metrics demo completed")


def demo_asr_metrics():
    """Demonstrate ASR metrics with structured logging."""
    print("\n=== ASR Metrics Demo ===")

    # Create ASR metrics with logging
    asr_metrics = ASRMetrics("demo_stream")

    print("Simulating ASR events...")

    # Simulate partial events
    for i in range(3):
        asr_metrics.on_partial_event(
            {
                "text": f"Hello world part {i+1}",
                "segment_id": "seg_001",
                "stability": 0.8 + i * 0.1,
            }
        )
        time.sleep(0.05)  # Small delay between partials

    # Simulate final event
    asr_metrics.on_final_event(
        {
            "text": "Hello world complete sentence",
            "segment_id": "seg_001",
            "eou_reason": "silence",
            "words": [
                {"word": "Hello", "start": 0.0, "end": 0.5},
                {"word": "world", "start": 0.6, "end": 1.0},
            ],
        }
    )

    # Get and display summary
    summary = asr_metrics.get_summary()
    print(f"ASR Session Summary:")
    print(f"  Stream ID: {summary['stream_id']}")
    print(f"  Events: {summary['events']}")
    print(f"  EOU Reasons: {summary['eou_reasons']}")

    if "performance" in summary:
        perf = summary["performance"]
        print(f"  Performance Targets:")
        for metric, met in perf.items():
            print(f"    {metric}: {'✓' if met else '✗'}")

    print("✓ ASR metrics demo completed")


def demo_mt_translator():
    """Demonstrate MT translator with metrics (mock translation)."""
    print("\n=== MT Translator Demo ===")

    # Mock a translation result to show the enhanced structure
    result = TranslationResult(
        text="世界你好",
        model="mock_nllb",
        src_lang="en",
        tgt_lang="zh",
        duration_ms=125.5,
        confidence=0.92,
    )

    print("Mock translation result:")
    print(f"  Input: 'Hello world' (en)")
    print(f"  Output: '{result.text}' (zh)")
    print(f"  Model: {result.model}")
    print(f"  Duration: {result.duration_ms}ms")
    print(f"  Confidence: {result.confidence}")

    print("✓ MT translator demo completed")


if __name__ == "__main__":
    print("LoquiLex Structured Logging and Performance Metrics Demo")
    print("=" * 60)

    try:
        demo_structured_logging()
        demo_performance_metrics()
        demo_asr_metrics()
        demo_mt_translator()

        print("\n" + "=" * 60)
        print("All demos completed successfully! 🎉")
        print("\nKey features demonstrated:")
        print("✓ Offline-safe structured logging with JSON format")
        print("✓ Automatic sensitive data redaction")
        print("✓ Performance metrics with thresholds")
        print("✓ ASR latency and throughput tracking")
        print("✓ MT translation timing")
        print("✓ Session correlation and component isolation")

    except Exception as e:
        print(f"\n❌ Demo failed with error: {e}")
        raise

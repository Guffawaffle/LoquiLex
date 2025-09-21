"""Tests for model indexing functionality."""

from __future__ import annotations

import json
import tempfile
import time
from pathlib import Path


from loquilex.indexing.worker import ModelIndex, ModelIndexer


def test_model_index_serialization():
    """Test ModelIndex serialization to/from dict."""
    index = ModelIndex(
        asr_models=[{"id": "small.en", "name": "small.en"}],
        mt_models=[{"id": "nllb-600M", "name": "nllb-600M"}],
        last_updated=1640995200.0,  # Fixed timestamp
        scan_duration_ms=150,
    )

    # Test to_dict
    data = index.to_dict()
    assert data["asr_models"] == [{"id": "small.en", "name": "small.en"}]
    assert data["mt_models"] == [{"id": "nllb-600M", "name": "nllb-600M"}]
    assert data["last_updated"] == 1640995200.0
    assert data["scan_duration_ms"] == 150

    # Test from_dict
    restored = ModelIndex.from_dict(data)
    assert restored == index


def test_model_indexer_basic():
    """Test basic ModelIndexer functionality."""
    with tempfile.TemporaryDirectory() as tmpdir:
        cache_path = Path(tmpdir) / "model_index.json"
        indexer = ModelIndexer(cache_path=cache_path, refresh_interval=1)

        # Get initial index (should trigger scan)
        index = indexer.get_index()
        assert isinstance(index, ModelIndex)
        assert isinstance(index.asr_models, list)
        assert isinstance(index.mt_models, list)
        assert index.last_updated > 0
        assert index.scan_duration_ms >= 0

        # Check cache was created
        assert cache_path.exists()

        # Verify cached data
        with open(cache_path) as f:
            cached_data = json.load(f)
        assert "asr_models" in cached_data
        assert "mt_models" in cached_data


def test_model_indexer_refresh_logic():
    """Test indexer refresh logic."""
    with tempfile.TemporaryDirectory() as tmpdir:
        cache_path = Path(tmpdir) / "model_index.json"
        indexer = ModelIndexer(cache_path=cache_path, refresh_interval=2)

        # Get initial index
        index1 = indexer.get_index()
        first_time = index1.last_updated

        # Immediate second call should return cached version
        index2 = indexer.get_index()
        assert index2.last_updated == first_time

        # Force refresh should update
        index3 = indexer.refresh_index(force=True)
        assert index3.last_updated > first_time


def test_model_indexer_convenience_methods():
    """Test convenience methods for getting models."""
    with tempfile.TemporaryDirectory() as tmpdir:
        cache_path = Path(tmpdir) / "model_index.json"
        indexer = ModelIndexer(cache_path=cache_path)

        asr_models = indexer.get_asr_models()
        mt_models = indexer.get_mt_models()

        assert isinstance(asr_models, list)
        assert isinstance(mt_models, list)


def test_model_indexer_background_worker():
    """Test background worker start/stop."""
    with tempfile.TemporaryDirectory() as tmpdir:
        cache_path = Path(tmpdir) / "model_index.json"
        indexer = ModelIndexer(cache_path=cache_path, refresh_interval=1)

        # Start background worker
        indexer.start_background_worker()
        time.sleep(0.1)  # Brief pause for thread to start

        # Should have a worker thread
        assert indexer._worker_thread is not None
        assert indexer._worker_thread.is_alive()

        # Stop worker
        indexer.stop_background_worker()
        assert indexer._worker_thread is None


def test_model_indexer_cache_loading():
    """Test loading from existing cache."""
    with tempfile.TemporaryDirectory() as tmpdir:
        cache_path = Path(tmpdir) / "model_index.json"

        # Create a fake cache file
        fake_data = {
            "asr_models": [{"id": "cached.en", "name": "cached"}],
            "mt_models": [],
            "last_updated": 1640995200.0,
            "scan_duration_ms": 100,
        }
        with open(cache_path, "w") as f:
            json.dump(fake_data, f)

        # Create indexer - should load from cache
        indexer = ModelIndexer(cache_path=cache_path)
        index = indexer._index

        assert index is not None
        assert len(index.asr_models) == 1
        assert index.asr_models[0]["id"] == "cached.en"
        assert index.last_updated == 1640995200.0

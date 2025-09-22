"""Model indexing worker for caching discovered models."""

from __future__ import annotations

import json
import logging
import threading
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

from ..api.model_discovery import list_asr_models, list_mt_models
from ..config.paths import resolve_out_dir

logger = logging.getLogger(__name__)


@dataclass
class ModelIndex:
    """Cached model index with metadata."""

    asr_models: List[Dict[str, Any]]
    mt_models: List[Dict[str, Any]]
    last_updated: float
    scan_duration_ms: int

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> ModelIndex:
        return cls(**data)


class ModelIndexer:
    """Background worker for indexing and caching locally available models."""

    STOP_TIMEOUT_SEC = 5.0
    ERROR_RETRY_SLEEP_SEC = 30.0

    def __init__(self, cache_path: Optional[Path] = None, refresh_interval: int = 300):
        """Initialize indexer.

        Args:
            cache_path: Path to cache file. Defaults to `<OUT_DIR>/model_index.json`,
                where `OUT_DIR` comes from `LX_OUT_DIR` (or legacy `LLX_OUT_DIR`) and
                falls back to `loquilex/out`.
            refresh_interval: Seconds between automatic re-indexing (default 5 minutes)
        """
        if cache_path is None:
            out_dir = resolve_out_dir()
            self.cache_path = out_dir / "model_index.json"
        else:
            self.cache_path = Path(cache_path)
        self.refresh_interval = refresh_interval
        self._index: Optional[ModelIndex] = None
        self._lock = threading.RLock()
        self._worker_thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()

        # Ensure cache directory exists
        self.cache_path.parent.mkdir(parents=True, exist_ok=True)

        # Load existing index if available
        self._load_cache()

    def _load_cache(self) -> None:
        """Load cached index from disk."""
        try:
            if self.cache_path.exists():
                with open(self.cache_path, "r") as f:
                    data = json.load(f)
                self._index = ModelIndex.from_dict(data)
                logger.debug(f"Loaded model index from {self.cache_path}")
        except Exception as e:
            logger.warning(f"Failed to load model index cache: {e}")

    def _save_cache(self) -> None:
        """Save current index to disk."""
        if self._index is None:
            return

        try:
            with open(self.cache_path, "w") as f:
                json.dump(self._index.to_dict(), f, indent=2)
            logger.debug(f"Saved model index to {self.cache_path}")
        except Exception as e:
            logger.warning(f"Failed to save model index cache: {e}")

    def _scan_models(self) -> ModelIndex:
        """Scan for available models and create index."""
        start_time = time.time()

        logger.debug("Scanning for available models...")
        asr_models = list_asr_models()
        mt_models = list_mt_models()

        scan_duration_ms = int((time.time() - start_time) * 1000)

        index = ModelIndex(
            asr_models=asr_models,
            mt_models=mt_models,
            last_updated=time.time(),
            scan_duration_ms=scan_duration_ms,
        )

        logger.info(
            f"Model scan complete: {len(asr_models)} ASR, {len(mt_models)} MT models "
            f"(took {scan_duration_ms}ms)"
        )

        return index

    def refresh_index(self, force: bool = False) -> ModelIndex:
        """Refresh the model index.

        Args:
            force: Force refresh even if cache is recent

        Returns:
            Updated model index
        """
        with self._lock:
            # Check if refresh is needed
            if not force and self._index is not None:
                age = time.time() - self._index.last_updated
                if age < self.refresh_interval:
                    logger.debug(f"Index is recent ({age:.1f}s old), skipping refresh")
                    return self._index

            # Perform scan
            self._index = self._scan_models()
            self._save_cache()

            return self._index

    def get_index(self) -> ModelIndex:
        """Get current model index, refreshing if stale.

        Returns:
            Current model index
        """
        with self._lock:
            if self._index is None:
                return self.refresh_index(force=True)

            # Check staleness
            age = time.time() - self._index.last_updated
            if age > self.refresh_interval:
                logger.debug(f"Index is stale ({age:.1f}s old), refreshing")
                return self.refresh_index(force=True)

            return self._index

    def get_asr_models(self) -> List[Dict[str, Any]]:
        """Get cached ASR models."""
        return self.get_index().asr_models

    def get_mt_models(self) -> List[Dict[str, Any]]:
        """Get cached MT models."""
        return self.get_index().mt_models

    def start_background_worker(self) -> None:
        """Start background worker thread for automatic refreshing."""
        if self._worker_thread is not None and self._worker_thread.is_alive():
            logger.debug("Background worker already running")
            return

        self._stop_event.clear()
        self._worker_thread = threading.Thread(
            target=self._background_worker, name="ModelIndexer", daemon=True
        )
        self._worker_thread.start()
        logger.info("Started model indexing background worker")

    def stop_background_worker(self) -> None:
        """Stop background worker thread."""
        if self._worker_thread is None:
            return

        self._stop_event.set()
        self._worker_thread.join(timeout=self.STOP_TIMEOUT_SEC)
        if self._worker_thread.is_alive():
            logger.warning("Background worker did not stop cleanly")
        else:
            logger.info("Stopped model indexing background worker")
        self._worker_thread = None

    def _background_worker(self) -> None:
        """Background worker loop."""
        while not self._stop_event.is_set():
            try:
                # Wait for refresh interval or stop event
                if self._stop_event.wait(self.refresh_interval):
                    break  # Stop requested

                # Refresh if we haven't been stopped
                if not self._stop_event.is_set():
                    self.refresh_index(force=False)

            except Exception as e:
                logger.error(f"Error in background model indexing: {e}")
                # Continue running despite errors
                time.sleep(self.ERROR_RETRY_SLEEP_SEC)  # Brief pause before retrying


# Global singleton instance
_default_indexer: Optional[ModelIndexer] = None


def get_model_indexer() -> ModelIndexer:
    """Get the default model indexer instance."""
    global _default_indexer
    if _default_indexer is None:
        _default_indexer = ModelIndexer()
    return _default_indexer

"""Per-role model defaults with persistence."""

from __future__ import annotations

import json
import logging
import os
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, Optional

from .paths import resolve_out_dir

logger = logging.getLogger(__name__)


@dataclass
class ModelDefaults:
    """Default model selections per role."""

    # ASR defaults
    asr_model_id: str = ""
    asr_device: str = "auto"
    asr_compute_type: str = "float16"

    # MT defaults
    mt_model_id: str = ""
    mt_device: str = "auto"
    mt_compute_type: str = "int8_float16"

    # TTS defaults (placeholder for future)
    tts_model_id: str = ""
    tts_device: str = "auto"

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> ModelDefaults:
        # Filter to only known fields and drop None values so dataclass defaults apply
        known_fields = {f.name for f in cls.__dataclass_fields__.values()}
        filtered_data = {k: v for k, v in data.items() if k in known_fields and v is not None}
        return cls(**filtered_data)


class ModelDefaultsManager:
    """Manages persistent model defaults with fallback to environment variables."""

    def __init__(self, storage_path: Optional[Path] = None):
        """Initialize defaults manager.

        Args:
            storage_path: Path to defaults storage file. Defaults to
                `<OUT_DIR>/model_defaults.json`, where `OUT_DIR` comes from
                `LX_OUT_DIR` (or legacy `LLX_OUT_DIR`) and falls back to
                `loquilex/out`.
        """
        if storage_path is None:
            out_dir = resolve_out_dir()
            self.storage_path = out_dir / "model_defaults.json"
        else:
            assert os.path.isabs(
                str(storage_path)
            ), "storage_path must be absolute (trusted config)"
            self.storage_path = Path(storage_path)
        self._defaults: Optional[ModelDefaults] = None

        # Ensure storage directory exists
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)

        # Load existing defaults
        self._load_defaults()

    def _load_defaults(self) -> None:
        """Load defaults from storage, falling back to environment variables."""
        try:
            if self.storage_path.exists():
                with open(self.storage_path, "r") as f:
                    data = json.load(f)
                self._defaults = ModelDefaults.from_dict(data)
                logger.debug(f"Loaded model defaults from {self.storage_path}")
                return
        except Exception as e:
            logger.warning(f"Failed to load model defaults: {e}")

        # Fallback to environment variables for initial defaults
        self._defaults = ModelDefaults(
            asr_model_id=os.getenv("LX_ASR_MODEL", ""),
            asr_device=os.getenv("LX_DEVICE", "auto"),
            asr_compute_type=os.getenv("LX_ASR_COMPUTE", "float16"),
            mt_model_id=os.getenv("LX_NLLB_MODEL", "") or os.getenv("LX_M2M_MODEL", ""),
            mt_device=os.getenv("LX_MT_DEVICE", "auto"),
            mt_compute_type=os.getenv("LX_MT_COMPUTE_TYPE", "int8_float16"),
            tts_model_id="",  # No env var equivalent yet
            tts_device=os.getenv("LX_DEVICE", "auto"),
        )

        # Save initial defaults
        self._save_defaults()

    def _save_defaults(self) -> None:
        """Save current defaults to storage."""
        if self._defaults is None:
            return

        try:
            with open(self.storage_path, "w") as f:
                json.dump(self._defaults.to_dict(), f, indent=2)
            logger.debug(f"Saved model defaults to {self.storage_path}")
        except Exception as e:
            logger.warning(f"Failed to save model defaults: {e}")

    def get_defaults(self) -> ModelDefaults:
        """Get current model defaults."""
        if self._defaults is None:
            self._load_defaults()
        return self._defaults or ModelDefaults()

    def update_defaults(self, **kwargs) -> ModelDefaults:
        """Update model defaults.

        Args:
            **kwargs: Default values to update (asr_model_id, mt_model_id, etc.)

        Returns:
            Updated defaults
        """
        current = self.get_defaults()

        # Update only provided fields; ignore None to avoid nulling values
        for key, value in kwargs.items():
            if value is None:
                continue
            if hasattr(current, key):
                setattr(current, key, value)
            else:
                logger.warning(f"Unknown default field: {key}")

        self._defaults = current
        self._save_defaults()

        logger.info(f"Updated model defaults: {kwargs}")
        return current

    def get_asr_default(self) -> str:
        """Get default ASR model ID."""
        return self.get_defaults().asr_model_id

    def get_mt_default(self) -> str:
        """Get default MT model ID."""
        return self.get_defaults().mt_model_id

    def get_tts_default(self) -> str:
        """Get default TTS model ID."""
        return self.get_defaults().tts_model_id

    def set_asr_default(self, model_id: str) -> None:
        """Set default ASR model."""
        self.update_defaults(asr_model_id=model_id)

    def set_mt_default(self, model_id: str) -> None:
        """Set default MT model."""
        self.update_defaults(mt_model_id=model_id)

    def set_tts_default(self, model_id: str) -> None:
        """Set default TTS model."""
        self.update_defaults(tts_model_id=model_id)


# Global singleton instance
_default_manager: Optional[ModelDefaultsManager] = None


def get_model_defaults_manager() -> ModelDefaultsManager:
    """Get the default model defaults manager instance."""
    global _default_manager
    if _default_manager is None:
        _default_manager = ModelDefaultsManager()
    return _default_manager

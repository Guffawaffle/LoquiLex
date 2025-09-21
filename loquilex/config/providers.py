"""Provider configuration management for LoquiLex.

Handles tokens, credentials, and offline mode for various ML model providers.
"""

from __future__ import annotations

import os
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Any, Optional

from .defaults import _env, _env_bool


@dataclass
class HuggingFaceConfig:
    """HuggingFace provider configuration."""
    
    token: Optional[str] = None
    enabled: bool = True
    
    def __post_init__(self) -> None:
        """Validate token format if provided."""
        if self.token and not (
            self.token.startswith("hf_") or 
            len(self.token) in [34, 37]  # Standard HF token lengths
        ):
            raise ValueError("Invalid HuggingFace token format")


@dataclass
class BackendConfig:
    """Backend operation configuration."""
    
    offline: bool = False
    offline_enforced: bool = False
    
    def __post_init__(self) -> None:
        """Check if offline mode is enforced by environment."""
        self.offline_enforced = _env_bool("LX_OFFLINE", False)
        if self.offline_enforced:
            self.offline = True


@dataclass 
class ProvidersConfig:
    """Complete provider configuration."""
    
    huggingface: HuggingFaceConfig
    backend: BackendConfig
    
    @classmethod
    def from_env(cls) -> ProvidersConfig:
        """Create configuration from environment variables."""
        hf_token = os.getenv("LX_HF_TOKEN") or os.getenv("HUGGING_FACE_HUB_TOKEN")
        
        return cls(
            huggingface=HuggingFaceConfig(
                token=hf_token,
                enabled=True
            ),
            backend=BackendConfig(
                offline=_env_bool("LX_OFFLINE", False)
            )
        )
    
    @classmethod
    def from_file(cls, config_path: Path) -> Optional[ProvidersConfig]:
        """Load configuration from JSON file."""
        if not config_path.exists():
            return None
            
        try:
            with config_path.open('r') as f:
                data = json.load(f)
            
            hf_data = data.get('providers', {}).get('huggingface', {})
            backend_data = data.get('backend', {})
            
            return cls(
                huggingface=HuggingFaceConfig(
                    token=hf_data.get('token'),
                    enabled=hf_data.get('enabled', True)
                ),
                backend=BackendConfig(
                    offline=backend_data.get('offline', False)
                )
            )
        except (json.JSONDecodeError, KeyError, ValueError):
            return None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for API responses."""
        return {
            'providers': {
                'huggingface': {
                    'token': '***' if self.huggingface.token else None,
                    'enabled': self.huggingface.enabled,
                    'has_token': bool(self.huggingface.token)
                }
            },
            'backend': {
                'offline': self.backend.offline,
                'offline_enforced': self.backend.offline_enforced
            }
        }
    
    def save_to_file(self, config_path: Path) -> None:
        """Save configuration to JSON file."""
        config_path.parent.mkdir(parents=True, exist_ok=True)
        
        data = {
            'providers': {
                'huggingface': {
                    'token': self.huggingface.token,
                    'enabled': self.huggingface.enabled
                }
            },
            'backend': {
                'offline': self.backend.offline
            }
        }
        
        with config_path.open('w') as f:
            json.dump(data, f, indent=2)


# Global configuration instance
_config: Optional[ProvidersConfig] = None


def get_providers_config() -> ProvidersConfig:
    """Get the current providers configuration."""
    global _config
    
    if _config is None:
        # Try to load from file first, then fallback to environment
        config_path = Path.home() / '.loquilex' / 'providers.json'
        _config = ProvidersConfig.from_file(config_path)
        
        if _config is None:
            _config = ProvidersConfig.from_env()
    
    return _config


def update_providers_config(config: ProvidersConfig) -> None:
    """Update the global providers configuration."""
    global _config
    _config = config
    
    # Save to file for persistence
    config_path = Path.home() / '.loquilex' / 'providers.json'
    try:
        config.save_to_file(config_path)
    except Exception:
        # Ignore save errors for now, rely on in-memory config
        pass


def is_offline_mode() -> bool:
    """Check if system is in offline mode."""
    config = get_providers_config()
    return config.backend.offline or config.backend.offline_enforced


def get_hf_token() -> Optional[str]:
    """Get HuggingFace token if available and provider is enabled."""
    config = get_providers_config()
    
    if not config.huggingface.enabled:
        return None
        
    return config.huggingface.token
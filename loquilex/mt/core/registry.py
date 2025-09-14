"""MT provider registry for factory pattern."""

from __future__ import annotations

from typing import Callable, Dict

from .protocol import MTProvider

ProviderFactory = Callable[[], MTProvider]
_registry: Dict[str, ProviderFactory] = {}


def register_provider(name: str, factory: ProviderFactory) -> None:
    """Register a provider factory by name."""
    _registry[name] = factory


def available() -> list[str]:
    """Get list of available provider names."""
    return sorted(_registry.keys())


def create(name: str) -> MTProvider:
    """Create provider instance by name."""
    try:
        return _registry[name]()
    except KeyError:
        raise ValueError(f"Unknown MT provider: {name}")
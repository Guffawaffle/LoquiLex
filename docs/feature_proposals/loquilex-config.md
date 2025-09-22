Title: loquilex.config - Centralized runtime configuration
===============================================

Executive summary
-----------------

This proposal defines a small, dependency-free `loquilex.config` module to centralize runtime defaults and env-var parsing. It will replace scattered module-level constants (like memory fallbacks) and provide a single place to document configuration semantics, default values, and testing guidance.

Goals
-----

- Provide typed, well-documented settings accessible across the codebase.
- Back settings with environment variables using the `LX_` prefix.
- Keep implementation minimal (stdlib-only) but pluggable for future enhancements (pydantic, dynaconf).

Design
------

1. `loquilex/config.py` exports a `Settings` dataclass and a module-level `settings` instance.

Example shape:

```py
from dataclasses import dataclass
import os

@dataclass
class Settings:
    fallback_memory_total_gb: float = float(os.getenv("LX_FALLBACK_MEMORY_TOTAL_GB", "8.0"))
    fallback_memory_available_gb: float = float(os.getenv("LX_FALLBACK_MEMORY_AVAILABLE_GB", "4.0"))
    min_memory_gb: float = float(os.getenv("LX_MIN_MEMORY_GB", "8.0"))
    min_cpu_cores: int = int(os.getenv("LX_MIN_CPU_CORES", "2"))
    max_cpu_usage_percent: float = float(os.getenv("LX_MAX_CPU_USAGE", "80.0"))

# module-level instance used by imports
settings = Settings()
```

2. Move existing module-level defaults into `config.py` and import `settings` where needed.

Testing
-------

- Unit tests should monkeypatch `loquilex.config.settings` to set values for specific tests.
- Integration tests can set env vars to validate env-backed overrides.

Migration plan
--------------

1. Add `loquilex/config.py` with typed settings and module-level `settings` instance.
2. Update `loquilex.hardware.detection` to import `settings` and use `settings.fallback_memory_total_gb`, etc.
3. Run tests and update where necessary.

Notes
-----

- Avoid adding new dependencies in the first pass.
- If later we need richer validation or env parsing, consider adding pydantic and a migration path.

Checklist
---------

- [ ] Create `loquilex/config.py`.
- [ ] Update `loquilex.hardware.detection` to import from config.
- [ ] Add unit tests demonstrating monkeypatch usage.
- [ ] Update docs and issue template (this file is the proposal).

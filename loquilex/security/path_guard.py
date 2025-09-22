"""Helpers to enforce filesystem path safety constraints."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Sequence


class PathSecurityError(ValueError):
    """Raised when a path violates configured safety constraints."""


class PathGuard:
    """Utility for constraining filesystem operations to approved roots."""

    _DEFAULT_ALLOWED_PATTERN = re.compile(r"[^A-Za-z0-9_-]+")

    def __init__(
        self,
        allowed_roots: Sequence[str | Path],
        *,
        default_root: str | Path | None = None,
    ) -> None:
        if not allowed_roots:
            raise ValueError("allowed_roots must contain at least one entry")

        resolved_roots = tuple(Path(root).resolve(strict=False) for root in allowed_roots)
        self._allowed_roots = resolved_roots

        if default_root is None:
            self._default_root = self._allowed_roots[0]
        else:
            default_resolved = Path(default_root).resolve(strict=False)
            if not self._is_within_roots(default_resolved):
                raise ValueError("default_root must reside within allowed_roots")
            self._default_root = default_resolved

    @property
    def allowed_roots(self) -> tuple[Path, ...]:
        """Return the tuple of allowed root paths."""

        return self._allowed_roots

    def ensure_dir(
        self,
        candidate: str | Path,
        *,
        allow_relative: bool = True,
        create: bool = False,
        must_exist: bool = True,
    ) -> Path:
        """Return a safe directory path subject to guard constraints."""
        # When creating, normalisation must not require existence
        effective_must_exist = False if create else must_exist
        path = self._normalise(
            candidate, allow_relative=allow_relative, must_exist=effective_must_exist
        )

        if path.exists():
            if not path.is_dir():
                raise PathSecurityError(f"{path} is not a directory")
        else:
            if create:
                path.mkdir(parents=True, exist_ok=True)
            elif must_exist:
                raise PathSecurityError(f"directory does not exist: {path}")

        return path

    def ensure_file(
        self,
        base_dir: str | Path,
        name: str,
        *,
        suffix: str = "",
        create_parents: bool = False,
        must_exist: bool = False,
        allow_fallback: bool = True,
    ) -> Path:
        """Return a safe file path resolved against ``base_dir``.

        Args:
            base_dir: Directory the file must be located beneath.
            name: Untrusted file stem that will be sanitised.
            suffix: Optional file suffix (".json", ".txt", ...).
            create_parents: Whether to create parent directories on demand.
            must_exist: Require the file to already exist.
            allow_fallback: Allow sanitisation to substitute a default stem when
                the input collapses to an empty value.
        """

        base_path = self.ensure_dir(base_dir, allow_relative=False, create=create_parents)
        default_value = "item" if allow_fallback else ""
        safe_stem = self.sanitise_component(name, default=default_value)
        if not safe_stem:
            raise PathSecurityError("file name empty after sanitisation")
        candidate = (base_path / f"{safe_stem}{suffix}").resolve(strict=False)
        if not self._is_within_roots(candidate):
            raise PathSecurityError(f"file escapes allowed roots: {candidate}")

        if create_parents:
            candidate.parent.mkdir(parents=True, exist_ok=True)

        if must_exist and not candidate.exists():
            raise PathSecurityError(f"file does not exist: {candidate}")

        return candidate

    def resolve_relative(self, base_dir: str | Path, fragment: str | Path) -> Path:
        """Resolve ``fragment`` as a child of ``base_dir`` while enforcing constraints."""
        base_path = self.ensure_dir(base_dir, allow_relative=False, create=False)
        frag = Path(fragment)
        if frag.is_absolute():
            raise PathSecurityError("absolute fragments are not permitted")
        candidate = (base_path / frag).resolve(strict=False)
        if not self._is_within_roots(candidate):
            raise PathSecurityError(f"path escapes allowed roots: {candidate}")
        return candidate

    def _normalise(
        self, candidate: str | Path, *, allow_relative: bool, must_exist: bool = False
    ) -> Path:
        path = Path(candidate)

        try:
            if path.is_absolute():
                resolved = path.resolve(strict=must_exist)
            else:
                if not allow_relative:
                    raise PathSecurityError("relative paths are not permitted")
                resolved = (self._default_root / path).resolve(strict=must_exist)
        except FileNotFoundError as exc:
            raise PathSecurityError(f"path not found for resolution: {candidate}") from exc

        if not self._is_within_roots(resolved):
            raise PathSecurityError(f"path not permitted: {resolved}")
        return resolved

    def _is_within_roots(self, candidate: Path) -> bool:
        """
        Returns True if candidate is fully contained in one of the allowed roots,
        following normalization and canonicalization (symlinks resolved as far as possible).
        """
        # Normalize without requiring existence; resolves symlinks where possible
        candidate_resolved = candidate.resolve(strict=False)

        for root in self._allowed_roots:
            root_resolved = root.resolve(strict=False)
            try:
                candidate_resolved.relative_to(root_resolved)
            except ValueError:
                continue
            else:
                return True
        return False

    @classmethod
    def sanitise_component(
        cls,
        name: str,
        *,
        replacement: str = "_",
        max_length: int = 128,
        default: str = "item",
    ) -> str:
        """Return a safe filesystem component derived from ``name``.

        The sanitiser keeps alphanumeric characters along with ``-`` and ``_``.
        Any other characters are collapsed into the ``replacement`` token. An
        empty result falls back to ``default``.
        """

        if not replacement:
            raise ValueError("replacement must be a non-empty string")

        value = cls._DEFAULT_ALLOWED_PATTERN.sub(replacement, name)
        value = re.sub(f"{re.escape(replacement)}+", replacement, value).strip(replacement)

        if not value:
            value = default

        if len(value) > max_length:
            value = value[:max_length]

        return value


__all__ = ["PathGuard", "PathSecurityError"]

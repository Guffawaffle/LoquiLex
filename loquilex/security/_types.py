from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class CanonicalPath:
	"""
	Opaque handle for filesystem paths that have been validated by PathGuard.
	Do not construct directly outside PathGuard.
	"""
	_p: Path

	def as_path(self) -> Path:
		"""Return the underlying Path (use sparingly; prefer PathGuard APIs)."""
		return self._p

	def __fspath__(self) -> str:
		# Allows os.fspath(cp) and low-level APIs to consume it safely.
		return str(self._p)

	def __str__(self) -> str:  # pragma: no cover - trivial
		return str(self._p)

	def __repr__(self) -> str:  # pragma: no cover - trivial
		return f"CanonicalPath({self._p!s})"

	def __hash__(self) -> int:  # explicit for frozen dataclass clarity
		return hash(self._p)

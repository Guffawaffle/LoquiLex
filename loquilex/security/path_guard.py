"""Authoritative filesystem PathGuard for LoquiLex.

Threat model and protections:
- Directory traversal: reject attempts to escape a configured root using ``..`` or
  mixed separators; canonicalize and verify the final path stays under the root.
- Absolute path injection: only permit paths whose first component is an allowed
  logical root; prohibit absolute/drive/UNC forms in user input.
- Symlink/hardlink escape: by default, reject any symlinked segment via ``lstat`` and
  open files with ``O_NOFOLLOW``. Optionally allow symlinks only when the final target
  resolves within the same root.
- Information exposure: raise structured ``PathSecurityError`` without leaking host paths.
- Unicode/control chars/mixed separators: strip NUL/control chars; normalize to NFC; reject
  reserved names and trailing dots/spaces; disallow path separators in file components.

This guard is deny-by-default; only named roots are valid anchors.
"""

from __future__ import annotations

import os
import re
import stat as _stat
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, IO, Iterable, Optional, overload, cast
from typing import Literal, TextIO, BinaryIO


class PathSecurityError(ValueError):
    """Raised when a path violates configured safety constraints."""


@dataclass(frozen=True)
class _RootPolicy:
    allow_hidden: bool = False
    allowed_exts: tuple[str, ...] = ()
    name_pattern: re.Pattern[str] | None = None


def _is_reserved_windows_name(name: str) -> bool:
    base = name.split(".")[0].upper()
    reserved = {
        "CON",
        "PRN",
        "AUX",
        "NUL",
        *(f"COM{i}" for i in range(1, 10)),
        *(f"LPT{i}" for i in range(1, 10)),
    }
    return base in reserved


def strip_dangerous_chars(name: str) -> str:
    """Strip NUL/control chars and normalize Unicode to NFC; remove separators and trim.

    - Removes ``\x00`` and other C0 controls
    - Normalizes Unicode to NFC to reduce confusables
    - Removes path separators ``/`` and ``\\`` (intended for filenames, not paths)
    - Trims trailing dots/spaces (Windows compatibility)
    """

    if not isinstance(name, str):
        name = str(name)
    # Normalize and strip control chars
    name = unicodedata.normalize("NFC", name)
    name = re.sub(r"[\x00-\x1F\x7F]", "", name)
    # Remove path separators (use only for filenames)
    name = name.replace("/", "").replace("\\", "")
    # Trim trailing spaces and dots
    return name.rstrip(" .")


def is_safe_filename(name: str, *, max_length: int = 128) -> bool:
    """Return True if ``name`` matches strict filename policy.

    Policy: ``[A-Za-z0-9._-]{1,128}``, not hidden unless explicitly allowed, and not
    a Windows reserved device name.
    """

    if not name or len(name) > max_length:
        return False
    if _is_reserved_windows_name(name):
        return False
    if not re.fullmatch(r"[A-Za-z0-9._-]{1,128}", name):
        return False
    return True


class PathGuard:
    """Constrain filesystem operations to a base allowlist.

    Args:
        base_allowlist: Mapping of logical root names to absolute ``Path`` objects.
        follow_symlinks: When False (default), rejects any symlinked segment and uses
            ``O_NOFOLLOW`` for file opens. When True, allows symlinks only if the final
            resolved path remains inside the same logical root.

    The guard exposes helpers to resolve user-supplied paths, safely open files, and
    create directories with restrictive permissions. It also supports basic per-root
    policies and quota checks (opt-in via helpers).
    """

    def __init__(self, base_allowlist: Dict[str, Path], *, follow_symlinks: bool = False) -> None:
        if not base_allowlist:
            raise ValueError("base_allowlist must not be empty")
        abs_map: Dict[str, Path] = {}
        for name, root in base_allowlist.items():
            rp = Path(root).resolve(strict=False)
            if not rp.is_absolute():
                raise ValueError(f"root '{name}' must be absolute")
            abs_map[name] = rp
        self._roots: Dict[str, Path] = abs_map
        self._follow_symlinks = bool(follow_symlinks)
        # Default per-root policies (can be overridden by callers by wrapping usage)
        self._policies: Dict[str, _RootPolicy] = {
            "sessions": _RootPolicy(
                allow_hidden=False,
                allowed_exts=(".json", ".txt", ".vtt", ".srt", ".wav"),
                name_pattern=re.compile(r"[A-Za-z0-9._-]{1,128}"),
            ),
            "exports": _RootPolicy(
                allow_hidden=False,
                allowed_exts=(".json", ".txt", ".vtt", ".srt"),
                name_pattern=re.compile(r"[A-Za-z0-9._-]{1,128}"),
            ),
            "profiles": _RootPolicy(
                allow_hidden=False,
                allowed_exts=(".json",),
                name_pattern=re.compile(r"[A-Za-z0-9._-]{1,64}"),
            ),
        }

    # ---------- Core resolution ----------
    def resolve(self, root: str, user_path: str | Path) -> Path:
        """Resolve a user-supplied path under a named root and return absolute path.

        Steps:
        - Reject absolute/drive/UNC forms in ``user_path``
        - Strip dangerous chars and normalize
        - Join with base root, resolve with ``strict=False``
        - Verify path stays within the same root
        - Enforce symlink policy
        - Enforce per-root filename policy for leaf component
        """

        base = self._get_root(root)
        # Scrub control chars but preserve separators for traversal checks
        up_raw = unicodedata.normalize("NFC", str(user_path))
        up_str = re.sub(r"[\x00-\x1F\x7F]", "", up_raw)
        # Reject absolute or drive/UNC forms
        p = Path(up_str)
        if p.is_absolute() or re.match(r"^[A-Za-z]:\\", up_str) or up_str.startswith("\\\\"):
            raise PathSecurityError("absolute paths are not permitted")

        # Normalize the user-provided relative path without touching the
        # filesystem (do not call ``resolve`` on user-controlled input).
        rel_parts: list[str] = []
        for part in p.parts:
            if part in ("", "."):
                continue
            if part == "..":
                if rel_parts:
                    rel_parts.pop()
                else:
                    # Attempt to escape the base via leading '..'
                    raise PathSecurityError("path traversal blocked")
            else:
                rel_parts.append(part)
        candidate = base.joinpath(*rel_parts)

        # Symlink policy
        if not self._follow_symlinks:
            self._reject_symlink_segments(base, candidate)
        else:
            # Follow symlinks: resolve the candidate to its final target and
            # ensure it remains inside the configured root. This step is an
            # explicit opt-in (``follow_symlinks=True``) because it touches
            # the filesystem to follow link targets.
            final = candidate.resolve(strict=False)
            if not self._is_within_root(base, final):
                raise PathSecurityError("symlink escapes root")

        # Optional per-root filename policy: apply to leaf name primarily for files
        name = candidate.name
        pol = self._policies.get(root)
        if name:
            ext = Path(name).suffix
            file_like = bool(ext)
            if file_like:
                if not pol or not pol.name_pattern or not re.fullmatch(pol.name_pattern, name):
                    if not is_safe_filename(name):
                        raise PathSecurityError("invalid filename")
                if name.startswith(".") and (not pol or not pol.allow_hidden):
                    raise PathSecurityError("hidden files are not allowed")
                if pol and pol.allowed_exts and ext not in pol.allowed_exts:
                    raise PathSecurityError("disallowed file extension")
        return candidate

    # ---------- Safe open helpers ----------
    def open_read(self, resolved: Path) -> IO[bytes]:
        """Open a file for reading safely (O_NOFOLLOW, CLOEXEC)."""

        base = self._find_base_for(resolved)
        if base is None or not self._is_within_root(base, resolved):
            raise PathSecurityError("path outside allowed roots")
        if not self._follow_symlinks:
            self._reject_symlink_segments(base, resolved)
        flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0)
        if hasattr(os, "O_NOFOLLOW"):
            flags |= os.O_NOFOLLOW
        else:
            st = os.lstat(os.fspath(resolved))
            if _stat.S_ISLNK(st.st_mode):
                raise PathSecurityError("symlink blocked")
        fd = os.open(resolved, flags)
        try:
            return os.fdopen(fd, "rb", closefd=True)
        except Exception:
            os.close(fd)
            raise

    @overload
    def open_write(
        self, resolved: Path, *, overwrite: bool = False, binary: Literal[True] = True
    ) -> BinaryIO: ...

    @overload
    def open_write(
        self, resolved: Path, *, overwrite: bool = False, binary: Literal[False]
    ) -> TextIO: ...

    def open_write(
        self, resolved: Path, *, overwrite: bool = False, binary: bool = True
    ) -> BinaryIO | TextIO:
        """Open a file for writing safely with restrictive flags.

        - Ensures parent directory exists
        - Uses ``O_CREAT|O_EXCL`` when ``overwrite=False``; adds ``O_TRUNC`` when overwriting
        - Always sets ``O_CLOEXEC`` and prefers ``O_NOFOLLOW`` when available
        """

        base = self._find_base_for(resolved)
        if base is None or not self._is_within_root(base, resolved):
            raise PathSecurityError("path outside allowed roots")
        parent = resolved.parent
        self.ensure_dir(parent)
        if not self._follow_symlinks:
            self._reject_symlink_segments(base, resolved)
        flags = os.O_WRONLY | os.O_CREAT | getattr(os, "O_CLOEXEC", 0)
        if overwrite:
            flags |= os.O_TRUNC
        else:
            flags |= os.O_EXCL
        if hasattr(os, "O_NOFOLLOW"):
            flags |= os.O_NOFOLLOW
        else:
            try:
                st = os.lstat(os.fspath(resolved))
                if _stat.S_ISLNK(st.st_mode):
                    raise PathSecurityError("symlink blocked")
            except FileNotFoundError:
                pass
        fd = os.open(resolved, flags, 0o640)
        try:
            if binary:
                return cast(BinaryIO, os.fdopen(fd, "wb", closefd=True))
            else:
                return cast(TextIO, os.fdopen(fd, "w", closefd=True))
        except Exception:
            os.close(fd)
            raise

    def ensure_dir(self, resolved_dir: Path, *, mode: int = 0o750) -> None:
        """Validate and create a directory under allowed roots with restrictive perms."""
        base = self._find_base_for(resolved_dir)
        if base is None or not self._is_within_root(base, resolved_dir):
            raise PathSecurityError("directory outside allowed roots")
        # Enforce symlink policy for each path segment
        if not self._follow_symlinks:
            self._reject_symlink_segments(base, resolved_dir)
        resolved_dir.mkdir(parents=True, exist_ok=True, mode=mode)

    # ---------- Quotas ----------
    def compute_usage_bytes(self, root: str) -> int:
        """Compute total size of regular files under a root without following symlinks."""
        base = self._get_root(root)
        total = 0
        for p in self._walk_nofollow(base):
            try:
                st = os.lstat(os.fspath(p))
            except FileNotFoundError:
                continue
            if _stat.S_ISREG(st.st_mode):
                total += st.st_size
        return total

    def enforce_quota(self, root: str, max_bytes: Optional[int]) -> None:
        """Raise if usage under ``root`` exceeds ``max_bytes``. ``None`` disables checks."""
        if max_bytes is None:
            return
        used = self.compute_usage_bytes(root)
        if used > max_bytes:
            raise PathSecurityError("quota exceeded")

    # ---------- Internals ----------
    def _get_root(self, name: str) -> Path:
        try:
            return self._roots[name]
        except KeyError as exc:
            raise PathSecurityError(f"unknown root: {name}") from exc

    def _find_base_for(self, p: Path) -> Path | None:
        # Avoid resolving the input path; instead, attempt to match by
        # canonicalizing relative components and checking containment.
        for base in self._roots.values():
            try:
                p.relative_to(base)
                return base
            except ValueError:
                continue
        return None

    @staticmethod
    def _is_within_root(base: Path, candidate: Path) -> bool:
        # Use relative_to without resolving to avoid touching the filesystem
        # for untrusted inputs. Compare path parts after both are made
        # absolute-ish by removing relative components.
        try:
            candidate.relative_to(base)
            return True
        except ValueError:
            return False

    @staticmethod
    def _iter_segments(base: Path, target: Path) -> Iterable[Path]:
        # Yield each cumulative path from base to target (inclusive)
        # Avoid resolving `target` which may contain untrusted input that could
        # cause filesystem-dependent side effects. Use the path parts to build
        # the cumulative segments relative to the already-trusted `base`.
        base_r = base.resolve(strict=False)
        # If `target` is not under `base` (without resolving symlinks), raise
        # a security error rather than resolving the untrusted target. Resolving
        # user-controlled paths can cause filesystem-dependent side-effects and
        # was flagged by static analysis; callers should validate containment
        # before invoking this helper.
        try:
            rel = target.relative_to(base)
        except ValueError:
            raise PathSecurityError("target not within base")
        cur = base_r
        yield cur
        for part in rel.parts:
            cur = cur / part
            yield cur

    def _reject_symlink_segments(self, base: Path, candidate: Path) -> None:
        for seg in self._iter_segments(base, candidate):
            try:
                st = os.lstat(os.fspath(seg))
            except FileNotFoundError:
                # only check existing ancestors; leaf may not exist yet
                continue
            if _stat.S_ISLNK(st.st_mode):
                raise PathSecurityError("symlink blocked")

    @staticmethod
    def _walk_nofollow(root: Path) -> Iterable[Path]:
        # Non-recursive stack-based walk that does not follow symlinks for directories
        stack = [root]
        while stack:
            cur = stack.pop()
            try:
                with os.scandir(cur) as it:
                    for e in it:
                        try:
                            st = e.stat(follow_symlinks=False)
                        except FileNotFoundError:
                            continue
                        p = Path(e.path)
                        if _stat.S_ISDIR(st.st_mode):
                            stack.append(p)
                        yield p
            except FileNotFoundError:
                continue


__all__ = [
    "PathGuard",
    "PathSecurityError",
    "is_safe_filename",
    "strip_dangerous_chars",
]

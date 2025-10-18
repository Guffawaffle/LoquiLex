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
from ._types import CanonicalPath
from .path_sanitizer import (
    PathInputError,
    PathSecurityError as _PathSecurityError,
    normalize_filename,
    sanitize_path_string,
)


# Re-export PathSecurityError to maintain backward compatibility
class PathSecurityError(_PathSecurityError):
    """Raised when a path violates configured safety constraints."""


@dataclass(frozen=True)
class _RootPolicy:
    allow_hidden: bool = False
    allowed_exts: tuple[str, ...] = ()
    name_pattern: re.Pattern[str] | None = None


def _is_reserved_windows_name(name: str) -> bool:
    """Check if filename is a reserved Windows device name.

    DEPRECATED: Use normalize_filename() from path_sanitizer instead.
    This is kept for backward compatibility.
    """
    try:
        normalize_filename(name, allow_hidden=True, forbid_reserved=True)
        return False
    except PathInputError as e:
        return "reserved filename" in str(e)


def strip_dangerous_chars(name: str) -> str:
    """Strip NUL/control chars and normalize Unicode to NFC; remove separators and trim.

    DEPRECATED: Use normalize_filename() from path_sanitizer instead.
    This function is kept for backward compatibility but may return "untitled"
    for irrecoverable inputs.

    - Removes ``\x00`` and other C0 controls
    - Normalizes Unicode to NFC to reduce confusables
    - Removes path separators ``/`` and ``\\`` (intended for filenames, not paths)
    - Trims trailing dots/spaces (Windows compatibility)
    """
    if not isinstance(name, str):
        name = str(name)

    try:
        # Use sanitizer with permissive settings
        return normalize_filename(name, allow_hidden=True, forbid_reserved=False, max_length=255)
    except PathInputError:
        # Fallback for irrecoverable inputs
        return "untitled"


def is_safe_filename(name: str, *, max_length: int = 255) -> bool:
    """Return True if ``name`` matches strict filename policy.

    Updated to use sanitizer and default to 255 character limit for consistency.
    Policy: NFC-normalized, no control chars, not hidden, not reserved Windows names.
    """
    try:
        normalized = normalize_filename(
            name,
            max_length=max_length,
            allow_hidden=False,
            forbid_reserved=True,
        )
        # Additional legacy pattern check for strict compatibility
        return bool(re.fullmatch(r"[A-Za-z0-9._-]+", normalized))
    except PathInputError:
        return False


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

    # --- New minimal helpers (no behavior change) ---

    # Conservative, single-segment filename policy.
    # Keep local to PathGuard to avoid cross-module imports/regex drift.
    _FILENAME_RE = re.compile(r"^[A-Za-z0-9._-]{1,255}$")

    def canonicalize_leaf(self, name: str) -> str:
        """
        Validate a single leaf filename (no path separators).
        Raises ValueError/TypeError on invalid input. Does not touch the filesystem.
        """
        if not isinstance(name, str):
            raise TypeError("name must be str")
        # reject empties, absolute hints, parent jumps, and path separators
        if not name:
            raise ValueError("empty name")
        if name.startswith(("/", "\\")):
            raise ValueError("absolute or drive-like paths are not permitted")
        if name.startswith("."):
            raise ValueError("hidden or relative dot-segments not allowed")
        if "/" in name or "\\" in name:
            raise ValueError("leaf must be a single segment (no slashes)")
        if name in (".", ".."):
            raise ValueError("reserved path segment")
        if not self._FILENAME_RE.fullmatch(name):
            raise ValueError("invalid filename")
        return name

    def safe_join(self, root_name: str, leaf: str) -> CanonicalPath:
        """
        Join a validated leaf to a configured root **using existing guard rules**.
        This calls the current PathGuard.resolve(...) to avoid behavior changes today.
        Returns a CanonicalPath wrapper for downstream FS calls.
        """
        leaf = self.canonicalize_leaf(leaf)
        # Delegate to your existing resolve logic (non-resolving unless explicitly allowed).
        # If your resolve signature differs, adapt accordingly.
        p = self.resolve(root_name, leaf)
        return CanonicalPath(p)

    def open_read_cp(self, cp: CanonicalPath):
        """
        Read-only open for a CanonicalPath. Delegates to existing open_read().
        """
        return self.open_read(cp.as_path())

    def open_write_cp(
        self, cp: CanonicalPath, *, overwrite: bool = False, binary: bool = True
    ) -> BinaryIO | TextIO:
        """
        Write open for a CanonicalPath. Delegates to existing open_write().
        """
        # Use literals so mypy can pick the correct overload
        if binary:
            return self.open_write(cp.as_path(), overwrite=overwrite, binary=True)
        else:
            return self.open_write(cp.as_path(), overwrite=overwrite, binary=False)

    def ensure_dir_cp(self, cp: CanonicalPath):
        """
        Ensure parent directory exists for a CanonicalPath. Delegates to existing ensure_dir().
        """
        self.ensure_dir(cp.as_path().parent)

    def disk_usage_cp(self, cp: CanonicalPath):
        """
        shutil.disk_usage wrapper for CanonicalPath. Delegates to existing behavior.
        """
        # If you already wrap disk_usage elsewhere, call that instead.
        import shutil as _shutil

        return _shutil.disk_usage(str(cp))

    def wrap_absolute(self, abs_path: str | Path) -> CanonicalPath:
        """
        Accept a caller-provided absolute path and return a CanonicalPath
        **only if** it is lexically within a configured root.
        - No resolve() on user input.
        - Enforces existing symlink policy on ancestors when follow_symlinks is False.
        """
        p = Path(str(abs_path))
        if not p.is_absolute():
            raise PathSecurityError("expected absolute path")
        base = self._find_base_for(p)
        if base is None or not self._is_within_root(base, p):
            raise PathSecurityError("absolute path outside allowed roots")
        if not self._follow_symlinks:
            self._reject_symlink_segments(base, p)
        return CanonicalPath(p)

    # ---------- Core resolution ----------
    def resolve(self, root: str, user_path: str | Path) -> Path:
        """Resolve a user-supplied path under a named root and return absolute path.

        Steps:
        - Use path_sanitizer for validation and normalization
        - Join with base root, resolve with ``strict=False``
        - Verify path stays within the same root
        - Enforce symlink policy
        - Enforce per-root filename policy for leaf component
        """

        base = self._get_root(root)

        # REFACTORED: Use path_sanitizer for validation, but handle traversal manually
        # to preserve original PathGuard semantics
        try:
            # First, manually normalize and handle traversal on the raw input
            # This preserves the original behavior that allowed non-escaping patterns like dir/..

            # Now manually parse and normalize path components
            raw_normalized = unicodedata.normalize("NFC", str(user_path))

            # Basic character validation (reuse sanitizer's logic but manually)
            if re.search(r"[\x00-\x1F\x7F]", raw_normalized):
                raise PathSecurityError("control characters not permitted in path")
            if raw_normalized.startswith("~"):
                raise PathSecurityError("tilde expansion is not permitted")
            if raw_normalized.startswith("/"):
                raise PathSecurityError("absolute paths are not permitted")
            if raw_normalized.startswith("\\\\"):
                raise PathSecurityError("UNC paths are not permitted")
            if re.match(r"^[A-Za-z]:[/\\]", raw_normalized):
                raise PathSecurityError("drive-prefixed paths are not permitted")

            # Reject various traversal-ish encodings and Windows-style backslashes
            # which tests treat as suspicious input (e.g., "dir\\..\\file" or
            # percent-encoded sequences like "%2e%2e"). This preserves the
            # stricter historical behavior of rejecting traversal-like strings
            # even if they could be normalized into safe components.
            lower = raw_normalized.lower()
            if "\\" in raw_normalized or "%2e" in lower:
                raise PathSecurityError("path traversal blocked")

            # Parse components manually without losing ".." information
            raw_components = re.split(r"[/\\]+", raw_normalized)

            # Check for suspicious patterns: reject any path that has .. followed by more components
            # Removed flawed traversal detection logic; rely on stack-based resolution below.
            stack: list[str] = []  # Simulate the path stack

            for component in raw_components:
                if not component or component == ".":
                    continue  # Skip empty and current directory
                elif component == "..":
                    if stack:
                        # We can go up because we have something in the stack
                        stack.pop()
                    else:
                        # This would escape above the root - reject it
                        raise PathSecurityError("path traversal blocked")
                else:
                    # Regular component - validate it as a filename and add to stack
                    normalized_component = normalize_filename(
                        component,
                        allow_hidden=True,  # Allow hidden for now, policy applied later
                        forbid_reserved=True,
                        max_length=255,
                    )
                    stack.append(normalized_component)

            components = stack

        except (PathInputError, _PathSecurityError) as e:
            # Convert all sanitizer exceptions to PathGuard's PathSecurityError for compatibility
            raise PathSecurityError(str(e)) from e

        # Join with base root
        if not components:
            candidate = base
        else:
            candidate = base.joinpath(*components)

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
        # Final canonicalization: ensure resolved_dir (with symlinks resolved) stays within the canonical base
        canonical_base = base.resolve()
        canonical_target = resolved_dir.resolve(strict=False)
        try:
            canonical_target.relative_to(canonical_base)
        except ValueError:
            raise PathSecurityError("directory outside allowed roots (canonical check)")
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

    @staticmethod
    def _sanitize_path_input(raw: str) -> str:
        """Validate raw user input before any filesystem interpretation.

        REFACTORED: Now delegates to path_sanitizer for consistency.
        """
        try:
            # Convert all sanitizer exceptions to PathSecurityError for backward compatibility
            # For storage candidate validation we allow absolute paths (caller will
            # perform absolute checks). The sanitizer default forbids absolute
            # forms which would cause callers that expect to accept absolute
            # candidates to fail early with a misleading message. Pass
            # forbid_absolute=False here to permit absolute inputs and preserve
            # the original PathGuard behavior.
            return sanitize_path_string(raw, forbid_absolute=False)
        except (PathInputError, _PathSecurityError) as e:
            raise PathSecurityError(str(e)) from e

    @staticmethod
    def validate_storage_candidate(p: str | Path) -> Path:
        """Validate a user-chosen absolute directory for storage bootstrap."""
        if not p:
            raise PathSecurityError("empty path")

        try:
            raw_input = os.fspath(p)
        except TypeError as exc:
            raise PathSecurityError("path input must be path-like") from exc
        # If the caller provided a string that is not absolute, reject early
        # with the historically expected message "not absolute". This keeps
        # user-facing error strings stable for callers that pass relative
        # strings (e.g., UI form validation). Path objects that are absolute
        # will be permitted to proceed to sanitization.
        if isinstance(raw_input, str):
            # Windows drive letter or UNC or Unix absolute start
            if not (
                raw_input.startswith("/")
                or raw_input.startswith("\\\\")
                or re.match(r"^[A-Za-z]:[/\\]", raw_input)
            ):
                raise PathSecurityError("not absolute")

        # CodeQL: ensure sanitization precedes any Path/expanduser usage.
        safe_input = PathGuard._sanitize_path_input(raw_input)
        candidate = Path(safe_input).expanduser()
        if not candidate.is_absolute():
            raise PathSecurityError("not absolute")

        try:
            resolved = candidate.resolve(strict=False)
        except (OSError, ValueError) as exc:
            raise PathSecurityError("invalid path") from exc

        if not resolved.is_absolute():
            raise PathSecurityError("resolved path not absolute")

        # Explicit system roots to reject. Do not include root ('/') here
        # because every absolute path is under '/' and would cause spurious
        # rejections (previous behavior bug). Check only the usual system
        # directories which are considered unsafe for user storage.
        forbidden_roots = [
            Path("/proc"),
            Path("/sys"),
            Path("/dev"),
            Path("/run"),
            Path("/etc"),
            Path("/boot"),
            Path("/var/lib/docker"),
            Path("/usr"),
            Path("/bin"),
            Path("/sbin"),
            Path("/lib"),
            Path("/lib64"),
            Path("/root"),
        ]

        for forbidden in forbidden_roots:
            try:
                if resolved == forbidden:
                    raise PathSecurityError("system path not permitted")
                resolved.relative_to(forbidden)
            except ValueError:
                continue
            else:
                raise PathSecurityError("system path not permitted")

        # Special-case explicit root path '/' which we treat as a forbidden
        # system path for storage bootstrap attempts.
        if str(resolved) == "/":
            raise PathSecurityError("system path not permitted")

        # Additional robust check for system paths using string prefixes to
        # ensure entries like '/proc', '/sys', '/dev' and their subtrees are
        # rejected even if prior relative_to checks miss them due to symlinks
        # or platform resolution differences.
        system_paths = ["/", "/proc", "/sys", "/dev", "/run", "/etc", "/boot", "/root"]
        for sp in system_paths:
            if sp == "/":
                continue
            if str(resolved) == sp or str(resolved).startswith(sp + os.sep):
                raise PathSecurityError("system path not permitted")

        if not resolved.exists():
            parent = resolved.parent
            if not parent.exists():
                raise PathSecurityError("parent directory does not exist")
            if not os.access(parent, os.W_OK):
                raise PathSecurityError("parent directory not writable")
        elif resolved.is_file():
            raise PathSecurityError("path is a file, not a directory")
        elif not os.access(resolved, os.W_OK):
            raise PathSecurityError("directory not writable")

        return resolved

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

    def _iter_segments(self, base: Path, target: Path) -> Iterable[Path]:
        # Yield each cumulative path from base to target (inclusive)
        # Avoid resolving `target` which may contain untrusted input that could
        # cause filesystem-dependent side effects. Use the path parts to build
        # the cumulative segments relative to the already-trusted `base`.
        # Validate that base is a trusted root before resolving.
        if base not in self._roots.values():
            raise PathSecurityError("base path is not a trusted root")
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

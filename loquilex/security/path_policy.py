"""Filesystem path policy enforcement for LoquiLex.

This module provides filesystem-level policy enforcement that composes the
pure string sanitization from path_sanitizer with runtime checks for root
containment and safe file operations.

Key classes:
- PathPolicyConfig: Configuration for allowed filesystem roots
- PathPolicy: Runtime policy enforcement with safe operations

This module handles filesystem I/O and policy enforcement while delegating
all string normalization and validation to the path_sanitizer module.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Tuple

from .path_sanitizer import (
    PathSecurityError,
    sanitize_path_string,
    split_and_validate_components,
)


@dataclass(frozen=True)
class PathPolicyConfig:
    """Configuration for path policy enforcement.

    Args:
        allowed_roots: Tuple of absolute Path objects that serve as allowed roots
                      for user-provided paths. All resolved paths must be contained
                      within one of these roots.
    """

    allowed_roots: Tuple[Path, ...] = ()


class PathPolicy:
    """Filesystem path policy enforcement with root containment.

    This class handles runtime policy enforcement for filesystem operations,
    ensuring that all resolved paths remain within configured allowed roots.
    It composes the path_sanitizer for string validation and adds filesystem-
    level checks.

    Args:
        config: PathPolicyConfig specifying allowed filesystem roots
    """

    def __init__(self, config: PathPolicyConfig) -> None:
        self.config = config
        # Validate that all roots are absolute paths at initialization
        for root in config.allowed_roots:
            if not root.is_absolute():
                raise ValueError(f"allowed root must be absolute: {root}")

    def resolve_under(self, root: Path | str, user_path: str) -> Path:
        """Resolve a user path under a specified root with safety checks.

        Args:
            root: Absolute path to the intended root directory, or string path
            user_path: User-provided relative path string

        Returns:
            Resolved absolute Path that is verified to be under the root

        Raises:
            PathInputError: If user_path is malformed
            PathSecurityError: If resolved path is outside allowed roots

        Process:
            1. Sanitize the user path string (delegates to path_sanitizer)
            2. Split into validated components
            3. Join with root and resolve with strict=False
            4. Verify containment within allowed roots
        """
        # Convert root to Path if needed
        root_path = Path(root) if isinstance(root, str) else root

        # Verify root is allowed
        if not root_path.is_absolute():
            raise PathSecurityError("root must be absolute")

        # Check if root is in our allowed list
        root_resolved = root_path.resolve()
        allowed = False
        for allowed_root in self.config.allowed_roots:
            try:
                # Check if our root is within any allowed root
                root_resolved.relative_to(allowed_root.resolve())
                allowed = True
                break
            except ValueError:
                try:
                    # Or if any allowed root is within our root
                    root_resolved.relative_to(allowed_root.resolve())
                    allowed = True
                    break
                except ValueError:
                    continue

        if not allowed:
            raise PathSecurityError("root not in allowed roots")

        # Step 1: Handle empty path case (resolves to root itself)
        if not user_path.strip():
            # Empty path resolves to root itself
            candidate = root_path
        else:
            # Sanitize the user path (no filesystem operations)
            sanitized = sanitize_path_string(user_path)

            # Step 2: Split into validated components
            components = split_and_validate_components(sanitized)

            # Step 3: Join with root
            if not components:
                candidate = root_path
            else:
                candidate = root_path.joinpath(*components)

        # Step 4: Resolve to handle any symlinks or relative components
        resolved = candidate.resolve(strict=False)

        # Step 5: Verify containment within allowed roots
        contained = False
        for allowed_root in self.config.allowed_roots:
            try:
                allowed_resolved = allowed_root.resolve()
                resolved.relative_to(allowed_resolved)
                contained = True
                break
            except ValueError:
                continue

        if not contained:
            raise PathSecurityError("resolved path outside allowed roots")

        return resolved

    def open_read_nofollow(self, path: Path):
        """Open a file for reading with O_NOFOLLOW protection.

        Args:
            path: Absolute path to open (should be from resolve_under)

        Returns:
            File object opened in binary read mode

        Raises:
            PathSecurityError: If path is outside allowed roots or is a symlink

        TODO: Implement full O_NOFOLLOW with platform-specific guards
        """
        # Verify path is within allowed roots
        self._verify_containment(path)

        # TODO: Implement proper O_NOFOLLOW handling
        # For now, just open normally - this is a placeholder for the full implementation
        return open(path, "rb")

    def open_write_atomic(self, path: Path):
        """Open a file for atomic writing.

        Args:
            path: Absolute path to write (should be from resolve_under)

        Returns:
            File object for writing

        Raises:
            PathSecurityError: If path is outside allowed roots

        TODO: Implement atomic writes with temp file + rename
        """
        # Verify path is within allowed roots
        self._verify_containment(path)

        # TODO: Implement atomic write pattern:
        # 1. Create temp file in same directory
        # 2. Write to temp file
        # 3. Atomic rename/move to final location
        # For now, just open normally
        return open(path, "wb")

    def ensure_dir(self, path: Path, mode: int = 0o700) -> None:
        """Ensure directory exists with restrictive permissions.

        Args:
            path: Directory path to create
            mode: Directory permissions (default 0o700 for security)

        Raises:
            PathSecurityError: If path is outside allowed roots
        """
        # Verify path is within allowed roots
        self._verify_containment(path)

        # Create directory with restrictive permissions
        path.mkdir(parents=True, exist_ok=True, mode=mode)

    def _verify_containment(self, path: Path) -> None:
        """Verify that a path is contained within allowed roots.

        Args:
            path: Path to verify

        Raises:
            PathSecurityError: If path is outside allowed roots
        """
        if not path.is_absolute():
            raise PathSecurityError("path must be absolute for containment check")

        path_resolved = path.resolve()

        for allowed_root in self.config.allowed_roots:
            try:
                allowed_resolved = allowed_root.resolve()
                path_resolved.relative_to(allowed_resolved)
                return  # Found a containing root
            except ValueError:
                continue

        raise PathSecurityError("path outside allowed roots")


__all__ = [
    "PathPolicyConfig",
    "PathPolicy",
]

"""Pure string/path normalization and sanitization for LoquiLex.

This module provides side-effect-free path validation and normalization functions
that can be used independently of filesystem operations. No filesystem I/O is
performed by any function in this module.

Key functions:
- normalize_filename: Sanitize single filename components
- sanitize_path_string: Validate and normalize multi-segment paths  
- split_and_validate_components: Split paths and validate each component

All functions use deterministic NFC Unicode normalization and provide
configurable policies for hidden files, reserved names, and length limits.
"""

from __future__ import annotations

import re
import unicodedata
from typing import List


class PathInputError(ValueError):
    """Raised when path input is malformed or contains invalid characters."""


class PathSecurityError(ValueError):
    """Raised when a path violates configured safety constraints."""


def _is_reserved_windows_name(name: str) -> bool:
    """Check if filename is a reserved Windows device name."""
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


def normalize_filename(
    name: str,
    *,
    max_length: int = 255,
    allow_hidden: bool = False,
    forbid_reserved: bool = True,
) -> str:
    """Normalize and validate a single filename component.

    Args:
        name: Raw filename to normalize
        max_length: Maximum allowed length (default 255)
        allow_hidden: Whether to allow filenames starting with '.' (default False)
        forbid_reserved: Whether to reject Windows reserved names (default True)

    Returns:
        Normalized filename string

    Raises:
        PathInputError: If filename is invalid or violates constraints

    Process:
        1. NFC Unicode normalization
        2. Strip C0 control characters and DEL
        3. Strip trailing spaces and dots
        4. Reject path separators
        5. Check hidden file policy
        6. Check reserved name policy
        7. Check length constraints
    """
    if not isinstance(name, str):
        raise PathInputError("filename must be a string")

    if not name:
        raise PathInputError("filename cannot be empty")

    # Step 1: NFC normalization
    normalized = unicodedata.normalize("NFC", name)

    # Step 2: Strip control characters (C0 controls + DEL)
    cleaned = re.sub(r"[\x00-\x1F\x7F]", "", normalized)

    # Step 3: Strip trailing spaces and dots (Windows compatibility)
    cleaned = cleaned.rstrip(" .")

    if not cleaned:
        raise PathInputError("filename is empty after normalization")

    # Step 4: Reject path separators
    if "/" in cleaned or "\\" in cleaned:
        raise PathInputError("filename cannot contain path separators")

    # Step 5: Check hidden file policy
    if cleaned.startswith(".") and not allow_hidden:
        raise PathInputError("hidden files not allowed")

    # Step 6: Check reserved name policy
    if forbid_reserved and _is_reserved_windows_name(cleaned):
        raise PathInputError(f"reserved filename: {cleaned}")

    # Step 7: Check length constraints
    if len(cleaned) > max_length:
        raise PathInputError(f"filename too long: {len(cleaned)} > {max_length}")

    return cleaned


def sanitize_path_string(
    raw: str,
    *,
    forbid_absolute: bool = True,
    forbid_tilde: bool = True,
    forbid_traversal: bool = True,
    collapse_separators: bool = True,
    max_components: int = 128,
    max_total_length: int = 4096,
) -> str:
    """Sanitize and validate a multi-segment path string.

    Args:
        raw: Raw path string to sanitize
        forbid_absolute: Reject absolute paths (default True)
        forbid_tilde: Reject tilde expansion (default True)
        forbid_traversal: Reject '..' traversal segments (default True)
        collapse_separators: Collapse multiple separators (default True)
        max_components: Maximum path components (default 128)
        max_total_length: Maximum total path length (default 4096)

    Returns:
        Sanitized path string

    Raises:
        PathInputError: If path is malformed
        PathSecurityError: If path violates security policy

    Process:
        1. NFC Unicode normalization
        2. Check for control characters (error if found - no silent rewriting)
        3. Apply absolute/tilde/UNC/drive policies
        4. Apply traversal policy
        5. Collapse separators if enabled
        6. Check component and length limits
    """
    if not isinstance(raw, str):
        raise PathInputError("path must be a string")

    if not raw:
        raise PathInputError("path cannot be empty")

    # Step 1: NFC normalization
    normalized = unicodedata.normalize("NFC", raw)

    # Step 2: Check for control characters (strict - no silent removal for paths)
    if "\x00" in normalized:
        raise PathInputError("NUL byte in path")

    if re.search(r"[\x00-\x1F\x7F]", normalized):
        raise PathInputError("control characters not permitted in path")

    candidate = normalized

    # Step 3: Apply absolute/tilde/UNC/drive policies
    if forbid_tilde and candidate.startswith("~"):
        raise PathSecurityError("tilde expansion is not permitted")

    if forbid_absolute:
        if candidate.startswith("/"):
            raise PathSecurityError("absolute paths are not permitted")
        if candidate.startswith("\\\\"):
            raise PathSecurityError("UNC paths are not permitted")
        if re.match(r"^[A-Za-z]:[/\\]", candidate):
            raise PathSecurityError("drive-prefixed paths are not permitted")

    # Step 4: Apply traversal policy
    if forbid_traversal and re.search(r"(^|[/\\])\.\.([/\\]|$)", candidate):
        raise PathSecurityError("path traversal not permitted")

    # Step 5: Collapse separators if enabled
    if collapse_separators:
        # First check for excessive separators before collapsing
        if re.search(r"[/\\]{3,}", candidate):
            raise PathSecurityError("excessive path separators detected")
        # Normalize separators to forward slashes and collapse
        candidate = re.sub(r"[/\\]+", "/", candidate)

    # Strip trailing spaces and dots
    candidate = candidate.rstrip(" .")

    if not candidate:
        raise PathInputError("path is empty after sanitization")

    # Step 6: Check component and length limits
    if len(candidate) > max_total_length:
        raise PathInputError(f"path too long: {len(candidate)} > {max_total_length}")

    # Count components for validation (after normalization to avoid inflated counts)
    components = [c for c in candidate.split("/") if c and c not in (".", "..")]
    if len(components) > max_components:
        raise PathInputError(f"too many path components: {len(components)} > {max_components}")

    return candidate


def split_and_validate_components(
    sanitized_path: str,
    *,
    allow_hidden: bool = False,
    max_length: int = 255,
    forbid_reserved: bool = True,
) -> List[str]:
    """Split a sanitized path into components and validate each one.

    Args:
        sanitized_path: Already sanitized path string
        allow_hidden: Allow hidden files (default False)
        max_length: Maximum component length (default 255)
        forbid_reserved: Forbid Windows reserved names (default True)

    Returns:
        List of validated path components

    Raises:
        PathInputError: If any component is invalid

    Process:
        1. Split on forward and back slashes
        2. Filter out empty, '.', and '..' components
        3. Validate each component with normalize_filename
    """
    if not isinstance(sanitized_path, str):
        raise PathInputError("path must be a string")

    if not sanitized_path:
        return []

    # Step 1: Split on separators
    raw_components = re.split(r"[/\\]+", sanitized_path)

    # Step 2: Filter invalid components
    components = []
    for component in raw_components:
        if not component or component in (".", ".."):
            continue
        components.append(component)

    # Step 3: Validate each component
    validated = []
    for component in components:
        try:
            normalized = normalize_filename(
                component,
                max_length=max_length,
                allow_hidden=allow_hidden,
                forbid_reserved=forbid_reserved,
            )
            validated.append(normalized)
        except PathInputError as e:
            raise PathInputError(f"invalid path component '{component}': {e}") from e

    return validated


__all__ = [
    "PathInputError",
    "PathSecurityError",
    "normalize_filename",
    "sanitize_path_string",
    "split_and_validate_components",
]

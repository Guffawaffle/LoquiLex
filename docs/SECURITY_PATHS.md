# Filesystem Path Security

This document captures LoquiLex's filesystem path security model and the required usage patterns for any code handling user-influenced paths.

## Threat Model

- User-provided identifiers (e.g., session IDs, filenames, absolute paths from settings) must not cause file IO outside explicitly allowed roots.
- Directory traversal attempts (`..`, absolute injections), symlink escapes, and hidden/reserved filenames are blocked.
- Errors must not leak host filesystem paths; return stable, generic messages.

## PathGuard

`loquilex.security.PathGuard` is the single authority mediating any path derived from user input.

- Named roots: initialize with a mapping like `{ "sessions": OUT_ROOT, "profiles": PROFILES_ROOT }`.
- `resolve(root, user_path) -> Path`: Strict normalization; rejects absolute paths, traversal, and symlink escapes (by default). Applies per-root filename policy.
- `open_read(path)`, `open_write(path, overwrite=False, binary=True)`: Use `os.open` with `O_NOFOLLOW | O_CLOEXEC` and validate containment.
- `ensure_dir(path, mode=0o750)`: Create directories with restrictive permissions.
- Quotas: `compute_usage_bytes(root)`, `enforce_quota(root, max_bytes)` iterate with no-follow semantics.

Default roots:

- `sessions`: Output tree under `LX_OUT_DIR`.
- `exports`: `LX_OUT_DIR/exports`.
- `profiles`: `LX_OUT_DIR/profiles`.
- Additional absolute roots may be provided via `LX_ALLOWED_STORAGE_ROOTS` (colon-separated).

## Usage Guidelines

- Never call `open()` directly on user-influenced paths; instead:
  1) `safe = PATH_GUARD.resolve("sessions", user_fragment)`
  2) `PATH_GUARD.ensure_dir(safe.parent)` if writing
  3) `with PATH_GUARD.open_write(safe): ...`

- Only accept absolute paths in APIs that explicitly declare it (e.g., storage base directory). Validate via a helper like `_resolve_storage_dir()` that allows only locations contained in configured roots.

- Do not return host paths in errors; map `PathSecurityError` to `HTTP 400` with a generic message.

## Symlink Policy

- Default: `follow_symlinks=False` prohibits crossing symlinks during resolution and IO. If a root intentionally contains symlinks, set `follow_symlinks=True` only for that root and add tests.

## Filename Policy

- Hidden files (prefix `.`) are rejected.
- Basic safe filename characters: letters, numbers, `_`, `-`, `.`, with NFC normalization. Per-root extension allowlists may be added when needed.

## Quotas

- Use `compute_usage_bytes()` and `enforce_quota()` to bound storage consumption per root.

## Testing

- Unit tests in `tests/security/test_path_guard.py` cover traversal, absolute injection, hidden/invalid names, and non-escaping segments.
- Integration tests validate API behavior for storage info and base-directory selection.

## Extending Safely

- When introducing new endpoints or CLIs that accept a path or name:
  - Add a named root or reuse an existing one.
  - Route all resolution and IO through `PathGuard`.
  - Add tests for traversal/absolute/symlink cases.

# Path Sanitization Architecture

LoquiLex uses a layered approach to path security with clear separation of concerns:

## Architecture

### 1. PathSanitizer (`loquilex.security.path_sanitizer`)
**Pure string validation** - no filesystem I/O.

- `normalize_filename()` - Single component validation
- `sanitize_path_string()` - Multi-segment path validation
- `split_and_validate_components()` - Component parsing

**Features:**
- Deterministic NFC Unicode normalization
- Configurable policies (hidden files, reserved names, length limits)
- Windows reserved name detection (CON, PRN, AUX, NUL, COM1-9, LPT1-9)
- Control character and traversal attack prevention

### 2. PathPolicy (`loquilex.security.path_policy`)
**Filesystem policy enforcement** - composes sanitizer for validation.

- `PathPolicy.resolve_under()` - Safe path resolution within allowed roots
- Root containment verification
- Safe file operations (TODO: O_NOFOLLOW, atomic writes)

### 3. PathGuard (`loquilex.security.path_guard`)
**Legacy compatibility layer** - delegates to sanitizer while preserving existing API.

- Maintains backward compatibility for existing code
- Special handling for legacy traversal patterns (`dir/..` allowed, `dir/../file` rejected)
- Shim functions for `strip_dangerous_chars()`, `is_safe_filename()`

## Usage Guidelines

### New Code
Use the appropriate layer for your needs:

```python
# For simple filename validation
from loquilex.security.path_sanitizer import normalize_filename
filename = normalize_filename(user_input, max_length=255)

# For path policy enforcement
from loquilex.security.path_policy import PathPolicy, PathPolicyConfig
config = PathPolicyConfig(allowed_roots=(Path("/safe/root"),))
policy = PathPolicy(config)
safe_path = policy.resolve_under(root_path, user_path)

# For existing PathGuard code (works unchanged)
from loquilex.security import PathGuard
guard = PathGuard({"root": Path("/safe/root")})
resolved = guard.resolve("root", user_path)
```

### Migration Path
Existing code using PathGuard continues to work unchanged. Consider migrating to:
- PathSanitizer for pure validation needs
- PathPolicy for new filesystem policy enforcement

## Security Properties

- **No filesystem I/O in sanitizer** - deterministic, testable validation
- **Root containment** - all resolved paths verified within allowed roots
- **Unicode normalization** - consistent NFC handling prevents bypasses
- **Traversal prevention** - multiple layers of protection against `../` attacks
- **Windows compatibility** - reserved name and separator handling

## Testing

All modules have comprehensive test coverage:
- PathSanitizer: 31 tests covering edge cases, Unicode, limits
- PathPolicy: 27 tests covering root containment, integration
- PathGuard: 15 tests ensuring backward compatibility

Run security tests: `pytest tests/security/`

## Platform notes: Windows paths & TOCTOU

### Windows
- **Drive letters & separators:** Inputs may include `C:\` and `\`. Internally we normalize via `Path` APIs; callers should avoid mixing separators in user-facing strings.
- **Long paths:** Traditional MAX_PATH is ~260 chars. Modern Windows supports long paths with the `\\?\` prefix and policy/registry knobs. Our default **per-component** cap is 255 characters; the **total path** cap is configurable in `PathPolicyConfig`. When running on Windows, ensure long-path support is enabled if you need very deep directories.
- **Symlinks/Junctions:** Windows supports symlinks and directory junctions. Our policy treats both as potential escape vectors; containment checks are applied post-resolution. If `allow_follow_symlinks` is false, symlink/junction final components should be rejected.

### TOCTOU (Time-of-check vs. Time-of-use)
Filesystem checks and later use cannot be made perfectly atomic across all platforms and filesystems. We mitigate this by:
1. Canonicalizing and verifying containment (`commonpath`).
2. (Optional) Rejecting symlink final components on Unix using `O_NOFOLLOW` (with lstat fallback), which reduces race surface.
3. Encouraging callers to open files immediately after policy checks, using the same resolved path, and to re-apply critical invariants (e.g., re-check containment for follow-up operations).

If your integration requires stronger guarantees (e.g., write to directories controlled by untrusted users), prefer opening directories with `O_DIRECTORY | O_NOFOLLOW` (Unix) and using `openat`-style patterns where available.

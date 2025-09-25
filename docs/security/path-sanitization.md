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
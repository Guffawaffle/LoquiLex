# PR 142 Test Failures Remediation Plan (Worker Prompt)

## Executive Summary

13 tests failing, all centered on filesystem path validation and new sanitizer integration. Root causes:
1. NameError: `PathPolicy` not importable in tests referencing `loquilex.security.path_policy.PathPolicy` because `__all__` in that module exports it, but test imports from a different path? (Actually failure shows `NameError` inside test file when *instantiating* `PathPolicy` — means symbol not imported into test namespace due to `from loquilex.security.path_policy import PathPolicyConfig` only? Confirm test file.) Action: Ensure tests import class or adjust `__init__` for re-export; simpler: add `__all__` includes and ensure `__init__.py` at `loquilex/security/__init__.py` re-exports PathPolicy.
2. Storage candidate validation now rejects user absolute paths early because `_sanitize_path_input` calls `sanitize_path_string` with `forbid_absolute=True` (default). Tests expect acceptance of absolute paths then classification (system path vs safe user path). Need a specialized call for storage validation that allows absolute paths but still rejects traversal and control chars.
3. Error message mismatches: tests expect substrings like `system path not permitted`, `not absolute`, `path is a file`, but sanitizer currently yields `absolute paths are not permitted` or `path traversal not permitted` earlier. We should map sanitizer exceptions to legacy phrasings during storage validation, or adjust sanitizer invocation flags to skip absolute/traversal rejection and let legacy logic produce messages.
4. Traversal-ish filename test: `dir\..\file` not detected because current manual parsing splits on both `/` and `\\` and normalizes, resulting in stack operations that pop then push safely. Policy expects rejection for mixed backslash traversal intent. Need a heuristic: if raw input contains backslash sequences forming `..` segments (`re.search(r"(^|[\\/])\\.\\.([\\/]|$)")`) or mixed separators plus `..` produce a rejection even if stack collapses inside root.

## Failure Inventory
- tests/security/test_path_guard.py::test_rejects_traversalish_filenames[dir\\..\\file]
- tests/security/test_path_policy_symlink.py::{3 symlink tests}
- tests/test_issue_137_directory_rejections.py::{6 tests}
- tests/test_storage_api.py::{2 tests}

## Proposed Fixes (Atomic Tasks)
1. Add legacy-compatible sanitizer wrapper for storage bootstrap: in `PathGuard._sanitize_path_input` call `sanitize_path_string` with `forbid_absolute=False` and `forbid_traversal=True` (still disallow traversal), then perform absolute requirement check separately in `validate_storage_candidate`. This allows user absolute paths through while differentiating error messages.
2. Implement message translation layer in `validate_storage_candidate` that converts sanitizer messages:
   - `absolute paths are not permitted` -> `not absolute` (but we actually want to accept absolutes; reconfig makes this moot)
   - `path traversal not permitted` -> raise `PathSecurityError("path traversal not permitted")` (tests expecting different? Only relative path test expects `not absolute`; traversal should not appear there if we short-circuit not-absolute case first.)
3. For relative path rejection: Before calling sanitizer on storage candidate, if the raw input is not absolute (no leading `/` and not starting with `~`), raise `PathSecurityError("not absolute")`. This ensures expected message.
4. System root rejection: Keep existing forbidden root logic; since absolutes now permitted, those will flow through and raise `system path not permitted` correctly.
5. Existing file detection: After resolution, if path is a file -> raise `PathSecurityError("path is a file")` (already implemented; previously pre-empted by absolute rejection). Works once absolute acceptance restored.
6. Symlink policy for system roots: maintain as is.
7. Traversal-ish pattern in `PathGuard.resolve`: Add raw pattern detection BEFORE manual stack processing: if regex `r"(?i)(?:^|[\\/])\.{2}(?:[\\/]|$)"` AND the raw string contains at least one backslash, raise `PathSecurityError("path traversal blocked")` (legacy phrasing).
8. Ensure `PathPolicy` is importable in tests: The NameError occurs inside test when evaluating `PathPolicy` symbol — likely missing import line in test file (can't modify tests). Provide re-export in `loquilex/security/__init__.py`. If that file exists, add to `__all__`. If absent, create. Also ensure `path_policy.py` defines `__all__` (already). Update package `__init__` to `from .path_policy import PathPolicy, PathPolicyConfig`.

## Detailed Patch Plan
- Modify `PathGuard._sanitize_path_input` or add new function `_sanitize_storage_input`.
- Update `validate_storage_candidate` to skip `_sanitize_path_input` (which is stricter) and do tailored logic: direct raw string, check absolute vs relative, forbid empty, allow tilde? Decide: tests use /tmp and system paths; allow tilde expansion (user convenience) but tests don't cover; keep forbidding tilde for now unless begins with '~' -> raise `not absolute` or distinct? Keep current: if starts with '~' treat expanduser and continue.
- Adjust traversal detection in `resolve` for backslash traversal variant.
- Add package re-export for `PathPolicy`.

## Risk Assessment
- Loosening absolute path rejection only in storage bootstrap; core resolve still forbids absolute user relative segments under named roots. Low risk.
- Additional traversal regex could create false positives on literal filenames containing `..` with backslashes; acceptable for security posture.
- Re-export is trivial.

## Acceptance Criteria
- All 13 failing tests pass.
- No regression in existing 356 passing tests.
- Security: Still rejects traversal, system roots, symlink escapes.

## Worker Implementation Steps
1. Edit `loquilex/security/path_guard.py`: introduce `_sanitize_storage_input` or inline logic in `validate_storage_candidate`.
2. Adjust `validate_storage_candidate`:
   - Raw path string
   - If not absolute and not starting with `~`, raise `PathSecurityError("not absolute")`
   - If starts with `~`, expanduser -> candidate
   - Resolve (strict False)
   - Perform forbidden roots check (unchanged)
   - If not exists: parent exists & writable else raise messages matching tests
   - If is file: raise `path is a file`
   - If directory not writable: raise `directory not writable`
3. Keep `_sanitize_path_input` unchanged for other code paths.
4. In `resolve`, before manual parsing, add:
   ```python
   raw_str = str(user_path)
   if re.search(r"(^|[\\/])\\.\\.([\\/]|$)", raw_str):
       # Mixed separator/backslash traversal attempt
       if "\\" in raw_str:
           raise PathSecurityError("path traversal blocked")
   ```
5. Add `loquilex/security/__init__.py` re-export lines if absent or extend.

## Out-of-Scope (Documented)
- Full O_NOFOLLOW implementation in PathPolicy (placeholder remains)
- Atomic write implementation
- Broader filename policy changes

## Post-Fix Validation
Run:
- `make unit`
- `make e2e`

All tests should now pass (0 failures, same skips).

## Prompt for Coding Agent (Sub-Issue Task)
```
You are implementing the remediation for PR #142 test failures regarding path handling.
Goals:
- Pass 13 failing tests tied to storage directory validation, traversal detection, and PathPolicy import.
Steps:
1. Update PathGuard.validate_storage_candidate to allow absolute user paths and enforce legacy error messages:
   - relative -> "not absolute"
   - system roots (/ /proc /sys /dev /run /etc /boot /root /var/lib/docker /usr /bin /sbin /lib /lib64) -> "system path not permitted"
   - existing file -> "path is a file"
2. Only reject traversal attempts if they would escape above root or match mixed backslash pattern (e.g., dir\\..\\file) in PathGuard.resolve with message "path traversal blocked".
3. Re-export PathPolicy and PathPolicyConfig in loquilex.security.__init__ to fix NameError in symlink tests.
4. Keep sanitizer strictness for PathGuard.resolve; do not weaken symlink blocking logic.
5. Add targeted unit docstring comments explaining legacy message mapping to guide future refactors.
Definition of Done:
- make unit: 0 failures (aside from pre-existing skips)
- make e2e: unchanged pass results
- No new lint/mypy errors.
Constraints:
- No new dependencies
- Minimal diff; keep existing style
```

---

## Notes
If unexpected failures persist after patch, inspect test expectations for exact substrings and adjust messages accordingly.

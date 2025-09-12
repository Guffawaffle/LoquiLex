#task
Scan this repository for Python files that raise `E402: module level import not at top of file`.

#instructions
- For each file, move all imports (stdlib, third-party, then first-party) to the very top of the file, above any constants, functions, or runtime setup code.
- Preserve comments and docstrings in place at the very top, before imports.
- If an import must remain inside a function for lazy-loading, keep it there, but do not leave stray top-level imports below code.
- Use isort-style grouping:
  1. Standard library
  2. Third-party (e.g., numpy, sounddevice, torch)
  3. First-party (`loquilex.*`)
- Do not just silence the warning with `# noqa: E402`. Fix by reordering or relocating code.
- Apply Ruff’s `--fix` rules for `E402` and `I` (import sorting) across the repo.

#output
Generate diffs for each file that shows the corrected import order at the top.

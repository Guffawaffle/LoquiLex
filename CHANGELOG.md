# Changelog

## 0.1.0 – Rename to LoquiLex; LX_ env; GF_ fallback (deprecated)

- Renamed all code, tests, and docs from greenfield → loquilex
- Canonical environment prefix is now LX_*
- Legacy GF_* envs supported as silent fallback (one-time deprecation warning)
- All CLI entry points and scripts reference loquilex.cli.*
- Repo hygiene: .egg-info ignored, requirements and Makefile updated
- Added mapping table for GF_ → LX_ in README
- CI and test instructions updated
- GF_* envs will be removed in v0.3.0

# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Authoritative `PathGuard` with strict resolution, symlink protections, safe open helpers, and quota utilities
- CI: Bandit static analysis and grep guard workflow for unsafe path usage
- Documentation: `docs/SECURITY_PATHS.md` describing threat model and usage
- Migration guide for deprecated orchestration patterns: `docs/ORCHESTRATION_MIGRATION.md`

### Changed
- Legacy /events WebSocket alias is now dev-only and deprecated (use /ws instead)
- API server refactored to route session, profile, and storage paths through `PathGuard`

### Deprecated
- **`Session` class** (subprocess-based orchestration) - Use `StreamingSession` for in-process execution (#60)
- **`loquilex.cli.live_en_to_zh`** - CLI orchestrator deprecated in favor of TypeScript orchestration (#60)
- **`loquilex.cli.demo`** - CLI orchestrator deprecated in favor of TypeScript orchestration (#60)
- Migration path: Use JS-first architecture with TypeScript orchestrating Python executor services

### Fixed
- Blocked absolute/traversal path injections and hidden/reserved filename usage across API path flows

### Removed
- Removed features go here

## [0.1.0] - 2024-12-XX

### Added
- Initial release of LoquiLex
- Live EN→ZH captioning and translation
- WebSocket API for real-time streaming
- CLI tools for offline processing
- Local-first architecture with Whisper ASR and NLLB/M2M translation

### Changed
- Renamed all code, tests, and docs from greenfield → loquilex
- Canonical environment prefix is now LX_*
- All CLI entry points and scripts reference loquilex.cli.*
- Repo hygiene: .egg-info ignored, requirements and Makefile updated
- CI and test instructions updated

---

## Release Notes Process

### For Contributors
1. **Update CHANGELOG.md** with your changes before merging PRs
2. Use the [Unreleased] section for current development changes
3. Follow the format: `- Description of change (link to issue/PR)`
4. Group changes by type: Added, Changed, Fixed, Removed

### For Maintainers
1. **Before Release**: Move items from [Unreleased] to new version section
2. **Version Format**: Use Semantic Versioning (MAJOR.MINOR.PATCH)
3. **Date Format**: YYYY-MM-DD
4. **Tag Release**: `git tag v1.2.3 && git push --tags`
5. **Publish**: Build and upload to PyPI

### CHANGELOG Entry Template
```markdown
## [1.2.3] - 2024-12-31

### Added
- New feature description

### Changed
- Changed functionality description

### Fixed
- Bug fix description

### Removed
- Removed feature description
```

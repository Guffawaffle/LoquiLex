# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- New features go here

### Changed
- Changes in existing functionality go here

### Fixed
- Bug fixes go here

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

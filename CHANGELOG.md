# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Turkish language documentation support
- Comprehensive architecture documentation in `docs/internal-docs/`
- ADR (Architecture Decision Records) system
- VideoLivestream component for automated playlist generation
- Smart batch detection with regex pattern matching
- Hardware encoder auto-detection (NVENC, QSV, VAAPI)
- Background upload to Google Drive during batch processing
- Thread-safe batch queue with persistence
- TUI (Textual) interface for interactive management
- Continuous mode for VideoAutomation pipeline
- Statistics viewing for VideoAutomation

### Changed
- Improved error handling in audio validation
- Enhanced progress tracking during rendering
- Better codec selection algorithm with hardware acceleration priority
- Optimized concat list generation for long-duration videos
- Refactored batch system for better thread safety

### Fixed
- Audio looping duration calculation for edge cases
- Memory leaks in long-duration video concatenation
- FFmpeg progress parsing for different encoder outputs
- TUI rendering issues on small terminals
- Google Drive authentication token refresh

### Deprecated
- Legacy CLI wizard (use TUI instead)
- Old configuration format (use config.json)

### Removed
- Jamendo integration (use local music files)

### Security
- **CRITICAL**: Added comprehensive input validation and path security module (`video_renderer/security.py`)
- **CRITICAL**: Implemented secrets management system (`video_renderer/secrets.py`)
- **CRITICAL**: Added audit logging infrastructure (`video_renderer/audit.py`)
- Path traversal protection for all file operations
- Command injection prevention for FFmpeg commands
- Credential file validation with age and permission checks
- Atomic credential file writing (temp file + rename)
- Security event logging (file access, auth, violations)
- Updated .gitignore with secret and log file patterns
- Added security scanner scripts (bash + powershell)
- Security documentation in `docs/internal-docs/security/`

## [1.0.0] - 2024-01-XX

### Added
- Initial release of AutoVideo system
- Core video rendering with intro + loop concatenation
- Audio processing with looping and mixing
- Batch rendering support
- Google Drive integration
- YouTube upload automation
- Hardware acceleration support (NVENC, QSV, VAAPI)
- Smart resolution detection
- Duration options (presets, custom, random)
- Multi-codec support (AV1, H.264, H.265)
- TUI interface built with Textual
- Smart batch detection
- Session resume capability
- Comprehensive codec configuration

---

## Version History Summary

### Major Versions
- **1.0.0**: Initial stable release with core features

### Minor Versions
- Features, improvements, non-breaking changes

### Patch Versions
- Bug fixes, small improvements, documentation updates

---

## Release Notes Format

Each release includes:

1. **Version Number**: Following semantic versioning (MAJOR.MINOR.PATCH)
2. **Release Date**: YYYY-MM-DD format
3. **Sections**:
   - **Added**: New features
   - **Changed**: Changes to existing functionality
   - **Deprecated**: Features that will be removed in future releases
   - **Removed**: Features removed in this release
   - **Fixed**: Bug fixes
   - **Security**: Security-related changes

---

## Upgrade Guide

### From 0.x to 1.0

1. **Update dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

2. **Migrate configuration**:
   - Old config files are still supported
   - New features require updated config.json format

3. **Update imports**:
   - No breaking changes to public API

4. **Test your workflow**:
   - Run `python -m video_renderer --list-hw` to verify hardware detection
   - Test batch rendering with TUI

---

## Future Releases

### Planned for 1.1.0
- [ ] Web-based UI
- [ ] Docker containerization
- [ ] Enhanced codec support
- [ ] Plugin system foundation

### Planned for 2.0.0
- [ ] Distributed rendering
- [ ] Cloud rendering support
- [ ] Advanced audio processing
- [ ] Video effects and filters

---

**For more details, see the documentation in [docs/](docs/)**

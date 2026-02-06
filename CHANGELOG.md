# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.0] - 2025-02-06

### Added
- **Unified Render Mode System**: Single codebase with multiple render modes (standard, ramtest, ramdisk, high_vram)
- **Render Mode Selection**: `--mode` flag for selecting optimized render mode
- **Memory Tracking**: Optional memory usage tracking in ramtest mode
- **Rate Limiting**: Configurable rate limiting for memory-constrained systems
- **Enhanced GPU Configuration**: Per-mode GPU buffer optimization
- **Unified State Management**: Single state file format across all modes
- **Comprehensive Security Module**: Input validation, path security, credential management
- **Audit Logging**: Security event tracking for all operations
- **Error Reporting**: Centralized error reporting and logging
- **Credential Encryption**: At-rest encryption for stored credentials
- **File Permission Validation**: Automatic validation of credential file permissions
- **Sensitive Data Filtering**: Automatic masking of sensitive data in logs
- **OAuth State Parameter**: Enhanced OAuth security with state parameter
- **Stale Lock Cleanup**: Automatic cleanup of stale file locks
- **Enhanced Hardware Detection**: Improved timeout and string matching for encoder detection
- **GPU Fallback Chain**: Enhanced secondary fallback with better error reporting
- **Audio Silence Detection**: Automatic detection of silent segments in audio tracks
- **Audio Metadata Preservation**: Metadata preservation during audio processing
- **Mono Input Handling**: Improved handling of mono audio inputs
- **Audio Cache Invalidation**: Fixed cache invalidation for audio processing
- **Duration Calculation Error Handling**: Robust error handling for duration calculations
- **Large Concat List Optimization**: Optimized concat list generation for long-duration videos
- **FFmpeg Performance**: Optimized FFmpeg I/O performance and encoding parameters
- **Memory Management**: Enhanced memory management for batch queue operations
- **Thread Safety**: Improved thread-safety guarantees across all modules
- **Config Unification**: Unified configuration system with RenderModeConfig
- **TUI Hybrid Merge**: Unified TUI supporting all render modes
- **Comprehensive Documentation**: Complete user-facing and internal documentation

### Changed
- **TUI Architecture**: Unified TUI with mode selection screen
- **Config System**: Migrated from separate configs to unified RenderModeConfig
- **Import Paths**: Updated import paths for unified codebase
- **State File Format**: New state file format with auto-migration support
- **Hardware Detection**: Increased timeout from 3 to 5 seconds to reduce false negatives
- **GPU Buffer Configuration**: Per-mode GPU buffer optimization
- **Batch Queue**: Enhanced thread-safety and error recovery
- **Audio Processing**: Improved error handling and validation
- **Video Processing**: Fixed compatibility check logic
- **FFmpeg Integration**: Enhanced progress parsing and error handling
- **Security Module**: Comprehensive security improvements
- **Logging**: Centralized logging with sensitive data filtering
- **Error Reporting**: Centralized error reporting infrastructure

### Fixed
- **check_compatibility Logic Error**: Fixed result overwrite bug in video compatibility check
- **Progress Parsing Time Calculation**: Fixed time calculation in FFmpeg progress parser
- **FPS Parsing**: Fixed FPS parsing to use ALLOWED_FPS set
- **Codec Mapping**: Expanded codec mapping in _get_expected_codec_name
- **GPU Fallback Chain**: Enhanced GPU fallback with secondary fallback options
- **Hardware Encoder Detection**: Fixed timeout and improved string matching with word boundaries
- **VAAPI Device Path**: Added dynamic detection for VAAPI device path
- **Stale Lock Cleanup**: Fixed stale lock cleanup mechanism to prevent deadlock after crashes
- **SmartBatchDetector Patterns**: Added support for prefix patterns in auto-detection
- **Audio Mixing Amix Filter**: Fixed amix filter weights compatibility for different FFmpeg versions
- **Audio Cache Invalidation**: Fixed cache invalidation issue in audio processing
- **Duration Calculation**: Added robust error handling for duration calculations
- **Silence Detection**: Implemented silence detection for audio tracks
- **Metadata Preservation**: Implemented metadata preservation for audio files
- **Mono Input Handling**: Fixed mono input handling in audio processing
- **Google Drive Integration**: Improved error handling and added retry logic
- **YouTube Integration**: Added metadata validation and improved upload handling
- **FFmpeg Performance**: Optimized FFmpeg encoding parameters for better performance
- **I/O Performance**: Optimized I/O operations for better throughput
- **Memory Management**: Added memory management to BatchQueue
- **Thread Safety**: Enhanced thread-safety across all modules

### Deprecated
- **video_renderer_ramtest Module**: Use `--mode ramtest` flag instead
- **Legacy CLI Wizard**: Use TUI instead (`--tui`)
- **Old Config Format**: Migrate to new config format
- **Separate Ramtest Package**: Merged into main video_renderer package

### Security
- **CRITICAL**: Comprehensive input validation and path security module (`video_renderer/security.py`)
- **CRITICAL**: Secrets management system (`video_renderer/credential_crypto.py`)
- **CRITICAL**: Audit logging infrastructure (`video_renderer/audit.py`)
- **CRITICAL**: Error reporting system (`video_renderer/error_reporting.py`)
- **CRITICAL**: Centralized logging system (`video_renderer/logging.py`, `video_renderer/logging_config.py`)
- Path traversal protection for all file operations
- Command injection prevention for FFmpeg commands
- Credential file validation with age and permission checks
- Atomic credential file writing (temp file + rename)
- Security event logging (file access, auth, violations)
- Updated .gitignore with secret and log file patterns
- Sensitive data filtering in logs
- OAuth state parameter for enhanced security
- File permission validation
- Credential encryption at rest

### Performance
- **FFmpeg Optimization**: Optimized FFmpeg parameters for better encoding performance
- **I/O Optimization**: Optimized I/O operations for better throughput
- **Memory Optimization**: Added memory management to BatchQueue
- **GPU Buffer Optimization**: Per-mode GPU buffer configuration
- **Concat List Optimization**: Optimized concat list generation for long-duration videos
- **Hardware Detection Caching**: Added 5-minute cache for hardware detection results
- **Parallel Processing**: Optimized parallel processing for audio and video encoding

### Documentation
- **User Documentation**: Complete user-facing documentation
  - Installation Guide
  - Configuration Reference
  - Troubleshooting Guide
  - Migration Guide
  - Release Notes
- **API Documentation**: Complete API reference for all modules
- **Internal Documentation**: Comprehensive internal documentation
  - Architecture Analysis
  - Module Documentation
  - Development Guides
  - Security Documentation
  - ADRs (Architecture Decision Records)

### Testing
- **Test Suite**: Comprehensive test suite implementation
- **Thread Safety Tests**: Enhanced thread-safety testing
- **Integration Tests**: Full rendering pipeline tests
- **Security Tests**: Input validation and security testing
- **Performance Tests**: FFmpeg and audio processing performance tests

---

## [0.x] - Pre-Release

### Added
- Initial video rendering with intro + loop concatenation
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
- Turkish language documentation support
- ADR (Architecture Decision Records) system
- VideoLivestream component for automated playlist generation
- Smart batch detection with regex pattern matching
- Hardware encoder auto-detection
- Background upload to Google Drive during batch processing
- Thread-safe batch queue with persistence
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

### Removed
- Jamendo integration (use local music files)

---

## Version History Summary

### Major Versions
- **1.0.0**: Initial stable production release with unified render mode system

### Minor Versions
- Features, improvements, non-breaking changes

### Patch Versions
- Bug fixes, small improvements, documentation updates

---

## Upgrade Guide

### From 0.x to 1.0.0

See [MIGRATION.md](docs/MIGRATION.md) for detailed upgrade instructions.

**Quick steps:**

1. **Update dependencies**:
   ```bash
   pip install --upgrade -r requirements.txt
   ```

2. **Migrate configuration**:
   ```bash
   python -m video_renderer --migrate-config
   ```

3. **Update imports** (if using as library):
   ```python
   # Old
   from video_renderer_ramtest.config import RamTestConfig

   # New
   from video_renderer.config import get_render_config
   config = get_render_config("ramtest")
   ```

4. **Update scripts**:
   ```bash
   # Old
   python -m video_renderer_ramtest.app

   # New
   python -m video_renderer --tui --mode ramtest
   ```

5. **Test your workflow**:
   ```bash
   python -m video_renderer --health-check
   python -m video_renderer --list-hw
   ```

---

## Future Releases

### Planned for 1.1.0
- [ ] Windows RAM disk support
- [ ] Automatic high-VRAM detection
- [ ] Memory pressure warnings
- [ ] Web-based UI (beta)
- [ ] Enhanced codec support
- [ ] Plugin system foundation

### Planned for 2.0.0
- [ ] Distributed rendering
- [ ] Cloud rendering support
- [ ] Advanced audio processing
- [ ] Video effects and filters
- [ ] Plugin system

---

**For more details, see the documentation in [docs/](docs/)**

**Last Updated:** 2025-02-06
**Version:** 1.0.0

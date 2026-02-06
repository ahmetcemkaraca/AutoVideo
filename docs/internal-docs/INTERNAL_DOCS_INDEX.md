# Internal Documentation Index

Welcome to the AutoVideo internal documentation. This section contains documentation for developers working on the AutoVideo codebase.

---

## Table of Contents

- [Architecture](#architecture)
- [Development Guides](#development-guides)
- [Modules](#modules)
- [Security](#security)
- [Research & Analysis](#research--analysis)
- [Quality Assurance](#quality-assurance)

---

## Architecture

### System Architecture

- **[ARCHITECTURE_ANALYSIS_REPORT.md](architecture/ARCHITECTURE_ANALYSIS_REPORT.md)**
  - Complete system architecture analysis
  - Module dependencies and relationships
  - Design patterns and architectural decisions

- **[LEAD_ARCHITECT_ANALYSIS.md](architecture/LEAD_ARCHITECT_ANALYSIS.md)**
  - Lead architect's analysis and recommendations
  - Technical debt assessment
  - Refactoring priorities

- **[SYSTEM_DESIGN.md](architecture/system-design.md)**
  - High-level system design
  - Component interaction diagrams
  - Data flow architecture

- **[overview.md](architecture/overview.md)**
  - Quick overview of system architecture
  - Key components and their roles

### Data Flow

- **[DATA_FLOW.md](architecture/DATA_FLOW.md)** (TODO)
  - Detailed data flow diagrams
  - State management flow
  - Error handling flow

### Module Dependencies

- **[MODULE_DEPENDENCIES.md](architecture/MODULE_DEPENDENCIES.md)** (TODO)
  - Complete dependency graph
  - Import analysis
  - Circular dependency detection

---

## Development Guides

### Coding Standards

- **[CODING_STANDARDS.md](guides/CODING_STANDARDS.md)** (TODO)
  - Code style guide
  - Naming conventions
  - Documentation standards
  - Best practices

### Testing Guide

- **[TESTING_GUIDE.md](guides/testing-guide.md)**
  - Testing strategy and coverage goals
  - Unit testing guidelines
  - Integration testing guidelines
  - Test organization

### Debugging Guide

- **[DEBUGGING_GUIDE.md](guides/DEBUGGING_GUIDE.md)** (TODO)
  - Common debugging techniques
  - Tool recommendations
  - Troubleshooting procedures

### Contributing Guide

- **[contributing-guide.md](guides/contributing-guide.md)**
  - Contribution workflow
  - Pull request guidelines
  - Code review process

---

## Modules

### Core Modules

- **[batch_system.md](modules/batch_system.md)**
  - Batch queue architecture
  - Thread-safety implementation
  - Job lifecycle management

- **[ramtest_integration.md](modules/ramtest_integration.md)**
  - Ramtest mode integration
  - Memory tracking implementation
  - Performance optimization strategies

### Video Processing

- **[VIDEO_ENCODER.md](modules/VIDEO_ENCODER.md)** (TODO)
  - Video encoder internals
  - Codec configuration
  - Hardware acceleration

- **[AUDIO_PROCESSOR.md](modules/AUDIO_PROCESSOR.md)** (TODO)
  - Audio processing pipeline
  - Mixing and looping logic
  - Format conversion

### Validation System

- **[validation/architecture.md](validation/architecture.md)**
  - Validation module architecture
  - API reference for validators
  - Integration points
  - Extending validation checks

- **[validation/troubleshooting.md](validation/troubleshooting.md)**
  - Common validation errors and solutions
  - Platform-specific issues
  - FFmpeg/ffprobe requirements
  - Debugging validation failures

### Batch Queue

- **[batchqueue-thread-safety.md](batchqueue-thread-safety.md)**
  - Thread-safety implementation
  - Lock management
  - Concurrent operations

- **[batchqueue-refactor-summary.md](batchqueue-refactor-summary.md)**
  - Refactoring summary
  - Performance improvements
  - API changes

- **[batchqueue-before-after-comparison.md](batchqueue-before-after-comparison.md)**
  - Before/after comparison
  - Migration guide
  - Breaking changes

---

## Security

### Security Documentation

- **[SECURITY_HARDENING_REPORT.md](security/SECURITY_HARDENING_REPORT.md)**
  - Complete security hardening report
  - Vulnerability assessments
  - Security improvements implemented

- **[SECURITY_API_REFERENCE.md](security/SECURITY_API_REFERENCE.md)**
  - Security module API reference
  - Input validation functions
  - Security utilities

- **[SECURITY_USAGE_GUIDE.md](security/SECURITY_USAGE_GUIDE.md)**
  - Security usage guide
  - Best practices
  - Configuration examples

### Error Handling

- **[error-handling-guide.md](error-handling-guide.md)**
  - Error handling strategy
  - Exception hierarchy
  - Error reporting guidelines

---

## Research & Analysis

### Codebase Analysis

- **[codebase_analysis_report.md](research/codebase_analysis_report.md)**
  - Complete codebase analysis
  - Module inventory
  - Dependency mapping

### Performance Analysis

- **[performance_optimization_summary.md](../performance_optimization_summary.md)**
  - Performance optimization summary
  - Bottleneck identification
  - Optimization strategies

### Comparisons

- **[comparison_ramtest.md](comparison_ramtest.md)**
  - Ramtest vs standard mode comparison
  - Performance benchmarks
  - Use case recommendations

---

## Quality Assurance

### Test Analysis

- **[test-analysis-report.md](qa/test-analysis-report.md)**
  - Test coverage analysis
  - Test suite evaluation
  - Recommendations

### Production Readiness

- **[production_readiness_summary.md](production_readiness_summary.md)**
  - Production readiness assessment
  - Deployment checklist
  - Monitoring requirements

---

## Architecture Decision Records (ADRs)

Located in [`../adr/`](../adr/):

- **ADR-001:** Video Renderer Ramtest Merge
- **ADR-002:** Thread Safety Strategy
- **ADR-003:** Logging Architecture
- **ADR-004:** Config Management
- **ADR-005:** Test Framework Selection

---

## Quick Reference

### Key Files by Purpose

**Configuration:**
- `video_renderer/config.py` - Codec and render configuration

**Core Processing:**
- `video_renderer/video.py` - Video encoding and validation
- `video_renderer/audio.py` - Audio processing and validation
- `video_renderer/ffmpeg.py` - FFmpeg execution and probing

**Batch Processing:**
- `video_renderer/batch.py` - Batch queue management

**User Interface:**
- `video_renderer/app.py` - TUI application
- `video_renderer/screens/` - TUI screens

**Security:**
- `video_renderer/security.py` - Input validation
- `video_renderer/credential_crypto.py` - Credential management
- `video_renderer/audit.py` - Audit logging

**Validation:**
- `video_renderer/video.py` - VideoEncoder.check_compatibility()
- `video_renderer/audio.py` - AudioProcessor.validate_and_convert_track()
- `config/validation.py` - Config validation and JSON schemas
- `VideoAutomation/automation/validation.py` - Production readiness checks

**Logging:**
- `video_renderer/logging.py` - Logging utilities
- `video_renderer/logging_config.py` - Logging configuration
- `video_renderer/error_reporting.py` - Error reporting

### Important Patterns

**Render Mode Configuration:**
```python
from video_renderer.config import get_render_config

config = get_render_config("ramtest")
# Returns RenderModeConfig with mode-specific settings
```

**Security Validation:**
```python
from video_renderer.security import validate_path

safe_path = validate_path(user_input, base_dir=Path.cwd())
# Raises SecurityError if unsafe
```

**Audit Logging:**
```python
from video_renderer.audit import log_security_event

log_security_event("FILE_ACCESS", {"file": "video.mp4"})
```

**Video Validation:**
```python
from video_renderer.video import VideoEncoder
from video_renderer.ffmpeg import FFmpegRunner

runner = FFmpegRunner()
encoder = VideoEncoder(runner, codec_config, width=1920, height=1080)
is_compat, reason = encoder.check_compatibility(Path("video.mp4"))
if not is_compat:
    print(f"Incompatible: {reason}")
```

**Audio Validation:**
```python
from video_renderer.audio import AudioProcessor

processor = AudioProcessor(runner, tmp_dir)
valid, invalid = processor.validate_tracks(tracks, parallel=True)
```

---

## Development Workflow

### Setting Up Development Environment

1. **Clone repository:**
   ```bash
   git clone <repository>
   cd Video
   ```

2. **Create virtual environment:**
   ```bash
   python -m venv venv
   source venv/bin/activate  # Windows: venv\Scripts\activate
   ```

3. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   pip install -e ".[dev]"
   ```

4. **Run tests:**
   ```bash
   pytest
   ```

### Making Changes

1. **Create feature branch:**
   ```bash
   git checkout -b feature/your-feature
   ```

2. **Make changes and test:**
   ```bash
   pytest
   ```

3. **Update documentation:**
   - Update relevant internal docs
   - Add/update ADR if needed
   - Update CHANGELOG.md

4. **Create pull request:**
   - Describe changes
   - Reference related issues
   - Include testing summary

---

## Common Tasks

### Adding a New Render Mode

1. Update `video_renderer/config.py`:
   ```python
   @dataclass
   class RenderModeConfig:
       mode: str = "new_mode"
       # Add mode-specific settings
   ```

2. Update `get_render_config()` factory:
   ```python
   configs = {
       "new_mode": RenderModeConfig(mode="new_mode", ...)
   }
   ```

3. Update TUI mode selection screen
4. Add tests for new mode
5. Update documentation

### Adding a New Codec

1. Add codec config to `video_renderer/config.py`:
   ```python
   CODEC_NEW = CodecConfig(
       name="New Codec",
       encoder="libnew",
       preset="medium",
       crf=20
   )
   ```

2. Add to CODECS registry:
   ```python
   CODECS = {
       "new": CODEC_NEW,
       ...
   }
   ```

3. Update `get_best_encoder()` if hardware variant exists
4. Add tests
5. Update documentation

### Adding Security Validation

1. Add validation function to `video_renderer/security.py`:
   ```python
   def validate_custom_input(input: str) -> bool:
       # Validation logic
       pass
   ```

2. Add audit logging:
   ```python
   log_security_event("CUSTOM_VALIDATION", {...})
   ```

3. Add tests
4. Update security documentation

---

## Getting Help

### Internal Resources

- **Team Lead:** Review with lead architect for architectural decisions
- **Code Reviews:** Required for all changes
- **Testing:** Coordinate with QA team

### External Resources

- **Python Documentation:** https://docs.python.org/3/
- **FFmpeg Documentation:** https://ffmpeg.org/documentation.html
- **Textual Documentation:** https://textual.textual.io/

---

## Document Standards

### Formatting

- Use Markdown for all documentation
- Include code examples for all APIs
- Use relative paths for internal links
- Use absolute paths for external links

### Structure

Each document should include:
1. Title and brief description
2. Table of contents (if long)
3. Main content with examples
4. Related documents section
5. Last updated date

### Review Process

1. Draft documentation
2. Technical review
3. Peer review
4. Final approval
5. Merge to main

---

**Last Updated:** 2026-02-06
**Maintained By:** Development Team

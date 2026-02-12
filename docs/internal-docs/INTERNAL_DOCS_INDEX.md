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
- [Archived Documentation](#archived-documentation)

---

## Architecture

### System Architecture

- **[ARCHITECTURE_ANALYSIS_REPORT.md](architecture/ARCHITECTURE_ANALYSIS_REPORT.md)**
  - Complete system architecture analysis
  - Module dependencies and relationships
  - Design patterns and architectural decisions

- **[SYSTEM_DESIGN.md](architecture/system-design.md)**
  - High-level system design
  - Component interaction diagrams
  - Data flow architecture

- **[overview.md](architecture/overview.md)**
  - Quick overview of system architecture
  - Key components and their roles

---

## Development Guides

### Coding Standards

- **[contributing-guide.md](guides/contributing-guide.md)**
  - Contribution workflow
  - Pull request guidelines
  - Code review process

### Testing Guide

- **[testing-guide.md](guides/testing-guide.md)**
  - Testing strategy and coverage goals
  - Unit testing guidelines
  - Integration testing guidelines
  - Test organization

### Optimization Guide

- **[optimization_developer_guide.md](guides/optimization_developer_guide.md)**
  - Performance optimization techniques
  - Memory management
  - GPU utilization

### Error Handling

- **[error-handling-guide.md](error-handling-guide.md)**
  - Error handling strategy
  - Exception hierarchy
  - Error reporting guidelines

### Operations

- **[RUNBOOK.md](RUNBOOK.md)**
  - Operations runbook
  - Deployment procedures
  - Incident response

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

- **[comparison_ramtest.md](modules/comparison_ramtest.md)**
  - Ramtest vs standard mode comparison
  - Performance benchmarks
  - Use case recommendations

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

---

## Research & Analysis

### Codebase Analysis

- **[codebase_analysis_report.md](research/codebase_analysis_report.md)**
  - Complete codebase analysis
  - Module inventory
  - Dependency mapping

### Performance Analysis

- **[performance_optimization_summary.md](research/performance_optimization_summary.md)**
  - Performance optimization summary
  - Bottleneck identification
  - Optimization strategies

### Project History

- **[Project_Summary_Log.md](research/Project_Summary_Log.md)**
  - Development history and milestones
- **[dev_session_summary.md](research/dev_session_summary.md)**
  - Recent development sessions
- **[PROJE_ANALIZ_RAPORU.md](research/PROJE_ANALIZ_RAPORU.md)**
  - Turkish project analysis report
- **[IMPORT_ANALYSIS_REPORT.md](research/IMPORT_ANALYSIS_REPORT.md)**
  - Import and dependency analysis

---

## Quality Assurance

### Test Analysis

- **[test-analysis-report.md](qa/test-analysis-report.md)**
  - Test coverage analysis
  - Test suite evaluation
  - Recommendations

### Code Analysis

- **[CODE_ANALYSIS_REPORT.md](qa/CODE_ANALYSIS_REPORT.md)**
  - Static analysis findings
  - Critical issues
  - Recommendations

- **[CRITICAL_FIXES_SUMMARY.md](qa/CRITICAL_FIXES_SUMMARY.md)**
  - Critical issue fixes
  - Verification results
  - Impact assessment

- **[Video_Duration_Debug_Report.md](qa/Video_Duration_Debug_Report.md)**
  - Video duration debugging report

### Production Readiness

- **[production_readiness_summary.md](production_readiness_summary.md)**
  - Production readiness assessment
  - Deployment checklist
  - Monitoring requirements

---

## API Reference

### Video Renderer API

- **[video-renderer-api.md](api/video-renderer-api.md)**
  - Complete API documentation
  - Class references
  - Function signatures

---

## Architecture Decision Records (ADRs)

Located in [`../adr/`](../adr/):

- **ADR-001:** Video Renderer Ramtest Merge
- **ADR-002:** Thread Safety Strategy
- **ADR-003:** Logging Architecture
- **ADR-004:** Config Management
- **ADR-005:** Test Framework Selection
- **ADR-006:** Ramtest Integration Strategy

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

---

## Archived Documentation

Documentation that has been superseded or is kept for historical reference is located in [`archive/`](archive/):

- **v1.0.0/** - Version 1.0.0 documentation snapshot
- Historical analysis reports
- Superseded documentation

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

**Last Updated:** 2026-02-12
**Maintained By:** Development Team

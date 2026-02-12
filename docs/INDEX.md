# AutoVideo Documentation Index

Welcome to the AutoVideo documentation. This index helps you find the information you need.

## Getting Started

- [README.md](../README.md) - Project overview and quick start guide (English)
- [README_TR.md](../README_TR.md) - Proje genel bakış ve hızlı başlangıç kılavuzu (Türkçe)
- [CHANGELOG.md](../CHANGELOG.md) - Version history and changes
- [RAMTEST_QUICK_START.md](RAMTEST_QUICK_START.md) - RAM-optimized mode guide

## User Documentation

### Main Video Renderer
- [Installation Guide](../README.md#installation) - Set up AutoVideo on your system
- [Quick Start](../README.md#quick-start) - Get started with basic usage
- [Usage](../README.md#usage) - Detailed usage instructions
- [Configuration](CONFIG_REFERENCE.md) - Configuration reference
- [Troubleshooting](TROUBLESHOOTING.md) - Common issues and solutions

### Validation System
- [Video Validation Guide](video-validation.md) - Complete validation system documentation
- [Validation Architecture](internal-docs/validation/architecture.md) - Developer documentation for validation
- [Validation Troubleshooting](internal-docs/validation/troubleshooting.md) - Common validation errors and solutions

### VideoAutomation Pipeline
- [VideoAutomation README](../VideoAutomation/README.md) - Automated video generation guide
- [YouTube Setup](../VideoAutomation/README.md#youtube-api-kurulumu) - Configure YouTube API

### VideoLivestream Pipeline
- [VideoLivestream README](../VideoLivestream/README.md) - Livestream automation guide

## Developer Documentation

### Architecture
- [System Design](internal-docs/architecture/system-design.md) - Complete system architecture
- [Architecture Overview](internal-docs/architecture/overview.md) - High-level architecture overview
- [Architecture Analysis](internal-docs/architecture/ARCHITECTURE_ANALYSIS_REPORT.md) - Detailed architecture analysis

### Modules
- [Batch System](internal-docs/modules/batch_system.md) - Batch processing system details
- [Ramtest Integration](internal-docs/modules/ramtest_integration.md) - Testing variant integration
- [Ramtest Comparison](internal-docs/modules/comparison_ramtest.md) - Ramtest vs standard mode comparison

### API Reference
- [API Reference](api/API_REFERENCE.md) - Complete API documentation
- [Video Renderer API](internal-docs/api/video-renderer-api.md) - Video renderer specific API
- [Validation API Reference](internal-docs/validation/architecture.md#api-reference) - Validation system API

### Guides
- [Contributing Guide](internal-docs/guides/contributing-guide.md) - How to contribute
- [Testing Guide](internal-docs/guides/testing-guide.md) - Testing strategies and practices
- [Optimization Guide](internal-docs/guides/optimization_developer_guide.md) - Performance optimization
- [Error Handling Guide](internal-docs/error-handling-guide.md) - Error handling strategies
- [Runbook](internal-docs/RUNBOOK.md) - Operations runbook

### Security
- [Security API Reference](internal-docs/security/SECURITY_API_REFERENCE.md) - Security module API
- [Security Hardening Report](internal-docs/security/SECURITY_HARDENING_REPORT.md) - Security improvements
- [Security Usage Guide](internal-docs/security/SECURITY_USAGE_GUIDE.md) - Security best practices

### Architecture Decision Records
- [ADR-001: video_renderer & ramtest Integration](adr/ADR-001-video-renderer-ramtest-merge.md)
- [ADR-002: Thread-Safety Strategy](adr/ADR-002-thread-safety-strategy.md)
- [ADR-003: Logging Architecture](adr/ADR-003-logging-architecture.md)
- [ADR-004: Config Management](adr/ADR-004-config-management.md)
- [ADR-005: Test Framework Selection](adr/ADR-005-test-framework-selection.md)
- [ADR-006: Ramtest Integration Strategy](adr/ADR-006-ramtest-integration.md)

## Migration & Deployment

- [Migration Guide](MIGRATION.md) - Migration between versions
- [Production Readiness](internal-docs/production_readiness_summary.md) - Production deployment checklist

## Research & Analysis

- [Codebase Analysis](internal-docs/research/codebase_analysis_report.md) - Complete codebase analysis
- [Performance Optimization](internal-docs/research/performance_optimization_summary.md) - Performance findings
- [Project History](internal-docs/research/Project_Summary_Log.md) - Development history and milestones

## Quality Assurance

- [Test Analysis Report](internal-docs/qa/test-analysis-report.md) - Test coverage analysis
- [Code Analysis Report](internal-docs/qa/CODE_ANALYSIS_REPORT.md) - Static analysis findings
- [Critical Fixes Summary](internal-docs/qa/CRITICAL_FIXES_SUMMARY.md) - Critical issue fixes

## External Resources

- [Textual Documentation](https://textual.textual.io/) - TUI framework documentation
- [FFmpeg Documentation](https://ffmpeg.org/documentation.html) - FFmpeg official docs
- [Rich Documentation](https://rich.readthedocs.io/) - Terminal output formatting

## Documentation Structure

```
docs/
├── INDEX.md                           # This file
├── CONFIG_REFERENCE.md                # Configuration reference
├── MIGRATION.md                       # Migration guide
├── RAMTEST_QUICK_START.md             # RAM-optimized mode guide
├── TROUBLESHOOTING.md                 # Troubleshooting guide
├── video-validation.md                # Video validation guide
├── DOCUMENTATION_SUMMARY.md           # Documentation overview
│
├── adr/                               # Architecture Decision Records
│   ├── ADR-001-video-renderer-ramtest-merge.md
│   ├── ADR-002-thread-safety-strategy.md
│   ├── ADR-003-logging-architecture.md
│   ├── ADR-004-config-management.md
│   ├── ADR-005-test-framework-selection.md
│   └── ADR-006-ramtest-integration.md
│
├── api/                               # API documentation
│   └── API_REFERENCE.md
│
└── internal-docs/                     # Developer documentation
    ├── architecture/                  # Architecture documentation
    │   ├── system-design.md
    │   ├── overview.md
    │   └── ARCHITECTURE_ANALYSIS_REPORT.md
    ├── api/                           # API reference
    │   └── video-renderer-api.md
    ├── modules/                       # Module documentation
    │   ├── batch_system.md
    │   ├── ramtest_integration.md
    │   └── comparison_ramtest.md
    ├── guides/                        # Developer guides
    │   ├── contributing-guide.md
    │   ├── testing-guide.md
    │   └── optimization_developer_guide.md
    ├── security/                      # Security documentation
    │   ├── SECURITY_API_REFERENCE.md
    │   ├── SECURITY_HARDENING_REPORT.md
    │   └── SECURITY_USAGE_GUIDE.md
    ├── validation/                    # Validation documentation
    │   ├── architecture.md
    │   └── troubleshooting.md
    ├── research/                      # Research and analysis
    ├── qa/                            # Quality assurance reports
    └── archive/                       # Archived documentation
```

## Quick Links

### For Users
- [How to install](../README.md#installation)
- [Basic usage](../README.md#usage)
- [Video validation](video-validation.md)
- [Troubleshooting](TROUBLESHOOTING.md)
- [RAM-optimized mode](RAMTEST_QUICK_START.md)

### For Developers
- [System architecture](internal-docs/architecture/system-design.md)
- [API reference](api/API_REFERENCE.md)
- [Contributing](internal-docs/guides/contributing-guide.md)
- [Testing guide](internal-docs/guides/testing-guide.md)

### For Maintainers
- [Architecture decisions](adr/)
- [Runbook](internal-docs/RUNBOOK.md)
- [Release notes](../CHANGELOG.md)
- [Production readiness](internal-docs/production_readiness_summary.md)

## Documentation Languages

- **English**: Most documentation is available in English
- **Türkçe**: Kullanıcı dokümantasyonu Türkçe olarak mevcuttur

## Getting Help

If you can't find what you're looking for:

1. Check the [troubleshooting guide](TROUBLESHOOTING.md)
2. Search through [GitHub Issues](https://github.com/ahmetcemkaraca/AutoVideo/issues)
3. Join the [GitHub Discussions](https://github.com/ahmetcemkaraca/AutoVideo/discussions)
4. Create a new issue with your question

## Contributing to Documentation

We welcome improvements to the documentation! See the [Contributing Guide](internal-docs/guides/contributing-guide.md) for details.

### Documentation Guidelines

- Use clear, concise language
- Include code examples where helpful
- Keep both English and Turkish versions in sync
- Follow the existing documentation structure
- Update the index when adding new documents

---

**Last Updated**: 2026-02-12
**Documentation Version**: 2.0

# AutoVideo Documentation Index

Welcome to the AutoVideo documentation. This index helps you find the information you need.

## Getting Started

- [README.md](../README.md) - Project overview and quick start guide (English)
- [README_TR.md](../README_TR.md) - Proje genel bakış ve hızlı başlangıç kılavuzu (Türkçe)
- [CHANGELOG.md](../CHANGELOG.md) - Version history and changes

## User Documentation

### Main Video Renderer
- [Installation Guide](../README.md#installation) - Set up AutoVideo on your system
- [Quick Start](../README.md#quick-start) - Get started with basic usage
- [Usage](../README.md#usage) - Detailed usage instructions
- [Configuration](../README.md#configuration) - Configure AutoVideo for your needs
- [Troubleshooting](../README.md#troubleshooting) - Common issues and solutions

### VideoAutomation Pipeline
- [VideoAutomation README](../VideoAutomation/README.md) - Automated video generation guide
- [YouTube Setup](../VideoAutomation/README.md#youtube-api-kurulumu) - Configure YouTube API

### VideoLivestream Pipeline
- [VideoLivestream README](../VideoLivestream/README.md) - Livestream automation guide

## Developer Documentation

### Architecture
- [System Design](internal-docs/architecture/system-design.md) - Complete system architecture
- [Architecture Overview](internal-docs/architecture/overview.md) - High-level architecture overview
- [Batch System](internal-docs/modules/batch_system.md) - Batch processing system details
- [Ramtest Integration](internal-docs/modules/ramtest_integration.md) - Testing variant integration

### API Reference
- [Video Renderer API](internal-docs/api/video-renderer-api.md) - Complete API documentation

### Guides
- [Contributing Guide](internal-docs/guides/contributing-guide.md) - How to contribute
- [Testing Guide](internal-docs/guides/testing-guide.md) - Testing strategies and practices

### Architecture Decision Records
- [ADR-001: video_renderer & ramtest Integration](adr/ADR-001-video-renderer-ramtest-merge.md)
- [ADR-002: Thread-Safety Strategy](adr/ADR-002-thread-safety-strategy.md)
- [ADR-003: Logging Architecture](adr/ADR-003-logging-architecture.md)
- [ADR-004: Config Management](adr/ADR-004-config-management.md)
- [ADR-005: Test Framework Selection](adr/ADR-005-test-framework-selection.md)

## Project History

- [Project Summary](Project_Summary_Log.md) - Development history and milestones
- [Development Summary](dev_session_summary.md) - Recent development sessions
- [VPS Transition Notes](VPS_Gecis_ve_Gelistirme_Ozeti.md) - VPS deployment notes

## External Resources

- [Textual Documentation](https://textual.textual.io/) - TUI framework documentation
- [FFmpeg Documentation](https://ffmpeg.org/documentation.html) - FFmpeg official docs
- [Rich Documentation](https://rich.readthedocs.io/) - Terminal output formatting

## Documentation Structure

```
docs/
├── README.md                          # This file
├── adr/                               # Architecture Decision Records
│   ├── ADR-001-*.md
│   ├── ADR-002-*.md
│   └── ...
├── internal-docs/                     # Developer documentation
│   ├── architecture/                  # Architecture documentation
│   │   ├── system-design.md
│   │   ├── overview.md
│   │   └── ...
│   ├── api/                           # API reference
│   │   └── video-renderer-api.md
│   ├── modules/                       # Module documentation
│   │   ├── batch_system.md
│   │   ├── ramtest_integration.md
│   │   └── ...
│   └── guides/                        # Developer guides
│       ├── contributing-guide.md
│       ├── testing-guide.md
│       └── ...
└── *.md                               # Various project documentation
```

## Quick Links

### For Users
- [How to install](../README.md#installation)
- [Basic usage](../README.md#usage)
- [Troubleshooting](../README.md#troubleshooting)

### For Developers
- [System architecture](internal-docs/architecture/system-design.md)
- [API reference](internal-docs/api/video-renderer-api.md)
- [Contributing](internal-docs/guides/contributing-guide.md)

### For Maintainers
- [Architecture decisions](adr/)
- [Testing guide](internal-docs/guides/testing-guide.md)
- [Release notes](../CHANGELOG.md)

## Documentation Languages

- **English**: Most documentation is available in English
- **Türkçe**: Kullanıcı dokümantasyonu Türkçe olarak mevcuttur

## Getting Help

If you can't find what you're looking for:

1. Check the [troubleshooting guide](../README.md#troubleshooting)
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

**Last Updated**: 2024-01-XX
**Documentation Version**: 1.0

# Contributing to AutoVideo

Thank you for your interest in contributing to AutoVideo! This guide will help you get started.

## Table of Contents

- [Code of Conduct](#code-of-conduct)
- [Getting Started](#getting-started)
- [Development Workflow](#development-workflow)
- [Coding Standards](#coding-standards)
- [Testing Guidelines](#testing-guidelines)
- [Documentation](#documentation)
- [Pull Request Process](#pull-request-process)

## Code of Conduct

- Be respectful and inclusive
- Provide constructive feedback
- Focus on what is best for the community
- Show empathy towards other community members

## Getting Started

### Prerequisites

- Python 3.10 or higher
- FFmpeg installed and in PATH
- Git for version control
- A GitHub account

### Setup Development Environment

1. **Fork and Clone**:
   ```bash
   # Fork the repository on GitHub
   git clone https://github.com/YOUR_USERNAME/AutoVideo
   cd AutoVideo
   ```

2. **Create Virtual Environment**:
   ```bash
   python -m venv venv

   # On Windows:
   venv\Scripts\activate
   # On Linux/macOS:
   source venv/bin/activate
   ```

3. **Install Dependencies**:
   ```bash
   pip install -r requirements.txt
   pip install -e .
   ```

4. **Install Development Tools**:
   ```bash
   pip install pytest pytest-cov pytest-mock black flake8 mypy
   ```

5. **Verify Setup**:
   ```bash
   # Check FFmpeg
   ffmpeg -version

   # Run tests
   pytest tests/

   # Check code style
   flake8 video_renderer/
   ```

## Development Workflow

### 1. Create a Branch

```bash
git checkout -b feature/your-feature-name
# or
git checkout -b fix/your-bug-fix
```

Branch naming conventions:
- `feature/` - New features
- `fix/` - Bug fixes
- `refactor/` - Code refactoring
- `docs/` - Documentation changes
- `test/` - Test additions/changes

### 2. Make Changes

- Write clean, readable code
- Follow coding standards (see below)
- Add tests for new functionality
- Update documentation as needed

### 3. Test Your Changes

```bash
# Run all tests
pytest tests/

# Run specific test file
pytest tests/test_video.py

# Run with coverage
pytest --cov=video_renderer tests/

# Run type checking
mypy video_renderer/
```

### 4. Commit Changes

```bash
git add .
git commit -m "feat: add new feature"
```

Commit message format:
- `feat:` - New feature
- `fix:` - Bug fix
- `docs:` - Documentation changes
- `refactor:` - Code refactoring
- `test:` - Test changes
- `chore:` - Maintenance tasks

Examples:
```
feat: add AV1 codec support
fix: correct audio looping duration calculation
docs: update API documentation
refactor: simplify batch queue logic
test: add integration tests for rendering
```

### 5. Push and Create Pull Request

```bash
git push origin feature/your-feature-name
```

Then create a pull request on GitHub.

## Coding Standards

### Python Style Guide

Follow [PEP 8](https://pep8.org/) guidelines:

```python
# Good
def render_video(config: RenderConfig) -> Path:
    """Render video with given configuration."""
    encoder = VideoEncoder(config)
    return encoder.encode()

# Bad
def RenderVideo(c):
    e=VideoEncoder(c)
    return e.encode()
```

### Type Hints

Use type hints for function signatures:

```python
from typing import List, Optional
from pathlib import Path

def process_tracks(
    tracks: List[Path],
    duration: int,
    output: Optional[Path] = None
) -> Path:
    """Process audio tracks."""
    if output is None:
        output = Path("output.wav")
    return output
```

### Docstrings

Use Google-style docstrings:

```python
def concat_videos(
    videos: List[Path],
    output: Path,
    duration: int
) -> None:
    """Concatenate videos to target duration.

    Args:
        videos: List of video paths to concatenate
        output: Output video path
        duration: Target duration in seconds

    Raises:
        VideoEncodingError: If concatenation fails
    """
    pass
```

### Error Handling

Use specific exception types:

```python
# Good
try:
    encoder.encode()
except VideoEncodingError as e:
    logger.error(f"Encoding failed: {e}")
    raise

# Bad
try:
    encoder.encode()
except Exception:
    pass
```

### Constants

Use UPPER_CASE for constants:

```python
# Good
DEFAULT_WIDTH = 1920
DEFAULT_HEIGHT = 1080
MAX_DURATION = 36000

# Bad
default_width = 1920
DefaultHeight = 1080
```

## Testing Guidelines

### Unit Tests

Test individual functions and classes:

```python
def test_codec_config_to_ffmpeg_args():
    """Test CodecConfig converts to correct FFmpeg args."""
    config = CODEC_H264
    args = config.to_ffmpeg_args()

    assert "-c:v" in args
    assert "libx264" in args
    assert args[args.index("-preset") + 1] == "fast"
```

### Integration Tests

Test component interactions:

```python
def test_render_pipeline(tmpdir):
    """Test complete render pipeline."""
    # Setup
    intro = create_test_video(tmpdir, "intro.mp4")
    loop = create_test_video(tmpdir, "loop.mp4")

    # Execute
    config = RenderConfig(intro_path=intro, loop_path=loop)
    encoder = VideoEncoder(config)
    output = encoder.render()

    # Verify
    assert output.exists()
    assert get_duration(output) >= config.duration_seconds
```

### Test Coverage

Aim for >80% coverage:

```bash
pytest --cov=video_renderer --cov-report=html
```

### Fixtures

Use pytest fixtures for common test data:

```python
@pytest.fixture
def sample_config():
    """Create sample render configuration."""
    return RenderConfig(
        codec="av1",
        duration_seconds=3600
    )

def test_with_fixture(sample_config):
    """Test using fixture."""
    assert sample_config.codec == "av1"
```

## Documentation

### Code Documentation

- Document all public APIs
- Use docstrings for functions and classes
- Include usage examples

### README Updates

Update README.md for user-facing changes:

```markdown
## New Features

### AV1 Codec Support

AutoVideo now supports AV1 encoding for better compression:

```bash
python -m video_renderer --codec av1
```
```

### ADR Documentation

Create ADR for significant architectural changes:

```markdown
# ADR-XXX: Feature Name

## Status
Proposed

## Context
...

## Decision
...

## Consequences
...
```

## Pull Request Process

### Before Submitting

1. **Code Review Checklist**:
   - [ ] Code follows style guidelines
   - [ ] Tests pass locally
   - [ ] Coverage is adequate
   - [ ] Documentation is updated
   - [ ] Commits are clean and descriptive

2. **Self-Review**:
   ```bash
   # Run linter
   flake8 video_renderer/

   # Run formatter
   black video_renderer/

   # Run tests
   pytest tests/

   # Check types
   mypy video_renderer/
   ```

### PR Description

Include in your PR:

```markdown
## Description
Brief description of changes

## Type of Change
- [ ] Bug fix
- [ ] New feature
- [ ] Breaking change
- [ ] Documentation update

## Testing
How changes were tested

## Checklist
- [ ] Tests pass
- [ ] Documentation updated
- [ ] No breaking changes (or documented)
```

### Review Process

1. **Automatic Checks**: CI runs tests and linters
2. **Code Review**: Maintainers review your code
3. **Feedback**: Address review comments
4. **Approval**: Wait for approval
5. **Merge**: Maintainers merge your PR

## Getting Help

### Resources

- [Documentation](../README.md)
- [API Reference](api/video-renderer-api.md)
- [Architecture Docs](architecture/system-design.md)

### Communication

- GitHub Issues: Report bugs and request features
- GitHub Discussions: Ask questions and share ideas
- Pull Requests: Discuss code changes

### First-Time Contributors

We welcome first-time contributors! Look for issues labeled:
- `good first issue`
- `help wanted`
- `documentation`

## Recognition

Contributors are recognized in:
- CONTRIBUTORS.md file
- Release notes
- Project documentation

Thank you for contributing to AutoVideo!

---

**Document Version**: 1.0
**Last Updated**: 2024-01-XX

# Testing Guide for AutoVideo

This guide covers testing strategies, tools, and best practices for AutoVideo.

## Table of Contents

- [Testing Philosophy](#testing-philosophy)
- [Test Structure](#test-structure)
- [Writing Tests](#writing-tests)
- [Test Categories](#test-categories)
- [Mocking External Dependencies](#mocking-external-dependencies)
- [Running Tests](#running-tests)
- [Continuous Integration](#continuous-integration)

## Testing Philosophy

### Goals

1. **Reliability**: Catch bugs before they reach production
2. **Maintainability**: Make code changes safer
3. **Documentation**: Tests serve as usage examples
4. **Speed**: Run tests quickly for rapid iteration

### Principles

- **Test Behavior, Not Implementation**: Focus on what code does, not how
- **Independent Tests**: Each test should run in isolation
- **Repeatable**: Same results every time
- **Fast**: Prefer unit tests over integration tests
- **Clear**: Test names should describe what they test

## Test Structure

### Directory Layout

```
tests/
├── unit/                    # Unit tests
│   ├── __init__.py
│   ├── test_video.py        # Video encoding tests
│   ├── test_audio.py        # Audio processing tests
│   ├── test_batch.py        # Batch queue tests
│   ├── test_config.py       # Configuration tests
│   └── test_ffmpeg.py       # FFmpeg wrapper tests
├── integration/             # Integration tests
│   ├── __init__.py
│   ├── test_render_pipeline.py
│   └── test_automation.py
├── fixtures/                # Test fixtures
│   ├── videos/              # Sample video files
│   └── audio/               # Sample audio files
├── conftest.py              # Shared fixtures
└── __init__.py
```

### Fixture Organization

```python
# conftest.py
import pytest
from pathlib import Path

@pytest.fixture
def temp_dir(tmpdir):
    """Temporary directory for test files."""
    return Path(tmpdir)

@pytest.fixture
def sample_video(temp_dir):
    """Create a sample video file."""
    video_path = temp_dir / "sample.mp4"
    # Create video...
    return video_path

@pytest.fixture
def mock_config():
    """Mock render configuration."""
    from video_renderer.config import RenderConfig
    return RenderConfig(
        codec="h264",
        duration_seconds=3600
    )
```

## Writing Tests

### Unit Tests

Test individual functions and classes in isolation.

```python
# tests/unit/test_config.py
import pytest
from video_renderer.config import CodecConfig, CODEC_H264

class TestCodecConfig:
    """Test CodecConfig class."""

    def test_to_ffmpeg_args(self):
        """Test conversion to FFmpeg arguments."""
        config = CODEC_H264
        args = config.to_ffmpeg_args()

        assert "-c:v" in args
        assert "libx264" in args
        assert "-preset" in args
        assert "-crf" in args

    def test_crf_value(self):
        """Test CRF value is correct."""
        assert CODEC_H264.crf == 20

    def test_preset_value(self):
        """Test preset value is correct."""
        assert CODEC_H264.preset == "fast"
```

### Integration Tests

Test multiple components working together.

```python
# tests/integration/test_render_pipeline.py
import pytest
from pathlib import Path
from video_renderer.video import VideoEncoder
from video_renderer.audio import AudioProcessor
from video_renderer.config import RenderConfig

class TestRenderPipeline:
    """Test complete render pipeline."""

    def test_video_only_render(self, temp_dir):
        """Test rendering video without audio."""
        # Setup
        intro = self._create_test_video(temp_dir, "intro.mp4", 10)
        loop = self._create_test_video(temp_dir, "loop.mp4", 5)

        # Execute
        config = RenderConfig(
            intro_path=intro,
            loop_path=loop,
            duration_seconds=30,
            tmp_dir=temp_dir
        )
        encoder = VideoEncoder(config)
        output = encoder.render()

        # Verify
        assert output.exists()
        assert self._get_duration(output) >= 30

    def _create_test_video(self, directory, name, duration):
        """Helper to create test video."""
        # Implementation...
        pass

    def _get_duration(self, video_path):
        """Helper to get video duration."""
        # Implementation...
        pass
```

### Parametrized Tests

Test multiple scenarios with one test function.

```python
@pytest.mark.parametrize("codec_family,expected_encoder", [
    ("h264", "h264_nvenc"),
    ("h264", "libx264"),
    ("h265", "hevc_nvenc"),
    ("h265", "libx265"),
])
def test_encoder_selection(codec_family, expected_encoder):
    """Test encoder selection for different codecs."""
    from video_renderer.config import get_best_encoder

    config = get_best_encoder(codec_family)
    assert expected_encoder in config.encoder
```

## Test Categories

### 1. Unit Tests

**Purpose**: Test individual functions/classes

**Characteristics**:
- Fast (< 0.1s each)
- Isolated
- Mock external dependencies

**Examples**:
- Config parsing
- Codec selection
- Path manipulation
- Validation logic

### 2. Integration Tests

**Purpose**: Test component interactions

**Characteristics**:
- Slower (1-10s each)
- Real components
- Minimal mocking

**Examples**:
- Render pipeline
- Audio processing
- Batch queue operations
- State persistence

### 3. End-to-End Tests

**Purpose**: Test complete workflows

**Characteristics**:
- Slowest (10-60s each)
- Full system
- No mocking

**Examples**:
- Complete render with real FFmpeg
- YouTube upload flow
- Batch processing

## Mocking External Dependencies

### Mocking FFmpeg

```python
from unittest.mock import patch, MagicMock

def test_ffmpeg_runner_mock():
    """Test FFmpeg runner with mocked subprocess."""
    with patch('subprocess.run') as mock_run:
        # Mock successful FFmpeg run
        mock_run.return_value = MagicMock(
            returncode=0,
            stderr=b"frame=  100 fps= 30 q=28.0 size=    1000kB time=00:00:03.33 bitrate= 2456.7kbits/s speed=1.00x"
        )

        from video_renderer.ffmpeg import FFmpegRunner
        runner = FFmpegRunner(["ffmpeg", "-i", "input.mp4"])
        output = runner.run()

        assert "frame=  100" in output
        mock_run.assert_called_once()
```

### Mocking File Operations

```python
from pathlib import Path
from unittest.mock import mock_open

def test_config_load(monkeypatch):
    """Test config loading with mocked file."""
    import json
    from video_renderer.config import load_config

    mock_data = {"codec": "h264", "duration": "9:00:00"}

    def mock_read():
        return json.dumps(mock_data)

    monkeypatch.setattr(Path, "read_text", mock_read)
    config = load_config(Path("config.json"))

    assert config.codec == "h264"
```

### Mocking Google Drive API

```python
def test_drive_upload(mock_drive_service):
    """Test Drive upload with mocked API."""
    mock_drive_service.files().create().execute.return_value = {
        "id": "test_file_id"
    }

    from video_renderer.drive import DriveUploader
    uploader = DriveUploader()
    file_id = uploader.upload(Path("test.mp4"))

    assert file_id == "test_file_id"
```

## Running Tests

### Basic Commands

```bash
# Run all tests
pytest

# Run specific test file
pytest tests/unit/test_video.py

# Run specific test
pytest tests/unit/test_video.py::test_normalize

# Run with verbose output
pytest -v

# Run with coverage
pytest --cov=video_renderer --cov-report=html
```

### Markers

Use markers to categorize tests:

```python
@pytest.mark.unit
def test_config_parsing():
    """Unit test for config parsing."""
    pass

@pytest.mark.integration
def test_render_pipeline():
    """Integration test for render pipeline."""
    pass

@pytest.mark.slow
def test_long_render():
    """Test for long-duration render."""
    pass
```

Run marked tests:

```bash
# Run only unit tests
pytest -m unit

# Run only integration tests
pytest -m integration

# Skip slow tests
pytest -m "not slow"
```

### Hardware-Dependent Tests

Skip tests if hardware not available:

```python
import pytest
from video_renderer.config import detect_available_encoders

@pytest.mark.skipif(
    not detect_available_encoders().get("h264_nvenc"),
    reason="NVENC not available"
)
def test_nvenc_encoding():
    """Test NVENC encoding."""
    pass
```

## Continuous Integration

### GitHub Actions

```yaml
# .github/workflows/test.yml
name: Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest

    steps:
    - uses: actions/checkout@v2

    - name: Set up Python
      uses: actions/setup-python@v2
      with:
        python-version: '3.10'

    - name: Install dependencies
      run: |
        pip install -r requirements.txt
        pip install pytest pytest-cov

    - name: Run tests
      run: pytest --cov=video_renderer

    - name: Upload coverage
      uses: codecov/codecov-action@v2
```

### Coverage Goals

- **Overall**: > 80% coverage
- **Core Modules**: > 90% coverage
- **UI Code**: > 60% coverage (hard to test)

### Coverage Reports

```bash
# Generate HTML report
pytest --cov=video_renderer --cov-report=html

# View report
open htmlcov/index.html
```

## Best Practices

### 1. Test Naming

Use descriptive names:

```python
# Good
def test_normalize_video_preserves_resolution():
    """Test that normalization preserves source resolution."""
    pass

# Bad
def test_normalize():
    pass
```

### 2. Test Organization

Group related tests:

```python
class TestVideoEncoder:
    """Test VideoEncoder class."""

    def test_normalize(self):
        """Test video normalization."""
        pass

    def test_concat(self):
        """Test video concatenation."""
        pass
```

### 3. Setup and Teardown

Use fixtures for setup/teardown:

```python
@pytest.fixture
def encoder(mock_config):
    """Create encoder with mock config."""
    return VideoEncoder(mock_config)

def test_with_encoder(encoder):
    """Test using encoder fixture."""
    # Use encoder...
    pass
```

### 4. Assertions

Use specific assertions:

```python
# Good
assert result == expected
assert value in [1, 2, 3]
assert path.exists()

# Bad
assert result  # Vague
assert not not value  # Confusing
```

### 5. Error Messages

Include helpful messages:

```python
assert result == expected, f"Expected {expected}, got {result}"
```

## Debugging Tests

### Print Debugging

```python
def test_something():
    result = calculate()
    print(f"Result: {result}")  # Shows with pytest -s
    assert result == expected
```

Run with `-s` to see output:

```bash
pytest -s tests/unit/test_something.py
```

### Debugger

Use pytest's built-in debugger:

```bash
# Drop into debugger on failure
pytest --pdb

# Drop into debugger on error
pytest --pdb --trace
```

### Failing Tests

Run only failing tests:

```bash
# Run only last failed tests
pytest --lf

# Run tests until first failure
pytest -x
```

## Resources

- [pytest Documentation](https://docs.pytest.org/)
- [Python Testing Best Practices](https://docs.python-guide.org/writing/tests/)
- [Effective Python Testing](https://docs.pytest.org/en/stable/)

---

**Document Version**: 1.0
**Last Updated**: 2024-01-XX

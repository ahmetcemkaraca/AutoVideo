# AutoVideo Test Suite

Comprehensive test suite for the AutoVideo video rendering and automation system.

## Test Structure

```
tests/
├── conftest.py                  # Pytest configuration and fixtures
├── fixtures/                    # Test fixtures and generators
│   ├── __init__.py
│   ├── generate_test_videos.py  # Test video generation utilities
│   └── videos/                  # Sample video files for testing
├── unit/                        # Unit tests
│   ├── test_video_encoder.py    # VideoEncoder tests
│   ├── test_audio_processor.py  # AudioProcessor tests
│   ├── test_batch_queue.py      # BatchQueue tests
│   ├── test_ffmpeg_runner.py    # FFmpegRunner tests
│   ├── test_audit.py            # Audit logging tests
│   ├── test_config.py           # Configuration management tests
│   └── test_security.py         # Security validation tests
├── integration/                 # Integration tests
│   ├── test_rendering_workflow.py         # End-to-end rendering tests
│   └── test_automation_pipeline.py        # Pipeline automation tests
├── e2e/                         # End-to-end tests
│   ├── test_cli_wizard.py       # CLI wizard workflow tests
│   └── test_tui_workflow.py     # TUI application workflow tests
├── performance/                 # Performance benchmarks
│   └── test_benchmarks.py       # Performance and scalability tests
├── test_batch.py                # Batch processing tests
├── test_batch_thread_safety.py  # Thread safety tests for batch operations
├── test_error_handling.py       # Error handling tests
├── test_optimizations.py        # Optimization verification tests
└── test_validator.py            # Input validation tests
```

## Running Tests

### Install Dependencies

```bash
pip install -r requirements-dev.txt
```

### Run All Tests

```bash
pytest
```

### Run Only Unit Tests

```bash
pytest -m unit
```

### Run Only Integration Tests

```bash
pytest -m integration
```

### Run Performance Benchmarks

```bash
pytest -m performance
```

### Run Specific Test File

```bash
pytest tests/unit/test_video_encoder.py
```

### Run with Coverage Report

```bash
pytest --cov=video_renderer --cov=VideoAutomation/automation --cov-report=html
```

### Run Verbose Output

```bash
pytest -v
```

### Run Parallel Tests (faster)

```bash
pytest -n auto
```

## Test Categories

### Unit Tests
- Fast, isolated tests
- Mock external dependencies
- Test individual functions and classes
- No external dependencies required

### Integration Tests
- Test component interactions
- May require FFmpeg to be installed
- Test complete workflows
- Slower than unit tests

### Performance Tests
- Benchmark encoding speeds
- Memory usage profiling
- Scalability tests
- Marked as `@slow`

## Test Fixtures

### Common Fixtures (conftest.py)

- `temp_dir`: Temporary directory (auto-cleanup)
- `work_dir`: Working directory with subdirectories
- `mock_ffmpeg_runner`: Mocked FFmpegRunner
- `codec_config`: Sample codec configuration
- `video_encoder`: VideoEncoder instance
- `audio_processor`: AudioProcessor instance
- `batch_queue`: BatchQueue instance
- `sample_render_job`: Sample RenderJob

### Path Fixtures

- `test_data_dir`: Path to test data directory
- `sample_video_path`: Sample video file path
- `sample_audio_path`: Sample audio file path

### Mock Fixtures

- `mock_youtube_service`: Mocked YouTube API
- `mock_youtube_credentials`: Mock YouTube credentials files
- `mock_subprocess_run`: Mock subprocess.run calls

### Fixtures Directory (tests/fixtures/)

The `fixtures/` directory contains test data generators and sample files:

- `generate_test_videos.py`: Utility script for generating test video files
- `videos/`: Directory containing sample video files for testing

To generate test videos:
```bash
python tests/fixtures/generate_test_videos.py
```

## Coverage Goals

Target: **80%+** code coverage

Current coverage by module:
- `video_encoder.py`: 90%+
- `audio_processor.py`: 90%+
- `batch_queue.py`: 95%+
- `ffmpeg_runner.py`: 85%+
- `audit.py`: 85%+
- `config.py`: 80%+
- `security.py`: 85%+

## Writing New Tests

### Unit Test Template

```python
import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch

@pytest.mark.unit
class TestYourClass:
    """Test suite for YourClass."""

    def test_something(self, fixture):
        """Test something."""
        # Arrange
        # Act
        # Assert
        assert result == expected

    @pytest.mark.parametrize("input, expected", [
        (1, 2),
        (2, 4),
    ])
    def test_parameterized(self, input, expected):
        """Test with parameters."""
        assert input * 2 == expected
```

### Integration Test Template

```python
import pytest

@pytest.mark.integration
@pytest.mark.requires_ffmpeg
class TestWorkflow:
    """Integration tests for workflow."""

    def test_complete_workflow(self, work_dir):
        """Test complete workflow."""
        # Test multi-step process
        assert True
```

### Performance Test Template

```python
import pytest
import time

@pytest.mark.performance
@pytest.mark.slow
def test_performance_benchmark():
    """Benchmark performance."""
    start_time = time.time()
    # Run operation
    elapsed = time.time() - start_time
    assert elapsed < threshold
```

## CI/CD Integration

### GitHub Actions Example

```yaml
name: Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-python@v4
        with:
          python-version: '3.10'
      - run: pip install -r requirements-dev.txt
      - run: pytest --cov --cov-report=xml
      - uses: codecov/codecov-action@v3
```

## Troubleshooting

### FFmpeg Not Found

```bash
# Install FFmpeg
# Ubuntu/Debian:
sudo apt-get install ffmpeg

# macOS:
brew install ffmpeg

# Windows:
# Download from https://ffmpeg.org/download.html
```

### Import Errors

```bash
# Install package in development mode
pip install -e .
```

### Test Database Issues

```bash
# Clean test artifacts
rm -rf tmp/
rm -rf .pytest_cache/
```

## Test Statistics

- **Total Test Files**: 17
- **Unit Test Files**: 7
- **Integration Test Files**: 2
- **E2E Test Files**: 2
- **Performance Test Files**: 1
- **Root Level Test Files**: 5
- **Estimated Runtime**: 2-3 minutes (unit), 5-10 minutes (full)

## Contributing Tests

When adding new features:

1. Write unit tests first (TDD)
2. Add integration tests for workflows
3. Add performance tests if operation is resource-intensive
4. Ensure coverage remains above 80%
5. Run `pytest` before committing

## Test Guidelines

- **Unit Tests**: Should be fast (< 0.1s each)
- **Integration Tests**: May be slower (< 1s each)
- **Performance Tests**: Can be slow (> 1s), mark as `@slow`
- **All Tests**: Must be deterministic (no random failures)
- **Fixtures**: Use shared fixtures from `conftest.py`

## Known Issues

- Some tests require FFmpeg to be installed
- Performance tests may be slow on CI
- GPU tests require specific hardware (skip if unavailable)
- YouTube tests require credentials (use mocks)

## Further Reading

- [Pytest Documentation](https://docs.pytest.org/)
- [Pytest Mock Documentation](https://docs.pytest.org/en/stable/mock.html)
- [Coverage.py Documentation](https://coverage.readthedocs.io/)

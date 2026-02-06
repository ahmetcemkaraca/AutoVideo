# ADR-005: Test Framework Selection

## Status
Accepted

## Context
The project needs comprehensive testing for:
- Video encoding logic
- Audio processing
- Batch queue management
- TUI interactions
- Integration testing
- Hardware encoder detection

Challenges:
- FFmpeg integration requires real testing
- TUI testing is complex
- Hardware-dependent tests (NVENC, QSV, etc.)
- Long-running tests (video rendering)
- File system operations

## Decision
Use pytest as the primary testing framework with:

1. **pytest**: Core test framework with fixtures and assertions
2. **pytest-mock**: Mocking external dependencies
3. **pytest-cov**: Coverage reporting
4. **pytest-asyncio**: Async test support (if needed)
5. **tmpdir**: Temporary directory fixture for file tests
6. **unittest.mock**: Mock FFmpeg subprocess calls

### Test Structure

```
tests/
├── unit/              # Unit tests
│   ├── test_video.py
│   ├── test_audio.py
│   ├── test_batch.py
│   └── test_config.py
├── integration/       # Integration tests
│   ├── test_render_pipeline.py
│   └── test_automation.py
├── fixtures/          # Test fixtures
│   ├── videos/        # Sample videos
│   └── audio/         # Sample audio
└── conftest.py        # Shared fixtures
```

### Testing Strategy

```python
# Unit test example
def test_codec_config_to_ffmpeg_args():
    """Test CodecConfig converts to correct FFmpeg args."""
    config = CODEC_H264
    args = config.to_ffmpeg_args()

    assert "-c:v" in args
    assert "libx264" in args
    assert "-preset" in args
    assert "fast" in args

# Integration test example
def test_render_pipeline(tmpdir):
    """Test complete render pipeline with real files."""
    # Use temporary directory
    # Create test inputs
    # Run render
    # Verify outputs
    pass
```

## Consequences

### Positive
- Industry-standard testing framework
- Excellent fixture support
- Good integration with CI/CD
- Easy to write and read tests
- Coverage reporting built-in

### Negative
- Learning curve for pytest features
- Setup required for FFmpeg mocking
- Some tests are hardware-dependent

### Neutral
- Test suite can be slow with real FFmpeg calls
- Need to balance unit vs integration tests

## Testing Guidelines

1. **Unit Tests**: Fast, isolated, mock dependencies
2. **Integration Tests**: Real components, test workflows
3. **Fixtures**: Reusable test data and mocks
4. **Coverage**: Aim for >80% coverage
5. **CI/CD**: Run tests on every commit

### Hardware-Dependent Tests

```python
@pytest.mark.skipif(not has_nvenc(), reason="NVENC not available")
def test_nvenc_encoding():
    """Test NVENC encoding if hardware available."""
    pass
```

## Alternatives Considered

1. **unittest**: Standard library framework
   - Rejected: Less feature-rich, more verbose

2. **nose2**: unittest extension
   - Rejected: Less active development

3. **No Testing Framework**: Just manual testing
   - Rejected: No regression protection

## Implementation

See: `tests/` directory for test implementations

## Coverage Goals

- **Unit Tests**: 80%+ coverage
- **Integration Tests**: All critical paths
- **E2E Tests**: User-facing workflows

## Related Decisions
- ADR-001: video_renderer & ramtest integration
- ADR-002: Thread-safety strategy

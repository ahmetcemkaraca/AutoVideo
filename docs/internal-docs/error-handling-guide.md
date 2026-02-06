# Error Handling and Logging Integration Guide

This guide explains how to integrate the new error handling and logging system into your code.

## Overview

The video renderer now includes a comprehensive error handling and logging infrastructure:

- **Custom Exception Hierarchy** (`video_renderer/exceptions.py`)
- **Structured Logging** (`video_renderer/logging.py`)
- **Error Reporting** (`video_renderer/error_reporting.py`)

## Quick Start

### Basic Usage

```python
from video_renderer import (
    get_logger,
    FFmpegError,
    AudioProcessingError,
    handle_errors,
)

# Get a logger for your module
logger = get_logger("MyModule")

# Use structured logging
logger.info("Processing started", video_id="123", codec="h264")
logger.error("Processing failed", error=str(e), video_id="123")

# Raise custom exceptions
raise FFmpegError(
    message="Encoding failed",
    command=cmd,
    exit_code=1,
    stderr="Error output"
)
```

### With Error Handling Decorator

```python
from video_renderer import handle_errors, get_logger

logger = get_logger("VideoEncoder")

@handle_errors(default_return=None, raise_on_error=True, component="VideoEncoder")
def encode_video(source_path, output_path):
    logger.info("Starting encoding", source=str(source_path))
    # Your encoding logic here
    return output_path
```

### With Context Tracking

```python
from video_renderer import LogContext, generate_request_id, get_logger

logger = get_logger("MyModule")

with LogContext(
    request_id=generate_request_id(),
    component="VideoEncoder",
    session_id="my-session"
):
    logger.info("This log will have all context attached")
    # All logs in this block inherit the context
```

## Exception Hierarchy

### Base Exception

```python
from video_renderer import VideoRendererError, ErrorContext, ErrorSeverity

# Create custom exception with context
context = ErrorContext(
    severity=ErrorSeverity.ERROR,
    component="MyComponent",
    operation="encoding",
    user_action="Check the file format",
    recovery_possible=True
)

raise VideoRendererError(
    message="Encoding failed",
    details={"file": "video.mp4", "codec": "h264"},
    context=context
)
```

### FFmpeg Exceptions

```python
from video_renderer import FFmpegError, FFmpegNotFoundError, FFmpegCommandError

# FFmpeg not found
raise FFmpegNotFoundError(ffmpeg_path="/usr/bin/ffmpeg")

# FFmpeg command failed
raise FFmpegCommandError(
    message="Encoding failed",
    command=["ffmpeg", "-i", "input.mp4", "output.mp4"],
    exit_code=1,
    stderr="Error output",
    file_path=Path("input.mp4")
)
```

### Audio Processing Exceptions

```python
from video_renderer import AudioValidationError, AudioMixingError

# Invalid audio file
raise AudioValidationError(
    file_path=Path("music.mp3"),
    reason="File is corrupted"
)

# Mixing failed
raise AudioMixingError(
    tracks=[Path("track1.mp3"), Path("track2.mp3")],
    reason="Incompatible sample rates"
)
```

### Video Processing Exceptions

```python
from video_renderer import VideoCompatibilityError, VideoEncodingError

# Compatibility check failed
raise VideoCompatibilityError(
    file_path=Path("video.mp4"),
    reason="Resolution mismatch: 1920x1080 -> 3840x2160"
)

# Encoding failed
raise VideoEncodingError(
    file_path=Path("video.mp4"),
    codec="h264",
    reason="Hardware encoder not available"
)
```

### Validation Exceptions

```python
from video_renderer import FileValidationError, DurationValidationError

# File validation failed
raise FileValidationError(
    file_path=Path("video.mp4"),
    reason="File not found"
)

# Duration validation failed
raise DurationValidationError(
    duration=72000,
    min_value=60,
    max_value=43200
)
```

### State Exceptions

```python
from video_renderer import StateLoadError, StateCorruptedError

# State load failed
raise StateLoadError(
    state_path=Path("state.json"),
    reason="Permission denied"
)

# State corrupted
raise StateCorruptedError(
    state_path=Path("state.json"),
    parse_error="Invalid JSON"
)
```

## Logging

### Configuration

```python
from video_renderer import configure_logging, LogLevel
from pathlib import Path

# Configure global logging
configure_logging(
    level=LogLevel.INFO,
    log_dir=Path("logs"),
    log_file="video_renderer.log",
    enable_console=True,
    enable_json=True,
    max_bytes=10*1024*1024,  # 10MB
    backup_count=5
)
```

### Logging Levels

```python
from video_renderer import get_logger

logger = get_logger("MyModule")

# DEBUG: Detailed diagnostic info
logger.debug("Variable values", var1=value1, var2=value2)

# INFO: General progress updates
logger.info("Processing started", file_count=10)

# WARNING: Non-critical issues
logger.warning("File skipped", reason="Invalid format")

# ERROR: Error conditions
logger.error("Processing failed", error=str(e))

# CRITICAL: Severe errors
logger.critical("System failure", component="Encoder")
```

### Structured Logging

```python
# Log with structured context
logger.info(
    "Encoding progress",
    video_id="123",
    percent=45.5,
    fps=60.0,
    speed="1.2x"
)

# Log file operations
logger.file_operation("write", Path("output.mp4"))

# Log FFmpeg commands
logger.ffmpeg_command(["ffmpeg", "-i", "input.mp4", "output.mp4"])

# Log progress updates
logger.progress("encoding", percent=50.0)
```

### Context-Aware Logging

```python
from video_renderer import LogContext, set_context

# Using context manager
with LogContext(request_id="req-123", component="Encoder"):
    logger.info("This log has context")

# Using function-level context
def process_video(video_id):
    set_context(request_id=f"video-{video_id}", component="Processor")
    logger.info("Processing started")  # Has context
```

## Error Reporting

### Basic Error Reporting

```python
from video_renderer import report_error, format_error

try:
    # Your code here
    pass
except Exception as e:
    # Report the error
    record = report_error(e, video_id="123")

    # Format for user display
    user_message = format_error(e)
    print(user_message)
```

### Error Reporting Configuration

```python
from video_renderer import configure_error_reporting, ErrorReportConfig, ErrorReportingMode

# Configure error reporting
configure_error_reporting(ErrorReportConfig(
    mode=ErrorReportingMode.USER_FRIENDLY,
    show_stack_traces=False,
    show_technical_details=False,
    log_errors=True,
    enable_recovery=True
))
```

### Error Handling Decorators

```python
from video_renderer import handle_errors

@handle_errors(default_return=None, raise_on_error=False)
def risky_function():
    # This function's errors will be automatically reported
    pass
```

### Safe Execution

```python
from video_renderer import safe_execute

result = safe_execute(
    risky_function,
    arg1, arg2,
    default_return=None,
    raise_on_error=False
)
```

## Integration Examples

### Video Module Integration

```python
from video_renderer import (
    get_logger,
    VideoCompatibilityError,
    VideoEncodingError,
    LogContext,
    generate_request_id,
)

class VideoEncoder:
    def __init__(self):
        self.logger = get_logger("VideoEncoder")

    def normalize_video(self, source, output):
        with LogContext(
            request_id=generate_request_id(),
            component="VideoEncoder"
        ):
            self.logger.info(
                "Normalizing video",
                source=str(source),
                output=str(output)
            )

            try:
                # Your encoding logic
                pass
            except Exception as e:
                self.logger.error("Normalization failed", exc_info=e)
                raise VideoEncodingError(
                    message=f"Failed to normalize {source.name}",
                    file_path=source,
                    codec="h264",
                    reason=str(e)
                ) from e
```

### Audio Module Integration

```python
from video_renderer import (
    get_logger,
    AudioValidationError,
    AudioMixingError,
    handle_errors,
)

class AudioProcessor:
    def __init__(self):
        self.logger = get_logger("AudioProcessor")

    @handle_errors(default_return=[], raise_on_error=True)
    def validate_tracks(self, tracks):
        valid = []
        invalid = []

        for track in tracks:
            try:
                # Validation logic
                valid.append(track)
                self.logger.info("Track validated", track=str(track))
            except Exception as e:
                invalid.append((track, str(e)))
                self.logger.warning("Track validation failed", track=str(track))

        return valid, invalid
```

### FFmpeg Module Integration

```python
from video_renderer import (
    get_logger,
    FFmpegCommandError,
    FFmpegTimeoutError,
    log_errors,
)

class FFmpegRunner:
    def __init__(self):
        self.logger = get_logger("FFmpegRunner")

    @log_errors(reraise=True)
    def run(self, cmd, timeout=300):
        self.logger.ffmpeg_command(cmd)

        try:
            # Run command with timeout
            result = subprocess.run(cmd, timeout=timeout, check=True)
            return result
        except subprocess.TimeoutExpired:
            raise FFmpegTimeoutError(cmd, timeout)
        except subprocess.CalledProcessError as e:
            raise FFmpegCommandError(
                message="Command failed",
                command=cmd,
                exit_code=e.returncode,
                stderr=e.stderr
            )
```

## Best Practices

### 1. Always Use Structured Logging

```python
# GOOD
logger.info("Processing started", video_id=video_id, codec=codec)

# AVOID
logger.info(f"Processing started for video {video_id} with codec {codec}")
```

### 2. Use Specific Exception Types

```python
# GOOD
raise AudioValidationError(file_path, reason)

# AVOID
raise Exception("Audio validation failed")
```

### 3. Provide Context for Errors

```python
# GOOD
with LogContext(request_id=request_id, component="Encoder"):
    process_video()

# AVOID
process_video()  # No context
```

### 4. Include User Actions

```python
# GOOD
context = ErrorContext(
    user_action="Check that FFmpeg is installed and in PATH"
)

# AVOID
context = ErrorContext()  # No guidance
```

### 5. Use Decorators for Consistent Error Handling

```python
# GOOD
@handle_errors(component="VideoEncoder")
def encode_video():
    pass

# AVOID
def encode_video():
    try:
        pass
    except Exception:
        # Manual error handling
        pass
```

## Log File Management

### Viewing Logs

```python
from video_renderer.logging import parse_log_file, filter_logs

# Parse log file
logs = parse_log_file(Path("logs/video_renderer.log"))

# Filter by level
errors = filter_logs(logs, level="ERROR")

# Filter by component
encoder_logs = filter_logs(logs, component="VideoEncoder")
```

### Error Summary

```python
from video_renderer.logging import get_error_summary

# Get error summary
summary = get_error_summary(Path("logs/video_renderer.log"))
print(f"Total errors: {summary['total_errors']}")
print(f"By component: {summary['by_component']}")
```

## Testing

### Testing Error Handling

```python
import pytest
from video_renderer import FFmpegError, get_logger

def test_ffmpeg_error():
    logger = get_logger("test")

    with pytest.raises(FFmpegError) as exc_info:
        raise FFmpegError(
            message="Test error",
            command=["ffmpeg"],
            exit_code=1
        )

    assert "Test error" in str(exc_info.value)
```

### Mocking Logger

```python
from unittest.mock import patch
from video_renderer import get_logger

def test_with_mock_logger():
    with patch('video_renderer.logging.get_logger') as mock_logger:
        mock_logger.return_value.info = lambda **kwargs: None
        # Your test here
```

## Migration Guide

### From Print to Logger

```python
# BEFORE
print(f"Processing {video_file}")

# AFTER
logger.info("Processing video", video_file=str(video_file))
```

### From Generic Exception

```python
# BEFORE
raise Exception("Failed to encode video")

# AFTER
raise VideoEncodingError(
    file_path=video_file,
    codec="h264",
    reason="Encoding failed"
)
```

### From Basic Logging

```python
# BEFORE
import logging
logger = logging.getLogger(__name__)
logger.info("Processing started")

# AFTER
from video_renderer import get_logger
logger = get_logger(__name__)
logger.info("Processing started", component="VideoEncoder")
```

## Troubleshooting

### Common Issues

1. **Logger not outputting to file**
   - Check that log directory exists and is writable
   - Verify `configure_logging()` is called before `get_logger()`

2. **Context not appearing in logs**
   - Ensure `LogContext` is used as a context manager
   - Check that `enable_console=True` in configuration

3. **Error reporting not working**
   - Call `configure_error_reporting()` before using error reporting
   - Verify error reporting mode is not `SILENT`

## Additional Resources

- [Exception API Reference](#)
- [Logging API Reference](#)
- [Error Reporting API Reference](#)
- [Configuration Guide](#)

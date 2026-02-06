#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Example script demonstrating error handling and logging integration.

This script shows how to use the custom exception hierarchy,
structured logging, and error reporting in the video renderer.
"""

import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from video_renderer import (
    # Exceptions
    VideoRendererError,
    FFmpegError,
    FFmpegNotFoundError,
    FFmpegCommandError,
    AudioProcessingError,
    AudioValidationError,
    VideoProcessingError,
    VideoCompatibilityError,
    ValidationError,
    ErrorContext,
    ErrorSeverity,
    get_user_message,
    wrap_exception,

    # Logging
    get_logger,
    configure_logging,
    LogLevel,
    LogContext,
    set_context,
    generate_request_id,
    log_function_call,
    log_errors,

    # Error reporting
    configure_error_reporting,
    ErrorReportConfig,
    ErrorReportingMode,
    report_error,
    format_error,
    handle_errors,
    safe_execute,
)


def setup_logging():
    """Configure logging for the example."""
    configure_logging(
        level=LogLevel.DEBUG,
        log_dir=Path("logs"),
        log_file="example.log",
        enable_console=True,
        enable_json=True,
    )


def setup_error_reporting():
    """Configure error reporting for the example."""
    configure_error_reporting(ErrorReportConfig(
        mode=ErrorReportingMode.USER_FRIENDLY,
        show_stack_traces=False,
        log_errors=True,
    ))


# ═══════════════════════════════════════════════════════════════════════════════
# Example 1: Basic Logging
# ═══════════════════════════════════════════════════════════════════════════════

def example_basic_logging():
    """Demonstrate basic logging usage."""
    logger = get_logger("Example1")
    logger.info("=" * 60)
    logger.info("Example 1: Basic Logging")

    # Different log levels
    logger.debug("This is a debug message", detail="Not shown in INFO mode")
    logger.info("This is an info message", status="running")
    logger.warning("This is a warning", issue="minor")
    logger.error("This is an error", problem="something failed")

    # Structured logging
    logger.info(
        "Processing video",
        video_id="123",
        codec="h264",
        resolution="1920x1080",
        duration=3600
    )

    print("\n✓ Example 1 complete\n")


# ═══════════════════════════════════════════════════════════════════════════════
# Example 2: Context-Aware Logging
# ═══════════════════════════════════════════════════════════════════════════════

def example_context_logging():
    """Demonstrate context-aware logging."""
    logger = get_logger("Example2")
    logger.info("=" * 60)
    logger.info("Example 2: Context-Aware Logging")

    # Using LogContext
    with LogContext(
        request_id=generate_request_id(),
        session_id="example-session",
        component="VideoEncoder",
        user_id="example-user"
    ):
        logger.info("This log has all context attached")
        logger.info("Request ID is preserved across calls")

        # Nested context
        with LogContext(component="AudioProcessor"):
            logger.info("This log has a different component")
            logger.info("But same request ID")

    print("\n✓ Example 2 complete\n")


# ═══════════════════════════════════════════════════════════════════════════════
# Example 3: Custom Exceptions
# ═══════════════════════════════════════════════════════════════════════════════

def example_custom_exceptions():
    """Demonstrate custom exception usage."""
    logger = get_logger("Example3")
    logger.info("=" * 60)
    logger.info("Example 3: Custom Exceptions")

    # FFmpeg not found
    try:
        raise FFmpegNotFoundError(ffmpeg_path="/usr/bin/ffmpeg")
    except FFmpegError as e:
        logger.error("FFmpeg not found error", exc_info=e)
        print(f"User message: {get_user_message(e)}")

    # FFmpeg command error
    try:
        raise FFmpegCommandError(
            message="Encoding failed",
            command=["ffmpeg", "-i", "input.mp4", "output.mp4"],
            exit_code=1,
            stderr="Error: Invalid data",
            file_path=Path("input.mp4")
        )
    except FFmpegCommandError as e:
        logger.error("FFmpeg command failed", exc_info=e)
        print(f"Suggested action: {e.context.user_action}")

    # Audio validation error
    try:
        raise AudioValidationError(
            file_path=Path("music.mp3"),
            reason="File is corrupted"
        )
    except AudioProcessingError as e:
        logger.error("Audio validation failed", exc_info=e)
        print(f"Recovery possible: {e.context.recovery_possible}")

    # Video compatibility error
    try:
        raise VideoCompatibilityError(
            file_path=Path("video.mp4"),
            reason="Resolution mismatch: 1920x1080 -> 3840x2160",
            current_specs={"width": 1920, "height": 1080, "codec": "h264"}
        )
    except VideoProcessingError as e:
        logger.error("Video compatibility check failed", exc_info=e)

    print("\n✓ Example 3 complete\n")


# ═══════════════════════════════════════════════════════════════════════════════
# Example 4: Error Handling with Decorators
# ═══════════════════════════════════════════════════════════════════════════════

@handle_errors(default_return=None, raise_on_error=False, component="ExampleEncoder")
def risky_operation(video_id: str):
    """Example function that might fail."""
    logger = get_logger("Example4")

    logger.info("Starting risky operation", video_id=video_id)

    # Simulate an error
    if video_id == "fail":
        raise VideoCompatibilityError(
            file_path=Path("video.mp4"),
            reason="Simulated failure"
        )

    return f"Success: {video_id}"


def example_error_handling_decorators():
    """Demonstrate error handling with decorators."""
    logger = get_logger("Example4")
    logger.info("=" * 60)
    logger.info("Example 4: Error Handling with Decorators")

    # Successful operation
    result = risky_operation("123")
    logger.info("Operation succeeded", result=result)

    # Failed operation (handled by decorator)
    result = risky_operation("fail")
    if result is None:
        logger.info("Operation failed (handled by decorator)")

    print("\n✓ Example 4 complete\n")


# ═══════════════════════════════════════════════════════════════════════════════
# Example 5: Safe Execution
# ═══════════════════════════════════════════════════════════════════════════════

def divide_numbers(a: float, b: float) -> float:
    """Function that might fail."""
    return a / b


def example_safe_execution():
    """Demonstrate safe execution."""
    logger = get_logger("Example5")
    logger.info("=" * 60)
    logger.info("Example 5: Safe Execution")

    # Successful execution
    result = safe_execute(
        divide_numbers,
        10.0, 2.0,
        default_return=None,
        raise_on_error=False
    )
    logger.info("Division succeeded", result=result)

    # Failed execution (division by zero)
    result = safe_execute(
        divide_numbers,
        10.0, 0.0,
        default_return=float('inf'),
        raise_on_error=False
    )
    logger.info("Division failed (safe execution)", result=result)

    print("\n✓ Example 5 complete\n")


# ═══════════════════════════════════════════════════════════════════════════════
# Example 6: Error Reporting
# ═══════════════════════════════════════════════════════════════════════════════

def example_error_reporting():
    """Demonstrate error reporting."""
    logger = get_logger("Example6")
    logger.info("=" * 60)
    logger.info("Example 6: Error Reporting")

    # Report an error
    try:
        raise ValueError("Simulated error")
    except Exception as e:
        record = report_error(e, operation="example_operation")

        logger.info(
            "Error reported",
            exception_type=record.exception_type,
            severity=record.severity.value if isinstance(record.severity, ErrorSeverity) else record.severity,
            recovery_possible=record.recovery_possible
        )

        # Format for user display
        user_message = format_error(e, operation="example_operation")
        print(f"\nUser message:\n{user_message}\n")

    print("\n✓ Example 6 complete\n")


# ═══════════════════════════════════════════════════════════════════════════════
# Example 7: Function Call Logging
# ═══════════════════════════════════════════════════════════════════════════════

@log_function_call(include_args=True, include_result=True)
def calculate_video_bitrate(duration: int, target_size_mb: int) -> float:
    """Calculate required bitrate for a video."""
    # 1 MB = 8 Mb, duration in seconds
    bitrate_mbps = (target_size_mb * 8) / duration
    return bitrate_mbps * 1000  # Convert to kbps


def example_function_logging():
    """Demonstrate function call logging."""
    logger = get_logger("Example7")
    logger.info("=" * 60)
    logger.info("Example 7: Function Call Logging")

    # Call decorated function
    bitrate = calculate_video_bitrate(duration=3600, target_size_mb=100)
    logger.info("Calculated bitrate", bitrate_kbps=bitrate)

    print("\n✓ Example 7 complete\n")


# ═══════════════════════════════════════════════════════════════════════════════
# Example 8: Complex Error Scenarios
# ═══════════════════════════════════════════════════════════════════════════════

class VideoProcessor:
    """Example video processor with error handling."""

    def __init__(self):
        self.logger = get_logger("VideoProcessor")

    def process_video(
        self,
        input_path: Path,
        output_path: Path,
        codec: str = "h264"
    ) -> Path:
        """Process a video with comprehensive error handling."""
        request_id = generate_request_id()

        with LogContext(
            request_id=request_id,
            component="VideoProcessor",
            operation="process_video"
        ):
            self.logger.info(
                "Starting video processing",
                input=str(input_path),
                output=str(output_path),
                codec=codec
            )

            try:
                # Validate input
                if not input_path.exists():
                    raise ValidationError(
                        f"Input file not found: {input_path.name}",
                        field="input_path"
                    )

                # Check compatibility
                if codec not in ["h264", "hevc", "av1"]:
                    raise VideoCompatibilityError(
                        file_path=input_path,
                        reason=f"Unsupported codec: {codec}"
                    )

                # Simulate processing
                self.logger.info("Encoding video", codec=codec, percent=0)

                for i in range(0, 101, 25):
                    self.logger.progress("encoding", percent=float(i))
                    if i == 50 and "fail" in str(input_path):
                        raise VideoEncodingError(
                            file_path=input_path,
                            codec=codec,
                            reason="Simulated encoding failure"
                        )

                self.logger.info("Processing completed", output=str(output_path))
                return output_path

            except VideoRendererError as e:
                self.logger.error("Video processing failed", exc_info=e)
                raise
            except Exception as e:
                wrapped = wrap_exception(
                    e,
                    message="Unexpected error during video processing",
                    component="VideoProcessor",
                    operation="process_video"
                )
                self.logger.error("Unexpected error", exc_info=wrapped)
                raise wrapped


def example_complex_scenarios():
    """Demonstrate complex error scenarios."""
    logger = get_logger("Example8")
    logger.info("=" * 60)
    logger.info("Example 8: Complex Error Scenarios")

    processor = VideoProcessor()

    # Successful processing
    try:
        result = processor.process_video(
            input_path=Path("input.mp4"),
            output_path=Path("output.mp4"),
            codec="h264"
        )
        logger.info("Processing succeeded", result=str(result))
    except Exception as e:
        logger.error("Processing failed", exc_info=e)

    # Failed processing (file not found)
    try:
        result = processor.process_video(
            input_path=Path("nonexistent.mp4"),
            output_path=Path("output.mp4")
        )
    except ValidationError as e:
        logger.error("Validation failed (expected)", exc_info=e)

    # Failed processing (encoding failure)
    try:
        result = processor.process_video(
            input_path=Path("input_fail.mp4"),
            output_path=Path("output.mp4")
        )
    except VideoProcessingError as e:
        logger.error("Processing failed (expected)", exc_info=e)

    print("\n✓ Example 8 complete\n")


# ═══════════════════════════════════════════════════════════════════════════════
# Main
# ═══════════════════════════════════════════════════════════════════════════════

def main():
    """Run all examples."""
    print("\n" + "=" * 60)
    print("Error Handling and Logging Examples")
    print("=" * 60 + "\n")

    # Setup
    setup_logging()
    setup_error_reporting()

    # Run examples
    example_basic_logging()
    example_context_logging()
    example_custom_exceptions()
    example_error_handling_decorators()
    example_safe_execution()
    example_error_reporting()
    example_function_logging()
    example_complex_scenarios()

    print("=" * 60)
    print("All examples completed!")
    print("=" * 60)
    print("\nCheck logs/example.log for detailed output.\n")


if __name__ == "__main__":
    main()

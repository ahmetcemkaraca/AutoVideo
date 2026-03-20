#!/usr/bin/env python3
"""
Unit tests for error handling and logging system.
"""

import json
import sys
from datetime import datetime
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from video_renderer.error_reporting import (
    ErrorAggregator,
    ErrorRecord,
    ErrorReportingMode,
    handle_errors,
    safe_execute,
)
from video_renderer.exceptions import (
    AudioValidationError,
    ErrorContext,
    ErrorSeverity,
    FFmpegNotFoundError,
    VideoCompatibilityError,
    VideoRendererError,
    get_user_message,
)
from video_renderer.logging import (
    JSONFormatter,
    LogContext,
    LogLevel,
    generate_request_id,
    generate_session_id,
)
from video_renderer.logging_config import (
    ConfigPresets,
    ErrorReportingExtendedConfig,
    LoggingConfig,
    VideoRendererConfig,
)

# ═══════════════════════════════════════════════════════════════════════════════
# Test Functions
# ═══════════════════════════════════════════════════════════════════════════════


def test_exception_hierarchy():
    """Test custom exception hierarchy."""
    print("Testing exception hierarchy...")

    # Test base exception
    context = ErrorContext(
        severity=ErrorSeverity.ERROR,
        component="TestComponent",
        operation="test_operation",
        user_action="Test action",
        recovery_possible=True,
    )

    exc = VideoRendererError(message="Test error", details={"key": "value"}, context=context)

    assert exc.message == "Test error"
    assert exc.details == {"key": "value"}
    assert exc.context.component == "TestComponent"
    assert exc.context.recovery_possible == True

    # Test FFmpeg exception
    ffmpeg_exc = FFmpegNotFoundError()
    assert "FFmpeg not found" in str(ffmpeg_exc)

    # Test to_dict conversion
    exc_dict = exc.to_dict()
    assert exc_dict["message"] == "Test error"
    assert exc_dict["context"]["component"] == "TestComponent"

    print("[PASS] Exception hierarchy tests passed")


def test_audio_validation_error():
    """Test audio validation error."""
    print("Testing audio validation error...")

    exc = AudioValidationError(file_path=Path("test.mp3"), reason="File is corrupted")

    assert exc.context.file_path == Path("test.mp3")
    assert exc.context.recovery_possible == True
    assert exc.context.user_action is not None

    print("[PASS] Audio validation error tests passed")


def test_video_compatibility_error():
    """Test video compatibility error."""
    print("Testing video compatibility error...")

    exc = VideoCompatibilityError(
        file_path=Path("test.mp4"),
        reason="Resolution mismatch",
        current_specs={"width": 1920, "height": 1080},
    )

    assert exc.context.file_path == Path("test.mp4")
    assert exc.context.recovery_possible == True
    assert "compatibility_reason" in exc.context.technical_details
    assert exc.context.technical_details["compatibility_reason"] == "Resolution mismatch"
    assert "current_specs" in exc.context.technical_details

    print("[PASS] Video compatibility error tests passed")


def test_user_message():
    """Test user-friendly error messages."""
    print("Testing user-friendly error messages...")

    # Test VideoRendererError
    vr_exc = VideoRendererError(message="Test error", context=ErrorContext(user_action="Try again"))
    msg = get_user_message(vr_exc)
    assert "Test error" in msg

    # Test generic exception
    file_not_found = FileNotFoundError("test.txt")
    msg = get_user_message(file_not_found)
    assert "not found" in msg.lower()

    print("[PASS] User message tests passed")


def test_logging_config():
    """Test logging configuration."""
    print("Testing logging configuration...")

    # Test default config
    config = LoggingConfig()
    assert config.level == LogLevel.INFO  # Default is INFO
    assert config.enable_console == True

    # Test from_dict
    config_dict = {
        "level": "DEBUG",
        "log_dir": "/tmp/logs",
        "log_file": "test.log",
        "enable_console": False,
    }
    config = LoggingConfig.from_dict(config_dict)
    assert config.level == LogLevel.DEBUG
    # Note: Path conversion depends on OS
    # On Windows: \tmp\logs, On Unix: /tmp/logs
    assert str(config.log_dir).endswith("tmp/logs") or str(config.log_dir).endswith("tmp\\logs")
    assert config.enable_console == False

    # Test to_dict
    config_dict_out = config.to_dict()
    assert config_dict_out["level"] == "DEBUG"
    # Path gets converted to string, just check it contains the right parts
    assert "tmp" in config_dict_out["log_dir"] and "logs" in config_dict_out["log_dir"]

    print("[PASS] Logging configuration tests passed")


def test_error_reporting_config():
    """Test error reporting configuration."""
    print("Testing error reporting configuration...")

    # Test default config
    config = ErrorReportingExtendedConfig()
    assert config.mode == ErrorReportingMode.USER_FRIENDLY
    assert config.show_stack_traces == False

    # Test from_dict
    config_dict = {
        "mode": "debug",
        "show_stack_traces": True,
        "max_error_history": 50,
    }
    config = ErrorReportingExtendedConfig.from_dict(config_dict)
    assert config.mode == ErrorReportingMode.DEBUG
    assert config.show_stack_traces == True
    assert config.max_error_history == 50

    print("[PASS] Error reporting configuration tests passed")


def test_video_renderer_config():
    """Test complete configuration."""
    print("Testing complete configuration...")

    # Test default config
    config = VideoRendererConfig()
    assert config.logging.level == LogLevel.INFO
    assert config.error_reporting.mode == ErrorReportingMode.USER_FRIENDLY

    # Test to_dict
    config_dict = config.to_dict()
    assert "logging" in config_dict
    assert "error_reporting" in config_dict

    # Test from_dict
    config2 = VideoRendererConfig.from_dict(config_dict)
    assert config2.logging.level == config.logging.level

    print("[PASS] Complete configuration tests passed")


def test_config_presets():
    """Test configuration presets."""
    print("Testing configuration presets...")

    # Development preset
    dev_config = ConfigPresets.development()
    assert dev_config.logging.level == LogLevel.DEBUG
    assert dev_config.error_reporting.mode == ErrorReportingMode.DEBUG

    # Production preset
    prod_config = ConfigPresets.production()
    assert prod_config.logging.level == LogLevel.INFO
    assert prod_config.error_reporting.mode == ErrorReportingMode.USER_FRIENDLY

    # Silent preset
    silent_config = ConfigPresets.silent()
    assert silent_config.logging.level == LogLevel.ERROR
    assert silent_config.error_reporting.mode == ErrorReportingMode.SILENT

    print("[PASS] Configuration preset tests passed")


def test_request_id_generation():
    """Test request ID generation."""
    print("Testing request ID generation...")

    req_id1 = generate_request_id()
    req_id2 = generate_request_id()

    assert req_id1 != req_id2
    assert len(req_id1) > 0

    print("[PASS] Request ID generation tests passed")


def test_session_id_generation():
    """Test session ID generation."""
    print("Testing session ID generation...")

    session_id1 = generate_session_id()
    session_id2 = generate_session_id()

    assert session_id1 != session_id2
    assert len(session_id1) > 0

    print("[PASS] Session ID generation tests passed")


def test_log_context():
    """Test log context management."""
    print("Testing log context management...")

    from video_renderer.logging import component_var, request_id_var

    # Test context manager
    with LogContext(request_id="test-123", component="TestComponent"):
        assert request_id_var.get() == "test-123"
        assert component_var.get() == "TestComponent"

    # Context should be reset
    assert request_id_var.get() == ""
    assert component_var.get() == ""

    print("[PASS] Log context tests passed")


def test_safe_execute():
    """Test safe execution wrapper."""
    print("Testing safe execution...")

    # Successful execution
    result = safe_execute(lambda x, y: x + y, 1, 2, default_return=None, raise_on_error=False)
    assert result == 3

    # Failed execution
    result = safe_execute(lambda x: 1 / x, 0, default_return=float("inf"), raise_on_error=False)
    assert result == float("inf")

    print("[PASS] Safe execution tests passed")


def test_handle_errors_decorator():
    """Test error handling decorator."""
    print("Testing error handling decorator...")

    @handle_errors(default_return=None, raise_on_error=False)
    def failing_function():
        raise ValueError("Test error")

    result = failing_function()
    assert result is None

    print("[PASS] Error handling decorator tests passed")


def test_json_formatter():
    """Test JSON formatter."""
    print("Testing JSON formatter...")

    import logging

    formatter = JSONFormatter()
    record = logging.LogRecord(
        name="test",
        level=logging.INFO,
        pathname="test.py",
        lineno=1,
        msg="Test message",
        args=(),
        exc_info=None,
    )

    formatted = formatter.format(record)
    log_data = json.loads(formatted)

    assert log_data["level"] == "INFO"
    assert log_data["message"] == "Test message"
    assert "timestamp" in log_data

    print("[PASS] JSON formatter tests passed")


def test_error_aggregator():
    """Test error aggregator."""
    print("Testing error aggregator...")

    aggregator = ErrorAggregator()

    # Report an error
    exc = ValueError("Test error")
    record = aggregator.report_error(exc, request_id="test-123")

    assert record.exception_type == "ValueError"
    assert record.request_id == "test-123"

    # Get summary
    summary = aggregator.get_error_summary()
    assert summary["total_errors"] == 1
    assert "ValueError" in summary["by_component"]

    print("[PASS] Error aggregator tests passed")


def test_error_record_serialization():
    """Test error record serialization."""
    print("Testing error record serialization...")

    record = ErrorRecord(
        timestamp=datetime.now(),
        exception_type="TestError",
        message="Test message",
        user_message="User message",
        component="TestComponent",
        operation="test_operation",
        severity=ErrorSeverity.ERROR,
        recovery_possible=True,
        suggested_action="Try again",
        stack_trace=None,
        request_id="test-123",
        context={"key": "value"},
    )

    record_dict = record.to_dict()
    assert record_dict["exception_type"] == "TestError"
    assert record_dict["component"] == "TestComponent"
    assert record_dict["request_id"] == "test-123"

    print("[PASS] Error record serialization tests passed")


# ═══════════════════════════════════════════════════════════════════════════════
# Main Test Runner
# ═══════════════════════════════════════════════════════════════════════════════


def run_tests():
    """Run all tests."""
    print("\n" + "=" * 60)
    print("Error Handling and Logging Tests")
    print("=" * 60 + "\n")

    tests = [
        test_exception_hierarchy,
        test_audio_validation_error,
        test_video_compatibility_error,
        test_user_message,
        test_logging_config,
        test_error_reporting_config,
        test_video_renderer_config,
        test_config_presets,
        test_request_id_generation,
        test_session_id_generation,
        test_log_context,
        test_safe_execute,
        test_handle_errors_decorator,
        test_json_formatter,
        test_error_aggregator,
        test_error_record_serialization,
    ]

    passed = 0
    failed = 0

    for test in tests:
        try:
            test()
            passed += 1
        except Exception as e:
            print(f"[FAIL] {test.__name__} failed: {e}")
            failed += 1
        print()

    print("=" * 60)
    print(f"Tests passed: {passed}/{passed + failed}")
    print(f"Tests failed: {failed}/{passed + failed}")
    print("=" * 60)

    return failed == 0


if __name__ == "__main__":
    success = run_tests()
    sys.exit(0 if success else 1)

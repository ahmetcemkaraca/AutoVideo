#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Custom exception hierarchy for video renderer.

Provides structured exception handling with detailed error context,
user-friendly messages, and debug information.
"""

import sys
import traceback
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Union


# ═══════════════════════════════════════════════════════════════════════════════
# Error Severity Levels
# ═══════════════════════════════════════════════════════════════════════════════

class ErrorSeverity(Enum):
    """Severity levels for error classification."""
    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


# ═══════════════════════════════════════════════════════════════════════════════
# Error Context Data
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class ErrorContext:
    """
    Structured context information for errors.

    Attributes:
        severity: Error severity level
        component: Component/module where error occurred
        operation: Operation being performed
        file_path: Associated file path (if any)
        command: Command that caused error (if any)
        exit_code: Process exit code (if applicable)
        stdout: Standard output from process
        stderr: Standard error from process
        stack_trace: Python stack trace
        timestamp: When error occurred
        user_action: Suggested user action
        technical_details: Additional technical information
        recovery_possible: Whether error is recoverable
    """
    severity: ErrorSeverity = ErrorSeverity.ERROR
    component: Optional[str] = None
    operation: Optional[str] = None
    file_path: Optional[Path] = None
    command: Optional[List[str]] = None
    exit_code: Optional[int] = None
    stdout: Optional[str] = None
    stderr: Optional[str] = None
    stack_trace: Optional[str] = None
    timestamp: Optional[str] = None
    user_action: Optional[str] = None
    technical_details: Dict[str, Any] = field(default_factory=dict)
    recovery_possible: bool = False

    def to_dict(self) -> Dict[str, Any]:
        """Convert context to dictionary for serialization."""
        return {
            "severity": self.severity.value if isinstance(self.severity, ErrorSeverity) else self.severity,
            "component": self.component,
            "operation": self.operation,
            "file_path": str(self.file_path) if self.file_path else None,
            "command": self.command,
            "exit_code": self.exit_code,
            "stdout": self.stdout,
            "stderr": self.stderr,
            "stack_trace": self.stack_trace,
            "timestamp": self.timestamp,
            "user_action": self.user_action,
            "technical_details": self.technical_details,
            "recovery_possible": self.recovery_possible,
        }


# ═══════════════════════════════════════════════════════════════════════════════
# Base Exception Classes
# ═══════════════════════════════════════════════════════════════════════════════

class VideoRendererError(Exception):
    """
    Base exception for all video renderer errors.

    Provides structured error information with context, user-friendly messages,
    and technical details for debugging.

    Attributes:
        message: Human-readable error message
        details: Dictionary of additional error details
        context: Structured error context
        original_exception: Original exception if wrapping another error
    """

    def __init__(
        self,
        message: str,
        details: Optional[Dict[str, Any]] = None,
        context: Optional[ErrorContext] = None,
        original_exception: Optional[Exception] = None
    ):
        self.message = message
        self.details = details or {}
        self.context = context or ErrorContext()
        self.original_exception = original_exception

        # Set default component if not provided
        if self.context.component is None:
            self.context.component = self.__class__.__name__

        # Capture stack trace if not provided
        if self.context.stack_trace is None:
            self.context.stack_trace = traceback.format_exc()

        # Build full error message
        full_message = self._build_message()
        super().__init__(full_message)

    def _build_message(self) -> str:
        """Build the full error message with context."""
        parts = [self.message]

        if self.context.operation:
            parts.append(f"\n  Operation: {self.context.operation}")

        if self.context.file_path:
            parts.append(f"\n  File: {self.context.file_path}")

        if self.details:
            parts.append("\n  Details:")
            for key, value in self.details.items():
                if isinstance(value, (str, int, float, bool)):
                    parts.append(f"    {key}: {value}")
                else:
                    parts.append(f"    {key}: {type(value).__name__}")

        if self.context.user_action:
            parts.append(f"\n  Suggested action: {self.context.user_action}")

        return "".join(parts)

    def to_dict(self) -> Dict[str, Any]:
        """Convert exception to dictionary for logging/serialization."""
        return {
            "exception_type": self.__class__.__name__,
            "message": self.message,
            "details": self.details,
            "context": self.context.to_dict(),
            "original_exception": str(self.original_exception) if self.original_exception else None,
        }

    def __str__(self) -> str:
        return self._build_message()


# ═══════════════════════════════════════════════════════════════════════════════
# FFmpeg Related Exceptions
# ═══════════════════════════════════════════════════════════════════════════════

class FFmpegError(VideoRendererError):
    """
    Base exception for FFmpeg-related errors.

    Used when FFmpeg commands fail, files cannot be processed,
    or encoding/decoding issues occur.
    """

    def __init__(
        self,
        message: str,
        command: Optional[List[str]] = None,
        exit_code: Optional[int] = None,
        stderr: Optional[str] = None,
        file_path: Optional[Path] = None,
        **kwargs
    ):
        context = kwargs.pop('context', ErrorContext())
        context.command = command
        context.exit_code = exit_code
        context.stderr = stderr
        context.file_path = file_path
        context.operation = "ffmpeg_execution"

        details = kwargs.pop('details', {})
        if command:
            details['command'] = ' '.join(command)
        if exit_code is not None:
            details['exit_code'] = exit_code

        super().__init__(message, details=details, context=context, **kwargs)


class FFmpegNotFoundError(FFmpegError):
    """
    Raised when FFmpeg is not found or not executable.

    Suggested action: Install FFmpeg and ensure it's in PATH.
    """

    def __init__(self, ffmpeg_path: Optional[str] = None):
        message = f"FFmpeg not found at {ffmpeg_path}" if ffmpeg_path else "FFmpeg not found in PATH"

        context = ErrorContext(
            severity=ErrorSeverity.CRITICAL,
            component="FFmpeg",
            operation="ffmpeg_detection",
            user_action="Install FFmpeg and ensure it's in your system PATH. "
                       "Visit https://ffmpeg.org/download.html for instructions.",
            recovery_possible=False,
            technical_details={"ffmpeg_path": ffmpeg_path}
        )

        super().__init__(message, context=context)


class FFmpegCommandError(FFmpegError):
    """
    Raised when an FFmpeg command fails during execution.
    """

    def __init__(
        self,
        message: str,
        command: List[str],
        exit_code: int,
        stderr: str,
        file_path: Optional[Path] = None
    ):
        # Parse common FFmpeg errors for user-friendly messages
        user_action = self._parse_ffmpeg_error(stderr)

        context = ErrorContext(
            severity=ErrorSeverity.ERROR,
            component="FFmpeg",
            operation="command_execution",
            command=command,
            exit_code=exit_code,
            stderr=stderr,
            file_path=file_path,
            user_action=user_action,
            recovery_possible=True
        )

        super().__init__(message, command=command, exit_code=exit_code,
                        stderr=stderr, file_path=file_path, context=context)

    def _parse_ffmpeg_error(self, stderr: str) -> Optional[str]:
        """Parse FFmpeg stderr to provide helpful user actions."""
        stderr_lower = stderr.lower()

        if "no such file" in stderr_lower or "cannot open" in stderr_lower:
            return "Check that the input file exists and is accessible."

        if "invalid data" in stderr_lower:
            return "The input file may be corrupted. Try re-downloading or re-encoding it."

        if "codec not found" in stderr_lower:
            return "The required codec is not available. Install FFmpeg with full codec support."

        if "permission denied" in stderr_lower:
            return "Check file permissions. Ensure you have read access to input and write access to output directory."

        if "out of memory" in stderr_lower or "cannot allocate" in stderr_lower:
            return "System is low on memory. Close other applications or reduce output quality."

        if "hardware acceleration" in stderr_lower or "cuda" in stderr_lower:
            return "Hardware acceleration failed. The system will fall back to software encoding."

        return None


class FFmpegTimeoutError(FFmpegError):
    """
    Raised when an FFmpeg command times out.
    """

    def __init__(self, command: List[str], timeout_seconds: int, file_path: Optional[Path] = None):
        message = f"FFmpeg command timed out after {timeout_seconds} seconds"

        context = ErrorContext(
            severity=ErrorSeverity.WARNING,
            component="FFmpeg",
            operation="command_execution",
            command=command,
            file_path=file_path,
            user_action="The operation may be processing a very large file. "
                       "Consider increasing timeout or breaking into smaller chunks.",
            recovery_possible=True,
            technical_details={"timeout_seconds": timeout_seconds}
        )

        super().__init__(message, context=context)


# ═══════════════════════════════════════════════════════════════════════════════
# Audio Processing Exceptions
# ═══════════════════════════════════════════════════════════════════════════════

class AudioProcessingError(VideoRendererError):
    """
    Base exception for audio processing errors.
    """

    def __init__(self, message: str, file_path: Optional[Path] = None, **kwargs):
        context = kwargs.pop('context', ErrorContext())
        context.file_path = file_path
        context.operation = "audio_processing"

        super().__init__(message, context=context, **kwargs)


class AudioValidationError(AudioProcessingError):
    """
    Raised when audio file validation fails.
    """

    def __init__(self, file_path: Path, reason: str):
        message = f"Audio validation failed: {file_path.name}"

        context = ErrorContext(
            severity=ErrorSeverity.WARNING,
            component="AudioProcessor",
            operation="validation",
            file_path=file_path,
            user_action=f"Remove or replace the corrupted file: {file_path.name}",
            recovery_possible=True,
            technical_details={"validation_reason": reason}
        )

        super().__init__(message, file_path=file_path, context=context)


class AudioMixingError(AudioProcessingError):
    """
    Raised when audio mixing fails.
    """

    def __init__(self, tracks: List[Path], reason: str):
        track_names = [t.name for t in tracks]
        message = f"Failed to mix audio tracks: {', '.join(track_names)}"

        context = ErrorContext(
            severity=ErrorSeverity.ERROR,
            component="AudioProcessor",
            operation="audio_mixing",
            user_action="Check that all audio files have compatible formats and sample rates.",
            recovery_possible=True,
            technical_details={"tracks": track_names, "reason": reason}
        )

        super().__init__(message, context=context)


class AudioLoopError(AudioProcessingError):
    """
    Raised when audio looping fails or produces invalid output.
    """

    def __init__(self, track_path: Path, target_duration: int, actual_duration: float):
        message = f"Audio looping produced unexpected duration for {track_path.name}"

        context = ErrorContext(
            severity=ErrorSeverity.ERROR,
            component="AudioProcessor",
            operation="audio_looping",
            file_path=track_path,
            user_action="Check the source audio file for corruption or unusual format.",
            recovery_possible=True,
            technical_details={
                "target_duration": target_duration,
                "actual_duration": actual_duration,
                "duration_diff": abs(target_duration - actual_duration)
            }
        )

        super().__init__(message, file_path=track_path, context=context)


# ═══════════════════════════════════════════════════════════════════════════════
# Video Processing Exceptions
# ═══════════════════════════════════════════════════════════════════════════════

class VideoProcessingError(VideoRendererError):
    """
    Base exception for video processing errors.
    """

    def __init__(self, message: str, file_path: Optional[Path] = None, **kwargs):
        context = kwargs.pop('context', ErrorContext())
        context.file_path = file_path

        super().__init__(message, context=context, **kwargs)


class VideoCompatibilityError(VideoProcessingError):
    """
    Raised when video compatibility check fails.
    """

    def __init__(self, file_path: Path, reason: str, current_specs: Optional[Dict[str, Any]] = None):
        message = f"Video compatibility check failed: {reason}"

        context = ErrorContext(
            severity=ErrorSeverity.INFO,
            component="VideoEncoder",
            operation="compatibility_check",
            file_path=file_path,
            user_action="The video will be re-encoded to match target specifications.",
            recovery_possible=True,
            technical_details={
                "compatibility_reason": reason,
                "current_specs": current_specs or {}
            }
        )

        super().__init__(message, file_path=file_path, context=context)


class VideoEncodingError(VideoProcessingError):
    """
    Raised when video encoding fails.
    """

    def __init__(self, file_path: Path, codec: str, reason: str):
        message = f"Video encoding failed for {file_path.name} with codec {codec}"

        context = ErrorContext(
            severity=ErrorSeverity.ERROR,
            component="VideoEncoder",
            operation="encoding",
            file_path=file_path,
            user_action="Try using a different codec or check available hardware encoders with --list-hw.",
            recovery_possible=True,
            technical_details={"codec": codec, "encoding_reason": reason}
        )

        super().__init__(message, file_path=file_path, context=context)


class VideoConcatError(VideoProcessingError):
    """
    Raised when video concatenation fails.
    """

    def __init__(self, intro_path: Path, loop_path: Path, reason: str):
        message = f"Video concatenation failed for {intro_path.name} + {loop_path.name}"

        context = ErrorContext(
            severity=ErrorSeverity.ERROR,
            component="VideoEncoder",
            operation="concatenation",
            user_action="Ensure both videos have the same codec, resolution, and frame rate.",
            recovery_possible=True,
            technical_details={
                "intro_path": str(intro_path),
                "loop_path": str(loop_path),
                "reason": reason
            }
        )

        super().__init__(message, context=context)


# ═══════════════════════════════════════════════════════════════════════════════
# Validation Exceptions
# ═══════════════════════════════════════════════════════════════════════════════

class ValidationError(VideoRendererError):
    """
    Base exception for validation errors.
    """

    def __init__(self, message: str, field: Optional[str] = None, **kwargs):
        context = kwargs.pop('context', ErrorContext())
        context.operation = "validation"

        details = kwargs.pop('details', {})
        if field:
            details['field'] = field

        super().__init__(message, details=details, context=context, **kwargs)


class FileValidationError(ValidationError):
    """
    Raised when file validation fails.
    """

    def __init__(self, file_path: Path, reason: str):
        message = f"File validation failed: {file_path.name} - {reason}"

        context = ErrorContext(
            severity=ErrorSeverity.ERROR,
            component="Validator",
            operation="file_validation",
            file_path=file_path,
            user_action="Check that the file exists and is a valid media file.",
            recovery_possible=False,
            technical_details={"validation_reason": reason}
        )

        super().__init__(message, context=context)


class ConfigValidationError(ValidationError):
    """
    Raised when configuration validation fails.
    """

    def __init__(self, config_path: Optional[Path], field: str, reason: str):
        message = f"Configuration validation failed: {field} - {reason}"

        context = ErrorContext(
            severity=ErrorSeverity.ERROR,
            component="Config",
            operation="config_validation",
            user_action="Fix the configuration value and restart.",
            recovery_possible=False,
            technical_details={"config_path": str(config_path) if config_path else None, "field": field}
        )

        super().__init__(message, field=field, context=context)


class DurationValidationError(ValidationError):
    """
    Raised when duration validation fails.
    """

    def __init__(self, duration: int, min_value: int, max_value: int):
        message = f"Duration {duration} is outside valid range [{min_value}, {max_value}]"

        context = ErrorContext(
            severity=ErrorSeverity.ERROR,
            component="Validator",
            operation="duration_validation",
            user_action=f"Set duration between {min_value} and {max_value} seconds.",
            recovery_possible=False,
            technical_details={"duration": duration, "min": min_value, "max": max_value}
        )

        super().__init__(message, context=context)


# ═══════════════════════════════════════════════════════════════════════════════
# State and Persistence Exceptions
# ═══════════════════════════════════════════════════════════════════════════════

class StateError(VideoRendererError):
    """
    Base exception for state management errors.
    """

    def __init__(self, message: str, state_path: Optional[Path] = None, **kwargs):
        context = kwargs.pop('context', ErrorContext())
        context.operation = "state_management"
        context.file_path = state_path

        super().__init__(message, context=context, **kwargs)


class StateLoadError(StateError):
    """
    Raised when state file cannot be loaded.
    """

    def __init__(self, state_path: Path, reason: str):
        message = f"Failed to load state from {state_path.name}"

        context = ErrorContext(
            severity=ErrorSeverity.WARNING,
            component="StateManager",
            operation="state_load",
            file_path=state_path,
            user_action="The application will start with a fresh state. "
                       "Previous session data may be lost.",
            recovery_possible=True,
            technical_details={"load_reason": reason}
        )

        super().__init__(message, state_path=state_path, context=context)


class StateSaveError(StateError):
    """
    Raised when state cannot be saved.
    """

    def __init__(self, state_path: Path, reason: str):
        message = f"Failed to save state to {state_path.name}"

        context = ErrorContext(
            severity=ErrorSeverity.ERROR,
            component="StateManager",
            operation="state_save",
            file_path=state_path,
            user_action="Check disk space and file permissions. State may not persist between sessions.",
            recovery_possible=True,
            technical_details={"save_reason": reason}
        )

        super().__init__(message, state_path=state_path, context=context)


class StateCorruptedError(StateError):
    """
    Raised when state file is corrupted.
    """

    def __init__(self, state_path: Path, parse_error: str):
        message = f"State file is corrupted: {state_path.name}"

        context = ErrorContext(
            severity=ErrorSeverity.WARNING,
            component="StateManager",
            operation="state_parse",
            file_path=state_path,
            user_action="The corrupted state will be backed up and a fresh state created.",
            recovery_possible=True,
            technical_details={"parse_error": parse_error}
        )

        super().__init__(message, state_path=state_path, context=context)


# ═══════════════════════════════════════════════════════════════════════════════
# Batch Processing Exceptions
# ═══════════════════════════════════════════════════════════════════════════════

class BatchProcessingError(VideoRendererError):
    """
    Base exception for batch processing errors.
    """

    def __init__(self, message: str, job_id: Optional[str] = None, **kwargs):
        context = kwargs.pop('context', ErrorContext())
        context.operation = "batch_processing"

        details = kwargs.pop('details', {})
        if job_id:
            details['job_id'] = job_id

        super().__init__(message, details=details, context=context, **kwargs)


class BatchJobError(BatchProcessingError):
    """
    Raised when a batch job fails.
    """

    def __init__(self, job_id: str, reason: str, can_retry: bool = True):
        message = f"Batch job {job_id} failed: {reason}"

        context = ErrorContext(
            severity=ErrorSeverity.ERROR,
            component="BatchQueue",
            operation="job_execution",
            user_action="Retry the job or check the error details for more information.",
            recovery_possible=can_retry,
            technical_details={"job_id": job_id, "failure_reason": reason, "can_retry": can_retry}
        )

        super().__init__(message, job_id=job_id, context=context)


class BatchQueueError(BatchProcessingError):
    """
    Raised when batch queue operations fail.
    """

    def __init__(self, operation: str, reason: str):
        message = f"Batch queue operation failed: {operation}"

        context = ErrorContext(
            severity=ErrorSeverity.ERROR,
            component="BatchQueue",
            operation=operation,
            user_action="Check queue state and try again.",
            recovery_possible=True,
            technical_details={"queue_operation": operation, "reason": reason}
        )

        super().__init__(message, context=context)


# ═══════════════════════════════════════════════════════════════════════════════
# External Service Exceptions
# ═══════════════════════════════════════════════════════════════════════════════

class ExternalServiceError(VideoRendererError):
    """
    Base exception for external service errors (YouTube, Drive, etc.).
    """

    def __init__(self, message: str, service: str, **kwargs):
        context = kwargs.pop('context', ErrorContext())
        context.component = service
        context.operation = "external_service"

        super().__init__(message, context=context, **kwargs)


class YouTubeError(ExternalServiceError):
    """
    Raised when YouTube operations fail.
    """

    def __init__(self, operation: str, reason: str, status_code: Optional[int] = None):
        message = f"YouTube {operation} failed: {reason}"

        context = ErrorContext(
            severity=ErrorSeverity.ERROR,
            component="YouTube",
            operation=operation,
            user_action="Check your internet connection and API credentials.",
            recovery_possible=True,
            technical_details={"operation": operation, "status_code": status_code}
        )

        super().__init__(message, service="YouTube", context=context)


class DriveError(ExternalServiceError):
    """
    Raised when Google Drive operations fail.
    """

    def __init__(self, operation: str, reason: str):
        message = f"Google Drive {operation} failed: {reason}"

        context = ErrorContext(
            severity=ErrorSeverity.ERROR,
            component="Drive",
            operation=operation,
            user_action="Check your internet connection and API credentials.",
            recovery_possible=True,
            technical_details={"operation": operation}
        )

        super().__init__(message, service="Drive", context=context)


# ═══════════════════════════════════════════════════════════════════════════════
# Utility Functions
# ═══════════════════════════════════════════════════════════════════════════════

def wrap_exception(
    exception: Exception,
    message: str,
    component: Optional[str] = None,
    operation: Optional[str] = None
) -> VideoRendererError:
    """
    Wrap a generic exception in a VideoRendererError.

    Args:
        exception: Original exception to wrap
        message: New error message
        component: Component where error occurred
        operation: Operation being performed

    Returns:
        VideoRendererError with original exception attached
    """
    context = ErrorContext(
        component=component or type(exception).__name__,
        operation=operation,
        original_exception=str(exception),
        stack_trace=traceback.format_exc()
    )

    return VideoRendererError(
        message=message,
        context=context,
        original_exception=exception
    )


def create_error_report(exception: Exception, include_traceback: bool = True) -> Dict[str, Any]:
    """
    Create a comprehensive error report from an exception.

    Args:
        exception: Exception to report
        include_traceback: Whether to include full stack trace

    Returns:
        Dictionary with error report data
    """
    if isinstance(exception, VideoRendererError):
        report = exception.to_dict()
    else:
        report = {
            "exception_type": type(exception).__name__,
            "message": str(exception),
            "context": {},
        }

    if include_traceback:
        report["traceback"] = traceback.format_exc()

    return report


def get_user_message(exception: Exception) -> str:
    """
    Get a user-friendly error message from any exception.

    Args:
        exception: Exception to convert

    Returns:
        User-friendly error message
    """
    if isinstance(exception, VideoRendererError):
        return exception.message

    # Generic exceptions
    exception_type = type(exception).__name__

    if isinstance(exception, FileNotFoundError):
        return f"File not found: {exception.filename}"

    if isinstance(exception, PermissionError):
        return "Permission denied. Check file permissions."

    if isinstance(exception, (MemoryError, OverflowError)):
        return "System resources exhausted. Try reducing output quality or duration."

    # Default
    return f"An error occurred: {exception_type}"

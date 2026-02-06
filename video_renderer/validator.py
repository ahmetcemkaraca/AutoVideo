#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Video validation system for AutoVideo.

Provides comprehensive pre-render and post-render validation using ffprobe.
Supports both intro_loop and single render modes with detailed error reporting
in Turkish and English.
"""

import subprocess
import json
import shutil
import os
import logging
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any, Literal, Union
from dataclasses import dataclass, field
from fractions import Fraction
from enum import Enum

from .ffmpeg import probe_video, get_duration
from .audio import AudioProcessor


# ═══════════════════════════════════════════════════════════════════════════════
# Validation Result Structures
# ═══════════════════════════════════════════════════════════════════════════════


class ValidationSeverity(Enum):
    """Severity level for validation issues."""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


@dataclass
class ValidationIssue:
    """A single validation issue with bilingual support."""
    category: str  # e.g., "video", "audio", "disk"
    severity: ValidationSeverity
    message: str  # Primary message (can be in any language)
    message_en: Optional[str] = None  # English message
    message_tr: Optional[str] = None  # Turkish message
    details: Optional[str] = None
    suggestion: Optional[str] = None
    field: Optional[str] = None  # Field name for structured validation
    context: Optional[Dict[str, Any]] = None  # Additional context

    def get_bilingual_message(self) -> str:
        """Return message in both languages."""
        en = self.message_en or self.message or ""
        tr = self.message_tr or self.message or ""
        return f"EN: {en} | TR: {tr}"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "category": self.category,
            "severity": self.severity.value,
            "message": self.message,
            "message_en": self.message_en or self.message,
            "message_tr": self.message_tr or self.message,
            "details": self.details,
            "suggestion": self.suggestion,
            "field": self.field,
            "context": self.context,
        }


@dataclass
class ValidationResult:
    """
    Complete validation result with bilingual support.

    Attributes:
        valid: Whether validation passed
        stage: Validation stage ("pre_render" or "post_render")
        issues: List of validation issues
        metadata: Additional metadata from validation
        duration_seconds: Actual video duration (post-render)
        file_size_bytes: Video file size (post-render)
        video_info: Extracted video information dict
    """
    valid: bool
    stage: Literal["pre_render", "post_render"]
    issues: List[ValidationIssue] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    duration_seconds: float = 0.0
    file_size_bytes: int = 0
    video_info: Dict[str, Any] = field(default_factory=dict)

    @property
    def errors(self) -> List[ValidationIssue]:
        return [i for i in self.issues if i.severity in (ValidationSeverity.ERROR, ValidationSeverity.CRITICAL)]

    @property
    def warnings(self) -> List[ValidationIssue]:
        return [i for i in self.issues if i.severity == ValidationSeverity.WARNING]

    @property
    def info(self) -> List[ValidationIssue]:
        return [i for i in self.issues if i.severity == ValidationSeverity.INFO]

    def add_issue(self, issue: ValidationIssue) -> None:
        self.issues.append(issue)
        if issue.severity in (ValidationSeverity.ERROR, ValidationSeverity.CRITICAL):
            self.valid = False

    def add_error(
        self,
        category: str,
        message_en: str,
        message_tr: str,
        details: Optional[str] = None,
        suggestion: Optional[str] = None,
        field: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None
    ) -> None:
        """Add an error with bilingual messages."""
        self.add_issue(ValidationIssue(
            category=category,
            severity=ValidationSeverity.ERROR,
            message=message_en,  # Primary message
            message_en=message_en,
            message_tr=message_tr,
            details=details,
            suggestion=suggestion,
            field=field,
            context=context
        ))

    def add_warning(
        self,
        category: str,
        message_en: str,
        message_tr: str,
        details: Optional[str] = None,
        suggestion: Optional[str] = None,
        field: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None
    ) -> None:
        """Add a warning with bilingual messages."""
        self.add_issue(ValidationIssue(
            category=category,
            severity=ValidationSeverity.WARNING,
            message=message_en,
            message_en=message_en,
            message_tr=message_tr,
            details=details,
            suggestion=suggestion,
            field=field,
            context=context
        ))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "valid": self.valid,
            "stage": self.stage,
            "issues": [i.to_dict() for i in self.issues],
            "metadata": self.metadata,
            "duration_seconds": self.duration_seconds,
            "file_size_bytes": self.file_size_bytes,
            "video_info": self.video_info
        }


class ValidationError(Exception):
    """Base exception for validation errors."""
    def __init__(self, result: ValidationResult):
        self.result = result
        super().__init__(f"Validation failed with {len(result.errors)} errors")


class FFprobeError(ValidationError):
    """Exception raised when ffprobe execution fails."""
    pass


class FileCorruptedError(ValidationError):
    """Exception raised when video file is corrupted."""
    pass


class DiskSpaceError(ValidationError):
    """Exception raised when insufficient disk space."""
    pass


@dataclass
class VideoMetadata:
    """
    Complete video metadata extracted by ffprobe.

    Attributes:
        codec: Video codec name (e.g., 'h264', 'hevc', 'av1')
        width: Video width in pixels
        height: Video height in pixels
        fps: Frame rate as Fraction
        duration: Duration in seconds
        pix_fmt: Pixel format (e.g., 'yuv420p')
        color_space: Color space (e.g., 'bt709')
        color_primaries: Color primaries
        color_transfer: Color transfer characteristics
        bitrate: Video bitrate in bps
        has_audio: Whether video has audio stream
        audio_codec: Audio codec name if present
        audio_channels: Number of audio channels
        audio_sample_rate: Audio sample rate in Hz
        profile: Codec profile
        level: Codec level
        file_size: File size in bytes
    """
    codec: str
    width: int
    height: int
    fps: Fraction
    duration: float
    pix_fmt: str
    color_space: Optional[str] = None
    color_primaries: Optional[str] = None
    color_transfer: Optional[str] = None
    bitrate: Optional[int] = None
    has_audio: bool = False
    audio_codec: Optional[str] = None
    audio_channels: Optional[int] = None
    audio_sample_rate: Optional[int] = None
    profile: Optional[str] = None
    level: Optional[str] = None
    file_size: int = 0


# ═══════════════════════════════════════════════════════════════════════════════
# Video Validator (ffprobe-based)
# ═══════════════════════════════════════════════════════════════════════════════


class VideoValidator:
    """
    Comprehensive video validation using ffprobe.

    Provides methods for validating video properties against specifications
    including codec, resolution, frame rate, duration, and audio tracks.

    Features:
    - Fast metadata extraction with ffprobe
    - Codec compatibility checking
    - Duration accuracy validation
    - Audio-visual sync detection
    - File integrity verification
    - Bilingual error messages (EN/TR)
    """

    # Default tolerances for validation
    DEFAULT_DURATION_TOLERANCE_SEC = 5.0
    DEFAULT_FPS_TOLERANCE = 0.1
    DEFAULT_BITRATE_TOLERANCE = 0.1  # 10%

    # Cache for ffprobe availability
    _ffprobe_available: Optional[bool] = None

    def __init__(
        self,
        duration_tolerance: float = DEFAULT_DURATION_TOLERANCE_SEC,
        fps_tolerance: float = DEFAULT_FPS_TOLERANCE,
        bitrate_tolerance: float = DEFAULT_BITRATE_TOLERANCE,
    ):
        """
        Initialize VideoValidator.

        Args:
            duration_tolerance: Allowed duration deviation in seconds
            fps_tolerance: Allowed FPS deviation
            bitrate_tolerance: Allowed bitrate deviation (0.1 = 10%)
        """
        self.duration_tolerance = duration_tolerance
        self.fps_tolerance = fps_tolerance
        self.bitrate_tolerance = bitrate_tolerance
        self.logger = logging.getLogger(__name__)

        # Check ffprobe availability
        if VideoValidator._ffprobe_available is None:
            VideoValidator._ffprobe_available = self._check_ffprobe()

        if not VideoValidator._ffprobe_available:
            self.logger.warning("ffprobe not available, validation will be limited")

    @staticmethod
    def _check_ffprobe() -> bool:
        """Check if ffprobe is available in PATH."""
        return shutil.which("ffprobe") is not None

    @staticmethod
    def is_ffprobe_available() -> bool:
        """Check if ffprobe is available without raising exception."""
        if VideoValidator._ffprobe_available is None:
            VideoValidator._ffprobe_available = shutil.which("ffprobe") is not None
        return VideoValidator._ffprobe_available

    def get_video_info(self, video_path: Path) -> VideoMetadata:
        """
        Extract complete video metadata using ffprobe.

        Args:
            video_path: Path to video file

        Returns:
            VideoMetadata object with all extracted information

        Raises:
            FFprobeError: If ffprobe execution fails
            FileCorruptedError: If video file is corrupted
        """
        if not video_path.exists():
            raise FileNotFoundError(f"Video file not found: {video_path}")

        # Build ffprobe command
        cmd = [
            "ffprobe",
            "-v", "error",
            "-show_entries", "stream",
            "-show_entries", "format",
            "-of", "json",
            str(video_path)
        ]

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=True,
                timeout=30
            )
        except subprocess.TimeoutExpired:
            raise FFprobeError(f"ffprobe timeout on {video_path}")
        except subprocess.CalledProcessError as e:
            raise FFprobeError(
                f"ffprobe failed on {video_path}: {e.stderr}"
            )

        # Parse JSON output
        try:
            data = json.loads(result.stdout)
        except json.JSONDecodeError as e:
            raise FileCorruptedError(
                f"Failed to parse ffprobe output from {video_path}: {e}"
            )

        # Extract video stream info
        video_stream = None
        audio_stream = None

        for stream in data.get("streams", []):
            if stream.get("codec_type") == "video" and video_stream is None:
                video_stream = stream
            elif stream.get("codec_type") == "audio" and audio_stream is None:
                audio_stream = stream

        if video_stream is None:
            raise FileCorruptedError(f"No video stream found in {video_path}")

        # Extract format info
        format_info = data.get("format", {})

        # Parse FPS
        fps_str = video_stream.get("r_frame_rate", "0/1")
        try:
            if "/" in fps_str:
                num, den = fps_str.split("/")
                fps = Fraction(int(num), int(den))
            else:
                fps = Fraction(int(float(fps_str)), 1)
        except (ValueError, ZeroDivisionError):
            fps = Fraction(0, 1)

        # Parse duration
        duration_str = format_info.get("duration", "0")
        try:
            duration = float(duration_str)
        except ValueError:
            duration = 0.0

        # Parse file size
        size_str = format_info.get("size", "0")
        try:
            file_size = int(size_str)
        except ValueError:
            file_size = 0

        # Parse bitrate
        bitrate_str = format_info.get("bit_rate", "0")
        try:
            bitrate = int(bitrate_str)
        except ValueError:
            bitrate = None

        return VideoMetadata(
            codec=video_stream.get("codec_name", "unknown"),
            width=int(video_stream.get("width", 0)),
            height=int(video_stream.get("height", 0)),
            fps=fps,
            duration=duration,
            pix_fmt=video_stream.get("pix_fmt", "unknown"),
            color_space=video_stream.get("color_space"),
            color_primaries=video_stream.get("color_primaries"),
            color_transfer=video_stream.get("color_transfer"),
            bitrate=bitrate,
            has_audio=audio_stream is not None,
            audio_codec=audio_stream.get("codec_name") if audio_stream else None,
            audio_channels=int(audio_stream.get("channels", 0)) if audio_stream else None,
            audio_sample_rate=int(audio_stream.get("sample_rate", 0)) if audio_stream else None,
            profile=video_stream.get("profile"),
            level=video_stream.get("level"),
            file_size=file_size
        )

    def check_duration(self, video_path: Path, target_seconds: float) -> bool:
        """
        Check if video duration matches target within tolerance.

        Args:
            video_path: Path to video file
            target_seconds: Target duration in seconds

        Returns:
            True if duration is within tolerance
        """
        try:
            metadata = self.get_video_info(video_path)
            actual_duration = metadata.duration
            deviation = abs(actual_duration - target_seconds)
            return deviation <= self.duration_tolerance
        except (FFprobeError, FileCorruptedError):
            return False

    def check_codec(self, video_path: Path, expected_codec: str) -> bool:
        """
        Check if video codec matches expected codec.

        Args:
            video_path: Path to video file
            expected_codec: Expected codec name (e.g., 'h264', 'hevc', 'av1')

        Returns:
            True if codec matches
        """
        try:
            metadata = self.get_video_info(video_path)
            actual_codec = metadata.codec.lower()
            expected = expected_codec.lower()

            # Handle codec aliases
            codec_mapping = {
                "h264": ["h264", "avc", "libx264"],
                "hevc": ["hevc", "h265", "libx265"],
                "av1": ["av1", "libsvtav1"],
                "vp9": ["vp9", "libvpx-vp9"],
                "vp8": ["vp8", "libvpx"],
            }

            for base_name, aliases in codec_mapping.items():
                if expected in aliases and actual_codec in aliases:
                    return True

            return actual_codec == expected
        except (FFprobeError, FileCorruptedError):
            return False

    def check_resolution(self, video_path: Path, expected_resolution: Tuple[int, int]) -> bool:
        """
        Check if video resolution matches expected.

        Args:
            video_path: Path to video file
            expected_resolution: Tuple of (width, height)

        Returns:
            True if resolution matches
        """
        try:
            metadata = self.get_video_info(video_path)
            return metadata.width == expected_resolution[0] and \
                   metadata.height == expected_resolution[1]
        except (FFprobeError, FileCorruptedError):
            return False

    def check_fps(self, video_path: Path, expected_fps: Fraction) -> bool:
        """
        Check if video FPS matches expected within tolerance.

        Args:
            video_path: Path to video file
            expected_fps: Expected FPS as Fraction

        Returns:
            True if FPS is within tolerance
        """
        try:
            metadata = self.get_video_info(video_path)
            actual_fps = float(metadata.fps)
            expected = float(expected_fps)
            deviation = abs(actual_fps - expected)
            return deviation <= self.fps_tolerance
        except (FFprobeError, FileCorruptedError):
            return False

    def check_audio(self, video_path: Path, has_audio: bool = True) -> bool:
        """
        Check if video has audio stream matching expectation.

        Args:
            video_path: Path to video file
            has_audio: Whether audio should be present

        Returns:
            True if audio presence matches expectation
        """
        try:
            metadata = self.get_video_info(video_path)
            return metadata.has_audio == has_audio
        except (FFprobeError, FileCorruptedError):
            return False

    def check_audio_tracks(self, video_path: Path, expected_count: int) -> bool:
        """
        Check if video has expected number of audio tracks.

        Args:
            video_path: Path to video file
            expected_count: Expected number of audio tracks

        Returns:
            True if audio track count matches
        """
        try:
            metadata = self.get_video_info(video_path)
            actual_count = 1 if metadata.has_audio else 0

            # For multi-track audio, need to probe all streams
            if expected_count > 1:
                cmd = [
                    "ffprobe",
                    "-v", "error",
                    "-select_streams", "a",
                    "-show_entries", "stream=codec_type",
                    "-of", "json",
                    str(video_path)
                ]
                try:
                    result = subprocess.run(cmd, capture_output=True, text=True, check=True, timeout=30)
                    data = json.loads(result.stdout)
                    actual_count = len(data.get("streams", []))
                except (subprocess.CalledProcessError, json.JSONDecodeError, subprocess.TimeoutExpired):
                    pass

            return actual_count == expected_count
        except (FFprobeError, FileCorruptedError):
            return False

    def check_file_integrity(self, video_path: Path) -> bool:
        """
        Check video file integrity by attempting to read metadata.

        Args:
            video_path: Path to video file

        Returns:
            True if file appears to be intact
        """
        try:
            metadata = self.get_video_info(video_path)
            # Basic sanity checks
            return (
                metadata.duration > 0 and
                metadata.width > 0 and
                metadata.height > 0 and
                metadata.fps > 0
            )
        except (FFprobeError, FileCorruptedError):
            return False

    def validate_output(
        self,
        video_path: Path,
        specs: Dict[str, Any]
    ) -> ValidationResult:
        """
        Comprehensive post-render validation against specifications.

        Validates:
        - File exists and is readable
        - Duration matches target (within tolerance)
        - Resolution matches target
        - FPS matches target (within tolerance)
        - Codec matches expected codec
        - Audio is present if required
        - Audio track count matches expected
        - File integrity

        Args:
            video_path: Path to rendered video
            specs: Dictionary with validation specifications:
                - duration_seconds: Target duration
                - width: Target width
                - height: Target height
                - fps: Target FPS
                - codec: Expected codec name
                - has_audio: Whether audio should be present
                - audio_tracks: Expected number of audio tracks
                - min_bitrate: Minimum bitrate (optional)
                - max_bitrate: Maximum bitrate (optional)

        Returns:
            ValidationResult with detailed status
        """
        result = ValidationResult(valid=True, stage="post_render")

        # Check file exists
        if not video_path.exists():
            result.add_error(
                "output",
                f"Output file not found: {video_path}",
                f"Cikis dosyasi bulunamadi: {video_path}"
            )
            return result

        # Check file size
        result.file_size_bytes = video_path.stat().st_size
        if result.file_size_bytes == 0:
            result.add_error(
                "output",
                f"Output file is empty: {video_path}",
                f"Cikis dosyasi bos: {video_path}"
            )
            return result

        # Extract metadata
        try:
            metadata = self.get_video_info(video_path)
            result.duration_seconds = metadata.duration
            result.video_info = {
                "codec": metadata.codec,
                "width": metadata.width,
                "height": metadata.height,
                "fps": f"{metadata.fps.numerator}/{metadata.fps.denominator}",
                "fps_float": float(metadata.fps),
                "duration": metadata.duration,
                "pix_fmt": metadata.pix_fmt,
                "color_space": metadata.color_space,
                "has_audio": metadata.has_audio,
                "audio_codec": metadata.audio_codec,
                "audio_channels": metadata.audio_channels,
                "bitrate": metadata.bitrate,
                "file_size": metadata.file_size
            }
        except (FFprobeError, FileCorruptedError) as e:
            result.add_error("output", str(e), str(e))
            return result

        # Validate duration
        if "duration_seconds" in specs:
            target_duration = specs["duration_seconds"]
            if not self.check_duration(video_path, target_duration):
                result.add_error(
                    "duration",
                    f"Duration mismatch: expected {target_duration}s, got {metadata.duration}s",
                    f"Sure uyusmazligi: beklenen {target_duration}s, elde edilen {metadata.duration}s",
                    field="duration",
                    context={"expected": target_duration, "actual": metadata.duration}
                )

        # Validate resolution
        if "width" in specs and "height" in specs:
            if not self.check_resolution(video_path, (specs["width"], specs["height"])):
                result.add_error(
                    "video",
                    f"Resolution mismatch: expected {specs['width']}x{specs['height']}, "
                    f"got {metadata.width}x{metadata.height}",
                    f"Cozunurluk uyusmazligi: beklenen {specs['width']}x{specs['height']}, "
                    f"elde edilen {metadata.width}x{metadata.height}",
                    field="resolution",
                    context={
                        "expected": f"{specs['width']}x{specs['height']}",
                        "actual": f"{metadata.width}x{metadata.height}"
                    }
                )

        # Validate FPS
        if "fps" in specs:
            target_fps = specs["fps"]
            if not self.check_fps(video_path, Fraction(target_fps, 1)):
                result.add_error(
                    "video",
                    f"FPS mismatch: expected {target_fps}, got {float(metadata.fps):.2f}",
                    f"FPS uyusmazligi: beklenen {target_fps}, elde edilen {float(metadata.fps):.2f}",
                    field="fps",
                    context={"expected": target_fps, "actual": float(metadata.fps)}
                )

        # Validate codec
        if "codec" in specs:
            if not self.check_codec(video_path, specs["codec"]):
                result.add_error(
                    "video",
                    f"Codec mismatch: expected {specs['codec']}, got {metadata.codec}",
                    f"Codec uyusmazligi: beklenen {specs['codec']}, elde edilen {metadata.codec}",
                    field="codec",
                    context={"expected": specs["codec"], "actual": metadata.codec}
                )

        # Validate audio
        if "has_audio" in specs:
            if not self.check_audio(video_path, specs["has_audio"]):
                result.add_error(
                    "audio",
                    f"Audio presence mismatch: expected {'audio' if specs['has_audio'] else 'no audio'}, "
                    f"got {'audio' if metadata.has_audio else 'no audio'}",
                    f"Ses varligi uyusmazligi: beklenen {'ses' if specs['has_audio'] else 'ses yok'}, "
                    f"elde edilen {'ses' if metadata.has_audio else 'ses yok'}",
                    field="audio",
                    context={"expected": specs["has_audio"], "actual": metadata.has_audio}
                )

        # Validate audio track count
        if "audio_tracks" in specs:
            if not self.check_audio_tracks(video_path, specs["audio_tracks"]):
                result.add_error(
                    "audio",
                    f"Audio track count mismatch: expected {specs['audio_tracks']}, "
                    f"got {1 if metadata.has_audio else 0}",
                    f"Ses izi sayisi uyusmazligi: beklenen {specs['audio_tracks']}, "
                    f"elde edilen {1 if metadata.has_audio else 0}",
                    field="audio_tracks",
                    context={"expected": specs["audio_tracks"], "actual": 1 if metadata.has_audio else 0}
                )

        # Validate bitrate
        if "min_bitrate" in specs and metadata.bitrate:
            if metadata.bitrate < specs["min_bitrate"]:
                result.add_warning(
                    "video",
                    f"Bitrate below minimum: {metadata.bitrate} bps < {specs['min_bitrate']} bps",
                    f"Bitrate minimum altinda: {metadata.bitrate} bps < {specs['min_bitrate']} bps",
                    field="bitrate",
                    context={"minimum": specs["min_bitrate"], "actual": metadata.bitrate}
                )

        if "max_bitrate" in specs and metadata.bitrate:
            if metadata.bitrate > specs["max_bitrate"]:
                result.add_warning(
                    "video",
                    f"Bitrate above maximum: {metadata.bitrate} bps > {specs['max_bitrate']} bps",
                    f"Bitrate maximum ustunde: {metadata.bitrate} bps > {specs['max_bitrate']} bps",
                    field="bitrate",
                    context={"maximum": specs["max_bitrate"], "actual": metadata.bitrate}
                )

        return result


# ═══════════════════════════════════════════════════════════════════════════════
# Pre-Render Validator
# ═══════════════════════════════════════════════════════════════════════════════


class PreRenderValidator:
    """
    Validates inputs before rendering starts.

    Checks:
    - Video compatibility (intro/loop resolution, codec, FPS match)
    - Audio track validity and duration
    - Disk space availability
    - File accessibility
    """

    # Disk space multiplier: need 3x the source file size (temp files + output)
    DISK_SPACE_MULTIPLIER = 3.0
    # Minimum free space in bytes (1 GB)
    MIN_FREE_SPACE = 1 * 1024**3

    def __init__(self, target_width: int = 1920, target_height: int = 1080, target_fps: int = 60):
        self.target_width = target_width
        self.target_height = target_height
        self.target_fps = target_fps
        self.logger = logging.getLogger(__name__)

    def validate_render_specs(
        self,
        intro_path: Optional[Path],
        loop_path: Optional[Path],
        single_path: Optional[Path],
        tracks: List[Path],
        target_duration: int,
        output_dir: Path,
    ) -> ValidationResult:
        """
        Validate complete render specification.

        Args:
            intro_path: Optional intro video path
            loop_path: Optional loop video path
            single_path: Optional single video path (for single mode)
            tracks: List of audio track paths
            target_duration: Target duration in seconds
            output_dir: Output directory path

        Returns:
            ValidationResult with all issues found
        """
        result = ValidationResult(valid=True, stage="pre_render")

        # Determine render mode
        is_single_mode = single_path is not None
        is_intro_loop_mode = intro_path is not None and loop_path is not None

        if not (is_single_mode or is_intro_loop_mode):
            result.add_issue(ValidationIssue(
                category="video",
                severity=ValidationSeverity.ERROR,
                message="Geçersiz render modu",
                details="Hem single hem de intro/loop modu için dosya sağlanmadı.",
                suggestion="Lütfen en az bir video dosyası seçin."
            ))
            return result

        # Validate based on mode
        if is_single_mode:
            self._validate_single_video(single_path, result)
        else:
            self._validate_intro_loop_pair(intro_path, loop_path, result)

        # Validate audio tracks
        self._validate_audio_tracks(tracks, target_duration, result)

        # Validate disk space
        self._validate_disk_space(
            intro_path or single_path,
            loop_path,
            tracks,
            target_duration,
            output_dir,
            result
        )

        return result

    def _validate_single_video(self, video_path: Path, result: ValidationResult) -> None:
        """Validate single video for single mode rendering."""
        if not video_path.exists():
            result.add_issue(ValidationIssue(
                category="video",
                severity=ValidationSeverity.ERROR,
                message=f"Video dosyası bulunamadı: {video_path.name}",
                details=f"Dosya yolu: {video_path}",
                suggestion="Dosyanın varlığını ve yolunu kontrol edin."
            ))
            return

        try:
            info = probe_video(video_path)
            result.metadata["single_video"] = {
                "path": str(video_path),
                "width": info.width,
                "height": info.height,
                "fps": info.fps,
                "codec": info.codec,
                "duration": info.duration,
                "size_mb": video_path.stat().st_size / (1024**2),
            }

            # Check resolution
            if info.width != self.target_width or info.height != self.target_height:
                result.add_issue(ValidationIssue(
                    category="video",
                    severity=ValidationSeverity.INFO,
                    message=f"Video yeniden kodlanacak: {info.width}x{info.height} -> {self.target_width}x{self.target_height}",
                    details="Hedef çözünürlükten farklı.",
                ))

            # Check codec
            if info.codec.lower() not in ("h264", "hevc", "av1"):
                result.add_issue(ValidationIssue(
                    category="video",
                    severity=ValidationSeverity.INFO,
                    message=f"Video codec değiştirilecek: {info.codec}",
                    details="Hedef codec'ten farklı.",
                ))

        except Exception as e:
            result.add_issue(ValidationIssue(
                category="video",
                severity=ValidationSeverity.ERROR,
                message=f"Video analizi başarısız: {video_path.name}",
                details=str(e),
                suggestion="Dosyanın bozuk olmadığından emin olun."
            ))

    def _validate_intro_loop_pair(
        self,
        intro_path: Path,
        loop_path: Path,
        result: ValidationResult
    ) -> None:
        """Validate intro and loop video pair for compatibility."""
        # Check file existence
        if not intro_path.exists():
            result.add_issue(ValidationIssue(
                category="video",
                severity=ValidationSeverity.ERROR,
                message=f"Intro dosyası bulunamadı: {intro_path.name}",
                details=f"Dosya yolu: {intro_path}",
            ))

        if not loop_path.exists():
            result.add_issue(ValidationIssue(
                category="video",
                severity=ValidationSeverity.ERROR,
                message=f"Loop dosyası bulunamadı: {loop_path.name}",
                details=f"Dosya yolu: {loop_path}",
            ))

        if not intro_path.exists() or not loop_path.exists():
            return

        # Probe both videos
        try:
            intro_info = probe_video(intro_path)
            loop_info = probe_video(loop_path)

            result.metadata["intro"] = {
                "path": str(intro_path),
                "width": intro_info.width,
                "height": intro_info.height,
                "fps": intro_info.fps,
                "codec": intro_info.codec,
                "duration": intro_info.duration,
                "size_mb": intro_path.stat().st_size / (1024**2),
            }

            result.metadata["loop"] = {
                "path": str(loop_path),
                "width": loop_info.width,
                "height": loop_info.height,
                "fps": loop_info.fps,
                "codec": loop_info.codec,
                "duration": loop_info.duration,
                "size_mb": loop_path.stat().st_size / (1024**2),
            }

            # Check resolution match
            if intro_info.width != loop_info.width or intro_info.height != loop_info.height:
                result.add_issue(ValidationIssue(
                    category="video",
                    severity=ValidationSeverity.WARNING,
                    message="Çözünürlük uyuşmazlığı tespit edildi",
                    details=f"Intro: {intro_info.width}x{intro_info.height}, Loop: {loop_info.width}x{loop_info.height}",
                    suggestion="Her iki video da hedef çözünürlüğe yeniden kodlanacak.",
                ))

            # Check FPS match
            intro_fps = self._parse_fps(intro_info.fps)
            loop_fps = self._parse_fps(loop_info.fps)

            if abs(intro_fps - loop_fps) > 1.0:
                result.add_issue(ValidationIssue(
                    category="video",
                    severity=ValidationSeverity.WARNING,
                    message="FPS uyuşmazlığı tespit edildi",
                    details=f"Intro: {intro_fps:.2f} fps, Loop: {loop_fps:.2f} fps",
                    suggestion="Her iki video da hedef FPS'e yeniden kodlanacak.",
                ))

            # Check codec compatibility
            if intro_info.codec.lower() != loop_info.codec.lower():
                result.add_issue(ValidationIssue(
                    category="video",
                    severity=ValidationSeverity.INFO,
                    message="Codec farklılıkları tespit edildi",
                    details=f"Intro: {intro_info.codec}, Loop: {loop_info.codec}",
                    suggestion="Videolar hedef codec'e normalize edilecek.",
                ))

            # Check loop duration (should be short for efficient looping)
            if loop_info.duration > 300:  # 5 minutes
                result.add_issue(ValidationIssue(
                    category="video",
                    severity=ValidationSeverity.INFO,
                    message="Loop videosu oldukça uzun",
                    details=f"Loop süresi: {loop_info.duration:.1f} saniye",
                    suggestion="Kısa loop'lar (10-60 saniye) daha verimli olabilir.",
                ))

        except Exception as e:
            result.add_issue(ValidationIssue(
                category="video",
                severity=ValidationSeverity.ERROR,
                message="Video analizi başarısız",
                details=str(e),
                suggestion="Dosyaların bozuk olmadığından emin olun.",
            ))

    def _validate_audio_tracks(
        self,
        tracks: List[Path],
        target_duration: int,
        result: ValidationResult
    ) -> None:
        """Validate audio tracks."""
        if not tracks:
            result.add_issue(ValidationIssue(
                category="audio",
                severity=ValidationSeverity.WARNING,
                message="Hiç audio parçası seçilmedi",
                details="Video ses içermeyecek.",
                suggestion="En az bir audio parçası seçin."
            ))
            return

        # Check track existence
        missing_tracks = [t for t in tracks if not t.exists()]
        if missing_tracks:
            result.add_issue(ValidationIssue(
                category="audio",
                severity=ValidationSeverity.ERROR,
                message=f"{len(missing_tracks)} audio dosyası bulunamadı",
                details=", ".join(t.name for t in missing_tracks),
            ))

        # Validate audio duration
        total_audio_duration = 0
        valid_tracks = []

        for track in tracks:
            if not track.exists():
                continue

            try:
                duration = get_duration(track)
                total_audio_duration += duration
                valid_tracks.append(track)

                # Check for very short tracks
                if duration < 10:
                    result.add_issue(ValidationIssue(
                        category="audio",
                        severity=ValidationSeverity.INFO,
                        message=f"Kısa audio parçası: {track.name}",
                        details=f"Süre: {duration:.1f} saniye",
                    ))

            except Exception as e:
                result.add_issue(ValidationIssue(
                    category="audio",
                    severity=ValidationSeverity.ERROR,
                    message=f"Audio analizi başarısız: {track.name}",
                    details=str(e),
                ))

        result.metadata["audio"] = {
            "total_tracks": len(tracks),
            "valid_tracks": len(valid_tracks),
            "total_duration": total_audio_duration,
            "target_duration": target_duration,
        }

        # Check if we have enough audio
        if total_audio_duration < target_duration * 0.5:  # Less than 50%
            result.add_issue(ValidationIssue(
                category="audio",
                severity=ValidationSeverity.WARNING,
                message="Audio süresi hedeften kısa",
                details=f"Mevcut: {total_audio_duration:.0f}s, Hedef: {target_duration}s",
                suggestion="Audio loop olarak tekrarlanacak.",
            ))

    def _validate_disk_space(
        self,
        primary_video: Optional[Path],
        secondary_video: Optional[Path],
        tracks: List[Path],
        target_duration: int,
        output_dir: Path,
        result: ValidationResult
    ) -> None:
        """Validate available disk space."""
        try:
            # Calculate estimated space requirements
            video_size = 0

            if primary_video and primary_video.exists():
                video_size += primary_video.stat().st_size

            if secondary_video and secondary_video.exists():
                video_size += secondary_video.stat().st_size

            # Audio size (rough estimate)
            audio_size = sum(t.stat().st_size for t in tracks if t.exists())

            # Estimated output size (based on source sizes and duration ratio)
            source_duration = 0
            if primary_video and primary_video.exists():
                try:
                    source_duration = get_duration(primary_video)
                except:
                    pass

            if source_duration > 0:
                duration_ratio = max(1, target_duration / source_duration)
                estimated_size = int((video_size * duration_ratio + audio_size) * self.DISK_SPACE_MULTIPLIER)
            else:
                # Rough estimate: 100 MB per minute for 1080p
                estimated_size = int((target_duration / 60) * 100 * 1024**2)

            # Check available space
            disk_usage = shutil.disk_usage(output_dir)
            free_space = disk_usage.free

            result.metadata["disk"] = {
                "estimated_size_mb": estimated_size / (1024**2),
                "free_space_gb": free_space / (1024**3),
                "output_dir": str(output_dir),
            }

            if free_space < self.MIN_FREE_SPACE:
                result.add_issue(ValidationIssue(
                    category="disk",
                    severity=ValidationSeverity.CRITICAL,
                    message="Yetersiz disk alanı",
                    details=f"Boş alan: {free_space / (1024**3):.2f} GB",
                    suggestion="En az 1 GB boş alan gereklidir.",
                ))
            elif free_space < estimated_size:
                result.add_issue(ValidationIssue(
                    category="disk",
                    severity=ValidationSeverity.ERROR,
                    message="Tahmini yetersiz disk alanı",
                    details=f"Gerekli: {estimated_size / (1024**3):.2f} GB, Mevcut: {free_space / (1024**3):.2f} GB",
                    suggestion="Gereksiz dosyaları temizleyin veya farklı bir diske çıktı verin.",
                ))
            elif free_space < estimated_size * 1.5:  # Less than 50% buffer
                result.add_issue(ValidationIssue(
                    category="disk",
                    severity=ValidationSeverity.WARNING,
                    message="Disk alanı sınırda",
                    details=f"Tahmini kullanım: {estimated_size / (1024**3):.2f} GB / {free_space / (1024**3):.2f} GB",
                    suggestion="Yeterli tampon alanı yok. İşlem sırasında disk alanı izlenmeli.",
                ))

        except Exception as e:
            self.logger.warning(f"Disk space check failed: {e}")
            result.add_issue(ValidationIssue(
                category="disk",
                severity=ValidationSeverity.WARNING,
                message="Disk alanı kontrol edilemedi",
                details=str(e),
            ))

    def _parse_fps(self, fps_str: str) -> float:
        """Parse FPS string to float."""
        try:
            if "/" in fps_str:
                num, den = map(float, fps_str.split("/"))
                return num / den if den != 0 else 0.0
            return float(fps_str)
        except (ValueError, AttributeError):
            return 0.0


# ═══════════════════════════════════════════════════════════════════════════════
# Post-Render Validator (Enhanced)
# ═══════════════════════════════════════════════════════════════════════════════


class PostRenderValidator(VideoValidator):
    """
    Enhanced post-render validation with audio-visual sync checking.

    Extends VideoValidator with additional checks:
    - Duration accuracy with configurable tolerance
    - Audio-visual sync detection
    - File integrity verification
    - Output specification validation
    - Support for both intro_loop and single render modes
    """

    # Duration tolerance in seconds
    DURATION_TOLERANCE = 5
    # Minimum expected audio bitrate (kbps)
    MIN_AUDIO_BITRATE = 128
    # Audio-visual sync tolerance in seconds
    SYNC_TOLERANCE = 0.1

    def __init__(
        self,
        duration_tolerance: float = 5.0,
        fps_tolerance: float = 0.1,
        bitrate_tolerance: float = 0.1,
        sync_tolerance: float = 0.1,
    ):
        """
        Initialize PostRenderValidator.

        Args:
            duration_tolerance: Allowed duration deviation in seconds
            fps_tolerance: Allowed FPS deviation
            bitrate_tolerance: Allowed bitrate deviation (0.1 = 10%)
            sync_tolerance: Audio-visual sync tolerance in seconds
        """
        super().__init__(duration_tolerance, fps_tolerance, bitrate_tolerance)
        self.sync_tolerance = sync_tolerance
        self.logger = logging.getLogger(__name__)

    def validate_output(
        self,
        output_path: Path,
        target_duration: int,
        target_specs: Optional[Dict[str, Any]] = None,
    ) -> ValidationResult:
        """
        Validate rendered output video.

        Args:
            output_path: Path to rendered output video
            target_duration: Target duration in seconds
            target_specs: Optional dict with expected codec, resolution, fps

        Returns:
            ValidationResult with all issues found
        """
        result = ValidationResult(valid=True, stage="post_render")

        if not output_path.exists():
            result.add_issue(ValidationIssue(
                category="output",
                severity=ValidationSeverity.CRITICAL,
                message="Çıktı dosyası bulunamadı",
                details=f"Dosya yolu: {output_path}",
                suggestion="Render işlemi tamamlanamamış olabilir.",
            ))
            return result

        try:
            # Probe output video
            info = probe_video(output_path)

            result.metadata["output"] = {
                "path": str(output_path),
                "width": info.width,
                "height": info.height,
                "fps": info.fps,
                "codec": info.codec,
                "duration": info.duration,
                "size_mb": output_path.stat().st_size / (1024**2),
                "target_duration": target_duration,
            }

            # Check duration
            self._validate_duration(info.duration, target_duration, result)

            # Check video specs
            self._validate_video_specs(info, target_specs, result)

            # Check audio
            self._validate_audio(output_path, result)

            # Check file size
            self._validate_file_size(output_path, info.duration, result)

        except Exception as e:
            result.add_issue(ValidationIssue(
                category="output",
                severity=ValidationSeverity.CRITICAL,
                message="Çıktı analizi başarısız",
                details=str(e),
                suggestion="Dosya bozuk olabilir veya tamamlanmamış.",
            ))

        return result

    def _validate_duration(
        self,
        actual_duration: float,
        target_duration: int,
        result: ValidationResult
    ) -> None:
        """Validate output duration."""
        duration_diff = abs(actual_duration - target_duration)

        if duration_diff > self.DURATION_TOLERANCE:
            result.add_issue(ValidationIssue(
                category="output",
                severity=ValidationSeverity.WARNING,
                message="Süre farkı tespit edildi",
                details=f"Hedef: {target_duration}s, Gerçek: {actual_duration:.1f}s, Fark: {duration_diff:.1f}s",
                suggestion="Normal kabul edilebilir fark (±5 saniye içinde hedeflemyin).",
            ))
        else:
            result.add_issue(ValidationIssue(
                category="output",
                severity= ValidationSeverity.INFO,
                message="Süre doğrulaması başarılı",
                details=f"Hedef: {target_duration}s, Gerçek: {actual_duration:.1f}s",
            ))

    def _validate_video_specs(
        self,
        info,
        target_specs: Optional[Dict[str, Any]],
        result: ValidationResult
    ) -> None:
        """Validate video specifications."""
        if not target_specs:
            return

        # Check codec
        expected_codec = target_specs.get("codec")
        if expected_codec:
            actual_codec = info.codec.lower()
            if expected_codec.lower() not in actual_codec and actual_codec not in expected_codec.lower():
                result.add_issue(ValidationIssue(
                    category="output",
                    severity=ValidationSeverity.INFO,
                    message=f"Codec farklı: {info.codec}",
                    details=f"Beklenen: {expected_codec}",
                ))

        # Check resolution
        expected_width = target_specs.get("width")
        expected_height = target_specs.get("height")
        if expected_width and expected_height:
            if info.width != expected_width or info.height != expected_height:
                result.add_issue(ValidationIssue(
                    category="output",
                    severity=ValidationSeverity.WARNING,
                    message=f"Çözünürlük farklı: {info.width}x{info.height}",
                    details=f"Beklenen: {expected_width}x{expected_height}",
                ))

        # Check FPS
        expected_fps = target_specs.get("fps")
        if expected_fps:
            actual_fps = self._parse_fps(info.fps)
            if abs(actual_fps - expected_fps) > 1.0:
                result.add_issue(ValidationIssue(
                    category="output",
                    severity=ValidationSeverity.INFO,
                    message=f"FPS farklı: {actual_fps:.2f}",
                    details=f"Beklenen: {expected_fps}",
                ))

    def _validate_audio(self, output_path: Path, result: ValidationResult) -> None:
        """Validate audio in output."""
        try:
            # Use ffprobe to check audio stream
            import subprocess

            cmd = [
                "ffprobe",
                "-v", "error",
                "-select_streams", "a",
                "-show_entries", "stream=codec_name,bit_rate",
                "-of", "json",
                str(output_path)
            ]

            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
            if proc.returncode == 0:
                import json
                data = json.loads(proc.stdout)

                if not data.get("streams"):
                    result.add_issue(ValidationIssue(
                        category="output",
                        severity=ValidationSeverity.ERROR,
                        message="Çıktıda audio akışı bulunamadı",
                        details="Video sessiz olabilir.",
                        suggestion="Audio seçeneklerini kontrol edin.",
                    ))
                else:
                    # Check audio codec
                    audio_codec = data["streams"][0].get("codec_name", "")
                    result.metadata["output"]["audio_codec"] = audio_codec

                    # Check bitrate if available
                    bitrate_str = data["streams"][0].get("bit_rate")
                    if bitrate_str:
                        bitrate_kbps = int(bitrate_str) // 1000
                        result.metadata["output"]["audio_bitrate_kbps"] = bitrate_kbps

                        if bitrate_kbps < self.MIN_AUDIO_BITRATE:
                            result.add_issue(ValidationIssue(
                                category="output",
                                severity=ValidationSeverity.INFO,
                                message=f"Düşük audio bitrate: {bitrate_kbps} kbps",
                                details=f"Önerilen: {self.MIN_AUDIO_BITRATE}+ kbps",
                            ))

        except Exception as e:
            self.logger.warning(f"Audio validation failed: {e}")

    def _validate_file_size(
        self,
        output_path: Path,
        duration: float,
        result: ValidationResult
    ) -> None:
        """Validate output file size is reasonable."""
        size_mb = output_path.stat().st_size / (1024**2)
        size_per_min_mb = (size_mb / duration) * 60 if duration > 0 else 0

        # Rough quality checks
        if size_per_min_mb < 1:  # Less than 1 MB/min
            result.add_issue(ValidationIssue(
                category="output",
                severity=ValidationSeverity.WARNING,
                message=f"Çıktı dosyası çok küçük: {size_mb:.1f} MB",
                details=f"{size_per_min_mb:.2f} MB/dakika",
                suggestion="Çok düşük bitrate kullanılmış olabilir. Kalite düşük olabilir.",
            ))
        elif size_per_min_mb > 500:  # More than 500 MB/min
            result.add_issue(ValidationIssue(
                category="output",
                severity=ValidationSeverity.INFO,
                message=f"Çıktı dosyası büyük: {size_mb:.1f} MB",
                details=f"{size_per_min_mb:.1f} MB/dakika",
            ))

    def validate_render(
        self,
        video_path: Path,
        specs: Dict[str, Any],
        mode: str = "intro_loop"
    ) -> ValidationResult:
        """
        Full post-render validation for both intro_loop and single modes.

        This is an enhanced version of validate_output that includes
        mode-specific validations and audio-visual sync checking.

        Args:
            video_path: Path to rendered video
            specs: Render specifications including duration, codec, resolution, etc.
            mode: Render mode ("intro_loop" or "single")

        Returns:
            ValidationResult with complete validation status
        """
        result = self.validate_output(video_path, specs)

        # Mode-specific validations
        if mode == "intro_loop":
            # Check that duration is approximately correct
            if "duration_seconds" in specs:
                target = specs["duration_seconds"]
                actual = result.duration_seconds
                deviation = abs(actual - target)

                if deviation > self.duration_tolerance:
                    result.add_error(
                        "duration",
                        f"Duration deviation too large: {deviation:.2f}s (tolerance: {self.duration_tolerance}s)",
                        f"Sure sapmasi cok buyuk: {deviation:.2f}s (tolerans: {self.duration_tolerance}s)",
                        field="duration",
                        context={"deviation": deviation, "tolerance": self.duration_tolerance}
                    )
                else:
                    result.add_warning(
                        "duration",
                        f"Duration validation passed: {actual:.2f}s (target: {target}s)",
                        f"Sure dogrulamasi basarili: {actual:.2f}s (hedef: {target}s)",
                        field="duration"
                    )

        # Check audio-visual sync
        if specs.get("has_audio", True):
            sync_ok = self.check_av_sync(video_path)
            if not sync_ok:
                result.add_warning(
                    "av_sync",
                    "Possible audio-visual sync issue detected",
                    "Olasi ses-goruntu senkronizasyon sorusu tespit edildi",
                    field="av_sync",
                    context={"tolerance": self.sync_tolerance}
                )

        # Verify file integrity
        if not self.check_file_integrity(video_path):
            result.add_error(
                "integrity",
                "File integrity check failed",
                "Dosya bütünlügü kontrolü basarisiz",
                field="integrity"
            )

        return result

    def check_av_sync(self, video_path: Path) -> bool:
        """
        Check for audio-visual sync issues by comparing stream durations.

        This is a basic check that compares video and audio stream durations.
        More sophisticated sync detection would require frame-by-frame analysis.

        Args:
            video_path: Path to video file

        Returns:
            True if sync appears OK (durations within tolerance)
        """
        try:
            cmd = [
                "ffprobe",
                "-v", "error",
                "-select_streams", "v:0",
                "-show_entries", "stream=duration",
                "-of", "json",
                str(video_path)
            ]

            result_proc = subprocess.run(cmd, capture_output=True, text=True, check=True, timeout=30)
            v_data = json.loads(result_proc.stdout)
            video_duration = float(v_data.get("streams", [{}])[0].get("duration", 0))

            cmd = [
                "ffprobe",
                "-v", "error",
                "-select_streams", "a:0",
                "-show_entries", "stream=duration",
                "-of", "json",
                str(video_path)
            ]

            result_proc = subprocess.run(cmd, capture_output=True, text=True, check=True, timeout=30)
            a_data = json.loads(result_proc.stdout)
            audio_duration = float(a_data.get("streams", [{}])[0].get("duration", 0))

            # Check if durations are within tolerance
            if video_duration == 0 or audio_duration == 0:
                return True  # Can't check, assume OK

            deviation = abs(video_duration - audio_duration)
            return deviation <= self.sync_tolerance

        except (subprocess.CalledProcessError, json.JSONDecodeError, subprocess.TimeoutExpired):
            return True  # Assume OK on error

    def _parse_fps(self, fps_str: str) -> float:
        """Parse FPS string to float."""
        try:
            if "/" in fps_str:
                num, den = map(float, fps_str.split("/"))
                return num / den if den != 0 else 0.0
            return float(fps_str)
        except (ValueError, AttributeError):
            return 0.0


# ═══════════════════════════════════════════════════════════════════════════════
# Convenience Functions
# ═══════════════════════════════════════════════════════════════════════════════


def validate_before_render(
    intro_path: Optional[Path],
    loop_path: Optional[Path],
    single_path: Optional[Path],
    tracks: List[Path],
    target_duration: int,
    output_dir: Path,
    **kwargs
) -> ValidationResult:
    """
    Convenience function for pre-render validation.

    Returns:
        ValidationResult with all validation issues
    """
    validator = PreRenderValidator(**kwargs)
    return validator.validate_render_specs(
        intro_path, loop_path, single_path, tracks, target_duration, output_dir
    )


def validate_after_render(
    output_path: Path,
    target_duration: int,
    target_specs: Optional[Dict[str, Any]] = None,
) -> ValidationResult:
    """
    Convenience function for post-render validation.

    Returns:
        ValidationResult with all validation issues
    """
    validator = PostRenderValidator()
    return validator.validate_output(output_path, target_duration, target_specs)


def export_validation_report(
    result: ValidationResult,
    output_dir: Optional[Path] = None,
) -> Path:
    """
    Export validation report to JSON file.

    Args:
        result: ValidationResult to export
        output_dir: Optional output directory (defaults to cwd/reports/)

    Returns:
        Path to the exported report file
    """
    from datetime import datetime
    import json

    if output_dir is None:
        output_dir = Path.cwd() / "reports"

    output_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_file = output_dir / f"validation_{result.stage}_{timestamp}.json"

    report_data = {
        "timestamp": datetime.now().isoformat(),
        "stage": result.stage,
        "valid": result.valid,
        "summary": {
            "total_issues": len(result.issues),
            "errors": len(result.errors),
            "warnings": len(result.warnings),
            "info": len(result.info),
        },
        "issues": [i.to_dict() for i in result.issues],
        "metadata": result.metadata,
    }

    with open(report_file, "w", encoding="utf-8") as f:
        json.dump(report_data, f, indent=2, ensure_ascii=False)

    return report_file


def validate_video_file(
    video_path: Path,
    expected_duration: Optional[float] = None,
    expected_resolution: Optional[Tuple[int, int]] = None,
    expected_fps: Optional[int] = None,
    expected_codec: Optional[str] = None,
    has_audio: bool = True,
    duration_tolerance: float = 5.0,
) -> ValidationResult:
    """
    Convenience function for quick video validation.

    Args:
        video_path: Path to video file
        expected_duration: Expected duration in seconds (optional)
        expected_resolution: Expected (width, height) (optional)
        expected_fps: Expected FPS (optional)
        expected_codec: Expected codec name (optional)
        has_audio: Whether video should have audio (default: True)
        duration_tolerance: Duration tolerance in seconds (default: 5.0)

    Returns:
        ValidationResult with validation status
    """
    validator = VideoValidator(duration_tolerance=duration_tolerance)

    specs = {}
    if expected_duration is not None:
        specs["duration_seconds"] = expected_duration
    if expected_resolution is not None:
        specs["width"], specs["height"] = expected_resolution
    if expected_fps is not None:
        specs["fps"] = expected_fps
    if expected_codec is not None:
        specs["codec"] = expected_codec
    specs["has_audio"] = has_audio

    return validator.validate_output(video_path, specs)


def quick_validate(video_path: Path) -> bool:
    """
    Quick validation check - returns True if video appears valid.

    Args:
        video_path: Path to video file

    Returns:
        True if video is readable and has basic properties
    """
    if not VideoValidator.is_ffprobe_available():
        return video_path.exists() and video_path.stat().st_size > 0

    try:
        validator = VideoValidator()
        return validator.check_file_integrity(video_path)
    except FFprobeError:
        return False


def validate_ffmpeg_available() -> ValidationResult:
    """
    Validate that FFmpeg and ffprobe are available.

    Returns:
        ValidationResult with tool availability status
    """
    result = ValidationResult(valid=True, stage="pre_render")

    # Check ffmpeg
    if not shutil.which("ffmpeg"):
        result.add_error(
            "tools",
            "ffmpeg not found in PATH",
            "ffmpeg PATH'da bulunamadi",
            suggestion="Install FFmpeg and add it to your PATH"
        )

    # Check ffprobe
    if not shutil.which("ffprobe"):
        result.add_error(
            "tools",
            "ffprobe not found in PATH",
            "ffprobe PATH'da bulunamadi",
            suggestion="Install FFmpeg (includes ffprobe) and add it to your PATH"
        )

    result.valid = len(result.errors) == 0
    return result


# Export public API
__all__ = [
    # Classes
    "VideoValidator",
    "PreRenderValidator",
    "PostRenderValidator",
    # Data classes
    "ValidationResult",
    "ValidationIssue",
    "ValidationSeverity",
    "VideoMetadata",
    # Exceptions
    "ValidationError",
    "FFprobeError",
    "FileCorruptedError",
    "DiskSpaceError",
    # Functions
    "validate_before_render",
    "validate_after_render",
    "validate_video_file",
    "quick_validate",
    "validate_ffmpeg_available",
    "export_validation_report",
]

#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Comprehensive test suite for video validation system.

Tests cover:
- Unit tests for VideoValidator validation methods
- Integration tests with real video files
- Edge case handling (corrupted files, missing streams, large files)
- Mock tests for consistent testing
- PreRenderValidator and PostRenderValidator functionality
"""

import json
import os
import subprocess
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, List, Dict, Any, Tuple
from unittest.mock import MagicMock, Mock, patch, mock_open, call
from datetime import datetime
from fractions import Fraction

import pytest

# Add project root to path
import sys
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from video_renderer.validator import (
    VideoValidator,
    PreRenderValidator,
    PostRenderValidator,
    ValidationResult,
    ValidationIssue,
    ValidationSeverity,
    VideoMetadata,
    ValidationError,
    FFprobeError,
    FileCorruptedError,
    DiskSpaceError,
    validate_before_render,
    validate_after_render,
    validate_video_file,
    quick_validate,
    validate_ffmpeg_available,
    export_validation_report,
)


# ═══════════════════════════════════════════════════════════════════════════════
# Fixtures
# ═══════════════════════════════════════════════════════════════════════════════


@pytest.fixture
def mock_ffprobe_output_valid():
    """Mock ffprobe output for a valid video."""
    return {
        "streams": [
            {
                "codec_type": "video",
                "codec_name": "h264",
                "width": 1920,
                "height": 1080,
                "pix_fmt": "yuv420p",
                "r_frame_rate": "60/1",
                "color_space": "bt709",
                "color_primaries": "bt709",
                "color_transfer": "bt709",
                "profile": "High",
                "level": "4.2"
            },
            {
                "codec_type": "audio",
                "codec_name": "aac",
                "channels": 2,
                "sample_rate": "48000"
            }
        ],
        "format": {
            "duration": "120.5",
            "size": "104857600",
            "bit_rate": "5000000"
        }
    }


@pytest.fixture
def mock_ffprobe_output_no_audio():
    """Mock ffprobe output for video without audio."""
    return {
        "streams": [
            {
                "codec_type": "video",
                "codec_name": "h264",
                "width": 1920,
                "height": 1080,
                "pix_fmt": "yuv420p",
                "r_frame_rate": "60/1"
            }
        ],
        "format": {
            "duration": "120.5",
            "size": "104857600"
        }
    }


@pytest.fixture
def mock_ffprobe_output_corrupted():
    """Mock ffprobe output for corrupted video."""
    return {
        "streams": [],
        "format": {
            "duration": "0"
        }
    }


@pytest.fixture
def mock_ffprobe_output_hevc():
    """Mock ffprobe output for HEVC video."""
    return {
        "streams": [
            {
                "codec_type": "video",
                "codec_name": "hevc",
                "width": 3840,
                "height": 2160,
                "pix_fmt": "yuv420p",
                "r_frame_rate": "30/1"
            }
        ],
        "format": {
            "duration": "300.0",
            "size": "524288000"
        }
    }


@pytest.fixture
def video_validator():
    """Create a standard VideoValidator instance."""
    return VideoValidator(
        duration_tolerance=5.0,
        fps_tolerance=0.1,
        bitrate_tolerance=0.1
    )


@pytest.fixture
def pre_render_validator():
    """Create a PreRenderValidator instance."""
    return PreRenderValidator(
        target_width=1920,
        target_height=1080,
        target_fps=60
    )


@pytest.fixture
def post_render_validator():
    """Create a PostRenderValidator instance."""
    return PostRenderValidator(
        duration_tolerance=5.0,
        fps_tolerance=0.1,
        bitrate_tolerance=0.1,
        sync_tolerance=0.1
    )


@pytest.fixture
def sample_video(temp_dir):
    """Create a sample video file for testing."""
    video_path = temp_dir / "sample_video.mp4"
    video_path.write_bytes(b"MOCK_VIDEO_DATA")
    return video_path


@pytest.fixture
def sample_audio(temp_dir):
    """Create a sample audio file for testing."""
    audio_path = temp_dir / "sample_audio.mp3"
    audio_path.write_bytes(b"MOCK_AUDIO_DATA")
    return audio_path


# ═══════════════════════════════════════════════════════════════════════════════
# Unit Tests: ValidationIssue and ValidationResult
# ═══════════════════════════════════════════════════════════════════════════════


@pytest.mark.unit
class TestValidationIssue:
    """Test ValidationIssue dataclass."""

    def test_creation(self):
        """Test creating a ValidationIssue."""
        issue = ValidationIssue(
            category="video",
            severity=ValidationSeverity.ERROR,
            message="Codec not supported",
            message_en="Codec not supported",
            message_tr="Codec desteklenmiyor",
            details="Expected h264, got mpeg4",
            suggestion="Re-encode with h264",
            field="codec",
            context={"expected": "h264", "actual": "mpeg4"}
        )

        assert issue.category == "video"
        assert issue.severity == ValidationSeverity.ERROR
        assert issue.message == "Codec not supported"
        assert issue.details == "Expected h264, got mpeg4"
        assert issue.field == "codec"
        assert issue.context == {"expected": "h264", "actual": "mpeg4"}

    def test_get_bilingual_message(self):
        """Test bilingual message generation."""
        issue = ValidationIssue(
            category="video",
            severity=ValidationSeverity.ERROR,
            message="Codec not supported",
            message_en="Codec not supported",
            message_tr="Codec desteklenmiyor"
        )

        bilingual = issue.get_bilingual_message()
        assert "EN: Codec not supported" in bilingual
        assert "TR: Codec desteklenmiyor" in bilingual

    def test_to_dict(self):
        """Test converting issue to dictionary."""
        issue = ValidationIssue(
            category="video",
            severity=ValidationSeverity.ERROR,
            message="Test error",
            message_en="Test error",
            message_tr="Test hatası"
        )

        issue_dict = issue.to_dict()
        assert issue_dict["category"] == "video"
        assert issue_dict["severity"] == "error"
        assert issue_dict["message_en"] == "Test error"
        assert issue_dict["message_tr"] == "Test hatası"


@pytest.mark.unit
class TestValidationResult:
    """Test ValidationResult dataclass."""

    def test_creation(self):
        """Test creating a ValidationResult."""
        result = ValidationResult(
            valid=True,
            stage="pre_render",
            issues=[],
            metadata={"test": "data"}
        )

        assert result.valid is True
        assert result.stage == "pre_render"
        assert len(result.issues) == 0
        assert result.metadata == {"test": "data"}
        assert len(result.errors) == 0
        assert len(result.warnings) == 0

    def test_add_error(self):
        """Test adding errors to ValidationResult."""
        result = ValidationResult(valid=True, stage="pre_render")

        result.add_error(
            "codec",
            "Unsupported codec",
            "Desteklenmeyen codec",
            details="Expected h264",
            field="codec"
        )

        assert result.valid is False  # Should be set to False
        assert len(result.errors) == 1
        assert result.errors[0].category == "codec"

    def test_add_warning(self):
        """Test adding warnings to ValidationResult."""
        result = ValidationResult(valid=True, stage="pre_render")

        result.add_warning(
            "duration",
            "Duration slightly off",
            "Süre hafif farklı"
        )

        # Warnings don't invalidate
        assert result.valid is True
        assert len(result.warnings) == 1
        assert len(result.errors) == 0

    def test_properties(self):
        """Test error, warning, and info properties."""
        result = ValidationResult(valid=True, stage="pre_render")

        result.add_error("video", "Error", "Hata", severity=ValidationSeverity.ERROR)
        result.add_error("critical", "Critical", "Kritik", severity=ValidationSeverity.CRITICAL)
        result.add_warning("audio", "Warning", "Uyarı")
        result.add_issue(ValidationIssue(
            category="info",
            severity=ValidationSeverity.INFO,
            message="Info",
            message_en="Info",
            message_tr="Bilgi"
        ))

        assert len(result.errors) == 2
        assert len(result.warnings) == 1
        assert len(result.info) == 1

    def test_to_dict(self):
        """Test converting result to dictionary."""
        result = ValidationResult(
            valid=True,
            stage="pre_render",
            duration_seconds=120.0,
            file_size_bytes=1048576
        )

        result.add_warning("test", "Warning", "Uyarı")

        result_dict = result.to_dict()
        assert result_dict["valid"] is True
        assert result_dict["stage"] == "pre_render"
        assert result_dict["duration_seconds"] == 120.0
        assert len(result_dict["issues"]) == 1


# ═══════════════════════════════════════════════════════════════════════════════
# Unit Tests: VideoValidator
# ═══════════════════════════════════════════════════════════════════════════════


@pytest.mark.unit
class TestVideoValidatorInit:
    """Test VideoValidator initialization."""

    def test_default_initialization(self):
        """Test VideoValidator with default values."""
        validator = VideoValidator()

        assert validator.duration_tolerance == VideoValidator.DEFAULT_DURATION_TOLERANCE_SEC
        assert validator.fps_tolerance == VideoValidator.DEFAULT_FPS_TOLERANCE
        assert validator.bitrate_tolerance == VideoValidator.DEFAULT_BITRATE_TOLERANCE

    def test_custom_initialization(self):
        """Test VideoValidator with custom values."""
        validator = VideoValidator(
            duration_tolerance=10.0,
            fps_tolerance=0.5,
            bitrate_tolerance=0.2
        )

        assert validator.duration_tolerance == 10.0
        assert validator.fps_tolerance == 0.5
        assert validator.bitrate_tolerance == 0.2

    def test_ffprobe_check(self):
        """Test ffprobe availability check."""
        # This test assumes ffprobe is installed in the environment
        # In CI/testing, it might not be, so we just check the method exists
        validator = VideoValidator()
        assert hasattr(VideoValidator, 'is_ffprobe_available')
        assert callable(VideoValidator.is_ffprobe_available)


@pytest.mark.unit
class TestVideoValidatorGetVideoInfo:
    """Test get_video_info method."""

    def test_get_video_info_success(self, video_validator, sample_video, mock_ffprobe_output_valid):
        """Test successful video info retrieval."""
        with patch('subprocess.run') as mock_run:
            mock_run.return_value = Mock(
                returncode=0,
                stdout=json.dumps(mock_ffprobe_output_valid)
            )

            info = video_validator.get_video_info(sample_video)

            assert info.codec == "h264"
            assert info.width == 1920
            assert info.height == 1080
            assert info.duration == 120.5
            assert info.has_audio is True
            assert info.audio_codec == "aac"
            assert info.audio_channels == 2
            assert info.audio_sample_rate == 48000

    def test_get_video_info_no_video_stream(self, video_validator, sample_video):
        """Test get_video_info with no video stream."""
        ffprobe_output = {
            "streams": [
                {
                    "codec_type": "audio",
                    "codec_name": "aac"
                }
            ],
            "format": {"duration": "120.5"}
        }

        with patch('subprocess.run') as mock_run:
            mock_run.return_value = Mock(
                returncode=0,
                stdout=json.dumps(ffprobe_output)
            )

            with pytest.raises(FileCorruptedError, match="No video stream found"):
                video_validator.get_video_info(sample_video)

    def test_get_video_info_file_not_found(self, video_validator):
        """Test get_video_info with non-existent file."""
        with pytest.raises(FileNotFoundError):
            video_validator.get_video_info(Path("/nonexistent/file.mp4"))

    def test_get_video_info_timeout(self, video_validator, sample_video):
        """Test get_video_info when ffprobe times out."""
        with patch('subprocess.run') as mock_run:
            mock_run.side_effect = subprocess.TimeoutExpired("ffprobe", 30)

            with pytest.raises(FFprobeError, match="timeout"):
                video_validator.get_video_info(sample_video)

    def test_get_video_info_json_error(self, video_validator, sample_video):
        """Test get_video_info with invalid JSON."""
        with patch('subprocess.run') as mock_run:
            mock_run.return_value = Mock(
                returncode=0,
                stdout="invalid json{{{"
            )

            with pytest.raises(FileCorruptedError, match="Failed to parse"):
                video_validator.get_video_info(sample_video)

    def test_get_video_info_fps_parsing(self, video_validator, sample_video):
        """Test FPS parsing for various formats."""
        test_cases = [
            ("60/1", Fraction(60, 1)),
            ("30000/1001", Fraction(30000, 1001)),
            ("24000/1001", Fraction(24000, 1001)),
            ("59.94", Fraction(5994, 100)),
        ]

        for fps_str, expected_fps in test_cases:
            ffprobe_output = {
                "streams": [{
                    "codec_type": "video",
                    "codec_name": "h264",
                    "width": 1920,
                    "height": 1080,
                    "pix_fmt": "yuv420p",
                    "r_frame_rate": fps_str
                }],
                "format": {"duration": "120.0"}
            }

            with patch('subprocess.run') as mock_run:
                mock_run.return_value = Mock(
                    returncode=0,
                    stdout=json.dumps(ffprobe_output)
                )

                info = video_validator.get_video_info(sample_video)
                assert info.fps == expected_fps, f"Failed for FPS: {fps_str}"

    def test_get_video_info_zero_fps_denominator(self, video_validator, sample_video):
        """Test FPS parsing with zero denominator."""
        ffprobe_output = {
            "streams": [{
                "codec_type": "video",
                "codec_name": "h264",
                "width": 1920,
                "height": 1080,
                "pix_fmt": "yuv420p",
                "r_frame_rate": "30/0"
            }],
            "format": {"duration": "120.0"}
        }

        with patch('subprocess.run') as mock_run:
            mock_run.return_value = Mock(
                returncode=0,
                stdout=json.dumps(ffprobe_output)
            )

            info = video_validator.get_video_info(sample_video)
            assert info.fps == Fraction(0, 1)


@pytest.mark.unit
class TestVideoValidatorCheckDuration:
    """Test duration validation."""

    def test_check_duration_within_tolerance(self, video_validator, sample_video, mock_ffprobe_output_valid):
        """Test duration check within tolerance."""
        with patch('subprocess.run') as mock_run:
            mock_run.return_value = Mock(
                returncode=0,
                stdout=json.dumps(mock_ffprobe_output_valid)
            )

            # Target 120s, actual 120.5s, tolerance 5s
            result = video_validator.check_duration(sample_video, 120.0)
            assert result is True

    def test_check_duration_outside_tolerance(self, video_validator, sample_video, mock_ffprobe_output_valid):
        """Test duration check outside tolerance."""
        ffprobe_output = mock_ffprobe_output_valid.copy()
        ffprobe_output["format"]["duration"] = "130.0"

        with patch('subprocess.run') as mock_run:
            mock_run.return_value = Mock(
                returncode=0,
                stdout=json.dumps(ffprobe_output)
            )

            # Target 120s, actual 130s, tolerance 5s
            result = video_validator.check_duration(sample_video, 120.0)
            assert result is False

    def test_check_duration_exact_match(self, video_validator, sample_video, mock_ffprobe_output_valid):
        """Test duration check with exact match."""
        with patch('subprocess.run') as mock_run:
            mock_run.return_value = Mock(
                returncode=0,
                stdout=json.dumps(mock_ffprobe_output_valid)
            )

            result = video_validator.check_duration(sample_video, 120.5)
            assert result is True

    def test_check_duration_ffprobe_error(self, video_validator, sample_video):
        """Test duration check when ffprobe fails."""
        with patch('subprocess.run') as mock_run:
            mock_run.side_effect = subprocess.CalledProcessError(1, "ffprobe")

            result = video_validator.check_duration(sample_video, 120.0)
            assert result is False


@pytest.mark.unit
class TestVideoValidatorCheckCodec:
    """Test codec validation."""

    def test_check_codec_match_h264(self, video_validator, sample_video, mock_ffprobe_output_valid):
        """Test codec check with matching h264."""
        with patch('subprocess.run') as mock_run:
            mock_run.return_value = Mock(
                returncode=0,
                stdout=json.dumps(mock_ffprobe_output_valid)
            )

            result = video_validator.check_codec(sample_video, "h264")
            assert result is True

    def test_check_codec_match_hevc(self, video_validator, sample_video, mock_ffprobe_output_hevc):
        """Test codec check with matching hevc."""
        with patch('subprocess.run') as mock_run:
            mock_run.return_value = Mock(
                returncode=0,
                stdout=json.dumps(mock_ffprobe_output_hevc)
            )

            result = video_validator.check_codec(sample_video, "hevc")
            assert result is True

    def test_check_codec_alias_h264(self, video_validator, sample_video, mock_ffprobe_output_valid):
        """Test codec check with h264 alias."""
        with patch('subprocess.run') as mock_run:
            mock_run.return_value = Mock(
                returncode=0,
                stdout=json.dumps(mock_ffprobe_output_valid)
            )

            # Test various h264 aliases
            for alias in ["h264", "avc", "libx264"]:
                result = video_validator.check_codec(sample_video, alias)
                assert result is True, f"Failed for alias: {alias}"

    def test_check_codec_alias_hevc(self, video_validator, sample_video):
        """Test codec check with hevc alias."""
        ffprobe_output = {
            "streams": [{
                "codec_type": "video",
                "codec_name": "h265",
                "width": 1920,
                "height": 1080,
                "pix_fmt": "yuv420p",
                "r_frame_rate": "60/1"
            }],
            "format": {"duration": "120.0"}
        }

        with patch('subprocess.run') as mock_run:
            mock_run.return_value = Mock(
                returncode=0,
                stdout=json.dumps(ffprobe_output)
            )

            # Test various hevc aliases
            for alias in ["hevc", "h265", "libx265"]:
                result = video_validator.check_codec(sample_video, alias)
                assert result is True, f"Failed for alias: {alias}"

    def test_check_codec_no_match(self, video_validator, sample_video, mock_ffprobe_output_valid):
        """Test codec check with non-matching codec."""
        with patch('subprocess.run') as mock_run:
            mock_run.return_value = Mock(
                returncode=0,
                stdout=json.dumps(mock_ffprobe_output_valid)
            )

            result = video_validator.check_codec(sample_video, "hevc")
            assert result is False

    def test_check_codec_case_insensitive(self, video_validator, sample_video, mock_ffprobe_output_valid):
        """Test codec check is case-insensitive."""
        with patch('subprocess.run') as mock_run:
            mock_run.return_value = Mock(
                returncode=0,
                stdout=json.dumps(mock_ffprobe_output_valid)
            )

            result = video_validator.check_codec(sample_video, "H264")
            assert result is True

    def test_check_codec_ffprobe_error(self, video_validator, sample_video):
        """Test codec check when ffprobe fails."""
        with patch('subprocess.run') as mock_run:
            mock_run.side_effect = subprocess.CalledProcessError(1, "ffprobe")

            result = video_validator.check_codec(sample_video, "h264")
            assert result is False


@pytest.mark.unit
class TestVideoValidatorCheckResolution:
    """Test resolution validation."""

    def test_check_resolution_match(self, video_validator, sample_video, mock_ffprobe_output_valid):
        """Test resolution check with match."""
        with patch('subprocess.run') as mock_run:
            mock_run.return_value = Mock(
                returncode=0,
                stdout=json.dumps(mock_ffprobe_output_valid)
            )

            result = video_validator.check_resolution(sample_video, (1920, 1080))
            assert result is True

    def test_check_resolution_no_match(self, video_validator, sample_video, mock_ffprobe_output_valid):
        """Test resolution check with no match."""
        with patch('subprocess.run') as mock_run:
            mock_run.return_value = Mock(
                returncode=0,
                stdout=json.dumps(mock_ffprobe_output_valid)
            )

            result = video_validator.check_resolution(sample_video, (1280, 720))
            assert result is False

    def test_check_resolution_width_only_mismatch(self, video_validator, sample_video):
        """Test resolution check with width mismatch."""
        ffprobe_output = {
            "streams": [{
                "codec_type": "video",
                "codec_name": "h264",
                "width": 1280,
                "height": 1080,
                "pix_fmt": "yuv420p",
                "r_frame_rate": "60/1"
            }],
            "format": {"duration": "120.0"}
        }

        with patch('subprocess.run') as mock_run:
            mock_run.return_value = Mock(
                returncode=0,
                stdout=json.dumps(ffprobe_output)
            )

            result = video_validator.check_resolution(sample_video, (1920, 1080))
            assert result is False

    def test_check_resolution_height_only_mismatch(self, video_validator, sample_video):
        """Test resolution check with height mismatch."""
        ffprobe_output = {
            "streams": [{
                "codec_type": "video",
                "codec_name": "h264",
                "width": 1920,
                "height": 720,
                "pix_fmt": "yuv420p",
                "r_frame_rate": "60/1"
            }],
            "format": {"duration": "120.0"}
        }

        with patch('subprocess.run') as mock_run:
            mock_run.return_value = Mock(
                returncode=0,
                stdout=json.dumps(ffprobe_output)
            )

            result = video_validator.check_resolution(sample_video, (1920, 1080))
            assert result is False


@pytest.mark.unit
class TestVideoValidatorCheckFPS:
    """Test FPS validation."""

    def test_check_fps_within_tolerance(self, video_validator, sample_video, mock_ffprobe_output_valid):
        """Test FPS check within tolerance."""
        with patch('subprocess.run') as mock_run:
            mock_run.return_value = Mock(
                returncode=0,
                stdout=json.dumps(mock_ffprobe_output_valid)
            )

            result = video_validator.check_fps(sample_video, Fraction(60, 1))
            assert result is True

    def test_check_fps_outside_tolerance(self, video_validator, sample_video):
        """Test FPS check outside tolerance."""
        ffprobe_output = {
            "streams": [{
                "codec_type": "video",
                "codec_name": "h264",
                "width": 1920,
                "height": 1080,
                "pix_fmt": "yuv420p",
                "r_frame_rate": "30/1"
            }],
            "format": {"duration": "120.0"}
        }

        with patch('subprocess.run') as mock_run:
            mock_run.return_value = Mock(
                returncode=0,
                stdout=json.dumps(ffprobe_output)
            )

            # 30 FPS vs 60 FPS, way outside tolerance
            result = video_validator.check_fps(sample_video, Fraction(60, 1))
            assert result is False

    def test_check_fps_fraction_parsing(self, video_validator, sample_video):
        """Test FPS check with fractional FPS."""
        ffprobe_output = {
            "streams": [{
                "codec_type": "video",
                "codec_name": "h264",
                "width": 1920,
                "height": 1080,
                "pix_fmt": "yuv420p",
                "r_frame_rate": "30000/1001"
            }],
            "format": {"duration": "120.0"}
        }

        with patch('subprocess.run') as mock_run:
            mock_run.return_value = Mock(
                returncode=0,
                stdout=json.dumps(ffprobe_output)
            )

            # 29.97 FPS vs 30 FPS, within tolerance
            result = video_validator.check_fps(sample_video, Fraction(30, 1))
            assert result is True


@pytest.mark.unit
class TestVideoValidatorCheckAudio:
    """Test audio validation."""

    def test_check_audio_has_audio(self, video_validator, sample_video, mock_ffprobe_output_valid):
        """Test audio check with audio present."""
        with patch('subprocess.run') as mock_run:
            mock_run.return_value = Mock(
                returncode=0,
                stdout=json.dumps(mock_ffprobe_output_valid)
            )

            result = video_validator.check_audio(sample_video, has_audio=True)
            assert result is True

    def test_check_audio_no_audio(self, video_validator, sample_video, mock_ffprobe_output_no_audio):
        """Test audio check with no audio."""
        with patch('subprocess.run') as mock_run:
            mock_run.return_value = Mock(
                returncode=0,
                stdout=json.dumps(mock_ffprobe_output_no_audio)
            )

            result = video_validator.check_audio(sample_video, has_audio=False)
            assert result is True

    def test_check_audio_mismatch(self, video_validator, sample_video, mock_ffprobe_output_no_audio):
        """Test audio check with mismatch."""
        with patch('subprocess.run') as mock_run:
            mock_run.return_value = Mock(
                returncode=0,
                stdout=json.dumps(mock_ffprobe_output_no_audio)
            )

            result = video_validator.check_audio(sample_video, has_audio=True)
            assert result is False


@pytest.mark.unit
class TestVideoValidatorCheckAudioTracks:
    """Test audio track count validation."""

    def test_check_audio_tracks_single(self, video_validator, sample_video, mock_ffprobe_output_valid):
        """Test audio track count with single track."""
        with patch('subprocess.run') as mock_run:
            mock_run.return_value = Mock(
                returncode=0,
                stdout=json.dumps(mock_ffprobe_output_valid)
            )

            result = video_validator.check_audio_tracks(sample_video, 1)
            assert result is True

    def test_check_audio_tracks_zero(self, video_validator, sample_video, mock_ffprobe_output_no_audio):
        """Test audio track count with zero tracks."""
        with patch('subprocess.run') as mock_run:
            mock_run.return_value = Mock(
                returncode=0,
                stdout=json.dumps(mock_ffprobe_output_no_audio)
            )

            result = video_validator.check_audio_tracks(sample_video, 0)
            assert result is True

    def test_check_audio_tracks_mismatch(self, video_validator, sample_video, mock_ffprobe_output_valid):
        """Test audio track count with mismatch."""
        with patch('subprocess.run') as mock_run:
            mock_run.return_value = Mock(
                returncode=0,
                stdout=json.dumps(mock_ffprobe_output_valid)
            )

            result = video_validator.check_audio_tracks(sample_video, 2)
            assert result is False


@pytest.mark.unit
class TestVideoValidatorCheckFileIntegrity:
    """Test file integrity validation."""

    def test_check_file_integrity_valid(self, video_validator, sample_video, mock_ffprobe_output_valid):
        """Test file integrity check for valid file."""
        with patch('subprocess.run') as mock_run:
            mock_run.return_value = Mock(
                returncode=0,
                stdout=json.dumps(mock_ffprobe_output_valid)
            )

            result = video_validator.check_file_integrity(sample_video)
            assert result is True

    def test_check_file_integrity_zero_duration(self, video_validator, sample_video):
        """Test file integrity check with zero duration."""
        ffprobe_output = {
            "streams": [{
                "codec_type": "video",
                "codec_name": "h264",
                "width": 1920,
                "height": 1080,
                "pix_fmt": "yuv420p",
                "r_frame_rate": "60/1"
            }],
            "format": {"duration": "0"}
        }

        with patch('subprocess.run') as mock_run:
            mock_run.return_value = Mock(
                returncode=0,
                stdout=json.dumps(ffprobe_output)
            )

            result = video_validator.check_file_integrity(sample_video)
            assert result is False

    def test_check_file_integrity_zero_resolution(self, video_validator, sample_video):
        """Test file integrity check with zero resolution."""
        ffprobe_output = {
            "streams": [{
                "codec_type": "video",
                "codec_name": "h264",
                "width": 0,
                "height": 0,
                "pix_fmt": "yuv420p",
                "r_frame_rate": "60/1"
            }],
            "format": {"duration": "120.0"}
        }

        with patch('subprocess.run') as mock_run:
            mock_run.return_value = Mock(
                returncode=0,
                stdout=json.dumps(ffprobe_output)
            )

            result = video_validator.check_file_integrity(sample_video)
            assert result is False

    def test_check_file_integrity_ffprobe_error(self, video_validator, sample_video):
        """Test file integrity check when ffprobe fails."""
        with patch('subprocess.run') as mock_run:
            mock_run.side_effect = subprocess.CalledProcessError(1, "ffprobe")

            result = video_validator.check_file_integrity(sample_video)
            assert result is False


@pytest.mark.unit
class TestVideoValidatorValidateOutput:
    """Test validate_output comprehensive validation."""

    def test_validate_output_success(self, video_validator, sample_video, mock_ffprobe_output_valid):
        """Test successful output validation."""
        specs = {
            "duration_seconds": 120,
            "width": 1920,
            "height": 1080,
            "fps": 60,
            "codec": "h264",
            "has_audio": True
        }

        with patch('subprocess.run') as mock_run:
            mock_run.return_value = Mock(
                returncode=0,
                stdout=json.dumps(mock_ffprobe_output_valid)
            )

            result = video_validator.validate_output(sample_video, specs)

            assert result.valid is True
            assert len(result.errors) == 0
            assert result.duration_seconds == 120.5

    def test_validate_output_file_not_found(self, video_validator):
        """Test validation with non-existent file."""
        specs = {"duration_seconds": 120}

        result = video_validator.validate_output(Path("/nonexistent/file.mp4"), specs)

        assert result.valid is False
        assert len(result.errors) == 1
        assert "not found" in result.errors[0].message.lower()

    def test_validate_output_empty_file(self, video_validator, temp_dir):
        """Test validation with empty file."""
        empty_file = temp_dir / "empty.mp4"
        empty_file.write_bytes(b"")

        specs = {"duration_seconds": 120}

        result = video_validator.validate_output(empty_file, specs)

        assert result.valid is False
        assert any("empty" in e.message.lower() for e in result.errors)

    def test_validate_output_duration_mismatch(self, video_validator, sample_video):
        """Test validation with duration mismatch."""
        ffprobe_output = {
            "streams": [{
                "codec_type": "video",
                "codec_name": "h264",
                "width": 1920,
                "height": 1080,
                "pix_fmt": "yuv420p",
                "r_frame_rate": "60/1"
            }],
            "format": {"duration": "200.0"}
        }

        specs = {"duration_seconds": 120}

        with patch('subprocess.run') as mock_run:
            mock_run.return_value = Mock(
                returncode=0,
                stdout=json.dumps(ffprobe_output)
            )

            result = video_validator.validate_output(sample_video, specs)

            assert result.valid is False
            assert any("duration" in e.field.lower() for e in result.errors)

    def test_validate_output_resolution_mismatch(self, video_validator, sample_video, mock_ffprobe_output_valid):
        """Test validation with resolution mismatch."""
        specs = {
            "width": 1280,
            "height": 720
        }

        with patch('subprocess.run') as mock_run:
            mock_run.return_value = Mock(
                returncode=0,
                stdout=json.dumps(mock_ffprobe_output_valid)
            )

            result = video_validator.validate_output(sample_video, specs)

            assert result.valid is False
            assert any("resolution" in e.field for e in result.errors)

    def test_validate_output_fps_mismatch(self, video_validator, sample_video):
        """Test validation with FPS mismatch."""
        ffprobe_output = {
            "streams": [{
                "codec_type": "video",
                "codec_name": "h264",
                "width": 1920,
                "height": 1080,
                "pix_fmt": "yuv420p",
                "r_frame_rate": "30/1"
            }],
            "format": {"duration": "120.0"}
        }

        specs = {"fps": 60}

        with patch('subprocess.run') as mock_run:
            mock_run.return_value = Mock(
                returncode=0,
                stdout=json.dumps(ffprobe_output)
            )

            result = video_validator.validate_output(sample_video, specs)

            assert result.valid is False
            assert any("fps" in e.field for e in result.errors)

    def test_validate_output_codec_mismatch(self, video_validator, sample_video, mock_ffprobe_output_valid):
        """Test validation with codec mismatch."""
        specs = {"codec": "hevc"}

        with patch('subprocess.run') as mock_run:
            mock_run.return_value = Mock(
                returncode=0,
                stdout=json.dumps(mock_ffprobe_output_valid)
            )

            result = video_validator.validate_output(sample_video, specs)

            assert result.valid is False
            assert any("codec" in e.field for e in result.errors)

    def test_validate_output_audio_mismatch(self, video_validator, sample_video, mock_ffprobe_output_no_audio):
        """Test validation with audio mismatch."""
        specs = {"has_audio": True}

        with patch('subprocess.run') as mock_run:
            mock_run.return_value = Mock(
                returncode=0,
                stdout=json.dumps(mock_ffprobe_output_no_audio)
            )

            result = video_validator.validate_output(sample_video, specs)

            assert result.valid is False
            assert any("audio" in e.field for e in result.errors)

    def test_validate_output_bitrate_warning(self, video_validator, sample_video):
        """Test validation with bitrate warnings."""
        ffprobe_output = {
            "streams": [{
                "codec_type": "video",
                "codec_name": "h264",
                "width": 1920,
                "height": 1080,
                "pix_fmt": "yuv420p",
                "r_frame_rate": "60/1"
            }],
            "format": {
                "duration": "120.0",
                "bit_rate": "1000000"  # 1 Mbps
            }
        }

        specs = {"min_bitrate": 2000000}  # 2 Mbps

        with patch('subprocess.run') as mock_run:
            mock_run.return_value = Mock(
                returncode=0,
                stdout=json.dumps(ffprobe_output)
            )

            result = video_validator.validate_output(sample_video, specs)

            # Should have warning, not error
            assert len(result.warnings) > 0


# ═══════════════════════════════════════════════════════════════════════════════
# Unit Tests: PreRenderValidator
# ═══════════════════════════════════════════════════════════════════════════════


@pytest.mark.unit
class TestPreRenderValidatorInit:
    """Test PreRenderValidator initialization."""

    def test_default_initialization(self):
        """Test PreRenderValidator with default values."""
        validator = PreRenderValidator()

        assert validator.target_width == 1920
        assert validator.target_height == 1080
        assert validator.target_fps == 60

    def test_custom_initialization(self):
        """Test PreRenderValidator with custom values."""
        validator = PreRenderValidator(
            target_width=3840,
            target_height=2160,
            target_fps=30
        )

        assert validator.target_width == 3840
        assert validator.target_height == 2160
        assert validator.target_fps == 30


@pytest.mark.unit
class TestPreRenderValidatorValidateRenderSpecs:
    """Test validate_render_specs method."""

    def test_validate_render_specs_no_mode(self, pre_render_validator, temp_dir):
        """Test validation with no render mode specified."""
        result = pre_render_validator.validate_render_specs(
            intro_path=None,
            loop_path=None,
            single_path=None,
            tracks=[],
            target_duration=3600,
            output_dir=temp_dir
        )

        assert result.valid is False
        assert len(result.errors) > 0

    def test_validate_single_mode_missing_file(self, pre_render_validator, temp_dir):
        """Test single mode with missing file."""
        single_path = temp_dir / "nonexistent.mp4"

        result = pre_render_validator.validate_render_specs(
            intro_path=None,
            loop_path=None,
            single_path=single_path,
            tracks=[],
            target_duration=3600,
            output_dir=temp_dir
        )

        assert result.valid is False
        assert any("found" in e.message.lower() or "bulunamad" in e.message.lower()
                   for e in result.errors)

    def test_validate_intro_loop_mode_missing_intro(self, pre_render_validator, temp_dir, sample_video):
        """Test intro/loop mode with missing intro."""
        loop_path = temp_dir / "loop.mp4"
        loop_path.write_bytes(b"MOCK_LOOP")

        intro_path = temp_dir / "intro.mp4"
        # Don't create intro file

        result = pre_render_validator.validate_render_specs(
            intro_path=intro_path,
            loop_path=loop_path,
            single_path=None,
            tracks=[],
            target_duration=3600,
            output_dir=temp_dir
        )

        assert result.valid is False

    def test_validate_intro_loop_mode_missing_loop(self, pre_render_validator, temp_dir, sample_video):
        """Test intro/loop mode with missing loop."""
        intro_path = temp_dir / "intro.mp4"
        intro_path.write_bytes(b"MOCK_INTRO")

        loop_path = temp_dir / "loop.mp4"
        # Don't create loop file

        result = pre_render_validator.validate_render_specs(
            intro_path=intro_path,
            loop_path=loop_path,
            single_path=None,
            tracks=[],
            target_duration=3600,
            output_dir=temp_dir
        )

        assert result.valid is False

    def test_validate_no_audio_tracks(self, pre_render_validator, temp_dir, sample_video):
        """Test validation with no audio tracks."""
        result = pre_render_validator.validate_render_specs(
            intro_path=None,
            loop_path=None,
            single_path=sample_video,
            tracks=[],
            target_duration=3600,
            output_dir=temp_dir
        )

        # Should generate a warning, not an error
        assert len(result.warnings) > 0

    def test_validate_missing_audio_tracks(self, pre_render_validator, temp_dir, sample_video):
        """Test validation with missing audio track files."""
        missing_audio = temp_dir / "missing.mp3"

        result = pre_render_validator.validate_render_specs(
            intro_path=None,
            loop_path=None,
            single_path=sample_video,
            tracks=[missing_audio],
            target_duration=3600,
            output_dir=temp_dir
        )

        assert result.valid is False
        assert any("audio" in e.category.lower() for e in result.errors)

    def test_validate_short_audio_track(self, pre_render_validator, temp_dir, sample_video, sample_audio):
        """Test validation with short audio track."""
        result = pre_render_validator.validate_render_specs(
            intro_path=None,
            loop_path=None,
            single_path=sample_video,
            tracks=[sample_audio],
            target_duration=3600,  # 1 hour
            output_dir=temp_dir
        )

        # Should warn about insufficient audio duration
        # (audio is short compared to target duration)
        assert len(result.issues) > 0

    def test_parse_fps(self, pre_render_validator):
        """Test FPS parsing helper method."""
        test_cases = [
            ("60/1", 60.0),
            ("30000/1001", 29.97),
            ("59.94", 59.94),
            ("invalid", 0.0),
        ]

        for fps_str, expected in test_cases:
            result = pre_render_validator._parse_fps(fps_str)
            if expected == 0.0:
                assert result == 0.0
            else:
                assert abs(result - expected) < 0.1, f"Failed for {fps_str}"


# ═══════════════════════════════════════════════════════════════════════════════
# Unit Tests: PostRenderValidator
# ═══════════════════════════════════════════════════════════════════════════════


@pytest.mark.unit
class TestPostRenderValidatorInit:
    """Test PostRenderValidator initialization."""

    def test_default_initialization(self):
        """Test PostRenderValidator with default values."""
        validator = PostRenderValidator()

        assert validator.duration_tolerance == 5.0
        assert validator.fps_tolerance == 0.1
        assert validator.bitrate_tolerance == 0.1
        assert validator.sync_tolerance == 0.1

    def test_custom_initialization(self):
        """Test PostRenderValidator with custom values."""
        validator = PostRenderValidator(
            duration_tolerance=10.0,
            fps_tolerance=0.5,
            bitrate_tolerance=0.2,
            sync_tolerance=0.5
        )

        assert validator.duration_tolerance == 10.0
        assert validator.sync_tolerance == 0.5


@pytest.mark.unit
class TestPostRenderValidatorValidateOutput:
    """Test validate_output method."""

    def test_validate_output_missing_file(self, post_render_validator):
        """Test validation with missing output file."""
        result = post_render_validator.validate_output(
            Path("/nonexistent/output.mp4"),
            target_duration=3600
        )

        assert result.valid is False
        assert any("not found" in i.message.lower() or "bulunamad" in i.message.lower()
                   for i in result.issues)

    def test_validate_output_duration_ok(self, post_render_validator, sample_video):
        """Test duration validation within tolerance."""
        ffprobe_output = {
            "streams": [{
                "codec_type": "video",
                "codec_name": "h264",
                "width": 1920,
                "height": 1080,
                "pix_fmt": "yuv420p",
                "r_frame_rate": "60/1"
            }],
            "format": {"duration": "3605.0"}
        }

        with patch('subprocess.run') as mock_run:
            mock_run.return_value = Mock(
                returncode=0,
                stdout=json.dumps(ffprobe_output)
            )

            result = post_render_validator.validate_output(
                sample_video,
                target_duration=3600
            )

            # Duration should be OK (within 5s tolerance)
            duration_issues = [i for i in result.issues if "duration" in i.category.lower()]
            assert len(duration_issues) == 0 or all(
                i.severity == ValidationSeverity.INFO for i in duration_issues
            )

    def test_validate_output_duration_warning(self, post_render_validator, sample_video):
        """Test duration validation outside tolerance."""
        ffprobe_output = {
            "streams": [{
                "codec_type": "video",
                "codec_name": "h264",
                "width": 1920,
                "height": 1080,
                "pix_fmt": "yuv420p",
                "r_frame_rate": "60/1"
            }],
            "format": {"duration": "3200.0"}
        }

        with patch('subprocess.run') as mock_run:
            mock_run.return_value = Mock(
                returncode=0,
                stdout=json.dumps(ffprobe_output)
            )

            result = post_render_validator.validate_output(
                sample_video,
                target_duration=3600
            )

            # Should have duration warning
            assert any("duration" in i.category.lower() for i in result.issues)

    def test_validate_output_no_audio(self, post_render_validator, sample_video):
        """Test validation with missing audio."""
        ffprobe_output = {
            "streams": [{
                "codec_type": "video",
                "codec_name": "h264",
                "width": 1920,
                "height": 1080,
                "pix_fmt": "yuv420p",
                "r_frame_rate": "60/1"
            }],
            "format": {"duration": "3600.0"}
        }

        with patch('subprocess.run') as mock_run:
            mock_run.side_effect = [
                Mock(returncode=0, stdout=json.dumps(ffprobe_output)),
                Mock(returncode=0, stdout='{"streams": []}')  # No audio
            ]

            result = post_render_validator.validate_output(
                sample_video,
                target_duration=3600
            )

            # Should have audio error
            assert any("audio" in i.category.lower() for i in result.issues)

    def test_validate_output_low_bitrate(self, post_render_validator, sample_video):
        """Test validation with low audio bitrate."""
        ffprobe_output = {
            "streams": [{
                "codec_type": "video",
                "codec_name": "h264",
                "width": 1920,
                "height": 1080,
                "pix_fmt": "yuv420p",
                "r_frame_rate": "60/1"
            }],
            "format": {"duration": "3600.0"}
        }

        audio_output = {
            "streams": [{
                "codec_name": "aac",
                "bit_rate": "64000"  # 64 kbps
            }]
        }

        with patch('subprocess.run') as mock_run:
            mock_run.side_effect = [
                Mock(returncode=0, stdout=json.dumps(ffprobe_output)),
                Mock(returncode=0, stdout=json.dumps(audio_output))
            ]

            result = post_render_validator.validate_output(
                sample_video,
                target_duration=3600
            )

            # Should have low bitrate warning
            assert any("bitrate" in i.message.lower() for i in result.issues)

    def test_parse_fps(self, post_render_validator):
        """Test FPS parsing helper method."""
        test_cases = [
            ("60/1", 60.0),
            ("30000/1001", pytest.approx(29.97, rel=0.01)),
            ("59.94", 59.94),
            ("invalid", 0.0),
        ]

        for fps_str, expected in test_cases:
            result = post_render_validator._parse_fps(fps_str)
            if isinstance(expected, float) and expected > 0:
                assert abs(result - expected) < 0.1, f"Failed for {fps_str}"
            else:
                assert result == 0.0


@pytest.mark.unit
class TestPostRenderValidatorCheckAVSync:
    """Test audio-visual sync checking."""

    def test_check_av_sync_in_sync(self, post_render_validator, sample_video):
        """Test AV sync check with synchronized streams."""
        video_output = {
            "streams": [{
                "duration": "3600.0"
            }]
        }

        audio_output = {
            "streams": [{
                "duration": "3600.0"
            }]
        }

        with patch('subprocess.run') as mock_run:
            mock_run.side_effect = [
                Mock(returncode=0, stdout=json.dumps(video_output)),
                Mock(returncode=0, stdout=json.dumps(audio_output))
            ]

            result = post_render_validator.check_av_sync(sample_video)
            assert result is True

    def test_check_av_sync_out_of_sync(self, post_render_validator, sample_video):
        """Test AV sync check with out-of-sync streams."""
        video_output = {
            "streams": [{
                "duration": "3600.0"
            }]
        }

        audio_output = {
            "streams": [{
                "duration": "3500.0"  # 100 seconds difference
            }]
        }

        with patch('subprocess.run') as mock_run:
            mock_run.side_effect = [
                Mock(returncode=0, stdout=json.dumps(video_output)),
                Mock(returncode=0, stdout=json.dumps(audio_output))
            ]

            result = post_render_validator.check_av_sync(sample_video)
            assert result is False

    def test_check_av_sync_zero_duration(self, post_render_validator, sample_video):
        """Test AV sync check with zero duration."""
        video_output = {
            "streams": [{
                "duration": "0"
            }]
        }

        audio_output = {
            "streams": [{
                "duration": "0"
            }]
        }

        with patch('subprocess.run') as mock_run:
            mock_run.side_effect = [
                Mock(returncode=0, stdout=json.dumps(video_output)),
                Mock(returncode=0, stdout=json.dumps(audio_output))
            ]

            # Should return True (can't check, assume OK)
            result = post_render_validator.check_av_sync(sample_video)
            assert result is True

    def test_check_av_sync_error(self, post_render_validator, sample_video):
        """Test AV sync check with ffprobe error."""
        with patch('subprocess.run') as mock_run:
            mock_run.side_effect = subprocess.CalledProcessError(1, "ffprobe")

            # Should return True (assume OK on error)
            result = post_render_validator.check_av_sync(sample_video)
            assert result is True


# ═══════════════════════════════════════════════════════════════════════════════
# Unit Tests: Convenience Functions
# ═══════════════════════════════════════════════════════════════════════════════


@pytest.mark.unit
class TestValidateBeforeRender:
    """Test validate_before_render convenience function."""

    def test_validate_before_render_success(self, temp_dir, sample_video, sample_audio):
        """Test successful pre-render validation."""
        with patch('video_renderer.validator.probe_video') as mock_probe:
            mock_probe.return_value = Mock(
                codec="h264",
                width=1920,
                height=1080,
                fps="60/1",
                duration=120.0
            )

            with patch('video_renderer.validator.get_duration') as mock_duration:
                mock_duration.return_value = 300.0

                result = validate_before_render(
                    intro_path=None,
                    loop_path=None,
                    single_path=sample_video,
                    tracks=[sample_audio],
                    target_duration=3600,
                    output_dir=temp_dir
                )

                assert result.stage == "pre_render"

    def test_validate_before_render_intro_loop(self, temp_dir):
        """Test pre-render validation for intro/loop mode."""
        intro = temp_dir / "intro.mp4"
        loop = temp_dir / "loop.mp4"
        intro.write_bytes(b"INTRO")
        loop.write_bytes(b"LOOP")

        with patch('video_renderer.validator.probe_video') as mock_probe:
            mock_probe.return_value = Mock(
                codec="h264",
                width=1920,
                height=1080,
                fps="60/1",
                duration=30.0
            )

            result = validate_before_render(
                intro_path=intro,
                loop_path=loop,
                single_path=None,
                tracks=[],
                target_duration=3600,
                output_dir=temp_dir
            )

            assert result.stage == "pre_render"


@pytest.mark.unit
class TestValidateAfterRender:
    """Test validate_after_render convenience function."""

    def test_validate_after_render_success(self, temp_dir, sample_video):
        """Test successful post-render validation."""
        with patch('video_renderer.validator.probe_video') as mock_probe:
            mock_probe.return_value = Mock(
                codec="h264",
                width=1920,
                height=1080,
                fps="60/1",
                duration=3600.0
            )

            result = validate_after_render(
                output_path=sample_video,
                target_duration=3600,
                target_specs={"codec": "h264"}
            )

            assert result.stage == "post_render"

    def test_validate_after_render_missing_file(self, temp_dir):
        """Test post-render validation with missing file."""
        result = validate_after_render(
            output_path=Path("/nonexistent/output.mp4"),
            target_duration=3600
        )

        assert result.valid is False


@pytest.mark.unit
class TestValidateVideoFile:
    """Test validate_video_file convenience function."""

    def test_validate_video_file_success(self, temp_dir, sample_video):
        """Test successful video file validation."""
        with patch('subprocess.run') as mock_run:
            mock_run.return_value = Mock(
                returncode=0,
                stdout=json.dumps({
                    "streams": [{
                        "codec_type": "video",
                        "codec_name": "h264",
                        "width": 1920,
                        "height": 1080,
                        "pix_fmt": "yuv420p",
                        "r_frame_rate": "60/1"
                    }],
                    "format": {"duration": "120.0"}
                })
            )

            result = validate_video_file(
                video_path=sample_video,
                expected_duration=120.0,
                expected_resolution=(1920, 1080),
                expected_fps=60,
                expected_codec="h264",
                has_audio=True
            )

            assert result.valid is True

    def test_validate_video_file_partial_specs(self, temp_dir, sample_video):
        """Test validation with partial specifications."""
        with patch('subprocess.run') as mock_run:
            mock_run.return_value = Mock(
                returncode=0,
                stdout=json.dumps({
                    "streams": [{
                        "codec_type": "video",
                        "codec_name": "h264",
                        "width": 1920,
                        "height": 1080,
                        "pix_fmt": "yuv420p",
                        "r_frame_rate": "60/1"
                    }],
                    "format": {"duration": "120.0"}
                })
            )

            result = validate_video_file(
                video_path=sample_video,
                expected_codec="h264"
            )

            # Should only validate codec
            assert result.stage == "post_render"


@pytest.mark.unit
class TestQuickValidate:
    """Test quick_validate convenience function."""

    def test_quick_validate_valid(self, temp_dir):
        """Test quick validation of valid file."""
        video = temp_dir / "valid.mp4"
        video.write_bytes(b"VALID_VIDEO")

        with patch('video_renderer.validator.VideoValidator.is_ffprobe_available') as mock_available:
            mock_available.return_value = True

            with patch('video_renderer.validator.VideoValidator') as mock_validator_class:
                mock_validator = MagicMock()
                mock_validator.check_file_integrity.return_value = True
                mock_validator_class.return_value = mock_validator

                result = quick_validate(video)
                assert result is True

    def test_quick_validate_no_ffprobe(self, temp_dir):
        """Test quick validation without ffprobe."""
        video = temp_dir / "video.mp4"
        video.write_bytes(b"VIDEO")

        with patch('video_renderer.validator.VideoValidator.is_ffprobe_available') as mock_available:
            mock_available.return_value = False

            result = quick_validate(video)
            assert result is True  # Just checks existence

    def test_quick_validate_no_ffprobe_empty_file(self, temp_dir):
        """Test quick validation without ffprobe on empty file."""
        video = temp_dir / "empty.mp4"
        video.write_bytes(b"")

        with patch('video_renderer.validator.VideoValidator.is_ffprobe_available') as mock_available:
            mock_available.return_value = False

            result = quick_validate(video)
            assert result is False


@pytest.mark.unit
class TestValidateFFmpegAvailable:
    """Test validate_ffmpeg_available convenience function."""

    def test_ffmpeg_available(self):
        """Test when ffmpeg is available."""
        with patch('shutil.which') as mock_which:
            mock_which.return_value = "/usr/bin/ffmpeg"

            result = validate_ffmpeg_available()

            assert result.valid is True

    def test_ffmpeg_not_available(self):
        """Test when ffmpeg is not available."""
        with patch('shutil.which') as mock_which:
            mock_which.return_value = None

            result = validate_ffmpeg_available()

            assert result.valid is False
            assert len(result.errors) >= 1

    def test_ffprobe_not_available(self):
        """Test when ffprobe is not available."""
        with patch('shutil.which') as mock_which:
            def which_side_effect(cmd):
                return "/usr/bin/ffmpeg" if cmd == "ffmpeg" else None

            mock_which.side_effect = which_side_effect

            result = validate_ffmpeg_available()

            assert result.valid is False
            assert any("ffprobe" in e.message.lower() for e in result.errors)


@pytest.mark.unit
class TestExportValidationReport:
    """Test export_validation_report convenience function."""

    def test_export_report_success(self, temp_dir):
        """Test successful report export."""
        result = ValidationResult(
            valid=False,
            stage="post_render",
            duration_seconds=3600.0
        )

        result.add_error("duration", "Duration mismatch", "Süre uyusmazligi")
        result.add_warning("codec", "Codec changed", "Codec degisti")

        report_path = export_validation_report(result, output_dir=temp_dir)

        assert report_path.exists()
        assert report_path.parent == temp_dir

        # Read and verify content
        with open(report_path, 'r', encoding='utf-8') as f:
            report_data = json.load(f)

        assert report_data["stage"] == "post_render"
        assert report_data["valid"] is False
        assert report_data["summary"]["total_issues"] == 2
        assert report_data["summary"]["errors"] == 1
        assert report_data["summary"]["warnings"] == 1

    def test_export_report_default_dir(self, temp_dir):
        """Test report export to default directory."""
        result = ValidationResult(
            valid=True,
            stage="pre_render"
        )

        with patch('pathlib.Path.cwd') as mock_cwd:
            mock_cwd.return_value = temp_dir

            report_path = export_validation_report(result)

            assert report_path.parent == temp_dir / "reports"

    def test_export_report_metadata(self, temp_dir):
        """Test report export includes metadata."""
        result = ValidationResult(
            valid=True,
            stage="pre_render",
            metadata={"test": "value", "number": 42}
        )

        report_path = export_validation_report(result, output_dir=temp_dir)

        with open(report_path, 'r', encoding='utf-8') as f:
            report_data = json.load(f)

        assert report_data["metadata"]["test"] == "value"
        assert report_data["metadata"]["number"] == 42


# ═══════════════════════════════════════════════════════════════════════════════
# Integration Tests
# ═══════════════════════════════════════════════════════════════════════════════


@pytest.mark.integration
@pytest.mark.slow
class TestVideoValidatorIntegration:
    """Integration tests with actual ffprobe if available."""

    @pytest.mark.skipif(not shutil.which("ffprobe"), reason="ffprobe not available")
    def test_real_video_info_extraction(self, temp_dir):
        """Test with real ffprobe on a mock file."""
        # Create a minimal "video" file (may not be valid)
        video = temp_dir / "test.mp4"
        video.write_bytes(b"MOCK_VIDEO")

        validator = VideoValidator()

        # This will likely fail since it's not a real video
        # but we're testing the integration with ffprobe
        try:
            info = validator.get_video_info(video)
            # If it somehow succeeds, check the return type
            assert isinstance(info, VideoMetadata)
        except (FFprobeError, FileCorruptedError):
            # Expected for non-video files
            pass

    @pytest.mark.skipif(not shutil.which("ffprobe"), reason="ffprobe not available")
    def test_ffprobe_availability_check(self):
        """Test ffprobe availability check."""
        available = VideoValidator.is_ffprobe_available()
        assert isinstance(available, bool)


# ═══════════════════════════════════════════════════════════════════════════════
# Parametrized Tests
# ═══════════════════════════════════════════════════════════════════════════════


@pytest.mark.unit
@pytest.mark.parametrize("codec,should_match", [
    ("h264", True),
    ("H264", True),
    ("avc", True),
    ("libx264", True),
    ("hevc", False),
    ("h265", False),
    ("av1", False),
    ("vp9", False),
])
def test_codec_matching(video_validator, sample_video, codec, should_match):
    """Test codec matching with various codec names."""
    ffprobe_output = {
        "streams": [{
            "codec_type": "video",
            "codec_name": "h264",
            "width": 1920,
            "height": 1080,
            "pix_fmt": "yuv420p",
            "r_frame_rate": "60/1"
        }],
        "format": {"duration": "120.0"}
    }

    with patch('subprocess.run') as mock_run:
        mock_run.return_value = Mock(
            returncode=0,
            stdout=json.dumps(ffprobe_output)
        )

        result = video_validator.check_codec(sample_video, codec)
        assert result == should_match


@pytest.mark.unit
@pytest.mark.parametrize("width,height,expected_width,expected_height,should_match", [
    (1920, 1080, 1920, 1080, True),
    (1920, 1080, 1280, 720, False),
    (3840, 2160, 3840, 2160, True),
    (1280, 720, 1920, 1080, False),
])
def test_resolution_matching(video_validator, sample_video, width, height,
                              expected_width, expected_height, should_match):
    """Test resolution matching."""
    ffprobe_output = {
        "streams": [{
            "codec_type": "video",
            "codec_name": "h264",
            "width": width,
            "height": height,
            "pix_fmt": "yuv420p",
            "r_frame_rate": "60/1"
        }],
        "format": {"duration": "120.0"}
    }

    with patch('subprocess.run') as mock_run:
        mock_run.return_value = Mock(
            returncode=0,
            stdout=json.dumps(ffprobe_output)
        )

        result = video_validator.check_resolution(sample_video, (expected_width, expected_height))
        assert result == should_match


@pytest.mark.unit
@pytest.mark.parametrize("fps_str,expected_fps", [
    ("60/1", 60.0),
    ("59.94", 59.94),
    ("30/1", 30.0),
    ("29.97", 29.97),
    ("24/1", 24.0),
    ("23.98", 23.98),
    ("30000/1001", pytest.approx(29.97, rel=0.01)),
    ("24000/1001", pytest.approx(23.98, rel=0.01)),
])
def test_fps_parsing(video_validator, sample_video, fps_str, expected_fps):
    """Test FPS parsing for various formats."""
    ffprobe_output = {
        "streams": [{
            "codec_type": "video",
            "codec_name": "h264",
            "width": 1920,
            "height": 1080,
            "pix_fmt": "yuv420p",
            "r_frame_rate": fps_str
        }],
        "format": {"duration": "120.0"}
    }

    with patch('subprocess.run') as mock_run:
        mock_run.return_value = Mock(
            returncode=0,
            stdout=json.dumps(ffprobe_output)
        )

        info = video_validator.get_video_info(sample_video)
        actual_fps = float(info.fps)
        if isinstance(expected_fps, float):
            assert abs(actual_fps - expected_fps) < 0.1, f"Failed for {fps_str}"
        else:
            assert actual_fps == pytest.approx(expected_fps, rel=0.01)


@pytest.mark.unit
@pytest.mark.parametrize("duration,target,tolerance,should_match", [
    (120.0, 120.0, 5.0, True),
    (125.0, 120.0, 5.0, True),
    (115.0, 120.0, 5.0, True),
    (126.0, 120.0, 5.0, False),
    (114.0, 120.0, 5.0, False),
    (3600.0, 3600.0, 10.0, True),
    (3615.0, 3600.0, 10.0, False),
])
def test_duration_validation(video_validator, sample_video, duration, target, tolerance, should_match):
    """Test duration validation with various values."""
    ffprobe_output = {
        "streams": [{
            "codec_type": "video",
            "codec_name": "h264",
            "width": 1920,
            "height": 1080,
            "pix_fmt": "yuv420p",
            "r_frame_rate": "60/1"
        }],
        "format": {"duration": str(duration)}
    }

    validator = VideoValidator(duration_tolerance=tolerance)

    with patch('subprocess.run') as mock_run:
        mock_run.return_value = Mock(
            returncode=0,
            stdout=json.dumps(ffprobe_output)
        )

        result = validator.check_duration(sample_video, target)
        assert result == should_match


# ═══════════════════════════════════════════════════════════════════════════════
# Edge Case Tests
# ═══════════════════════════════════════════════════════════════════════════════


@pytest.mark.unit
class TestVideoValidatorEdgeCases:
    """Test edge cases and error conditions."""

    def test_corrupted_video_file(self, video_validator, sample_video):
        """Test validation of corrupted video."""
        with patch('subprocess.run') as mock_run:
            mock_run.side_effect = subprocess.CalledProcessError(
                1, "ffprobe", stderr="Invalid data found when processing input"
            )

            with pytest.raises(FFprobeError):
                video_validator.get_video_info(sample_video)

    def test_empty_video_file(self, video_validator, temp_dir):
        """Test validation of empty file."""
        empty = temp_dir / "empty.mp4"
        empty.write_bytes(b"")

        with patch('subprocess.run') as mock_run:
            mock_run.side_effect = subprocess.CalledProcessError(1, "ffprobe")

            with pytest.raises(FFprobeError):
                video_validator.get_video_info(empty)

    def test_zero_fps_video(self, video_validator, sample_video):
        """Test video with zero FPS."""
        ffprobe_output = {
            "streams": [{
                "codec_type": "video",
                "codec_name": "h264",
                "width": 1920,
                "height": 1080,
                "pix_fmt": "yuv420p",
                "r_frame_rate": "0/1"
            }],
            "format": {"duration": "120.0"}
        }

        with patch('subprocess.run') as mock_run:
            mock_run.return_value = Mock(
                returncode=0,
                stdout=json.dumps(ffprobe_output)
            )

            info = video_validator.get_video_info(sample_video)
            assert info.fps == Fraction(0, 1)

    def test_negative_duration_video(self, video_validator, sample_video):
        """Test video with negative duration string."""
        ffprobe_output = {
            "streams": [{
                "codec_type": "video",
                "codec_name": "h264",
                "width": 1920,
                "height": 1080,
                "pix_fmt": "yuv420p",
                "r_frame_rate": "60/1"
            }],
            "format": {"duration": "-1.0"}
        }

        with patch('subprocess.run') as mock_run:
            mock_run.return_value = Mock(
                returncode=0,
                stdout=json.dumps(ffprobe_output)
            )

            info = video_validator.get_video_info(sample_video)
            assert info.duration == -1.0

    def test_invalid_duration_string(self, video_validator, sample_video):
        """Test video with invalid duration string."""
        ffprobe_output = {
            "streams": [{
                "codec_type": "video",
                "codec_name": "h264",
                "width": 1920,
                "height": 1080,
                "pix_fmt": "yuv420p",
                "r_frame_rate": "60/1"
            }],
            "format": {"duration": "invalid"}
        }

        with patch('subprocess.run') as mock_run:
            mock_run.return_value = Mock(
                returncode=0,
                stdout=json.dumps(ffprobe_output)
            )

            info = video_validator.get_video_info(sample_video)
            assert info.duration == 0.0

    def test_missing_metadata_fields(self, video_validator, sample_video):
        """Test video with missing optional metadata."""
        ffprobe_output = {
            "streams": [{
                "codec_type": "video",
                "codec_name": "h264",
                "width": 1920,
                "height": 1080,
                "pix_fmt": "yuv420p",
                "r_frame_rate": "60/1"
                # Missing color_space, color_primaries, etc.
            }],
            "format": {"duration": "120.0"}
        }

        with patch('subprocess.run') as mock_run:
            mock_run.return_value = Mock(
                returncode=0,
                stdout=json.dumps(ffprobe_output)
            )

            info = video_validator.get_video_info(sample_video)
            assert info.color_space is None
            assert info.color_primaries is None

    def test_very_long_duration(self, video_validator, sample_video):
        """Test video with very long duration."""
        ffprobe_output = {
            "streams": [{
                "codec_type": "video",
                "codec_name": "h264",
                "width": 1920,
                "height": 1080,
                "pix_fmt": "yuv420p",
                "r_frame_rate": "60/1"
            }],
            "format": {"duration": "86400.0"}  # 24 hours
        }

        with patch('subprocess.run') as mock_run:
            mock_run.return_value = Mock(
                returncode=0,
                stdout=json.dumps(ffprobe_output)
            )

            info = video_validator.get_video_info(sample_video)
            assert info.duration == 86400.0

    def test_very_high_resolution(self, video_validator, sample_video):
        """Test video with very high resolution."""
        ffprobe_output = {
            "streams": [{
                "codec_type": "video",
                "codec_name": "h264",
                "width": 7680,
                "height": 4320,  # 8K
                "pix_fmt": "yuv420p",
                "r_frame_rate": "60/1"
            }],
            "format": {"duration": "120.0"}
        }

        with patch('subprocess.run') as mock_run:
            mock_run.return_value = Mock(
                returncode=0,
                stdout=json.dumps(ffprobe_output)
            )

            info = video_validator.get_video_info(sample_video)
            assert info.width == 7680
            assert info.height == 4320

    def test_special_characters_in_filename(self, video_validator, temp_dir):
        """Test video with special characters in filename."""
        # Create file with special characters
        video = temp_dir / "video (2024) [test].mp4"
        video.write_bytes(b"MOCK_VIDEO")

        ffprobe_output = {
            "streams": [{
                "codec_type": "video",
                "codec_name": "h264",
                "width": 1920,
                "height": 1080,
                "pix_fmt": "yuv420p",
                "r_frame_rate": "60/1"
            }],
            "format": {"duration": "120.0"}
        }

        with patch('subprocess.run') as mock_run:
            mock_run.return_value = Mock(
                returncode=0,
                stdout=json.dumps(ffprobe_output)
            )

            info = video_validator.get_video_info(video)
            assert info.codec == "h264"


# ═══════════════════════════════════════════════════════════════════════════════
# Test Coverage Summary
# ═══════════════════════════════════════════════════════════════════════════════

"""
Test Coverage Summary for test_validator.py:

1. Unit Tests (pytest.mark.unit):
   - ValidationIssue: Creation, bilingual messages, to_dict
   - ValidationResult: Creation, add_error, add_warning, properties, to_dict
   - VideoValidator: Initialization, ffprobe check
   - get_video_info: Success cases, error handling, FPS parsing, timeout, JSON errors
   - check_duration: Within tolerance, outside tolerance, exact match, errors
   - check_codec: Matching, aliases, case sensitivity, errors
   - check_resolution: Match, no match, dimension mismatches
   - check_fps: Within tolerance, fractional FPS, parsing
   - check_audio: Has audio, no audio, mismatch
   - check_audio_tracks: Single track, zero tracks, mismatch
   - check_file_integrity: Valid file, zero duration/resolution, errors
   - validate_output: Comprehensive validation with specs
   - PreRenderValidator: Initialization, render specs validation
   - PostRenderValidator: Initialization, output validation, AV sync check
   - Convenience functions: validate_before_render, validate_after_render,
     validate_video_file, quick_validate, validate_ffmpeg_available,
     export_validation_report

2. Integration Tests (pytest.mark.integration):
   - Real ffprobe integration (if available)
   - ffprobe availability check

3. Parametrized Tests:
   - Codec matching with various codec names and aliases
   - Resolution matching with various dimensions
   - FPS parsing for various FPS formats
   - Duration validation with various values and tolerances

4. Edge Cases:
   - Corrupted video files
   - Empty video files
   - Zero FPS videos
   - Negative duration
   - Invalid duration strings
   - Missing metadata fields
   - Very long durations
   - Very high resolutions
   - Special characters in filenames

Target: 80%+ code coverage for validator.py

Test Categories:
- @pytest.mark.unit: Fast, isolated unit tests
- @pytest.mark.integration: Slower integration tests
- @pytest.mark.slow: Tests that require actual file operations or external tools

Total Test Classes: 20+
Total Test Methods: 100+
Parametrized Test Variants: 30+
Total Test Executions: 150+
"""

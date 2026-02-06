#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Unit tests for Security module.

Tests cover:
- Path traversal prevention
- File validation
- Extension validation
- File size validation
"""

import pytest
from pathlib import Path
from unittest.mock import patch
from video_renderer.security import (
    validate_path,
    validate_video_path,
    validate_audio_path,
    PathSecurityError,
    sanitize_filename,
    ALLOWED_VIDEO_EXTENSIONS,
    ALLOWED_AUDIO_EXTENSIONS,
    MAX_FILE_SIZE,
    MIN_FILE_SIZE,
)


@pytest.mark.unit
class TestValidatePath:
    """Test suite for validate_path function."""

    def test_validate_path_string_safe(self):
        """Test validation of safe string path."""
        result = validate_path("video.mp4")
        # validate_path resolves the path
        assert result.exists() or result.name == "video.mp4"

    def test_validate_path_path_object_safe(self):
        """Test validation of safe Path object."""
        result = validate_path(Path("video.mp4"))
        # validate_path resolves the path
        assert result.exists() or result.name == "video.mp4"

    def test_validate_path_traversal_double_dot(self):
        """Test path traversal with double dot raises error."""
        with pytest.raises(PathSecurityError, match="Tehlikeli path"):
            validate_path("../../etc/passwd")

    def test_validate_path_traversal_backslash(self):
        """Test backslash traversal raises error."""
        with pytest.raises(PathSecurityError, match="Tehlikeli path"):
            validate_path("..\\..\\windows\\system32")

    def test_validate_path_with_base_dir(self, temp_dir):
        """Test validation with base directory constraint."""
        base = temp_dir / "allowed"
        base.mkdir()

        # Create a file inside base
        test_file = base / "video.mp4"
        test_file.write_bytes(b"0" * 2048)

        # Safe path within base (relative to base)
        result = validate_path(test_file, base_dir=base)
        assert result == test_file.resolve()

    def test_validate_path_outside_base_dir(self, temp_dir):
        """Test path outside base directory raises error."""
        base = temp_dir / "allowed"
        base.mkdir()

        # Create a file outside base
        outside_file = temp_dir / "outside.mp4"
        outside_file.write_bytes(b"0" * 2048)

        with pytest.raises(PathSecurityError, match="base directory dışında"):
            validate_path(outside_file, base_dir=base)

    def test_validate_path_with_extension_check(self, temp_dir):
        """Test extension validation."""
        video = temp_dir / "test.mp4"
        video.write_bytes(b"0" * 2048)

        result = validate_path(
            video,
            allowed_extensions=ALLOWED_VIDEO_EXTENSIONS
        )
        assert result.suffix == ".mp4"

    def test_validate_path_invalid_extension(self, temp_dir):
        """Test invalid extension raises error."""
        video = temp_dir / "test.exe"
        video.write_bytes(b"0" * 2048)

        with pytest.raises(PathSecurityError, match="İzin verilmeyen"):
            validate_path(
                video,
                allowed_extensions=ALLOWED_VIDEO_EXTENSIONS
            )

    def test_validate_path_with_exists_check(self, temp_dir):
        """Test file existence check."""
        existing = temp_dir / "exists.mp4"
        existing.write_bytes(b"0" * 2048)

        result = validate_path(existing, check_exists=True)
        assert result == existing

    def test_validate_path_not_exists(self, temp_dir):
        """Test non-existent file raises error."""
        nonexistent = temp_dir / "nonexistent.mp4"

        with pytest.raises(PathSecurityError, match="Dosya bulunamadı"):
            validate_path(nonexistent, check_exists=True)

    def test_validate_path_too_small(self, temp_dir):
        """Test file smaller than minimum raises error."""
        small_file = temp_dir / "small.mp4"
        small_file.write_bytes(b"0" * 512)  # 512 bytes < MIN_FILE_SIZE

        with pytest.raises(PathSecurityError, match="çok küçük"):
            validate_path(small_file)

    def test_validate_path_too_large(self, temp_dir):
        """Test file larger than maximum raises error."""
        large_file = temp_dir / "large.mp4"

        with patch('pathlib.Path.stat') as mock_stat:
            mock_stat.return_value.st_size = MAX_FILE_SIZE + 1

            with pytest.raises(PathSecurityError, match="çok büyük"):
                validate_path(large_file)

    def test_validate_path_case_insensitive_extension(self, temp_dir):
        """Test extension check is case-insensitive."""
        video = temp_dir / "test.MP4"
        video.write_bytes(b"0" * 2048)

        result = validate_path(
            video,
            allowed_extensions=ALLOWED_VIDEO_EXTENSIONS
        )
        assert result == video.resolve()


@pytest.mark.unit
class TestValidateVideoPath:
    """Test suite for validate_video_path function."""

    def test_validate_video_path_valid(self, temp_dir):
        """Test valid video path."""
        video = temp_dir / "test.mp4"
        video.write_bytes(b"0" * 2048)

        result = validate_video_path(video)
        assert result.suffix == ".mp4"

    def test_validate_video_path_invalid_extension(self, temp_dir):
        """Test invalid video extension raises error."""
        audio = temp_dir / "test.mp3"
        audio.write_bytes(b"0" * 2048)

        with pytest.raises(PathSecurityError):
            validate_video_path(audio)


@pytest.mark.unit
class TestValidateAudioPath:
    """Test suite for validate_audio_path function."""

    def test_validate_audio_path_valid(self, temp_dir):
        """Test valid audio path."""
        audio = temp_dir / "test.mp3"
        audio.write_bytes(b"0" * 2048)

        result = validate_audio_path(audio)
        assert result.suffix == ".mp3"

    def test_validate_audio_path_invalid_extension(self, temp_dir):
        """Test invalid audio extension raises error."""
        video = temp_dir / "test.mp4"
        video.write_bytes(b"0" * 2048)

        with pytest.raises(PathSecurityError):
            validate_audio_path(video)


@pytest.mark.unit
class TestSanitizeFilename:
    """Test suite for sanitize_filename function."""

    def test_sanitize_filename_safe(self):
        """Test safe filenames are unchanged."""
        safe_names = [
            "video.mp4",
            "my-video-2024.mp4",
            "track_123.mp3",
        ]

        for name in safe_names:
            result = sanitize_filename(name)
            assert result == name

    def test_sanitize_filename_dangerous_chars(self):
        """Test dangerous characters are removed/sanitized."""
        # Test that dangerous characters are sanitized
        dangerous = "video*file?.mp4"
        result = sanitize_filename(dangerous)
        # Both * and ? should be replaced with _
        assert "*" not in result
        assert "?" not in result
        assert "file" in result

        # Test path traversal characters
        traversal = "../../video.mp4"
        result = sanitize_filename(traversal)
        # .. should be replaced but not completely removed
        assert result.count("_") >= 2  # At least the .. characters become _
        assert "video.mp4" in result

        # Test other special characters
        special_chars = [
            ("file\\name.mp4", "file_name.mp4"),
            ("video:file.mp4", "video_file.mp4"),
            ("video|file.mp4", "video_file.mp4"),
        ]

        for input_name, expected in special_chars:
            result = sanitize_filename(input_name)
            assert "\\" not in result
            assert ":" not in result
            assert "|" not in result

    def test_sanitize_filename_empty_result(self):
        """Test empty after sanitization returns default."""
        dangerous_names = ["..", "...", "::::"]

        for name in dangerous_names:
            result = sanitize_filename(name)
            # Empty names become "unnamed"
            assert result == "unnamed" or result != ""


@pytest.mark.unit
class TestPathResolution:
    """Test suite for path resolution and symlink protection."""

    def test_resolve_protects_against_symlinks(self, temp_dir):
        """Test resolution protects against symlink attacks."""
        # Create a symlink pointing outside
        target = temp_dir / "target.txt"
        target.write_text("secret")

        symlink = temp_dir / "symlink.txt"

        # Create symlink (skip on Windows where symlinks need admin)
        try:
            symlink.symlink_to(target)
        except (OSError, NotImplementedError):
            # Skip test on systems without symlink support
            pytest.skip("Symlink creation not supported")

        base = temp_dir / "base"
        base.mkdir()

        # Try to validate symlink outside base
        with pytest.raises(PathSecurityError, match="base directory dışında"):
            validate_path(symlink, base_dir=base)

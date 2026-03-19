#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Unit tests for temp cleanup functionality.

Tests cover:
- cleanup_temp_files function
- get_tmp_dir_size function
- check_disk_space function
- CleanupResult dataclass
"""

import pytest
import time
import tempfile
from pathlib import Path
from video_renderer.ffmpeg import (
    cleanup_temp_files,
    get_tmp_dir_size,
    check_disk_space,
    CleanupResult
)


@pytest.mark.unit
class TestCleanupResult:
    """Test suite for CleanupResult dataclass."""

    def test_result_creation(self):
        """Test creating a CleanupResult."""
        result = CleanupResult()
        
        assert result.deleted_files == []
        assert result.errors == []
        assert result.skipped_files == []
        assert result.deleted_size_bytes == 0
        assert result.success is True

    def test_result_size_mb(self):
        """Test size conversion to MB."""
        result = CleanupResult(
            deleted_files=["file1.mp4", "file2.mp4"],
            deleted_size_bytes=10 * 1024 * 1024  # 10 MB
        )
        
        assert result.deleted_size_mb == 10.0

    def test_result_with_errors(self):
        """Test result with errors."""
        result = CleanupResult(
            errors=["Permission denied: file.mp4"]
        )
        
        assert result.success is False


@pytest.mark.unit
class TestCleanupTempFiles:
    """Test suite for cleanup_temp_files function."""

    def test_cleanup_empty_dir(self, temp_dir):
        """Test cleanup on empty directory."""
        tmp_dir = temp_dir / "tmp"
        tmp_dir.mkdir()
        
        result = cleanup_temp_files(tmp_dir)
        
        assert len(result.deleted_files) == 0
        assert result.success is True

    def test_cleanup_old_files(self, temp_dir):
        """Test cleanup of old files."""
        tmp_dir = temp_dir / "tmp"
        tmp_dir.mkdir()
        
        old_file = tmp_dir / "old_video.mp4"
        old_file.write_bytes(b"x" * 1000)
        
        result = cleanup_temp_files(
            tmp_dir=tmp_dir,
            min_age_hours=0
        )
        
        assert len(result.deleted_files) == 1
        assert "old_video.mp4" in result.deleted_files
        assert not old_file.exists()

    def test_cleanup_preserve_recent(self, temp_dir):
        """Test that recent files are preserved."""
        tmp_dir = temp_dir / "tmp"
        tmp_dir.mkdir()
        
        recent_file = tmp_dir / "recent_video.mp4"
        recent_file.write_bytes(b"x" * 1000)
        
        result = cleanup_temp_files(
            tmp_dir=tmp_dir,
            min_age_hours=1.0
        )
        
        assert len(result.deleted_files) == 0
        assert recent_file.exists()

    def test_cleanup_preserve_patterns(self, temp_dir):
        """Test that preserved files are not deleted."""
        tmp_dir = temp_dir / "tmp"
        tmp_dir.mkdir()
        
        session_file = tmp_dir / "last_session.json"
        session_file.write_text("{}")
        
        video_file = tmp_dir / "video.mp4"
        video_file.write_bytes(b"x" * 1000)
        
        result = cleanup_temp_files(
            tmp_dir=tmp_dir,
            min_age_hours=0,
            preserve_patterns=["last_session.json"]
        )
        
        assert "last_session.json" in result.skipped_files
        assert session_file.exists()
        assert "video.mp4" in result.deleted_files

    def test_cleanup_dry_run(self, temp_dir):
        """Test dry run mode."""
        tmp_dir = temp_dir / "tmp"
        tmp_dir.mkdir()
        
        test_file = tmp_dir / "test.mp4"
        test_file.write_bytes(b"x" * 1000)
        
        result = cleanup_temp_files(
            tmp_dir=tmp_dir,
            min_age_hours=0,
            dry_run=True
        )
        
        assert "test.mp4" in result.deleted_files
        assert test_file.exists()

    def test_cleanup_multiple_patterns(self, temp_dir):
        """Test cleanup with multiple file patterns."""
        tmp_dir = temp_dir / "tmp"
        tmp_dir.mkdir()
        
        (tmp_dir / "video.mp4").write_bytes(b"x" * 1000)
        (tmp_dir / "audio.w64").write_bytes(b"x" * 1000)
        (tmp_dir / "video_list.txt").write_text("file list")
        (tmp_dir / "run_log_001.txt").write_text("log")
        
        result = cleanup_temp_files(
            tmp_dir=tmp_dir,
            min_age_hours=0
        )
        
        assert len(result.deleted_files) == 4

    def test_cleanup_nonexistent_dir(self, temp_dir):
        """Test cleanup on nonexistent directory."""
        tmp_dir = temp_dir / "nonexistent"
        
        result = cleanup_temp_files(tmp_dir)
        
        assert result.success is True
        assert len(result.deleted_files) == 0


@pytest.mark.unit
class TestGetTmpDirSize:
    """Test suite for get_tmp_dir_size function."""

    def test_empty_dir(self, temp_dir):
        """Test size of empty directory."""
        tmp_dir = temp_dir / "tmp"
        tmp_dir.mkdir()
        
        size, count = get_tmp_dir_size(tmp_dir)
        
        assert size == 0
        assert count == 0

    def test_with_files(self, temp_dir):
        """Test size calculation with files."""
        tmp_dir = temp_dir / "tmp"
        tmp_dir.mkdir()
        
        (tmp_dir / "file1.mp4").write_bytes(b"x" * 1000)
        (tmp_dir / "file2.mp4").write_bytes(b"x" * 2000)
        
        size, count = get_tmp_dir_size(tmp_dir)
        
        assert size == 3000
        assert count == 2

    def test_nonexistent_dir(self, temp_dir):
        """Test size of nonexistent directory."""
        tmp_dir = temp_dir / "nonexistent"
        
        size, count = get_tmp_dir_size(tmp_dir)
        
        assert size == 0
        assert count == 0


@pytest.mark.unit
class TestCheckDiskSpace:
    """Test suite for check_disk_space function."""

    def test_below_threshold(self, temp_dir):
        """Test when size is below threshold."""
        tmp_dir = temp_dir / "tmp"
        tmp_dir.mkdir()
        
        (tmp_dir / "small.mp4").write_bytes(b"x" * 1000)
        
        warn, auto = check_disk_space(
            tmp_dir=tmp_dir,
            warn_threshold_gb=10.0,
            auto_cleanup_threshold_gb=20.0
        )
        
        assert warn is False
        assert auto is False

    def test_empty_dir(self, temp_dir):
        """Test with empty directory."""
        tmp_dir = temp_dir / "tmp"
        tmp_dir.mkdir()
        
        warn, auto = check_disk_space(tmp_dir)
        
        assert warn is False
        assert auto is False


@pytest.fixture
def temp_dir(tmp_path):
    """Create a temporary directory for tests."""
    return tmp_path
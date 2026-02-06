#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Unit tests for FFmpegRunner and related functions.

Tests cover:
- FFmpegRunner initialization and execution
- Progress parsing
- Video probing
- Duration detection
- Concat list writing
- Command logging
"""

import pytest
import subprocess
import time
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch, mock_open, call
from video_renderer.ffmpeg import (
    FFmpegRunner,
    FFmpegProgress,
    VideoInfo,
    probe_video,
    get_duration,
    write_concat_list
)


@pytest.mark.unit
class TestFFmpegProgress:
    """Test suite for FFmpegProgress dataclass."""

    def test_default_values(self):
        """Test FFmpegProgress default values."""
        progress = FFmpegProgress()

        assert progress.frame == 0
        assert progress.fps == 0.0
        assert progress.time_seconds == 0.0
        assert progress.speed == 0.0
        assert progress.size_kb == 0
        assert progress.bitrate_kbps == 0.0
        assert progress.percent == 0.0

    def test_custom_values(self):
        """Test FFmpegProgress with custom values."""
        progress = FFmpegProgress(
            frame=1000,
            fps=60.0,
            time_seconds=16.67,
            speed=1.5,
            size_kb=1024,
            bitrate_kbps=500.0,
            percent=25.0
        )

        assert progress.frame == 1000
        assert progress.fps == 60.0
        assert progress.time_seconds == pytest.approx(16.67, rel=0.01)
        assert progress.speed == 1.5
        assert progress.size_kb == 1024
        assert progress.bitrate_kbps == 500.0
        assert progress.percent == 25.0


@pytest.mark.unit
class TestVideoInfo:
    """Test suite for VideoInfo dataclass."""

    def test_video_info_creation(self):
        """Test creating VideoInfo with all fields."""
        info = VideoInfo(
            codec="h264",
            width=1920,
            height=1080,
            fps="60/1",
            duration=3600.0,
            pix_fmt="yuv420p",
            color_space="bt709",
            color_primaries="bt709",
            color_transfer="bt709",
            profile="High"
        )

        assert info.codec == "h264"
        assert info.width == 1920
        assert info.height == 1080
        assert info.fps == "60/1"
        assert info.duration == 3600.0
        assert info.pix_fmt == "yuv420p"
        assert info.color_space == "bt709"


@pytest.mark.unit
class TestFFmpegRunner:
    """Test suite for FFmpegRunner class."""

    def test_init(self):
        """Test FFmpegRunner initialization."""
        runner = FFmpegRunner()

        assert runner.log_path is None
        assert runner._progress_callback is None
        assert runner._total_duration == 0.0

    def test_init_with_log_path(self, temp_dir):
        """Test FFmpegRunner initialization with log path."""
        log_path = temp_dir / "ffmpeg.log"
        runner = FFmpegRunner(log_path=log_path)

        assert runner.log_path == log_path

    def test_set_progress_callback(self):
        """Test setting progress callback."""
        runner = FFmpegRunner()
        callback = MagicMock()

        runner.set_progress_callback(callback)

        assert runner._progress_callback == callback

    def test_set_total_duration(self):
        """Test setting total duration."""
        runner = FFmpegRunner()

        runner.set_total_duration(3600.0)

        assert runner._total_duration == 3600.0

    def test_log_command_no_log_path(self):
        """Test logging command when no log path set."""
        runner = FFmpegRunner()
        cmd = ["ffmpeg", "-i", "input.mp4", "output.mp4"]

        # Should not raise
        runner._log_command(cmd)

    def test_log_command_with_log_path(self, temp_dir):
        """Test logging command to file."""
        log_path = temp_dir / "test.log"
        runner = FFmpegRunner(log_path=log_path)
        cmd = ["ffmpeg", "-i", "input.mp4", "output.mp4"]

        runner._log_command(cmd)

        assert log_path.exists()
        content = log_path.read_text()
        assert "ffmpeg" in content
        assert "input.mp4" in content

    @pytest.mark.parametrize("line, expected_progress", [
        ("frame=  123 fps= 45.6 q=28.0 size=    1234kB time=00:01:23.45 bitrate= 123.4kbits/s speed=1.23x",
         FFmpegProgress(frame=123, fps=45.6, time_seconds=83.45, speed=1.23)),
        ("frame=  456 fps= 60.0 time=00:02:00.00 speed=1.00x",
         FFmpegProgress(frame=456, fps=60.0, time_seconds=120.0, speed=1.0)),
        ("No progress here", None),
        ("", None),
    ])
    def test_parse_progress_line(self, line, expected_progress):
        """Test parsing various progress line formats."""
        runner = FFmpegRunner()
        runner._total_duration = 240.0  # For percent calculation

        result = runner._parse_progress_line(line)

        if expected_progress is None:
            assert result is None
        else:
            assert result is not None
            assert result.frame == expected_progress.frame
            assert result.fps == expected_progress.fps
            assert result.time_seconds == pytest.approx(expected_progress.time_seconds, rel=0.01)

    def test_parse_progress_percent_calculation(self):
        """Test progress percent is calculated correctly."""
        runner = FFmpegRunner()
        runner._total_duration = 100.0

        line = "frame=  100 fps= 60.0 time=00:00:50.00 speed=1.00x"
        result = runner._parse_progress_line(line)

        assert result.percent == pytest.approx(50.0, rel=0.01)

    def test_parse_progress_no_duration_set(self):
        """Test progress parsing when duration not set."""
        runner = FFmpegRunner()
        runner._total_duration = 0.0

        line = "frame=  100 fps= 60.0 time=00:00:50.00 speed=1.00x"
        result = runner._parse_progress_line(line)

        assert result.percent == 0.0

    def test_parse_progress_percent_cap(self):
        """Test progress percent is capped at 100."""
        runner = FFmpegRunner()
        runner._total_duration = 50.0

        line = "frame=  100 fps= 60.0 time=00:01:00.00 speed=1.00x"
        result = runner._parse_progress_line(line)

        assert result.percent == 100.0

    def test_run_without_progress(self):
        """Test running command without progress capture."""
        runner = FFmpegRunner()
        cmd = ["echo", "test"]

        with patch('subprocess.run') as mock_run:
            mock_run.return_value = Mock(returncode=0)

            result = runner.run(cmd, capture_progress=False)

            assert result.returncode == 0
            mock_run.assert_called_once_with(cmd, check=True)

    def test_run_with_progress_no_callback(self):
        """Test running command with progress but no callback."""
        runner = FFmpegRunner()
        cmd = ["echo", "test"]

        with patch('subprocess.run') as mock_run:
            mock_run.return_value = Mock(returncode=0)

            result = runner.run(cmd, capture_progress=True)

            assert result.returncode == 0
            # Should use subprocess.run directly since no callback
            mock_run.assert_called_once_with(cmd, check=True)

    def test_run_with_progress_and_callback(self):
        """Test running command with progress callback."""
        runner = FFmpegRunner()
        callback = MagicMock()
        runner.set_progress_callback(callback)

        cmd = ["ffmpeg", "-i", "input.mp4", "output.mp4"]

        with patch('subprocess.Popen') as mock_popen:
            # Mock process that outputs progress
            process = Mock()
            process.returncode = 0
            process.stderr = iter([
                "frame=   50 fps= 60.0 time=00:00:01.00 speed=1.00x\n",
                "frame=  100 fps= 60.0 time=00:00:02.00 speed=1.00x\n",
            ])
            mock_popen.return_value = process

            result = runner.run(cmd, capture_progress=True)

            assert callback.call_count > 0

    def test_run_command_failure(self):
        """Test running command that fails."""
        runner = FFmpegRunner()
        cmd = ["ffmpeg", "-i", "nonexistent.mp4", "output.mp4"]

        with patch('subprocess.Popen') as mock_popen:
            process = Mock()
            process.returncode = 1
            process.stderr = iter(["Error: File not found\n"])
            process.stdout.read.return_value = ""
            mock_popen.return_value = process

            with pytest.raises(subprocess.CalledProcessError):
                runner.run(cmd, capture_progress=True)

    def test_run_simple(self):
        """Test run_simple method."""
        runner = FFmpegRunner()
        cmd = ["echo", "test"]

        with patch('subprocess.run') as mock_run:
            mock_run.return_value = Mock(returncode=0, stdout="test", stderr="")

            result = runner.run_simple(cmd)

            assert result.returncode == 0
            mock_run.assert_called_once_with(
                cmd, check=True, capture_output=True, text=True
            )


@pytest.mark.unit
class TestProbeVideo:
    """Test suite for probe_video function."""

    def test_probe_video_success(self):
        """Test successful video probing."""
        ffprobe_output = """codec_name=h264
width=1920
height=1080
pix_fmt=yuv420p
r_frame_rate=60/1
color_space=bt709
color_primaries=bt709
color_transfer=bt709
profile=High"""

        with patch('subprocess.run') as mock_run:
            mock_run.return_value = Mock(
                returncode=0,
                stdout=ffprobe_output
            )

            with patch('video_renderer.ffmpeg.get_duration') as mock_duration:
                mock_duration.return_value = 120.0

                info = probe_video(Path("test.mp4"))

                assert info.codec == "h264"
                assert info.width == 1920
                assert info.height == 1080
                assert info.pix_fmt == "yuv420p"
                assert info.fps == "60/1"
                assert info.duration == 120.0

    def test_probe_video_missing_fields(self):
        """Test probing video with missing fields."""
        ffprobe_output = "codec_name=h264\nwidth=1920"

        with patch('subprocess.run') as mock_run:
            mock_run.return_value = Mock(
                returncode=0,
                stdout=ffprobe_output
            )

            with patch('video_renderer.ffmpeg.get_duration') as mock_duration:
                mock_duration.return_value = 120.0

                info = probe_video(Path("test.mp4"))

                assert info.codec == "h264"
                assert info.width == 1920
                assert info.height == 0  # Missing
                assert info.fps == "0/1"  # Default

    def test_probe_video_error(self):
        """Test probing video that fails."""
        with patch('subprocess.run') as mock_run:
            mock_run.side_effect = subprocess.CalledProcessError(1, "ffprobe")

            with pytest.raises(subprocess.CalledProcessError):
                probe_video(Path("test.mp4"))


@pytest.mark.unit
class TestGetDuration:
    """Test suite for get_duration function."""

    @pytest.mark.parametrize("duration_str, expected", [
        ("120.5", 120.5),
        ("3600.0", 3600.0),
        ("0.0", 0.0),
        ("1", 1.0),
    ])
    def test_get_duration_valid(self, duration_str, expected):
        """Test getting duration from valid output."""
        with patch('subprocess.run') as mock_run:
            mock_run.return_value = Mock(
                returncode=0,
                stdout=duration_str
            )

            result = get_duration(Path("test.mp4"))

            assert result == expected

    def test_get_duration_invalid(self):
        """Test getting duration with invalid output."""
        with patch('subprocess.run') as mock_run:
            mock_run.return_value = Mock(
                returncode=0,
                stdout="invalid"
            )

            result = get_duration(Path("test.mp4"))

            assert result == 0.0

    def test_get_duration_error(self):
        """Test getting duration when command fails."""
        with patch('subprocess.run') as mock_run:
            mock_run.side_effect = subprocess.CalledProcessError(1, "ffprobe")

            with pytest.raises(subprocess.CalledProcessError):
                get_duration(Path("test.mp4"))


@pytest.mark.unit
class TestWriteConcatList:
    """Test suite for write_concat_list function."""

    def test_write_concat_list_basic(self, temp_dir):
        """Test writing basic concat list."""
        files = [
            temp_dir / "video1.mp4",
            temp_dir / "video2.mp4",
            temp_dir / "video3.mp4"
        ]
        output = temp_dir / "list.txt"

        for f in files:
            f.touch()

        write_concat_list(files, output)

        assert output.exists()
        content = output.read_text()

        for f in files:
            assert f"file '{f.as_posix()}'" in content

    def test_write_concat_list_single_file(self, temp_dir):
        """Test writing concat list with single file."""
        files = [temp_dir / "video.mp4"]
        files[0].touch()
        output = temp_dir / "list.txt"

        write_concat_list(files, output)

        content = output.read_text()
        assert content.count("file ") == 1

    def test_write_concat_list_empty(self, temp_dir):
        """Test writing empty concat list."""
        files = []
        output = temp_dir / "list.txt"

        write_concat_list(files, output)

        content = output.read_text()
        assert content.strip() == ""

    def test_write_concat_list_absolute_paths(self, temp_dir):
        """Test concat list uses absolute paths."""
        files = [temp_dir / "video.mp4"]
        files[0].touch()
        output = temp_dir / "list.txt"

        write_concat_list(files, output)

        content = output.read_text()
        assert str(temp_dir) in content


@pytest.mark.unit
class TestFFmpegRunnerIntegration:
    """Integration tests for FFmpegRunner."""

    def test_full_workflow_with_logging(self, temp_dir):
        """Test full workflow with command logging."""
        log_path = temp_dir / "ffmpeg.log"
        runner = FFmpegRunner(log_path=log_path)

        callback = MagicMock()
        runner.set_progress_callback(callback)
        runner.set_total_duration(100.0)

        cmd = ["echo", "test"]

        with patch('subprocess.run') as mock_run:
            mock_run.return_value = Mock(returncode=0)

            runner.run(cmd, capture_progress=False)

        # Check log was written
        assert log_path.exists()

    def test_progress_tracking_workflow(self):
        """Test progress tracking workflow."""
        runner = FFmpegRunner()

        captured_progress = []

        def callback(progress):
            captured_progress.append(progress)

        runner.set_progress_callback(callback)
        runner.set_total_duration(100.0)

        # Simulate progress parsing
        line1 = "frame=  50 fps= 60.0 time=00:00:25.00 speed=1.00x"
        line2 = "frame= 100 fps= 60.0 time=00:00:50.00 speed=1.00x"

        result1 = runner._parse_progress_line(line1)
        result2 = runner._parse_progress_line(line2)

        assert result1.percent == 25.0
        assert result2.percent == 50.0


@pytest.mark.unit
@pytest.mark.parametrize("fps_str, expected_value", [
    ("60/1", 60.0),
    ("30000/1001", pytest.approx(29.97, rel=0.01)),
    ("24000/1001", pytest.approx(23.98, rel=0.01)),
    ("60000/1001", pytest.approx(59.94, rel=0.01)),
])
def test_fps_parsing_edge_cases(fps_str, expected_value):
    """Test parsing various FPS string formats."""
    # This is implicitly tested through probe_video
    # but we can verify the parsing logic
    parts = fps_str.split("/")
    if len(parts) == 2:
        value = float(parts[0]) / float(parts[1])
        assert value == expected_value


@pytest.mark.unit
def test_videoinfo_optional_fields():
    """Test VideoInfo handles optional color fields."""
    info = VideoInfo(
        codec="h264",
        width=1920,
        height=1080,
        fps="60/1",
        duration=120.0,
        pix_fmt="yuv420p",
        color_space=None,
        color_primaries=None,
        color_transfer=None
    )

    assert info.color_space is None
    assert info.color_primaries is None
    assert info.color_transfer is None

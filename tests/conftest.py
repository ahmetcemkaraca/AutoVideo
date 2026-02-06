#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Pytest configuration and shared fixtures for AutoVideo tests.

This module provides:
- Path fixtures for test data
- Mock fixtures for external dependencies
- Configuration fixtures
- Utility functions for test setup
"""

import json
import os
import shutil
import tempfile
from pathlib import Path
from typing import List, Generator, Optional
from unittest.mock import MagicMock, Mock, patch
import pytest
from dataclasses import dataclass
from datetime import datetime

# Add project root to path for imports
import sys
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


# ═══════════════════════════════════════════════════════════════════════════════
# Path Fixtures
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.fixture
def temp_dir() -> Generator[Path, None, None]:
    """Create a temporary directory that is cleaned up after the test."""
    with tempfile.TemporaryDirectory() as tmp:
        yield Path(tmp)


@pytest.fixture
def work_dir(temp_dir: Path) -> Path:
    """Create a working directory with subdirectories."""
    work = temp_dir / "work"
    work.mkdir()
    (work / "tmp").mkdir()
    (work / "music").mkdir()
    (work / "background").mkdir()
    (work / "archive").mkdir()
    return work


@pytest.fixture
def test_data_dir() -> Path:
    """Get the path to the test data directory."""
    return Path(__file__).parent / "fixtures" / "data"


@pytest.fixture
def sample_video_path(test_data_dir: Path) -> Path:
    """Get path to a sample video file (may need to be created)."""
    return test_data_dir / "sample_video.mp4"


@pytest.fixture
def sample_audio_path(test_data_dir: Path) -> Path:
    """Get path to a sample audio file (may need to be created)."""
    return test_data_dir / "sample_audio.mp3"


# ═══════════════════════════════════════════════════════════════════════════════
# FFmpeg Mocks
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.fixture
def mock_ffmpeg_installed() -> Mock:
    """Mock that FFmpeg is installed and available."""
    with patch('shutil.which') as mock_which:
        mock_which.return_value = '/usr/bin/ffmpeg'
        yield mock_which


@pytest.fixture
def mock_ffprobe_output() -> dict:
    """Sample ffprobe output for testing."""
    return {
        "codec_name": "h264",
        "width": "1920",
        "height": "1080",
        "pix_fmt": "yuv420p",
        "r_frame_rate": "60/1",
        "color_space": "bt709",
        "color_primaries": "bt709",
        "color_transfer": "bt709",
        "profile": "High"
    }


@pytest.fixture
def mock_video_info() -> "VideoInfo":
    """Create a mock VideoInfo object."""
    from video_renderer.ffmpeg import VideoInfo
    return VideoInfo(
        codec="h264",
        width=1920,
        height=1080,
        fps="60/1",
        duration=120.0,
        pix_fmt="yuv420p",
        color_space="bt709",
        color_primaries="bt709",
        color_transfer="bt709",
        profile="High"
    )


@pytest.fixture
def mock_subprocess_run(mock_video_info):
    """Mock subprocess.run for ffprobe calls."""
    with patch('subprocess.run') as mock_run:
        # Mock ffprobe output
        mock_run.return_value = Mock(
            returncode=0,
            stdout=f"codec_name={mock_video_info.codec}\n"
                   f"width={mock_video_info.width}\n"
                   f"height={mock_video_info.height}\n"
                   f"pix_fmt={mock_video_info.pix_fmt}\n"
                   f"r_frame_rate={mock_video_info.fps}\n"
                   f"color_space={mock_video_info.color_space}\n"
                   f"color_primaries={mock_video_info.color_primaries}\n"
                   f"color_transfer={mock_video_info.color_transfer}\n"
                   f"profile={mock_video_info.profile}\n",
            stderr=""
        )
        yield mock_run


@pytest.fixture
def mock_ffmpeg_runner():
    """Mock FFmpegRunner with progress tracking."""
    from video_renderer.ffmpeg import FFmpegRunner, FFmpegProgress

    runner = MagicMock(spec=FFmpegRunner)
    runner.run = MagicMock(return_value=Mock(returncode=0))
    runner.run_simple = MagicMock(return_value=Mock(returncode=0))
    runner.set_progress_callback = MagicMock()
    runner.set_total_duration = MagicMock()

    return runner


# ═══════════════════════════════════════════════════════════════════════════════
# Video Renderer Fixtures
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.fixture
def codec_config():
    """Get a sample codec configuration."""
    from config import CODEC_H264
    return CODEC_H264


@pytest.fixture
def color_config():
    """Get a sample color configuration."""
    from config import COLOR_BT709
    return COLOR_BT709


@pytest.fixture
def video_encoder(mock_ffmpeg_runner, codec_config, color_config):
    """Create a VideoEncoder instance with mocked dependencies."""
    from video_renderer.video import VideoEncoder
    return VideoEncoder(
        runner=mock_ffmpeg_runner,
        codec_config=codec_config,
        color_config=color_config,
        width=1920,
        height=1080,
        fps=60
    )


@pytest.fixture
def audio_processor(mock_ffmpeg_runner, temp_dir):
    """Create an AudioProcessor instance with mocked dependencies."""
    from video_renderer.audio import AudioProcessor
    return AudioProcessor(
        runner=mock_ffmpeg_runner,
        tmp_dir=temp_dir
    )


@pytest.fixture
def batch_queue(temp_dir):
    """Create a BatchQueue instance with test queue file."""
    from video_renderer.batch import BatchQueue
    queue_file = temp_dir / "test_batch_queue.json"
    return BatchQueue(queue_file=queue_file)


# ═══════════════════════════════════════════════════════════════════════════════
# Render Job Fixtures
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.fixture
def sample_render_job(work_dir):
    """Create a sample RenderJob."""
    from video_renderer.batch import RenderJob, JobStatus

    job = RenderJob(id=1)
    job.intro_path = work_dir / "intro.mp4"
    job.loop_path = work_dir / "loop.mp4"
    job.mode = "intro_loop"
    job.codec_family = "h264"
    job.duration_str = "1:00:00"
    job.total_seconds = 3600
    job.tracks = [work_dir / "music" / "track1.mp3"]
    job.backgrounds = [(work_dir / "background" / "rain.mp3", -8.0)]
    job.output_path = work_dir / "output.mp4"
    job.status = JobStatus.CONFIGURING

    return job


@pytest.fixture
def queued_render_job(sample_render_job):
    """Create a queued RenderJob."""
    from video_renderer.batch import JobStatus
    sample_render_job.status = JobStatus.QUEUED
    return sample_render_job


# ═══════════════════════════════════════════════════════════════════════════════
# Test Media File Creation
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.fixture
def create_test_video(work_dir):
    """Factory function to create test video files."""
    def _create(
        name: str,
        duration: float = 10.0,
        codec: str = "h264",
        width: int = 1920,
        height: int = 1080,
        fps: int = 60
    ) -> Path:
        """Create a minimal test video file."""
        video_path = work_dir / name

        # Create a minimal valid video file using FFmpeg if available
        # For unit tests, we might just create an empty file with .mp4 extension
        # or use a pre-generated test video
        video_path.touch()

        return video_path

    return _create


@pytest.fixture
def create_test_audio(work_dir):
    """Factory function to create test audio files."""
    def _create(
        name: str,
        duration: float = 10.0,
        format: str = "mp3"
    ) -> Path:
        """Create a minimal test audio file."""
        audio_path = work_dir / name
        audio_path.touch()
        return audio_path

    return _create


# ═══════════════════════════════════════════════════════════════════════════════
# YouTube API Mocks
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.fixture
def mock_youtube_service():
    """Mock YouTube service object."""
    mock_service = MagicMock()
    mock_service.videos.return_value.insert.return_value.execute.return_value = {
        'id': 'test_video_id_12345'
    }
    return mock_service


@pytest.fixture
def mock_youtube_credentials(temp_dir):
    """Create mock YouTube credentials files."""
    client_secrets = temp_dir / "client_secrets.json"
    credentials_file = temp_dir / "youtube_credentials.json"

    # Create mock client secrets
    client_secrets.write_text(json.dumps({
        "installed": {
            "client_id": "test_client_id",
            "client_secret": "test_client_secret",
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token"
        }
    }))

    # Create mock credentials
    credentials_file.write_text(json.dumps({
        "token": "test_token",
        "refresh_token": "test_refresh_token",
        "token_uri": "https://oauth2.googleapis.com/token",
        "client_id": "test_client_id",
        "client_secret": "test_client_secret",
        "scopes": ["https://www.googleapis.com/auth/youtube.upload"]
    }))

    return {
        "client_secrets": client_secrets,
        "credentials": credentials_file
    }


# ═══════════════════════════════════════════════════════════════════════════════
# Pipeline Configuration Fixtures
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.fixture
def pipeline_config(work_dir, mock_youtube_credentials):
    """Create a PipelineConfig for testing."""
    from config import PipelineConfig, YouTubeConfig

    config = PipelineConfig(
        work_dir=work_dir,
        music_dir=work_dir / "music",
        output_dir=work_dir / "output",
        intro_video=work_dir / "intro.mp4",
        loop_video=work_dir / "loop.mp4",
        target_duration="1:00:00",
        codec="h264"
    )

    config.youtube = YouTubeConfig(
        client_secrets_file=str(mock_youtube_credentials["client_secrets"]),
        credentials_file=str(mock_youtube_credentials["credentials"])
    )

    return config


# ═══════════════════════════════════════════════════════════════════════════════
# State Management Fixtures
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.fixture
def state_file(temp_dir):
    """Create a state file for testing."""
    return temp_dir / "test_state.json"


@pytest.fixture
def sample_state_data():
    """Sample state data for testing."""
    return {
        "videos": [
            {
                "video_id": "abc123",
                "title": "Test Video",
                "genre": "ambient",
                "style": "relaxing",
                "duration": "1:00:00",
                "local_path": "/path/to/video.mp4",
                "created_at": "2024-01-01T00:00:00",
                "uploaded_at": "2024-01-01T00:05:00"
            }
        ],
        "stats": {
            "total_videos": 1,
            "total_duration_hours": 1.0
        },
        "last_run": "2024-01-01T00:00:00"
    }


# ═══════════════════════════════════════════════════════════════════════════════
# Progress Callback Mocks
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.fixture
def mock_progress_callback():
    """Mock progress callback function."""
    callback = MagicMock()
    callback.return_value = None
    return callback


@pytest.fixture
def captured_progress():
    """Fixture to capture progress updates."""
    captured = []

    def capture(progress):
        from video_renderer.ffmpeg import FFmpegProgress
        if isinstance(progress, FFmpegProgress):
            captured.append(progress)

    return capture, captured


# ═══════════════════════════════════════════════════════════════════════════════
# Test Utilities
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.fixture
def skip_if_no_ffmpeg():
    """Skip test if FFmpeg is not installed."""
    if not shutil.which("ffmpeg"):
        pytest.skip("FFmpeg not installed")
    yield


@pytest.fixture
def skip_if_no_gpu():
    """Skip test if GPU acceleration is not available."""
    # Could check for nvidia-smi or similar
    # For now, this is just a marker
    yield


@pytest.fixture
def freeze_time():
    """Freeze time for deterministic tests."""
    from freezegun import freeze_time as ft

    def _freeze(dt=None):
        if dt is None:
            dt = datetime(2024, 1, 1, 0, 0, 0)
        return ft(dt)

    return _freeze


# ═══════════════════════════════════════════════════════════════════════════════
# Benchmark Fixtures
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.fixture
def benchmark_data_dir(test_data_dir):
    """Get path to benchmark data directory."""
    return test_data_dir / "benchmarks"


@pytest.fixture
def performance_thresholds():
    """Performance thresholds for benchmarks."""
    return {
        "video_encoding": {
            "1080p_60fps_h264": {"max_seconds_per_minute": 30},
            "1080p_60fps_h265": {"max_seconds_per_minute": 60},
            "1080p_60fps_av1": {"max_seconds_per_minute": 120}
        },
        "audio_processing": {
            "stereo_48khz": {"max_realtime_factor": 0.5}
        }
    }


# ═══════════════════════════════════════════════════════════════════════════════
# Markers Configuration
# ═══════════════════════════════════════════════════════════════════════════════

def pytest_configure(config):
    """Configure custom pytest markers."""
    config.addinivalue_line(
        "markers", "unit: mark test as a unit test"
    )
    config.addinivalue_line(
        "markers", "integration: mark test as an integration test"
    )
    config.addinivalue_line(
        "markers", "performance: mark test as a performance benchmark"
    )
    config.addinivalue_line(
        "markers", "slow: mark test as slow-running"
    )
    config.addinivalue_line(
        "markers", "ffmpeg: mark test as requiring FFmpeg"
    )
    config.addinivalue_line(
        "markers", "youtube: mark test as requiring YouTube API"
    )
    config.addinivalue_line(
        "markers", "gpu: mark test as requiring GPU"
    )

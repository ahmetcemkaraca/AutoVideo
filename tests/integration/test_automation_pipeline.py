#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Integration tests for VideoAutomation pipeline.

Tests cover:
- End-to-end automation workflow
- YouTube upload integration
- State management
- Configuration handling
"""

import pytest
import json
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch, call
from VideoAutomation.automation.pipeline import AutomationPipeline, parse_duration_to_seconds
from VideoAutomation.automation.config import PipelineConfig, YouTubeConfig
from VideoAutomation.automation.state import StateManager


@pytest.mark.integration
class TestAutomationPipeline:
    """Integration tests for automation pipeline."""

    @pytest.fixture
    def pipeline_config(self, work_dir, mock_youtube_credentials):
        """Create a pipeline configuration for testing."""
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

    @pytest.fixture
    def sample_music_files(self, work_dir):
        """Create sample music files."""
        music_dir = work_dir / "music"
        music_dir.mkdir(parents=True, exist_ok=True)

        files = [
            music_dir / "track1.mp3",
            music_dir / "track2.mp3",
            music_dir / "track3.mp3"
        ]
        for f in files:
            f.touch()

        return files

    def test_pipeline_initialization(self, pipeline_config):
        """Test pipeline initialization."""
        pipeline = AutomationPipeline(pipeline_config)

        assert pipeline.config == pipeline_config
        assert pipeline.state is not None
        assert pipeline.youtube is not None

    def test_get_track_files(self, pipeline_config, sample_music_files):
        """Test getting track files from music directory."""
        pipeline = AutomationPipeline(pipeline_config)

        tracks = pipeline._get_track_files()

        assert len(tracks) == 3
        assert all(t.exists() for t in tracks)

    def test_get_track_files_no_music(self, pipeline_config):
        """Test getting track files when none exist."""
        pipeline = AutomationPipeline(pipeline_config)

        tracks = pipeline._get_track_files()

        assert len(tracks) == 0

    def test_select_style(self, pipeline_config):
        """Test style selection."""
        pipeline = AutomationPipeline(pipeline_config)

        pipeline.config.styles = ["relaxing", "energetic", "focus"]
        pipeline.config.genres = ["ambient", "lofi", "classical"]

        style, genre = pipeline._select_style()

        assert style in pipeline.config.styles
        assert genre in pipeline.config.genres

    def test_select_style_defaults(self, pipeline_config):
        """Test style selection with defaults."""
        pipeline = AutomationPipeline(pipeline_config)

        pipeline.config.styles = []
        pipeline.config.genres = []

        style, genre = pipeline._select_style()

        assert style == "relaxing"
        assert genre == "ambient"

    def test_render_video(self, pipeline_config, sample_music_files):
        """Test video rendering process."""
        pipeline = AutomationPipeline(pipeline_config)

        # Create intro/loop files
        pipeline.config.intro_video.touch()
        pipeline.config.loop_video.touch()

        with patch('video_renderer.video.probe_video') as mock_probe, \
             patch('video_renderer.video.get_duration') as mock_duration, \
             patch('subprocess.run') as mock_subprocess:

            from video_renderer.ffmpeg import VideoInfo
            mock_probe.return_value = VideoInfo(
                codec="hevc", width=1920, height=1080, fps="60/1",
                duration=30.0, pix_fmt="yuv420p", color_space="bt709"
            )
            mock_duration.return_value = 30.0
            mock_subprocess.return_value = Mock(returncode=0)

            video_path = pipeline._render_video("relaxing", "ambient")

            assert video_path is not None
            assert video_path.exists()

    def test_render_video_no_music(self, pipeline_config):
        """Test rendering fails when no music available."""
        pipeline = AutomationPipeline(pipeline_config)

        video_path = pipeline._render_video("relaxing", "ambient")

        assert video_path is None

    def test_upload_video(self, pipeline_config, sample_music_files):
        """Test YouTube upload process."""
        pipeline = AutomationPipeline(pipeline_config)

        # Create a mock video
        video_path = pipeline.config.output_dir / "test_video.mp4"
        video_path.parent.mkdir(parents=True, exist_ok=True)
        video_path.touch()

        # Mock YouTube service
        pipeline.youtube.youtube = MagicMock()
        pipeline.youtube.videos.return_value.insert.return_value.execute.return_value = {
            'id': 'test_video_id_123'
        }

        with patch('VideoAutomation.automation.pipeline.upload_with_exponential_backoff') as mock_upload:
            mock_upload.return_value = 'test_video_id_123'

            video_id = pipeline._upload_video(video_path, "relaxing", "ambient")

            assert video_id == 'test_video_id_123'

    def test_run_once_success(self, pipeline_config, sample_music_files):
        """Test successful single pipeline run."""
        pipeline = AutomationPipeline(pipeline_config)

        pipeline.config.intro_video.touch()
        pipeline.config.loop_video.touch()

        with patch.object(pipeline, '_render_video') as mock_render, \
             patch.object(pipeline, '_upload_video') as mock_upload:

            mock_render.return_value = pipeline.config.output_dir / "test.mp4"
            mock_render.return_value.touch()
            mock_upload.return_value = 'test_video_id'

            result = pipeline.run_once()

            assert result is True
            mock_render.assert_called_once()
            mock_upload.assert_called_once()

    def test_run_once_no_music(self, pipeline_config):
        """Test pipeline run fails with no music."""
        pipeline = AutomationPipeline(pipeline_config)

        result = pipeline.run_once()

        assert result is False

    def test_run_once_render_failure(self, pipeline_config, sample_music_files):
        """Test pipeline run handles render failure."""
        pipeline = AutomationPipeline(pipeline_config)

        with patch.object(pipeline, '_render_video') as mock_render:
            mock_render.return_value = None

            result = pipeline.run_once()

            assert result is False

    def test_parse_duration_to_seconds(self):
        """Test duration parsing for pipeline."""
        assert parse_duration_to_seconds("1:00:00") == 3600
        assert parse_duration_to_seconds("0:30:00") == 1800
        assert parse_duration_to_seconds("30:00") == 1800
        assert parse_duration_to_seconds("60") == 3600


@pytest.mark.integration
class TestStateManager:
    """Integration tests for state management."""

    def test_state_manager_init(self, temp_dir):
        """Test state manager initialization."""
        state_file = temp_dir / "state.json"
        manager = StateManager(state_file)

        assert manager.state_file == state_file
        assert manager.state["videos"] == []
        assert manager.state["stats"]["total_videos"] == 0

    def test_add_video(self, temp_dir):
        """Test adding a video to state."""
        state_file = temp_dir / "state.json"
        manager = StateManager(state_file)

        manager.add_video(
            video_id="test123",
            title="Test Video",
            genre="ambient",
            style="relaxing",
            duration="1:00:00",
            local_path="/path/to/video.mp4"
        )

        assert len(manager.state["videos"]) == 1
        assert manager.state["videos"][0]["video_id"] == "test123"
        assert manager.state["stats"]["total_videos"] == 1

    def test_add_multiple_videos(self, temp_dir):
        """Test adding multiple videos."""
        state_file = temp_dir / "state.json"
        manager = StateManager(state_file)

        for i in range(5):
            manager.add_video(
                video_id=f"video{i}",
                title=f"Video {i}",
                genre="ambient",
                style="relaxing",
                duration="1:00:00",
                local_path=f"/path/to/video{i}.mp4"
            )

        assert len(manager.state["videos"]) == 5
        assert manager.state["stats"]["total_videos"] == 5

    def test_state_persistence(self, temp_dir):
        """Test state persists across instances."""
        state_file = temp_dir / "state.json"

        # Create and populate
        manager1 = StateManager(state_file)
        manager1.add_video(
            video_id="test123",
            title="Test",
            genre="ambient",
            style="relaxing",
            duration="1:00:00",
            local_path="/path/to/video.mp4"
        )

        # Load in new instance
        manager2 = StateManager(state_file)

        assert len(manager2.state["videos"]) == 1
        assert manager2.state["videos"][0]["video_id"] == "test123"

    def test_update_stats(self, temp_dir):
        """Test stats update."""
        state_file = temp_dir / "state.json"
        manager = StateManager(state_file)

        manager.add_video(
            video_id="test1",
            title="Test 1",
            genre="ambient",
            style="relaxing",
            duration="2:00:00",
            local_path="/path/to/video1.mp4"
        )

        manager.add_video(
            video_id="test2",
            title="Test 2",
            genre="lofi",
            style="energetic",
            duration="1:30:00",
            local_path="/path/to/video2.mp4"
        )

        assert manager.state["stats"]["total_videos"] == 2
        # Stats should track total duration
        assert manager.state["stats"]["total_duration_hours"] > 0

    def test_update_last_run(self, temp_dir):
        """Test last run timestamp update."""
        import time
        from datetime import datetime

        state_file = temp_dir / "state.json"
        manager = StateManager(state_file)

        before = datetime.now().timestamp()
        manager._update_last_run()
        after = datetime.now().timestamp()

        last_run = datetime.fromisoformat(manager.state["last_run"])
        last_run_ts = last_run.timestamp()

        assert before <= last_run_ts <= after


@pytest.mark.integration
class TestYouTubeUploader:
    """Integration tests for YouTube uploader."""

    @pytest.fixture
    def mock_credentials(self, temp_dir):
        """Create mock YouTube credentials."""
        client_secrets = temp_dir / "client_secrets.json"
        credentials = temp_dir / "credentials.json"

        client_secrets.write_text(json.dumps({
            "installed": {
                "client_id": "test_id",
                "client_secret": "test_secret"
            }
        }))

        credentials.write_text(json.dumps({
            "token": "test_token",
            "refresh_token": "test_refresh"
        }))

        return client_secrets, credentials

    def test_uploader_init(self, mock_credentials):
        """Test YouTube uploader initialization."""
        from VideoAutomation.automation.youtube import YouTubeUploader

        uploader = YouTubeUploader(mock_credentials[0], mock_credentials[1])

        assert uploader.client_secrets_file == mock_credentials[0]
        assert uploader.credentials_file == mock_credentials[1]

    def test_upload_with_mock_service(self, temp_dir, mock_credentials):
        """Test upload with mocked YouTube service."""
        from VideoAutomation.automation.youtube import YouTubeUploader

        uploader = YouTubeUploader(mock_credentials[0], mock_credentials[1])

        # Mock the YouTube service
        mock_service = MagicMock()
        mock_service.videos.return_value.insert.return_value.execute.return_value = {
            'id': 'uploaded_video_id'
        }
        uploader.youtube = mock_service

        video = temp_dir / "video.mp4"
        video.touch()

        result = uploader.upload(
            video_path=video,
            title="Test Video",
            description="Test Description",
            tags=["test", "video"]
        )

        assert result == 'uploaded_video_id'

    def test_exponential_backoff(self, temp_dir, mock_credentials):
        """Test exponential backoff on errors."""
        from VideoAutomation.automation.youtube import YouTubeUploader, upload_with_exponential_backoff

        uploader = YouTubeUploader(mock_credentials[0], mock_credentials[1])

        # Mock service that fails twice then succeeds
        mock_service = MagicMock()
        call_count = [0]

        def side_effect(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] < 3:
                raise Exception("Upload failed")
            return {'id': 'video_id'}

        mock_service.videos.return_value.insert.return_value.execute.side_effect = side_effect
        uploader.youtube = mock_service

        video = temp_dir / "video.mp4"
        video.touch()

        result = upload_with_exponential_backoff(
            uploader,
            video,
            "Test",
            "Description",
            ["tag"]
        )

        assert result == 'video_id'
        assert call_count[0] == 3


@pytest.mark.integration
class TestPipelineConfiguration:
    """Integration tests for pipeline configuration."""

    def test_load_config_from_file(self, temp_dir):
        """Test loading configuration from file."""
        from VideoAutomation.automation.config import load_config_from_file

        config_file = temp_dir / "config.json"

        config_data = {
            "work_dir": str(temp_dir),
            "music_dir": str(temp_dir / "music"),
            "output_dir": str(temp_dir / "output"),
            "target_duration": "1:00:00",
            "codec": "h264",
            "styles": ["relaxing", "energetic"],
            "genres": ["ambient", "lofi"],
            "delay_between_videos": 60,
            "youtube": {
                "client_secrets_file": str(temp_dir / "client_secrets.json"),
                "credentials_file": str(temp_dir / "credentials.json"),
                "title_template": "{duration} {style} Music",
                "description_template": "Relaxing {style} music",
                "default_tags": ["music", "relaxing"]
            }
        }

        config_file.write_text(json.dumps(config_data, indent=2))

        config = load_config_from_file(config_file)

        assert config.target_duration == "1:00:00"
        assert config.codec == "h264"
        assert len(config.styles) == 2
        assert config.youtube.title_template == "{duration} {style} Music"

    def test_default_config(self, temp_dir):
        """Test default configuration values."""
        config = PipelineConfig(work_dir=temp_dir)

        assert config.target_duration == "9:00:00"
        assert config.codec == "av1"
        assert config.delay_between_videos == 300
        assert config.styles == []
        assert config.genres == []

    def test_config_validation(self, temp_dir):
        """Test configuration validation."""
        config = PipelineConfig(work_dir=temp_dir)

        # Should create directories
        assert config.music_dir.exists()
        assert config.output_dir.exists()

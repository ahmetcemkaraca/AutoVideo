#!/usr/bin/env python3
"""
Unit tests for Drive Sync module.

Tests cover:
- DriveSyncService initialization
- File categorization
- State management
- Sync operations (mocked)
"""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from video_renderer.drive_sync import DriveSyncResult, DriveSyncService, sync_drive_assets


@pytest.mark.unit
class TestDriveSyncResult:
    """Test suite for DriveSyncResult dataclass."""

    def test_result_creation(self):
        """Test creating a DriveSyncResult."""
        result = DriveSyncResult()

        assert result.downloaded == []
        assert result.skipped == []
        assert result.errors == []
        assert result.success is True

    def test_result_with_downloads(self):
        """Test result with downloaded files."""
        result = DriveSyncResult(
            downloaded=[Path("music/track1.mp3"), Path("music/track2.mp3")],
            skipped=["existing.mp3"],
            errors=[],
        )

        assert len(result.downloaded) == 2
        assert len(result.skipped) == 1
        assert result.success is True

    def test_result_with_errors(self):
        """Test result with errors."""
        result = DriveSyncResult(errors=["Failed to download file.mp3"])

        assert result.success is False


@pytest.mark.unit
class TestDriveSyncService:
    """Test suite for DriveSyncService class."""

    def test_service_init(self, temp_dir):
        """Test DriveSyncService initialization."""
        state_file = temp_dir / "sync_state.json"

        service = DriveSyncService(
            root_folder_id="test_folder_id", base_dir=temp_dir, state_file=state_file
        )

        assert service.root_folder_id == "test_folder_id"
        assert service.base_dir == temp_dir

    def test_sync_dir_creation(self, temp_dir):
        """Test sync directory creation."""
        service = DriveSyncService(root_folder_id="test_folder_id", base_dir=temp_dir)

        sync_dir = service._sync_dir("music")

        assert sync_dir.exists()
        assert sync_dir.name == "music"

    def test_state_management(self, temp_dir):
        """Test state save and load."""
        state_file = temp_dir / "sync_state.json"

        service = DriveSyncService(
            root_folder_id="test_folder_id", base_dir=temp_dir, state_file=state_file
        )

        folder_state = {
            "file_id_123": {
                "name": "test.mp3",
                "md5Checksum": "abc123",
                "path": str(temp_dir / "music" / "test.mp3"),
            }
        }

        service._save_folder_state("music", folder_state)

        loaded_state = service._state_for("music")

        assert loaded_state == folder_state

    @patch("video_renderer.drive_sync.DriveUploader")
    def test_sync_music_files(self, mock_uploader_class, temp_dir):
        """Test syncing music files from Drive."""
        mock_uploader = MagicMock()
        mock_uploader_class.return_value = mock_uploader

        mock_uploader.list_folders.return_value = [{"id": "music_folder_id", "name": "music"}]

        mock_uploader.list_files.return_value = [
            {
                "id": "file_1",
                "name": "track1.mp3",
                "md5Checksum": "abc123",
                "mimeType": "audio/mpeg",
            },
            {
                "id": "file_2",
                "name": "track2.wav",
                "md5Checksum": "def456",
                "mimeType": "audio/wav",
            },
        ]

        mock_uploader.download_file.return_value = (True, "Downloaded")

        service = DriveSyncService(root_folder_id="root_folder_id", base_dir=temp_dir)

        result = service.sync()

        assert len(result.downloaded) == 2
        assert len(result.errors) == 0

    @patch("video_renderer.drive_sync.DriveUploader")
    def test_sync_skip_existing(self, mock_uploader_class, temp_dir):
        """Test that existing files are skipped."""
        mock_uploader = MagicMock()
        mock_uploader_class.return_value = mock_uploader

        mock_uploader.list_folders.return_value = [{"id": "music_folder_id", "name": "music"}]

        mock_uploader.list_files.return_value = [
            {
                "id": "file_1",
                "name": "track1.mp3",
                "md5Checksum": "abc123",
                "mimeType": "audio/mpeg",
            }
        ]

        service = DriveSyncService(root_folder_id="root_folder_id", base_dir=temp_dir)

        service._save_folder_state(
            "music",
            {
                "file_1": {
                    "name": "track1.mp3",
                    "md5Checksum": "abc123",
                    "path": str(temp_dir / "music" / "track1.mp3"),
                }
            },
        )

        result = service.sync()

        assert len(result.skipped) >= 1
        mock_uploader.download_file.assert_not_called()

    @patch("video_renderer.drive_sync.DriveUploader")
    def test_sync_handles_errors(self, mock_uploader_class, temp_dir):
        """Test that download errors are handled."""
        mock_uploader = MagicMock()
        mock_uploader_class.return_value = mock_uploader

        mock_uploader.list_folders.return_value = [{"id": "music_folder_id", "name": "music"}]

        mock_uploader.list_files.return_value = [
            {
                "id": "file_1",
                "name": "track1.mp3",
                "md5Checksum": "abc123",
                "mimeType": "audio/mpeg",
            }
        ]

        mock_uploader.download_file.return_value = (False, "Network error")

        service = DriveSyncService(root_folder_id="root_folder_id", base_dir=temp_dir)

        result = service.sync()

        assert len(result.errors) == 1
        assert "track1.mp3" in result.errors[0]

    @patch("video_renderer.drive_sync.DriveUploader")
    def test_sync_missing_folder(self, mock_uploader_class, temp_dir):
        """Test handling of missing Drive folder."""
        mock_uploader = MagicMock()
        mock_uploader_class.return_value = mock_uploader

        mock_uploader.list_folders.return_value = []

        service = DriveSyncService(root_folder_id="root_folder_id", base_dir=temp_dir)

        result = service.sync()

        assert len(result.errors) >= 1
        assert any("not found" in e for e in result.errors)


@pytest.mark.unit
class TestSyncDriveAssets:
    """Test suite for sync_drive_assets convenience function."""

    @patch("video_renderer.drive_sync.DriveSyncService")
    def test_sync_drive_assets(self, mock_service_class, temp_dir):
        """Test sync_drive_assets function."""
        mock_service = MagicMock()
        mock_service_class.return_value = mock_service

        mock_result = DriveSyncResult(
            downloaded=[Path("music/track1.mp3")], skipped=["existing.mp3"], errors=[]
        )
        mock_service.sync.return_value = mock_result

        result = sync_drive_assets(root_folder_id="test_folder_id", base_dir=temp_dir)

        assert result == mock_result
        mock_service_class.assert_called_once_with(
            root_folder_id="test_folder_id", base_dir=temp_dir
        )


@pytest.fixture
def temp_dir(tmp_path):
    """Create a temporary directory for tests."""
    return tmp_path

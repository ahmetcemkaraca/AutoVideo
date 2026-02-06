#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
State management for tracking uploads.

Uses unified StateManager from video_renderer for persistence.
"""

import sys
from pathlib import Path
from typing import Dict, Optional
from datetime import datetime

# Import unified StateManager from parent package
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from video_renderer.state_manager import StateManager, StateSnapshot


# ═══════════════════════════════════════════════════════════════════════════════
# Data Types
# ═══════════════════════════════════════════════════════════════════════════════

class VideoRecord:
    """
    Record of a generated video.

    Attributes:
        video_id: YouTube video ID
        title: Video title
        created_at: ISO timestamp of creation
        uploaded_at: ISO timestamp of YouTube upload
        genre: Music genre
        style: Video style
        duration: Video duration string
        local_path: Path to local video file
    """

    def __init__(
        self,
        video_id: str,
        title: str,
        created_at: str,
        uploaded_at: Optional[str] = None,
        genre: str = "",
        style: str = "",
        duration: str = "",
        local_path: Optional[str] = None
    ):
        self.video_id = video_id
        self.title = title
        self.created_at = created_at
        self.uploaded_at = uploaded_at
        self.genre = genre
        self.style = style
        self.duration = duration
        self.local_path = local_path

    def to_dict(self) -> Dict:
        """Convert to dictionary."""
        return {
            "video_id": self.video_id,
            "title": self.title,
            "created_at": self.created_at,
            "uploaded_at": self.uploaded_at,
            "genre": self.genre,
            "style": self.style,
            "duration": self.duration,
            "local_path": self.local_path,
        }

    @classmethod
    def from_dict(cls, data: Dict) -> "VideoRecord":
        """Create from dictionary."""
        return cls(**data)

    def __repr__(self) -> str:
        return f"VideoRecord(id={self.video_id}, title={self.title})"


# ═══════════════════════════════════════════════════════════════════════════════
# Pipeline State Manager
# ═══════════════════════════════════════════════════════════════════════════════

class PipelineState:
    """
    Complete pipeline state using unified StateManager.

    Manages video records, statistics, and metadata for the automation pipeline.
    Uses the unified StateManager for thread-safe, atomic persistence.

    State Format Version: 1.0
    """

    STATE_VERSION = "1.0"

    def __init__(self, state_file: Path, enable_locking: bool = True):
        """
        Initialize pipeline state.

        Args:
            state_file: Path to state file
            enable_locking: Enable cross-process file locking
        """
        self.state_file = state_file
        self._state = StateManager(
            state_file=state_file,
            version=self.STATE_VERSION,
            auto_save=False,  # We'll save explicitly
            enable_locking=enable_locking
        )

        # Load existing state
        self._load_videos()

    def _load_videos(self) -> None:
        """Load video records from state."""
        videos_data = self.state.get("videos", {})
        self._videos: Dict[str, VideoRecord] = {}

        for video_id, video_data in videos_data.items():
            self._videos[video_id] = VideoRecord.from_dict(video_data)

    def _save_videos(self) -> None:
        """Save video records to state."""
        videos_data = {
            vid: record.to_dict()
            for vid, record in self._videos.items()
        }
        self.state.set("videos", videos_data, save=False)

    def add_video(
        self,
        video_id: str,
        title: str,
        genre: str = "",
        style: str = "",
        duration: str = "",
        local_path: Optional[str] = None,
    ) -> None:
        """
        Record a created video.

        Args:
            video_id: YouTube video ID
            title: Video title
            genre: Music genre
            style: Video style
            duration: Duration string
            local_path: Path to local video file
        """
        now = datetime.now().isoformat()

        self._videos[video_id] = VideoRecord(
            video_id=video_id,
            title=title,
            created_at=now,
            genre=genre,
            style=style,
            duration=duration,
            local_path=local_path,
        )

        # Update counters
        total = self.state.get_int("total_videos_created", 0)
        self.state.set("total_videos_created", total + 1, save=False)
        self.state.set("last_run", now, save=False)

        # Save videos and state
        self._save_videos()
        self.state._save()

    def mark_video_uploaded(self, video_id: str) -> None:
        """
        Mark a video as uploaded to YouTube.

        Args:
            video_id: YouTube video ID
        """
        if video_id in self._videos:
            self._videos[video_id].uploaded_at = datetime.now().isoformat()
            self._save_videos()
            self.state._save()

    def get_video(self, video_id: str) -> Optional[VideoRecord]:
        """
        Get a video record by ID.

        Args:
            video_id: YouTube video ID

        Returns:
            VideoRecord or None if not found
        """
        return self._videos.get(video_id)

    def get_all_videos(self) -> Dict[str, VideoRecord]:
        """
        Get all video records.

        Returns:
            Dictionary of video_id -> VideoRecord
        """
        return self._videos.copy()

    def delete_video(self, video_id: str) -> bool:
        """
        Delete a video record.

        Args:
            video_id: YouTube video ID

        Returns:
            True if video was deleted
        """
        if video_id in self._videos:
            del self._videos[video_id]
            self._save_videos()
            self.state._save()
            return True
        return False

    @property
    def state(self) -> StateManager:
        """Get the underlying StateManager."""
        return self._state

    @property
    def stats(self) -> Dict[str, int]:
        """
        Get pipeline statistics.

        Returns:
            Dictionary with statistics
        """
        return {
            "total_videos": self.state.get_int("total_videos_created", 0),
            "uploaded_videos": sum(
                1 for v in self._videos.values() if v.uploaded_at
            ),
        }

    @property
    def last_run(self) -> Optional[str]:
        """
        Get last run timestamp.

        Returns:
            ISO timestamp or None
        """
        return self.state.get_str("last_run")

    @property
    def video_count(self) -> int:
        """Get total number of videos."""
        return len(self._videos)

    def create_snapshot(self) -> StateSnapshot:
        """
        Create state snapshot for backup.

        Returns:
            StateSnapshot with current state
        """
        return self.state.create_snapshot()

    def restore_snapshot(self, snapshot: StateSnapshot) -> None:
        """
        Restore state from snapshot.

        Args:
            snapshot: Snapshot to restore
        """
        self.state.restore_snapshot(snapshot)
        self._load_videos()

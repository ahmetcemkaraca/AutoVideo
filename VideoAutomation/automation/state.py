#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
State management for tracking uploads.
"""

import json
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import List, Dict, Optional
from datetime import datetime


# ═══════════════════════════════════════════════════════════════════════════════
# Data Types
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class VideoRecord:
    """Record of a generated video."""
    video_id: str  # YouTube video ID
    title: str
    created_at: str  # ISO timestamp
    uploaded_at: Optional[str] = None
    genre: str = ""
    style: str = ""
    duration: str = ""
    local_path: Optional[str] = None


@dataclass
class PipelineState:
    """Complete pipeline state."""
    videos: Dict[str, VideoRecord] = field(default_factory=dict)
    last_run: Optional[str] = None
    total_videos_created: int = 0


# ═══════════════════════════════════════════════════════════════════════════════
# State Manager
# ═══════════════════════════════════════════════════════════════════════════════

class StateManager:
    """
    Manages persistent state for the automation pipeline.
    """

    def __init__(self, state_file: Path):
        self.state_file = state_file
        self._state: PipelineState = PipelineState()
        self._load()

    def _load(self):
        """Load state from file."""
        if not self.state_file.exists():
            return

        try:
            with open(self.state_file, "r", encoding="utf-8") as f:
                data = json.load(f)

            # Parse videos
            videos = {}
            for video_id, video_data in data.get("videos", {}).items():
                videos[video_id] = VideoRecord(**video_data)

            self._state = PipelineState(
                videos=videos,
                last_run=data.get("last_run"),
                total_videos_created=data.get("total_videos_created", 0),
            )

        except Exception as e:
            print(f"Warning: Could not load state file: {e}")

    def save(self):
        """Save state to file."""
        self.state_file.parent.mkdir(parents=True, exist_ok=True)

        data = {
            "videos": {
                vid: asdict(video) for vid, video in self._state.videos.items()
            },
            "last_run": self._state.last_run,
            "total_videos_created": self._state.total_videos_created,
        }

        with open(self.state_file, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    def add_video(
        self,
        video_id: str,
        title: str,
        genre: str = "",
        style: str = "",
        duration: str = "",
        local_path: Optional[str] = None,
    ):
        """Record a created video."""
        now = datetime.now().isoformat()

        self._state.videos[video_id] = VideoRecord(
            video_id=video_id,
            title=title,
            created_at=now,
            genre=genre,
            style=style,
            duration=duration,
            local_path=local_path,
        )
        self._state.total_videos_created += 1
        self._state.last_run = now
        self.save()

    def mark_video_uploaded(self, video_id: str):
        """Mark a video as uploaded to YouTube."""
        if video_id in self._state.videos:
            self._state.videos[video_id].uploaded_at = datetime.now().isoformat()
            self.save()

    @property
    def stats(self) -> Dict[str, int]:
        """Get pipeline statistics."""
        return {
            "total_videos": self._state.total_videos_created,
        }

    @property
    def last_run(self) -> Optional[str]:
        """Get last run timestamp."""
        return self._state.last_run

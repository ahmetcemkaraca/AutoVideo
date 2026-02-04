#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
State management for tracking used tracks and uploads.
"""

import json
import time
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import List, Dict, Optional, Set
from datetime import datetime


# ═══════════════════════════════════════════════════════════════════════════════
# Data Types
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class UsedTrack:
    """Record of a used Jamendo track."""
    track_id: str
    name: str
    artist: str
    used_at: str  # ISO timestamp
    video_id: Optional[str] = None  # YouTube video ID if uploaded


@dataclass
class VideoRecord:
    """Record of a generated video."""
    video_id: str  # YouTube video ID
    title: str
    created_at: str  # ISO timestamp
    uploaded_at: Optional[str] = None
    track_ids: List[str] = field(default_factory=list)
    genre: str = ""
    mood: str = ""
    duration: str = ""
    local_path: Optional[str] = None


@dataclass
class PipelineState:
    """Complete pipeline state."""
    used_tracks: Dict[str, UsedTrack] = field(default_factory=dict)
    videos: Dict[str, VideoRecord] = field(default_factory=dict)
    last_run: Optional[str] = None
    total_videos_created: int = 0
    total_tracks_used: int = 0


# ═══════════════════════════════════════════════════════════════════════════════
# State Manager
# ═══════════════════════════════════════════════════════════════════════════════

class StateManager:
    """
    Manages persistent state for the automation pipeline.
    Tracks used music to avoid duplicates.
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
            
            # Parse used tracks
            used_tracks = {}
            for track_id, track_data in data.get("used_tracks", {}).items():
                used_tracks[track_id] = UsedTrack(**track_data)
            
            # Parse videos
            videos = {}
            for video_id, video_data in data.get("videos", {}).items():
                videos[video_id] = VideoRecord(**video_data)
            
            self._state = PipelineState(
                used_tracks=used_tracks,
                videos=videos,
                last_run=data.get("last_run"),
                total_videos_created=data.get("total_videos_created", 0),
                total_tracks_used=data.get("total_tracks_used", 0),
            )
            
        except Exception as e:
            print(f"Warning: Could not load state file: {e}")
    
    def save(self):
        """Save state to file."""
        self.state_file.parent.mkdir(parents=True, exist_ok=True)
        
        data = {
            "used_tracks": {
                tid: asdict(track) for tid, track in self._state.used_tracks.items()
            },
            "videos": {
                vid: asdict(video) for vid, video in self._state.videos.items()
            },
            "last_run": self._state.last_run,
            "total_videos_created": self._state.total_videos_created,
            "total_tracks_used": self._state.total_tracks_used,
        }
        
        with open(self.state_file, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    
    def is_track_used(self, track_id: str) -> bool:
        """Check if a track has been used before."""
        return track_id in self._state.used_tracks
    
    def get_used_track_ids(self) -> Set[str]:
        """Get set of all used track IDs."""
        return set(self._state.used_tracks.keys())
    
    def mark_track_used(
        self,
        track_id: str,
        name: str,
        artist: str,
        video_id: Optional[str] = None
    ):
        """Mark a track as used."""
        self._state.used_tracks[track_id] = UsedTrack(
            track_id=track_id,
            name=name,
            artist=artist,
            used_at=datetime.now().isoformat(),
            video_id=video_id,
        )
        self._state.total_tracks_used += 1
        self.save()
    
    def add_video(
        self,
        video_id: str,
        title: str,
        track_ids: List[str],
        genre: str = "",
        mood: str = "",
        duration: str = "",
        local_path: Optional[str] = None,
    ):
        """Record a created video."""
        now = datetime.now().isoformat()
        
        self._state.videos[video_id] = VideoRecord(
            video_id=video_id,
            title=title,
            created_at=now,
            track_ids=track_ids,
            genre=genre,
            mood=mood,
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
            "total_tracks": self._state.total_tracks_used,
            "unique_tracks": len(self._state.used_tracks),
        }
    
    @property
    def last_run(self) -> Optional[str]:
        """Get last run timestamp."""
        return self._state.last_run


# ═══════════════════════════════════════════════════════════════════════════════
# Filter Unused Tracks
# ═══════════════════════════════════════════════════════════════════════════════

def filter_unused_tracks(tracks: list, state: StateManager) -> list:
    """
    Filter out tracks that have already been used.
    
    Args:
        tracks: List of JamendoTrack objects
        state: StateManager instance
        
    Returns:
        Filtered list with only unused tracks
    """
    used_ids = state.get_used_track_ids()
    return [t for t in tracks if t.id not in used_ids]

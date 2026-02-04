#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Configuration for YouTube livestream system.

Structure:
  content/
  ├── set1/
  │   ├── intro.mp4
  │   ├── loop.mp4
  │   ├── music/
  │   ├── bg/
  │   └── playlists/  (10 JSON files)
  ├── set2/
  │   └── ...
"""

import json
import os
import random
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional


# ═══════════════════════════════════════════════════════════════════════════════
# Track Configuration
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class TrackConfig:
    """Configuration for a music track."""
    file: str
    order: int
    
    @classmethod
    def from_dict(cls, data: dict) -> "TrackConfig":
        return cls(file=data.get("file", ""), order=data.get("order", 0))


@dataclass
class BackgroundConfig:
    """Configuration for background audio."""
    file: str
    gain_db: float = -8.0
    
    @classmethod
    def from_dict(cls, data: dict) -> "BackgroundConfig":
        return cls(file=data.get("file", ""), gain_db=data.get("gain_db", -8.0))


# ═══════════════════════════════════════════════════════════════════════════════
# Playlist Configuration
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class PlaylistConfig:
    """Configuration for a playlist (defines track order)."""
    name: str
    tracks: List[TrackConfig]
    backgrounds: List[BackgroundConfig]
    
    @classmethod
    def from_file(cls, path: Path) -> "PlaylistConfig":
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        
        tracks = [TrackConfig.from_dict(t) for t in data.get("tracks", [])]
        tracks.sort(key=lambda x: x.order)
        backgrounds = [BackgroundConfig.from_dict(b) for b in data.get("backgrounds", [])]
        
        return cls(
            name=data.get("name", path.stem),
            tracks=tracks,
            backgrounds=backgrounds
        )
    
    def get_track_files(self, music_dir: Path) -> List[Path]:
        return [music_dir / t.file for t in self.tracks if (music_dir / t.file).exists()]
    
    def get_background_files(self, bg_dir: Path) -> List[tuple]:
        result = []
        for bg in self.backgrounds:
            path = bg_dir / bg.file
            if path.exists():
                result.append((path, bg.gain_db))
        return result


# ═══════════════════════════════════════════════════════════════════════════════
# Video Set Configuration
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class VideoSet:
    """
    A video set = intro + loop + music + bg + playlists.
    Each set plays for 1-3 hours before switching.
    """
    name: str
    path: Path
    intro_video: Path
    loop_video: Path
    music_dir: Path
    bg_dir: Path
    playlists_dir: Path
    
    _playlists: List[PlaylistConfig] = field(default_factory=list, repr=False)
    
    @classmethod
    def from_path(cls, set_path: Path) -> "VideoSet":
        if not set_path.is_dir():
            raise ValueError(f"Not a directory: {set_path}")
        
        # Find intro
        intro = None
        for ext in [".mp4", ".mkv", ".webm", ".mov"]:
            candidate = set_path / f"intro{ext}"
            if candidate.exists():
                intro = candidate
                break
        if not intro:
            raise ValueError(f"No intro video in {set_path}")
        
        # Find loop
        loop = None
        for ext in [".mp4", ".mkv", ".webm", ".mov"]:
            candidate = set_path / f"loop{ext}"
            if candidate.exists():
                loop = candidate
                break
        if not loop:
            raise ValueError(f"No loop video in {set_path}")
        
        return cls(
            name=set_path.name,
            path=set_path,
            intro_video=intro,
            loop_video=loop,
            music_dir=set_path / "music",
            bg_dir=set_path / "bg",
            playlists_dir=set_path / "playlists"
        )
    
    def load_playlists(self) -> List[PlaylistConfig]:
        if self._playlists:
            return self._playlists
        
        if not self.playlists_dir.exists():
            return []
        
        playlists = []
        for f in sorted(self.playlists_dir.glob("*.json")):
            try:
                playlists.append(PlaylistConfig.from_file(f))
            except Exception:
                continue
        
        self._playlists = playlists
        return playlists
    
    def get_playlist(self, index: int) -> Optional[PlaylistConfig]:
        playlists = self.load_playlists()
        if not playlists:
            return None
        return playlists[index % len(playlists)]


# ═══════════════════════════════════════════════════════════════════════════════
# Stream Configuration
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class StreamConfig:
    """YouTube streaming settings."""
    rtmp_url: str = "rtmp://a.rtmp.youtube.com/live2"
    stream_key: str = ""
    video_bitrate: str = "4500k"
    audio_bitrate: str = "128k"
    resolution: str = "1920x1080"
    fps: int = 30
    preset: str = "veryfast"
    
    @property
    def full_rtmp_url(self) -> str:
        return f"{self.rtmp_url}/{self.stream_key}"


@dataclass
class GlobalConfig:
    """Global livestream configuration."""
    content_dir: Path  # Contains video sets
    stream: StreamConfig
    min_duration_minutes: int = 60
    max_duration_minutes: int = 180
    state_file: Path = None
    
    def __post_init__(self):
        if self.state_file is None:
            self.state_file = self.content_dir.parent / "state.json"
    
    @classmethod
    def from_file(cls, path: Path) -> "GlobalConfig":
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        
        content_dir = Path(data.get("content_dir", "./content"))
        
        stream_data = data.get("stream", {})
        stream = StreamConfig(
            rtmp_url=stream_data.get("rtmp_url", "rtmp://a.rtmp.youtube.com/live2"),
            stream_key=stream_data.get("stream_key", ""),
            video_bitrate=stream_data.get("video_bitrate", "4500k"),
            audio_bitrate=stream_data.get("audio_bitrate", "128k"),
            resolution=stream_data.get("resolution", "1920x1080"),
            fps=stream_data.get("fps", 30),
            preset=stream_data.get("preset", "veryfast"),
        )
        
        return cls(
            content_dir=content_dir,
            stream=stream,
            min_duration_minutes=data.get("min_duration_minutes", 60),
            max_duration_minutes=data.get("max_duration_minutes", 180),
        )
    
    def discover_video_sets(self) -> List[VideoSet]:
        """Find all video sets in content directory."""
        if not self.content_dir.exists():
            return []
        
        sets = []
        for subdir in sorted(self.content_dir.iterdir()):
            if subdir.is_dir():
                try:
                    sets.append(VideoSet.from_path(subdir))
                except ValueError:
                    continue
        return sets


# ═══════════════════════════════════════════════════════════════════════════════
# Default Templates
# ═══════════════════════════════════════════════════════════════════════════════

DEFAULT_CONFIG = """{
  "content_dir": "./content",
  "min_duration_minutes": 60,
  "max_duration_minutes": 180,
  "stream": {
    "rtmp_url": "rtmp://a.rtmp.youtube.com/live2",
    "stream_key": "YOUR_YOUTUBE_STREAM_KEY",
    "video_bitrate": "4500k",
    "audio_bitrate": "128k",
    "resolution": "1920x1080",
    "fps": 30,
    "preset": "veryfast"
  }
}
"""


def generate_playlists(video_set: VideoSet, count: int = 10):
    """Generate playlist JSON files with shuffled track orders."""
    video_set.playlists_dir.mkdir(parents=True, exist_ok=True)
    
    # Get music files
    music_files = []
    if video_set.music_dir.exists():
        for ext in [".mp3", ".wav", ".flac", ".ogg", ".m4a"]:
            music_files.extend(video_set.music_dir.glob(f"*{ext}"))
    
    # Get bg files
    bg_files = []
    if video_set.bg_dir.exists():
        for ext in [".mp3", ".wav", ".flac", ".ogg", ".m4a"]:
            bg_files.extend(video_set.bg_dir.glob(f"*{ext}"))
    
    for i in range(1, count + 1):
        playlist_file = video_set.playlists_dir / f"{i:02d}.json"
        
        # Shuffle tracks
        shuffled = list(music_files)
        random.shuffle(shuffled)
        
        tracks = [{"file": t.name, "order": idx + 1} for idx, t in enumerate(shuffled)]
        backgrounds = [{"file": b.name, "gain_db": -8.0} for b in bg_files]
        
        data = {
            "name": f"Playlist {i}",
            "tracks": tracks,
            "backgrounds": backgrounds
        }
        
        with open(playlist_file, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    
    return count

#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Configuration for video automation pipeline.
"""

import os
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Dict, Optional


# ═══════════════════════════════════════════════════════════════════════════════
# Environment Variables
# ═══════════════════════════════════════════════════════════════════════════════

def get_env(key: str, default: Optional[str] = None) -> str:
    """Get environment variable or default."""
    value = os.environ.get(key, default)
    if value is None:
        raise ValueError(f"Environment variable {key} is required")
    return value


def get_env_optional(key: str, default: str = "") -> str:
    """Get optional environment variable."""
    return os.environ.get(key, default)


# ═══════════════════════════════════════════════════════════════════════════════
# API Configuration
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class YouTubeConfig:
    """YouTube API configuration."""
    client_secrets_file: str = "client_secrets.json"
    credentials_file: str = "youtube_credentials.json"

    # Upload settings
    default_category: str = "10"  # Music category
    default_privacy: str = "public"  # public, private, unlisted

    # Video metadata templates
    title_template: str = "{duration} {style} Music | {genre} | Relaxing Background"
    description_template: str = """🎵 {duration} of {style} {genre} music for relaxation, study, sleep, and meditation.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📺 Subscribe for more relaxing content!
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

#relaxingmusic #{genre} #ambient #sleepmusic #studymusic #meditation
"""

    default_tags: List[str] = field(default_factory=lambda: [
        "relaxing music", "ambient", "sleep music", "study music",
        "meditation music", "peaceful", "calming", "background music"
    ])

    @classmethod
    def from_env(cls) -> "YouTubeConfig":
        return cls(
            client_secrets_file=get_env_optional("YOUTUBE_CLIENT_SECRETS", "client_secrets.json"),
            credentials_file=get_env_optional("YOUTUBE_CREDENTIALS", "youtube_credentials.json"),
        )


# ═══════════════════════════════════════════════════════════════════════════════
# Pipeline Configuration
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class PipelineConfig:
    """Main pipeline configuration."""
    # Directories
    work_dir: Path = field(default_factory=Path.cwd)
    music_dir: Optional[Path] = None
    output_dir: Optional[Path] = None
    state_file: Optional[Path] = None

    # Video settings
    intro_video: Optional[Path] = None
    loop_video: Optional[Path] = None
    target_duration: str = "08:00:00"  # HH:MM:SS
    codec: str = "av1"

    # Pipeline settings
    continuous_mode: bool = False  # Run continuously
    delay_between_videos: int = 300  # Seconds between video generations

    # Style and genre options (replaces Jamendo moods/genres)
    styles: List[str] = field(default_factory=lambda: [
        "relaxing", "calm", "peaceful", "meditative", "sleep"
    ])
    genres: List[str] = field(default_factory=lambda: [
        "ambient", "classical", "electronic", "jazz", "lounge",
        "chillout", "newage"
    ])

    # API config
    youtube: YouTubeConfig = field(default_factory=YouTubeConfig)

    def __post_init__(self):
        if self.music_dir is None:
            self.music_dir = self.work_dir / "music"
        if self.output_dir is None:
            self.output_dir = self.work_dir / "output"
        if self.state_file is None:
            self.state_file = self.work_dir / "state.json"

    @classmethod
    def from_file(cls, path: Path) -> "PipelineConfig":
        """Load config from JSON file."""
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)

        config = cls(
            work_dir=Path(data.get("work_dir", ".")),
            target_duration=data.get("target_duration", "08:00:00"),
            codec=data.get("codec", "av1"),
            continuous_mode=data.get("continuous_mode", False),
            delay_between_videos=data.get("delay_between_videos", 300),
        )

        if "intro_video" in data:
            config.intro_video = Path(data["intro_video"])
        if "loop_video" in data:
            config.loop_video = Path(data["loop_video"])

        # Style and genre config
        if "styles" in data:
            config.styles = data["styles"]
        if "genres" in data:
            config.genres = data["genres"]

        # YouTube config
        if "youtube" in data:
            y = data["youtube"]
            config.youtube.client_secrets_file = y.get("client_secrets_file", "client_secrets.json")
            if "title_template" in y:
                config.youtube.title_template = y["title_template"]
            if "description_template" in y:
                config.youtube.description_template = y["description_template"]
            if "tags" in y:
                config.youtube.default_tags = y["tags"]

        return config

    def save(self, path: Path):
        """Save config to JSON file."""
        data = {
            "work_dir": str(self.work_dir),
            "target_duration": self.target_duration,
            "codec": self.codec,
            "continuous_mode": self.continuous_mode,
            "delay_between_videos": self.delay_between_videos,
            "styles": self.styles,
            "genres": self.genres,
            "youtube": {
                "client_secrets_file": self.youtube.client_secrets_file,
                "title_template": self.youtube.title_template,
                "description_template": self.youtube.description_template,
                "tags": self.youtube.default_tags,
            }
        }

        if self.intro_video:
            data["intro_video"] = str(self.intro_video)
        if self.loop_video:
            data["loop_video"] = str(self.loop_video)

        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)


# ═══════════════════════════════════════════════════════════════════════════════
# Default Config Template
# ═══════════════════════════════════════════════════════════════════════════════

DEFAULT_CONFIG_TEMPLATE = """{
  "work_dir": ".",
  "intro_video": "intro.mp4",
  "loop_video": "loop.mp4",
  "target_duration": "08:00:00",
  "codec": "av1",
  "continuous_mode": false,
  "delay_between_videos": 300,
  "styles": ["relaxing", "calm", "peaceful", "meditative"],
  "genres": ["ambient", "classical", "electronic", "jazz", "chillout"],
  "youtube": {
    "client_secrets_file": "client_secrets.json",
    "title_template": "{duration} {style} Music | {genre} | Relaxing Background",
    "description_template": "🎵 {duration} of {style} {genre} music...",
    "tags": ["relaxing music", "ambient", "sleep music", "study music"]
  }
}
"""

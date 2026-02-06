#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
VideoAutomation pipeline configuration.

Extracted and adapted from VideoAutomation/automation/config_v2.py.
Provides production-ready configuration with validation, environment variable support,
and configuration migrations.
"""

import json
import re
import os
import logging
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import List, Dict, Optional, Any

from .base import BaseConfig
from .constants import VideoCodec, PrivacyStatus, PIPELINE_AUDIO_FORMATS, PIPELINE_VIDEO_FORMATS

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════════════
# Configuration Version
# ═══════════════════════════════════════════════════════════════════════════════

CONFIG_VERSION = 2
CONFIG_FORMAT_VERSION = "2.0"


# ═══════════════════════════════════════════════════════════════════════════════
# YouTube Category IDs
# ═══════════════════════════════════════════════════════════════════════════════

YOUTUBE_CATEGORIES = {
    "music": "10",
    "entertainment": "24",
    "people_blogs": "22",
    "gaming": "20",
    "howto": "26",
    "news": "25",
    "sports": "17"
}


# ═══════════════════════════════════════════════════════════════════════════════
# Configuration Classes
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class YouTubeConfig(BaseConfig):
    """YouTube API configuration."""

    # Authentication
    client_secrets_file: str = "client_secrets.json"
    credentials_file: str = "youtube_credentials.json"

    # Upload settings
    default_category: str = "10"  # Music category
    default_privacy: str = "public"

    # Rate limiting
    max_uploads_per_day: int = 6  # YouTube daily limit
    min_upload_interval: int = 300  # Minimum seconds between uploads (5 min)

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

    # Advanced settings
    chunk_size: int = 1024 * 1024  # 1MB chunks for upload
    connect_timeout: int = 30  # Connection timeout in seconds
    read_timeout: int = 300  # Read timeout in seconds (5 min)

    def validate(self) -> List[str]:
        """
        Validate YouTube configuration.

        Returns:
            List of validation errors (empty if valid)
        """
        errors = []

        # Validate privacy status
        if self.default_privacy not in [e.value for e in PrivacyStatus]:
            errors.append(
                f"Invalid privacy status: {self.default_privacy}. "
                f"Must be one of: {[e.value for e in PrivacyStatus]}"
            )

        # Validate category
        if self.default_category not in YOUTUBE_CATEGORIES.values():
            errors.append(
                f"Invalid category ID: {self.default_category}. "
                f"Valid categories: {YOUTUBE_CATEGORIES}"
            )

        # Validate templates
        if not self.title_template:
            errors.append("Title template cannot be empty")

        # Check template variables
        title_vars = set(re.findall(r'\{(\w+)\}', self.title_template))
        required_vars = {"duration", "style", "genre"}
        missing_vars = required_vars - title_vars
        if missing_vars:
            errors.append(
                f"Title template missing required variables: {missing_vars}"
            )

        # Validate numeric values
        if self.max_uploads_per_day < 1:
            errors.append("max_uploads_per_day must be at least 1")

        if self.min_upload_interval < 0:
            errors.append("min_upload_interval cannot be negative")

        if self.chunk_size < 1024:
            errors.append("chunk_size must be at least 1024 bytes")

        return errors

    @classmethod
    def from_file(cls, path: Path) -> "YouTubeConfig":
        """Load config from JSON file."""
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return cls.from_dict(data)

    def to_file(self, path: Path) -> None:
        """Save config to JSON file."""
        with open(path, "w", encoding="utf-8") as f:
            json.dump(asdict(self), f, indent=2, ensure_ascii=False)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "YouTubeConfig":
        """Create config from dictionary."""
        return cls(
            client_secrets_file=data.get("client_secrets_file", "client_secrets.json"),
            credentials_file=data.get("credentials_file", "youtube_credentials.json"),
            default_category=data.get("default_category", "10"),
            default_privacy=data.get("default_privacy", "public"),
            max_uploads_per_day=data.get("max_uploads_per_day", 6),
            min_upload_interval=data.get("min_upload_interval", 300),
            title_template=data.get("title_template", cls().title_template),
            description_template=data.get("description_template", cls().description_template),
            default_tags=data.get("tags", cls().default_tags),
            chunk_size=data.get("chunk_size", 1024 * 1024),
            connect_timeout=data.get("connect_timeout", 30),
            read_timeout=data.get("read_timeout", 300)
        )

    @classmethod
    def from_env(cls) -> "YouTubeConfig":
        """Create config from environment variables."""
        return cls(
            client_secrets_file=os.getenv("YOUTUBE_CLIENT_SECRETS", "client_secrets.json"),
            credentials_file=os.getenv("YOUTUBE_CREDENTIALS", "youtube_credentials.json"),
            default_category=os.getenv("YOUTUBE_DEFAULT_CATEGORY", "10"),
            default_privacy=os.getenv("YOUTUBE_DEFAULT_PRIVACY", "public"),
            max_uploads_per_day=int(os.getenv("YOUTUBE_MAX_UPLOADS_PER_DAY", "6")),
            min_upload_interval=int(os.getenv("YOUTUBE_MIN_UPLOAD_INTERVAL", "300"))
        )


@dataclass
class RenderConfig:
    """Video rendering configuration for pipeline."""

    # Video settings
    codec: str = "av1"
    width: int = 1920
    height: int = 1080
    fps: int = 60
    target_duration: str = "08:00:00"  # HH:MM:SS

    # Quality settings
    video_bitrate: Optional[str] = None  # e.g., "5M"
    audio_bitrate: str = "192k"

    # Hardware acceleration
    use_hw_accel: bool = True
    preferred_encoder: Optional[str] = None  # Force specific encoder

    # Output settings
    output_prefix: str = "video"
    output_dir: Optional[Path] = None

    def validate(self) -> List[str]:
        """Validate render configuration."""
        errors = []

        # Validate codec
        try:
            VideoCodec(self.codec)
        except ValueError:
            errors.append(
                f"Invalid codec: {self.codec}. "
                f"Must be one of: {[e.value for e in VideoCodec]}"
            )

        # Validate resolution
        if self.width < 1 or self.height < 1:
            errors.append("Width and height must be positive")

        common_resolutions = {
            (3840, 2160), (2560, 1440), (1920, 1080),
            (1280, 720), (854, 480), (640, 360)
        }
        if (self.width, self.height) not in common_resolutions:
            errors.append(
                f"Unusual resolution: {self.width}x{self.height}. "
                f"Common resolutions: {common_resolutions}"
            )

        # Validate FPS
        if self.fps not in {24, 25, 30, 50, 60}:
            errors.append(f"Unusual FPS: {self.fps}. Common: 24, 25, 30, 50, 60")

        # Validate duration format
        if not re.match(r'^\d{1,2}:\d{2}:\d{2}$', self.target_duration):
            errors.append(
                f"Invalid duration format: {self.target_duration}. "
                f"Must be HH:MM:SS"
            )

        # Parse and validate duration
        try:
            h, m, s = map(int, self.target_duration.split(':'))
            if not (0 <= h < 24 and 0 <= m < 60 and 0 <= s < 60):
                errors.append("Invalid duration values")
        except Exception:
            errors.append("Failed to parse duration")

        # Validate bitrate format
        if self.video_bitrate and not re.match(r'^\d+[kKmM]?$', self.video_bitrate):
            errors.append(f"Invalid video bitrate format: {self.video_bitrate}")

        return errors

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "RenderConfig":
        """Create config from dictionary."""
        return cls(
            codec=data.get("codec", "av1"),
            width=data.get("width", 1920),
            height=data.get("height", 1080),
            fps=data.get("fps", 60),
            target_duration=data.get("target_duration", "08:00:00"),
            video_bitrate=data.get("video_bitrate"),
            audio_bitrate=data.get("audio_bitrate", "192k"),
            use_hw_accel=data.get("use_hw_accel", True),
            preferred_encoder=data.get("preferred_encoder")
        )


@dataclass
class PipelineConfig(BaseConfig):
    """Main pipeline configuration."""

    # Version
    version: int = CONFIG_VERSION
    format_version: str = CONFIG_FORMAT_VERSION

    # Directories
    work_dir: Path = field(default_factory=Path.cwd)
    music_dir: Optional[Path] = None
    output_dir: Optional[Path] = None
    state_file: Optional[Path] = None
    temp_dir: Optional[Path] = None

    # Pipeline settings
    continuous_mode: bool = False
    delay_between_videos: int = 300  # Seconds
    max_continuous_iterations: Optional[int] = None  # None = infinite

    # Style and genre options
    styles: List[str] = field(default_factory=lambda: [
        "relaxing", "calm", "peaceful", "meditative", "sleep"
    ])
    genres: List[str] = field(default_factory=lambda: [
        "ambient", "classical", "electronic", "jazz", "lounge",
        "chillout", "newage"
    ])

    # Video files
    intro_video: Optional[Path] = None
    loop_video: Optional[Path] = None

    # Sub-configurations
    youtube: YouTubeConfig = field(default_factory=YouTubeConfig)
    render: RenderConfig = field(default_factory=RenderConfig)

    # Logging
    log_level: str = "INFO"
    log_file: Optional[Path] = None

    # Monitoring
    enable_metrics: bool = False
    metrics_port: int = 9090

    def __post_init__(self):
        """Set default values for optional paths."""
        if isinstance(self.work_dir, str):
            self.work_dir = Path(self.work_dir)
        if isinstance(self.intro_video, str):
            self.intro_video = Path(self.intro_video)
        if isinstance(self.loop_video, str):
            self.loop_video = Path(self.loop_video)

        if self.music_dir is None:
            self.music_dir = self.work_dir / "music"
        elif isinstance(self.music_dir, str):
            self.music_dir = Path(self.music_dir)

        if self.output_dir is None:
            self.output_dir = self.work_dir / "output"
        elif isinstance(self.output_dir, str):
            self.output_dir = Path(self.output_dir)

        if self.state_file is None:
            self.state_file = self.work_dir / "state.json"
        elif isinstance(self.state_file, str):
            self.state_file = Path(self.state_file)

        if self.temp_dir is None:
            self.temp_dir = self.work_dir / "tmp"
        elif isinstance(self.temp_dir, str):
            self.temp_dir = Path(self.temp_dir)

        if self.log_file and isinstance(self.log_file, str):
            self.log_file = Path(self.log_file)

    def validate(self) -> List[str]:
        """
        Validate complete configuration.

        Returns:
            List of validation errors (empty if valid)
        """
        errors = []

        # Validate sub-configurations
        errors.extend(self.youtube.validate())
        errors.extend(self.render.validate())

        # Validate numeric values
        if self.delay_between_videos < 0:
            errors.append("delay_between_videos cannot be negative")

        if self.max_continuous_iterations is not None and self.max_continuous_iterations < 1:
            errors.append("max_continuous_iterations must be at least 1")

        # Validate lists
        if not self.styles:
            errors.append("styles list cannot be empty")

        if not self.genres:
            errors.append("genres list cannot be empty")

        # Validate log level
        valid_log_levels = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        if self.log_level.upper() not in valid_log_levels:
            errors.append(
                f"Invalid log level: {self.log_level}. "
                f"Must be one of: {valid_log_levels}"
            )

        # Validate port
        if not (1 <= self.metrics_port <= 65535):
            errors.append(f"Invalid metrics port: {self.metrics_port}")

        return errors

    @classmethod
    def from_file(cls, path: Path) -> "PipelineConfig":
        """
        Load configuration from JSON file.

        Args:
            path: Path to config file

        Returns:
            PipelineConfig instance
        """
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)

        # Check version and migrate if needed
        version = data.get("version", 1)
        if version < CONFIG_VERSION:
            data = cls._migrate_config(data, version)

        return cls._from_dict(data)

    @classmethod
    def _from_dict(cls, data: Dict[str, Any]) -> "PipelineConfig":
        """Create config from dictionary (internal)."""
        config = cls(
            version=data.get("version", CONFIG_VERSION),
            format_version=data.get("format_version", CONFIG_FORMAT_VERSION),
            work_dir=Path(data.get("work_dir", ".")),
            continuous_mode=data.get("continuous_mode", False),
            delay_between_videos=data.get("delay_between_videos", 300),
            max_continuous_iterations=data.get("max_continuous_iterations"),
            styles=data.get("styles", cls().styles),
            genres=data.get("genres", cls().genres),
            log_level=data.get("log_level", "INFO"),
            enable_metrics=data.get("enable_metrics", False),
            metrics_port=data.get("metrics_port", 9090)
        )

        # Parse paths
        if "intro_video" in data and data["intro_video"]:
            config.intro_video = Path(data["intro_video"])
        if "loop_video" in data and data["loop_video"]:
            config.loop_video = Path(data["loop_video"])

        # Parse sub-configs
        if "youtube" in data:
            config.youtube = YouTubeConfig.from_dict(data["youtube"])
        if "render" in data:
            config.render = RenderConfig.from_dict(data["render"])

        return config

    @staticmethod
    def _migrate_config(data: Dict[str, Any], from_version: int) -> Dict[str, Any]:
        """Migrate configuration from older version."""
        if from_version == 1:
            # v1 to v2 migration
            logger.info("Migrating config from v1 to v2")

            # Extract render settings
            render_data = {
                "codec": data.get("codec", "av1"),
                "target_duration": data.get("target_duration", "08:00:00")
            }
            data["render"] = render_data

            # Update version
            data["version"] = 2
            data["format_version"] = "2.0"

        return data

    def to_file(self, path: Optional[Path] = None):
        """
        Save configuration to JSON file.

        Args:
            path: Path to save to (defaults to work_dir/config.json)
        """
        if path is None:
            path = self.work_dir / "config.json"

        # Prepare data
        data = {
            "version": self.version,
            "format_version": self.format_version,
            "work_dir": str(self.work_dir),
            "continuous_mode": self.continuous_mode,
            "delay_between_videos": self.delay_between_videos,
            "max_continuous_iterations": self.max_continuous_iterations,
            "styles": self.styles,
            "genres": self.genres,
            "youtube": asdict(self.youtube),
            "render": asdict(self.render),
            "log_level": self.log_level,
            "enable_metrics": self.enable_metrics,
            "metrics_port": self.metrics_port
        }

        if self.intro_video:
            data["intro_video"] = str(self.intro_video)
        if self.loop_video:
            data["loop_video"] = str(self.loop_video)

        # Write to file with atomic write
        temp_file = path.with_suffix(".tmp")
        with open(temp_file, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

        temp_file.replace(path)

    def check_files_exist(self) -> List[str]:
        """
        Check that required files exist.

        Returns:
            List of missing files (empty if all exist)
        """
        missing = []

        # Check YouTube secrets
        if not Path(self.youtube.client_secrets_file).exists():
            missing.append(f"YouTube client secrets: {self.youtube.client_secrets_file}")

        # Check video files if specified
        if self.intro_video and not self.intro_video.exists():
            missing.append(f"Intro video: {self.intro_video}")

        if self.loop_video and not self.loop_video.exists():
            missing.append(f"Loop video: {self.loop_video}")

        return missing

    def check_music_files(self) -> tuple[List[Path], List[str]]:
        """
        Check for music files in music directory.

        Returns:
            Tuple of (found_files, errors)
        """
        errors = []
        files = []

        if not self.music_dir.exists():
            errors.append(f"Music directory not found: {self.music_dir}")
            return files, errors

        # Scan for audio files
        for ext in PIPELINE_AUDIO_FORMATS:
            files.extend(self.music_dir.glob(f"*{ext}"))

        if not files:
            errors.append(f"No music files found in: {self.music_dir}")

        return files, errors


# ═══════════════════════════════════════════════════════════════════════════════
# Default Config Template
# ═══════════════════════════════════════════════════════════════════════════════

DEFAULT_CONFIG_TEMPLATE = """{
  "version": 2,
  "format_version": "2.0",
  "work_dir": ".",
  "intro_video": "intro.mp4",
  "loop_video": "loop.mp4",
  "continuous_mode": false,
  "delay_between_videos": 300,
  "max_continuous_iterations": null,
  "styles": ["relaxing", "calm", "peaceful", "meditative", "sleep"],
  "genres": ["ambient", "classical", "electronic", "jazz", "lounge", "chillout", "newage"],
  "youtube": {
    "client_secrets_file": "client_secrets.json",
    "credentials_file": "youtube_credentials.json",
    "default_category": "10",
    "default_privacy": "public",
    "max_uploads_per_day": 6,
    "min_upload_interval": 300,
    "title_template": "{duration} {style} Music | {genre} | Relaxing Background",
    "description_template": "🎵 {duration} of {style} {genre} music...\\n#relaxingmusic",
    "tags": ["relaxing music", "ambient", "sleep music", "study music"],
    "chunk_size": 1048576,
    "connect_timeout": 30,
    "read_timeout": 300
  },
  "render": {
    "codec": "av1",
    "width": 1920,
    "height": 1080,
    "fps": 60,
    "target_duration": "08:00:00",
    "video_bitrate": null,
    "audio_bitrate": "192k",
    "use_hw_accel": true,
    "preferred_encoder": null
  },
  "log_level": "INFO",
  "enable_metrics": false,
  "metrics_port": 9090
}
"""


# ═══════════════════════════════════════════════════════════════════════════════
# Schema Generator
# ═══════════════════════════════════════════════════════════════════════════════

def generate_json_schema() -> Dict[str, Any]:
    """Generate JSON schema for PipelineConfig validation."""
    return {
        "$schema": "http://json-schema.org/draft-07/schema#",
        "title": "VideoAutomation Pipeline Configuration",
        "type": "object",
        "required": ["work_dir", "styles", "genres"],
        "properties": {
            "version": {"type": "integer", "const": 2},
            "format_version": {"type": "string", "const": "2.0"},
            "work_dir": {"type": "string"},
            "intro_video": {"type": "string"},
            "loop_video": {"type": "string"},
            "continuous_mode": {"type": "boolean"},
            "delay_between_videos": {"type": "integer", "minimum": 0},
            "max_continuous_iterations": {
                "oneOf": [
                    {"type": "null"},
                    {"type": "integer", "minimum": 1}
                ]
            },
            "styles": {
                "type": "array",
                "items": {"type": "string"},
                "minItems": 1
            },
            "genres": {
                "type": "array",
                "items": {"type": "string"},
                "minItems": 1
            },
            "youtube": {
                "type": "object",
                "properties": {
                    "client_secrets_file": {"type": "string"},
                    "credentials_file": {"type": "string"},
                    "default_category": {"type": "string"},
                    "default_privacy": {"enum": ["public", "private", "unlisted"]},
                    "max_uploads_per_day": {"type": "integer", "minimum": 1},
                    "min_upload_interval": {"type": "integer", "minimum": 0}
                }
            },
            "render": {
                "type": "object",
                "properties": {
                    "codec": {"enum": ["h264", "h265", "vp9", "av1"]},
                    "width": {"type": "integer", "minimum": 1},
                    "height": {"type": "integer", "minimum": 1},
                    "fps": {"enum": [24, 25, 30, 50, 60]},
                    "target_duration": {
                        "type": "string",
                        "pattern": "^\\d{1,2}:\\d{2}:\\d{2}$"
                    }
                }
            },
            "log_level": {
                "enum": ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
            },
            "enable_metrics": {"type": "boolean"},
            "metrics_port": {"type": "integer", "minimum": 1, "maximum": 65535}
        }
    }


def validate_with_schema(config_data: Dict[str, Any]) -> tuple[bool, List[str]]:
    """
    Validate config data against JSON schema.

    Returns:
        Tuple of (is_valid, list_of_errors)
    """
    try:
        import jsonschema
    except ImportError:
        logger.warning("jsonschema not installed, skipping schema validation")
        return True, []

    schema = generate_json_schema()
    validator = jsonschema.Draft7Validator(schema)

    errors = []
    for error in validator.iter_errors(config_data):
        path = " -> ".join(str(p) for p in error.path) if error.path else "root"
        errors.append(f"{path}: {error.message}")

    return len(errors) == 0, errors

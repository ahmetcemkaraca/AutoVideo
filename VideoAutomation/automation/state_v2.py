#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
State management v2 - Production-ready state persistence.

Features:
- Atomic writes to prevent corruption
- State versioning and migration
- Corruption recovery
- Thread-safe operations
- Automatic backups
"""

import json
import threading
import hashlib
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import List, Dict, Optional, Any, Tuple
from datetime import datetime
from contextlib import contextmanager
import logging
import shutil

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════════════
# Current State Version
# ═══════════════════════════════════════════════════════════════════════════════

STATE_VERSION = 2
STATE_FORMAT_VERSION = "2.0"

# Maximum state file size (10MB)
MAX_STATE_SIZE = 10 * 1024 * 1024

# Number of backups to keep
BACKUP_COUNT = 5


# ═══════════════════════════════════════════════════════════════════════════════
# Data Models
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
    file_size: Optional[int] = None  # Size in bytes
    upload_attempts: int = 0
    last_error: Optional[str] = None
    tags: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        """Validate and normalize the record."""
        if not self.video_id:
            raise ValueError("video_id is required")
        if not self.title:
            raise ValueError("title is required")
        if not self.created_at:
            self.created_at = datetime.now().isoformat()


@dataclass
class PipelineStats:
    """Pipeline statistics."""
    total_videos_created: int = 0
    total_uploads_attempted: int = 0
    total_uploads_successful: int = 0
    total_uploads_failed: int = 0
    total_render_time_seconds: float = 0.0
    total_upload_time_seconds: float = 0.0
    last_run: Optional[str] = None
    last_success: Optional[str] = None
    last_failure: Optional[str] = None
    consecutive_failures: int = 0
    consecutive_successes: int = 0


@dataclass
class PipelineState:
    """Complete pipeline state with versioning."""
    version: int = STATE_VERSION
    format_version: str = STATE_FORMAT_VERSION
    videos: Dict[str, VideoRecord] = field(default_factory=dict)
    stats: PipelineStats = field(default_factory=PipelineStats)
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now().isoformat())
    checksum: Optional[str] = None  # For integrity verification


# ═══════════════════════════════════════════════════════════════════════════════
# State Migration
# ═══════════════════════════════════════════════════════════════════════════════

class StateMigration:
    """Handle state format migrations."""

    @staticmethod
    def migrate_v1_to_v2(data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Migrate v1 state to v2 format.

        v1 format:
        {
            "videos": {video_id: {...}},
            "last_run": "...",
            "total_videos_created": N
        }

        v2 format:
        {
            "version": 2,
            "format_version": "2.0",
            "videos": {...},
            "stats": {...},
            "created_at": "...",
            "updated_at": "..."
        }
        """
        logger.info("Migrating state from v1 to v2")

        # Extract old data
        videos = data.get("videos", {})
        last_run = data.get("last_run")
        total_videos = data.get("total_videos_created", 0)

        # Convert video records
        migrated_videos = {}
        for video_id, video_data in videos.items():
            migrated_videos[video_id] = {
                "video_id": video_id,
                "title": video_data.get("title", ""),
                "created_at": video_data.get("created_at", ""),
                "uploaded_at": video_data.get("uploaded_at"),
                "genre": video_data.get("genre", ""),
                "style": video_data.get("style", ""),
                "duration": video_data.get("duration", ""),
                "local_path": video_data.get("local_path"),
                "upload_attempts": 0,
                "last_error": None,
                "tags": [],
                "metadata": {}
            }

        # Create new structure
        return {
            "version": 2,
            "format_version": "2.0",
            "videos": migrated_videos,
            "stats": {
                "total_videos_created": total_videos,
                "total_uploads_attempted": 0,
                "total_uploads_successful": 0,
                "total_uploads_failed": 0,
                "total_render_time_seconds": 0.0,
                "total_upload_time_seconds": 0.0,
                "last_run": last_run,
                "last_success": None,
                "last_failure": None,
                "consecutive_failures": 0,
                "consecutive_successes": 0
            },
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat(),
            "checksum": None
        }

    @classmethod
    def migrate(cls, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Migrate state data to current version.

        Args:
            data: State data to migrate

        Returns:
            Migrated state data
        """
        version = data.get("version", 1)

        if version == STATE_VERSION:
            return data

        if version == 1:
            data = cls.migrate_v1_to_v2(data)
            return data

        raise ValueError(f"Unknown state version: {version}")


# ═══════════════════════════════════════════════════════════════════════════════
# State Manager v2
# ═══════════════════════════════════════════════════════════════════════════════

class StateManager:
    """
    Production-ready state manager with atomic writes and corruption recovery.
    """

    def __init__(
        self,
        state_file: Path,
        auto_backup: bool = True,
        backup_count: int = BACKUP_COUNT
    ):
        """
        Initialize state manager.

        Args:
            state_file: Path to state file
            auto_backup: Automatically create backups
            backup_count: Number of backups to keep
        """
        self.state_file = state_file
        self.auto_backup = auto_backup
        self.backup_count = backup_count
        self._state: PipelineState = PipelineState()
        self._lock = threading.Lock()
        self._file_lock = None

        # Create state directory if needed
        self.state_file.parent.mkdir(parents=True, exist_ok=True)

        # Load existing state or create new
        self._load_or_create()

    def _load_or_create(self):
        """Load existing state or create new one."""
        if self.state_file.exists():
            try:
                self._load()
            except Exception as e:
                logger.error(f"Failed to load state file: {e}")
                logger.info("Attempting recovery from backup")
                self._recover_from_backup()

                if self._state is None or not self._state.videos:
                    logger.warning("Backup recovery failed, creating new state")
                    self._state = PipelineState()
        else:
            self._state = PipelineState()
            self._save()

    def _load(self):
        """Load state from file with validation."""
        # Check file size
        file_size = self.state_file.stat().st_size
        if file_size > MAX_STATE_SIZE:
            raise ValueError(
                f"State file too large: {file_size} bytes "
                f"(max {MAX_STATE_SIZE} bytes)"
            )

        with open(self.state_file, "r", encoding="utf-8") as f:
            data = json.load(f)

        # Verify checksum if present
        if "checksum" in data and data["checksum"]:
            stored_checksum = data["checksum"]
            data["checksum"] = None  # Clear for recalculation
            calculated_checksum = self._calculate_checksum(data)
            data["checksum"] = stored_checksum

            if stored_checksum != calculated_checksum:
                logger.warning("State file checksum mismatch, data may be corrupted")

        # Migrate if needed
        data = StateMigration.migrate(data)

        # Parse videos
        videos = {}
        for video_id, video_data in data.get("videos", {}).items():
            try:
                videos[video_id] = VideoRecord(**video_data)
            except Exception as e:
                logger.warning(f"Failed to parse video record {video_id}: {e}")

        # Parse stats
        stats_data = data.get("stats", {})
        stats = PipelineStats(**{
            k: v for k, v in stats_data.items()
            if k in PipelineStats.__dataclass_fields__
        })

        self._state = PipelineState(
            version=data.get("version", STATE_VERSION),
            format_version=data.get("format_version", STATE_FORMAT_VERSION),
            videos=videos,
            stats=stats,
            created_at=data.get("created_at", datetime.now().isoformat()),
            updated_at=data.get("updated_at", datetime.now().isoformat()),
            checksum=data.get("checksum")
        )

    def _save(self):
        """Save state to file atomically."""
        with self._lock:
            # Update timestamp
            self._state.updated_at = datetime.now().isoformat()

            # Serialize state
            data = {
                "version": self._state.version,
                "format_version": self._state.format_version,
                "videos": {
                    vid: asdict(video) for vid, video in self._state.videos.items()
                },
                "stats": asdict(self._state.stats),
                "created_at": self._state.created_at,
                "updated_at": self._state.updated_at,
            }

            # Calculate checksum
            data["checksum"] = self._calculate_checksum(data)

            # Write to temporary file
            temp_file = self.state_file.with_suffix(".tmp")
            try:
                with open(temp_file, "w", encoding="utf-8") as f:
                    json.dump(data, f, indent=2, ensure_ascii=False)

                # Atomic rename
                temp_file.replace(self.state_file)

                # Create backup if enabled
                if self.auto_backup:
                    self._create_backup()

            except Exception as e:
                logger.error(f"Failed to save state: {e}")
                if temp_file.exists():
                    temp_file.unlink()
                raise

    @staticmethod
    def _calculate_checksum(data: Dict[str, Any]) -> str:
        """Calculate checksum of state data."""
        # Sort keys for consistent hashing
        normalized = json.dumps(data, sort_keys=True, ensure_ascii=False)
        return hashlib.sha256(normalized.encode()).hexdigest()

    def _create_backup(self):
        """Create a backup of the current state file."""
        if not self.state_file.exists():
            return

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_file = self.state_file.parent / f"{self.state_file.stem}_{timestamp}.json"

        try:
            shutil.copy2(self.state_file, backup_file)
            logger.debug(f"Created backup: {backup_file.name}")

            # Clean old backups
            self._cleanup_old_backups()

        except Exception as e:
            logger.warning(f"Failed to create backup: {e}")

    def _cleanup_old_backups(self):
        """Remove old backups, keeping only the most recent."""
        backups = sorted(
            self.state_file.parent.glob(f"{self.state_file.stem}_*.json"),
            reverse=True
        )

        for old_backup in backups[self.backup_count:]:
            try:
                old_backup.unlink()
                logger.debug(f"Removed old backup: {old_backup.name}")
            except Exception as e:
                logger.warning(f"Failed to remove old backup {old_backup.name}: {e}")

    def _recover_from_backup(self):
        """Attempt to recover state from the most recent backup."""
        backups = sorted(
            self.state_file.parent.glob(f"{self.state_file.stem}_*.json"),
            reverse=True
        )

        for backup in backups:
            try:
                logger.info(f"Attempting recovery from backup: {backup.name}")

                # Temporarily use backup file
                original_file = self.state_file
                self.state_file = backup
                self._load()
                self.state_file = original_file

                # Save recovered state
                self._save()

                logger.info("Successfully recovered from backup")
                return

            except Exception as e:
                logger.warning(f"Failed to recover from backup {backup.name}: {e}")
                continue

        logger.error("All recovery attempts failed")

    @contextmanager
    def _atomic_write(self):
        """
        Context manager for atomic write operations.

        Usage:
            with state_manager._atomic_write():
                # Modify state
                state_manager.add_video(...)
                # State is automatically saved on exit
        """
        with self._lock:
            yield
            self._save()

    # ═══════════════════════════════════════════════════════════════════════════════
    # Public API
    # ═══════════════════════════════════════════════════════════════════════════════

    def add_video(
        self,
        video_id: str,
        title: str,
        genre: str = "",
        style: str = "",
        duration: str = "",
        local_path: Optional[str] = None,
        file_size: Optional[int] = None,
        tags: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None
    ):
        """
        Record a newly created video.

        Args:
            video_id: Unique video identifier
            title: Video title
            genre: Music genre
            style: Music style
            duration: Duration string (HH:MM:SS)
            local_path: Path to local file
            file_size: File size in bytes
            tags: List of tags
            metadata: Additional metadata
        """
        with self._atomic_write():
            now = datetime.now().isoformat()

            self._state.videos[video_id] = VideoRecord(
                video_id=video_id,
                title=title,
                created_at=now,
                genre=genre,
                style=style,
                duration=duration,
                local_path=local_path,
                file_size=file_size,
                tags=tags or [],
                metadata=metadata or {}
            )

            # Update stats
            self._state.stats.total_videos_created += 1
            self._state.stats.last_run = now
            self._state.stats.consecutive_successes += 1
            self._state.stats.consecutive_failures = 0
            self._state.stats.last_success = now

    def mark_upload_attempt(self, video_id: str):
        """Record an upload attempt for a video."""
        with self._atomic_write():
            if video_id in self._state.videos:
                self._state.videos[video_id].upload_attempts += 1
                self._state.stats.total_uploads_attempted += 1

    def mark_upload_success(self, video_id: str):
        """Mark a video as successfully uploaded."""
        with self._atomic_write():
            if video_id in self._state.videos:
                self._state.videos[video_id].uploaded_at = datetime.now().isoformat()
                self._state.videos[video_id].last_error = None
                self._state.stats.total_uploads_successful += 1

    def mark_upload_failed(self, video_id: str, error: str):
        """Mark a video upload as failed."""
        with self._atomic_write():
            if video_id in self._state.videos:
                self._state.videos[video_id].last_error = error
                self._state.stats.total_uploads_failed += 1
                self._state.stats.consecutive_failures += 1
                self._state.stats.consecutive_failures = 0
                self._state.stats.last_failure = datetime.now().isoformat()

    def get_video(self, video_id: str) -> Optional[VideoRecord]:
        """Get a video record by ID."""
        return self._state.videos.get(video_id)

    def get_all_videos(self) -> Dict[str, VideoRecord]:
        """Get all video records."""
        return self._state.videos.copy()

    def delete_video(self, video_id: str) -> bool:
        """
        Delete a video record.

        Returns:
            True if video was deleted
        """
        with self._atomic_write():
            if video_id in self._state.videos:
                del self._state.videos[video_id]
                return True
            return False

    def update_stats(
        self,
        render_time: Optional[float] = None,
        upload_time: Optional[float] = None
    ):
        """
        Update pipeline statistics.

        Args:
            render_time: Time spent rendering in seconds
            upload_time: Time spent uploading in seconds
        """
        with self._atomic_write():
            if render_time is not None:
                self._state.stats.total_render_time_seconds += render_time
            if upload_time is not None:
                self._state.stats.total_upload_time_seconds += upload_time

    @property
    def stats(self) -> PipelineStats:
        """Get pipeline statistics."""
        return self._state.stats

    @property
    def is_healthy(self) -> bool:
        """
        Check if pipeline state is healthy.

        Returns:
            True if consecutive failures < 5
        """
        return self._state.stats.consecutive_failures < 5

    @property
    def video_count(self) -> int:
        """Get total number of videos."""
        return len(self._state.videos)

    def force_save(self):
        """Force save state to disk."""
        self._save()

    def create_backup(self) -> Path:
        """
        Manually create a backup.

        Returns:
            Path to backup file
        """
        self._create_backup()
        return self._get_latest_backup()

    def _get_latest_backup(self) -> Optional[Path]:
        """Get path to most recent backup."""
        backups = list(
            self.state_file.parent.glob(f"{self.state_file.stem}_*.json")
        )
        if backups:
            return max(backups, key=lambda p: p.stat().st_mtime)
        return None

    def validate(self) -> Tuple[bool, List[str]]:
        """
        Validate state integrity.

        Returns:
            Tuple of (is_valid, list_of_issues)
        """
        issues = []

        # Check for required fields
        if not self._state.created_at:
            issues.append("Missing created_at timestamp")

        # Validate video records
        for video_id, video in self._state.videos.items():
            if video.video_id != video_id:
                issues.append(f"Video ID mismatch: {video_id} vs {video.video_id}")
            if not video.title:
                issues.append(f"Video {video_id} missing title")
            if not video.created_at:
                issues.append(f"Video {video_id} missing created_at")

        # Check stats consistency
        if self._state.stats.total_videos_created != len(self._state.videos):
            issues.append(
                f"Stats video count mismatch: "
                f"{self._state.stats.total_videos_created} vs {len(self._state.videos)}"
            )

        return len(issues) == 0, issues

    def export_json(self) -> str:
        """Export state as JSON string."""
        data = {
            "version": self._state.version,
            "format_version": self._state.format_version,
            "videos": {
                vid: asdict(video) for vid, video in self._state.videos.items()
            },
            "stats": asdict(self._state.stats),
            "created_at": self._state.created_at,
            "updated_at": self._state.updated_at,
        }
        return json.dumps(data, indent=2, ensure_ascii=False)

    def import_json(self, json_str: str, merge: bool = False):
        """
        Import state from JSON string.

        Args:
            json_str: JSON string to import
            merge: If True, merge with existing state. If False, replace.
        """
        data = json.loads(json_str)
        data = StateMigration.migrate(data)

        if merge:
            # Merge videos
            for video_id, video_data in data.get("videos", {}).items():
                if video_id not in self._state.videos:
                    self._state.videos[video_id] = VideoRecord(**video_data)
        else:
            # Replace entire state
            videos = {}
            for video_id, video_data in data.get("videos", {}).items():
                videos[video_id] = VideoRecord(**video_data)

            stats_data = data.get("stats", {})
            stats = PipelineStats(**{
                k: v for k, v in stats_data.items()
                if k in PipelineStats.__dataclass_fields__
            })

            self._state = PipelineState(
                version=data.get("version", STATE_VERSION),
                format_version=data.get("format_version", STATE_FORMAT_VERSION),
                videos=videos,
                stats=stats,
                created_at=data.get("created_at", datetime.now().isoformat()),
                updated_at=datetime.now().isoformat()
            )

        self._save()

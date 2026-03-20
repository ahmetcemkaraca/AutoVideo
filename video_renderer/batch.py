#!/usr/bin/env python3
"""
Batch Rendering System.

Allows configuring multiple render jobs while previous ones are processing.

Thread-Safe Implementation:
- All public methods use threading.Lock for synchronization
- File I/O uses atomic write patterns with temp files
- Callbacks are invoked outside of critical sections
- Job objects are returned as copies to prevent external modification

State Management:
- Uses unified StateManager for persistence
- Cross-process file locking for concurrent access
- Automatic stale lock cleanup
"""

import logging
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass, field, replace
from enum import Enum
from pathlib import Path
from typing import Any

from .ffmpeg import check_disk_space
from .hash_ledger import HashLedger
from .state_manager import StateManager

logger = logging.getLogger(__name__)


class JobStatus(Enum):
    """Render job status."""

    PENDING = "pending"
    CONFIGURING = "configuring"
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETE = "complete"
    ERROR = "error"
    CANCELLED = "cancelled"


@dataclass(frozen=False)
class RenderJob:
    """
    Represents a single render job.

    Note: This class is mutable for performance reasons.
    The BatchQueue returns copies to prevent external modification.
    """

    id: int
    intro_path: Path | None = None
    loop_path: Path | None = None
    single_video_path: Path | None = None
    mode: str = "intro_loop"  # intro_loop or single
    codec_family: str = "av1"
    target_fps: float = 60.0
    video_bitrate: str | None = None  # e.g., "5000k" or "5M"
    duration_str: str = "9:00:00"
    total_seconds: int = 32400
    tracks: list[Path] = field(default_factory=list)
    backgrounds: list[tuple] = field(default_factory=list)
    output_path: Path | None = None
    status: JobStatus = JobStatus.PENDING
    progress: float = 0.0
    error_message: str | None = None
    started_at: str | None = None
    completed_at: str | None = None
    upload_enabled: bool = False
    upload_folder_id: str | None = None
    upload_status: str = "pending"  # pending, uploading, complete, error
    upload_file_id: str | None = None
    skip_duplicate: bool = True  # Skip if source already rendered
    force_render: bool = False  # Force render even if duplicate

    def to_dict(self) -> dict[str, Any]:
        """Convert to serializable dict."""
        return {
            "id": self.id,
            "intro": str(self.intro_path) if self.intro_path else None,
            "loop": str(self.loop_path) if self.loop_path else None,
            "single_video": str(self.single_video_path) if self.single_video_path else None,
            "mode": self.mode,
            "codec": self.codec_family,
            "target_fps": self.target_fps,
            "duration": self.duration_str,
            "duration_sec": self.total_seconds,
            "tracks": [str(t) for t in self.tracks],
            "backgrounds": [(str(p), db) for p, db in self.backgrounds],
            "output": str(self.output_path) if self.output_path else None,
            "status": self.status.value,
            "progress": self.progress,
            "error": self.error_message,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "upload_enabled": self.upload_enabled,
            "upload_folder_id": self.upload_folder_id,
            "upload_status": self.upload_status,
            "upload_file_id": self.upload_file_id,
            "skip_duplicate": self.skip_duplicate,
            "force_render": self.force_render,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "RenderJob":
        """Create from dict."""
        job = cls(id=data["id"])
        job.intro_path = Path(data["intro"]) if data.get("intro") else None
        job.loop_path = Path(data["loop"]) if data.get("loop") else None
        job.single_video_path = Path(data["single_video"]) if data.get("single_video") else None
        job.mode = data.get("mode", "intro_loop")
        job.codec_family = data.get("codec", "av1")
        job.target_fps = data.get("target_fps", 60.0)
        job.duration_str = data.get("duration", "9:00:00")
        job.total_seconds = data.get("duration_sec", 32400)
        job.tracks = [Path(t) for t in data.get("tracks", [])]
        job.backgrounds = [(Path(p), db) for p, db in data.get("backgrounds", [])]
        job.output_path = Path(data["output"]) if data.get("output") else None
        job.status = JobStatus(data.get("status", "pending"))
        job.progress = data.get("progress", 0.0)
        job.error_message = data.get("error")
        job.started_at = data.get("started_at")
        job.completed_at = data.get("completed_at")
        job.upload_enabled = data.get("upload_enabled", False)
        job.upload_folder_id = data.get("upload_folder_id")
        job.upload_status = data.get("upload_status", "pending")
        job.upload_file_id = data.get("upload_file_id")
        job.skip_duplicate = data.get("skip_duplicate", True)
        job.force_render = data.get("force_render", False)
        return job

    def copy(self) -> "RenderJob":
        """
        Create a deep copy of this job.
        Used to prevent external modification of internal state.
        """
        return replace(self, tracks=self.tracks.copy(), backgrounds=self.backgrounds.copy())


class BatchQueue:
    """
    Thread-safe queue of render jobs with unified state management.

    Thread-Safety Guarantees:
    - All state modifications are protected by threading.Lock
    - Uses StateManager for atomic file persistence
    - Callbacks are invoked outside critical sections
    - Returned job objects are copies to prevent external modification

    State Management:
    - Uses StateManager for persistence
    - Cross-process file locking for concurrent access
    - Automatic stale lock cleanup

    Memory Management:
    - Max queue size limits concurrent jobs
    - Memory limit calculated from available system RAM
    - Automatic memory-aware queue sizing

    Usage:
        queue = BatchQueue()
        job = queue.create_job()
        # Configure job...
        queue.queue_job(job.id)
    """

    # System memory reservation (GB)
    SYSTEM_RESERVED_GB = 4

    # Default max concurrent jobs
    DEFAULT_MAX_QUEUE_SIZE = 5

    # State format version
    STATE_VERSION = "1.0"

    def __init__(
        self,
        queue_file: Path | None = None,
        max_queue_size: int | None = None,
        memory_limit_gb: int | None = None,
        enable_locking: bool = True,
    ):
        """
        Initialize batch queue.

        Args:
            queue_file: Path to queue state file
            max_queue_size: Maximum concurrent jobs
            memory_limit_gb: Memory limit in GB
            enable_locking: Enable cross-process file locking
        """
        self._jobs: list[RenderJob] = []
        self._current_job_id: int | None = None
        self._queue_file = queue_file or Path.cwd() / "tmp" / "batch_queue.json"
        self._next_id = 1
        self._lock = threading.RLock()  # RLock for reentrant calls
        self._on_job_complete: Callable[[RenderJob], None] | None = None
        self._on_job_error: Callable[[RenderJob, str], None] | None = None
        self._on_progress: Callable[[RenderJob, float], None] | None = None
        self._callback_lock = threading.Lock()  # Separate lock for callbacks

        # Memory management
        self._max_queue_size = max_queue_size or self.DEFAULT_MAX_QUEUE_SIZE
        self._memory_limit = memory_limit_gb or self._get_memory_limit()

        # Initialize StateManager for unified state persistence
        self.state = StateManager(
            state_file=self._queue_file,
            version=self.STATE_VERSION,
            auto_save=False,  # We'll save explicitly
            enable_locking=enable_locking,
        )

        # Initialize HashLedger for duplicate prevention
        ledger_file = Path.cwd() / "config" / "ledger.json"
        self.hash_ledger = HashLedger(ledger_file=ledger_file, enable_locking=enable_locking)

        # Load existing queue
        self._load()

    def _get_memory_limit(self) -> int:
        """
        Calculate memory limit for batch processing.

        Returns:
            Memory limit in GB (reserves 4GB for system)
        """
        try:
            import psutil

            available_gb = psutil.virtual_memory().available / (1024**3)
            # Reserve memory for system
            limit = max(1, int(available_gb - self.SYSTEM_RESERVED_GB))
            return limit
        except ImportError:
            # Fallback if psutil not available

            # Rough estimate: assume 8GB if we can't detect
            return max(1, 8 - self.SYSTEM_RESERVED_GB)

    def _load(self) -> None:
        """
        Load queue from StateManager.

        Thread-safe: StateManager handles file locking.
        """
        if not self.state.load():
            # No existing state, start fresh
            self._jobs = []
            self._next_id = 1
            return

        # Parse jobs from state
        jobs_data = self.state.get("jobs", [])
        self._jobs = [RenderJob.from_dict(j) for j in jobs_data]
        self._next_id = self.state.get("next_id", 1)

        # Find max id to prevent conflicts
        if self._jobs:
            self._next_id = max(j.id for j in self._jobs) + 1

    def _save(self) -> None:
        """
        Save queue to StateManager with validation.

        Thread-safe: StateManager handles atomic writes with validation.
        Fixed: Add validation to prevent corrupting queue file with invalid data.
        """
        # Validate data before saving
        if not isinstance(self._jobs, list):
            logger.error("Invalid jobs type for save, expected list")
            raise ValueError("Jobs must be a list")

        if not isinstance(self._next_id, int) or self._next_id < 1:
            logger.error(f"Invalid next_id for save: {self._next_id}")
            raise ValueError(f"next_id must be a positive integer, got {self._next_id}")

        # Validate each job before serialization
        for job in self._jobs:
            if not hasattr(job, "id") or not isinstance(job.id, int):
                logger.error(f"Invalid job in queue: {job}")
                raise ValueError("All jobs must have valid id attribute")

        data = {
            "jobs": [j.to_dict() for j in self._jobs],
            "next_id": self._next_id,
        }

        # StateManager will handle atomic write with temp file and rename
        try:
            self.state.update(data, save=True)  # Explicitly save since auto_save=False
        except Exception as e:
            logger.error(f"Failed to save batch queue: {e}")
            raise

    def _invoke_callback_safe(self, callback: Callable, *args) -> None:
        """
        Invoke callback in a thread-safe manner.

        Callbacks are invoked outside the main lock to prevent deadlocks.
        Uses a separate lock to serialize callback execution.
        """
        if callback is None:
            return

        def safe_invoke():
            try:
                with self._callback_lock:
                    callback(*args)
            except Exception as e:
                logger.error(f"Error in callback: {e}")

        # Spawn thread for callback to avoid holding lock
        threading.Thread(target=safe_invoke, daemon=True).start()

    def create_job(self, **kwargs) -> RenderJob:
        """
        Create a new pending job.

        Thread-safe: Returns a copy of the created job.
        """
        with self._lock:
            job = RenderJob(id=self._next_id, **kwargs)
            job.status = JobStatus.CONFIGURING
            self._next_id += 1
            self._jobs.append(job)
            self._save()
            return job.copy()

    def queue_job(self, job_id: int) -> RenderJob | None:
        """
        Mark a job as ready to run.

        Thread-safe: Returns a copy of the queued job.
        """
        with self._lock:
            job = self._get_job_unsafe(job_id)
            if job and job.status == JobStatus.CONFIGURING:
                job.status = JobStatus.QUEUED
                self._save()
                return job.copy()
        return None

    def get_job(self, job_id: int) -> RenderJob | None:
        """
        Get a job by ID.

        Thread-safe: Returns a copy of the job.
        """
        with self._lock:
            job = self._get_job_unsafe(job_id)
            return job.copy() if job else None

    def _get_job_unsafe(self, job_id: int) -> RenderJob | None:
        """Internal: Get job without lock (caller must hold lock)."""
        for job in self._jobs:
            if job.id == job_id:
                return job
        return None

    def get_queued_jobs(self) -> list[RenderJob]:
        """
        Get all queued jobs.

        Thread-safe: Returns a list of copies.
        """
        with self._lock:
            return [j.copy() for j in self._jobs if j.status == JobStatus.QUEUED]

    def get_pending_jobs(self) -> list[RenderJob]:
        """
        Get all pending/configuring jobs.

        Thread-safe: Returns a list of copies.
        """
        with self._lock:
            return [
                j.copy()
                for j in self._jobs
                if j.status in (JobStatus.PENDING, JobStatus.CONFIGURING)
            ]

    def get_all_jobs(self) -> list[RenderJob]:
        """
        Get all jobs regardless of status.

        Thread-safe: Returns a list of copies.
        """
        with self._lock:
            return [j.copy() for j in self._jobs]

    def get_next_job(self) -> RenderJob | None:
        """
        Get next job to run.

        Thread-safe: Returns a copy of the job.
        """
        with self._lock:
            for job in self._jobs:
                if job.status == JobStatus.QUEUED:
                    return job.copy()
        return None

    def start_job(self, job_id: int) -> RenderJob | None:
        """
        Mark a job as running.

        Thread-safe: Returns a copy of the started job.
        """
        with self._lock:
            job = self._get_job_unsafe(job_id)
            if job:
                job.status = JobStatus.RUNNING
                job.started_at = time.strftime("%Y-%m-%d %H:%M:%S")
                job.progress = 0.0
                self._current_job_id = job_id
                self._save()
                return job.copy()
        return None

    def update_progress(self, job_id: int, progress: float) -> None:
        """
        Update job progress.

        Thread-safe: Invokes progress callback outside lock.
        """
        job_copy = None
        with self._lock:
            job = self._get_job_unsafe(job_id)
            if job:
                job.progress = max(0.0, min(100.0, progress))
                job_copy = job.copy()

        # Invoke callback outside lock
        if job_copy and self._on_progress:
            self._invoke_callback_safe(self._on_progress, job_copy, job_copy.progress)

    def complete_job(self, job_id: int) -> RenderJob | None:
        """
        Mark a job as complete.

        Thread-safe: Invokes completion callback outside lock.
        """
        job_copy = None
        with self._lock:
            job = self._get_job_unsafe(job_id)
            if job:
                job.status = JobStatus.COMPLETE
                job.progress = 100.0
                job.completed_at = time.strftime("%Y-%m-%d %H:%M:%S")
                self._current_job_id = None
                self._save()
                job_copy = job.copy()

        # Invoke callback outside lock
        if job_copy and self._on_job_complete:
            self._invoke_callback_safe(self._on_job_complete, job_copy)

        return job_copy

    def fail_job(self, job_id: int, error: str) -> RenderJob | None:
        """
        Mark a job as failed.

        Thread-safe: Invokes error callback outside lock.
        """
        job_copy = None
        with self._lock:
            job = self._get_job_unsafe(job_id)
            if job:
                job.status = JobStatus.ERROR
                job.error_message = error
                job.completed_at = time.strftime("%Y-%m-%d %H:%M:%S")
                self._current_job_id = None
                self._save()
                job_copy = job.copy()

        # Invoke callback outside lock
        if job_copy and self._on_job_error:
            self._invoke_callback_safe(self._on_job_error, job_copy, error)

        return job_copy

    def cancel_job(self, job_id: int) -> RenderJob | None:
        """
        Cancel a job.

        Thread-safe: Returns a copy of the cancelled job.
        """
        with self._lock:
            job = self._get_job_unsafe(job_id)
            if job and job.status in (JobStatus.PENDING, JobStatus.CONFIGURING, JobStatus.QUEUED):
                job.status = JobStatus.CANCELLED
                self._save()
                return job.copy()
        return None

    def remove_job(self, job_id: int) -> bool:
        """
        Remove a job from queue.

        Thread-safe: Cannot remove running jobs.
        """
        with self._lock:
            job = self._get_job_unsafe(job_id)
            if job and job.status != JobStatus.RUNNING:
                self._jobs.remove(job)
                self._save()
                return True
        return False

    def clear_completed(self) -> int:
        """
        Remove all completed/error/cancelled jobs.

        Thread-safe: Returns count of cleared jobs.
        """
        with self._lock:
            initial = len(self._jobs)
            self._jobs = [
                j
                for j in self._jobs
                if j.status not in (JobStatus.COMPLETE, JobStatus.ERROR, JobStatus.CANCELLED)
            ]
            self._save()
            return initial - len(self._jobs)

    def get_summary(self) -> dict[str, int]:
        """
        Get queue summary.

        Thread-safe: Returns snapshot of current state.
        """
        with self._lock:
            summary = {status.value: 0 for status in JobStatus}
            for job in self._jobs:
                summary[job.status.value] += 1
            return summary

    def should_render_job(self, job: RenderJob) -> bool:
        """
        Check if job should be rendered (duplicate check).

        Args:
            job: Render job to check

        Returns:
            True if should render, False if duplicate (skip)
        """
        if not job.skip_duplicate or job.force_render:
            return True

        if job.mode == "single" and job.single_video_path:
            return self.hash_ledger.check_and_register(
                single_path=job.single_video_path, force=False
            )
        elif job.intro_path and job.loop_path:
            return self.hash_ledger.check_and_register(
                intro_path=job.intro_path, loop_path=job.loop_path, force=False
            )

        return True

    def register_render_complete(self, job: RenderJob) -> bool:
        """
        Register a completed render in the hash ledger.

        Args:
            job: Completed render job

        Returns:
            True if registered successfully
        """
        if job.mode == "single" and job.single_video_path:
            return self.hash_ledger.register(
                single_path=job.single_video_path, output_path=job.output_path
            )
        elif job.intro_path and job.loop_path:
            return self.hash_ledger.register(
                intro_path=job.intro_path, loop_path=job.loop_path, output_path=job.output_path
            )

        return False

    def set_callbacks(
        self,
        on_complete: Callable[[RenderJob], None] | None = None,
        on_error: Callable[[RenderJob, str], None] | None = None,
        on_progress: Callable[[RenderJob, float], None] | None = None,
    ) -> None:
        """
        Set event callbacks.

        Callbacks are invoked in separate threads to avoid deadlocks.
        """
        with self._lock:
            self._on_job_complete = on_complete
            self._on_job_error = on_error
            self._on_progress = on_progress

    def cleanup_temp_files(self, min_age_hours: float = 1.0) -> dict:
        """
        Clean up temporary files from render operations.

        Args:
            min_age_hours: Minimum file age in hours before deletion

        Returns:
            Dict with cleanup results
        """
        from .ffmpeg import cleanup_temp_files as do_cleanup

        tmp_dir = self._queue_file.parent

        should_warn, should_auto = check_disk_space(tmp_dir)

        if should_auto:
            min_age_hours = 0.5

        result = do_cleanup(tmp_dir=tmp_dir, min_age_hours=min_age_hours)

        return {
            "deleted": len(result.deleted_files),
            "size_mb": result.deleted_size_mb,
            "errors": result.errors,
        }

    @property
    def queue_file(self) -> Path:
        """Get queue file path (thread-safe)."""
        return self._queue_file

    @property
    def current_job_id(self) -> int | None:
        """Get current job ID (thread-safe)."""
        with self._lock:
            return self._current_job_id

    @property
    def job_count(self) -> int:
        """Get total job count (thread-safe)."""
        with self._lock:
            return len(self._jobs)


def parse_duration(dur_str: str) -> int:
    """Parse duration string to seconds."""
    if dur_str == "random_8_10":
        import random

        return random.randint(28800, 36000)

    try:
        parts = dur_str.strip().split(":")
        if len(parts) == 3:
            h, m, s = map(int, parts)
            return h * 3600 + m * 60 + s
        elif len(parts) == 2:
            m, s = map(int, parts)
            return m * 60 + s
        else:
            # Single number - treat as seconds, not hours
            return int(parts[0])
    except Exception:
        return 0


@dataclass(frozen=True)
class BatchPair:
    """
    Represents a detected intro/loop pair.

    Immutable for thread-safety.
    """

    name: str
    intro: Path
    loop: Path

    @property
    def is_valid(self) -> bool:
        return self.intro.exists() and self.loop.exists()


class SmartBatchDetector:
    """
    Detects matching intro/loop pairs in a directory.

    Thread-safe: Scan operations are independent and stateless.
    """

    def __init__(self, directory: Path = None):
        self.directory = directory or Path.cwd()

    def scan(self) -> list[BatchPair]:
        """
        Scan directory for matching pairs using regex.

        Thread-safe: Returns immutable pairs.

        Matches:
        Suffix patterns (existing):
        - {name}_intro.mp4 / {name}_loop.mp4
        - {name}intro.mp4 / {name}loop.mp4
        - Intro variants: _intro, -intro, intro (case insensitive)
        - Loop variants: _loop, -loop, loop (case insensitive)

        Prefix patterns (new):
        - intro_{name}.mp4 / loop_{name}.mp4
        - intro-{name}.mp4 / loop-{name}.mp4
        - intro.mp4 / loop.mp4 (treated as "Video")
        """
        pairs: list[BatchPair] = []
        import re

        # Get all video files
        videos = []
        from config import VIDEO_EXTENSIONS

        for ext in VIDEO_EXTENSIONS:
            videos.extend(list(self.directory.glob(f"*{ext}")))

        # Helper to find base name (supports both suffix and prefix patterns)
        def extract_base(name: str, type_key: str) -> str | None:
            """
            Extract base name by removing type suffix OR prefix.

            Supported patterns:
            - Suffix: {name}_intro, {name}-intro, {name}intro
            - Prefix: intro_{name}, loop-{name}
            - Standalone: intro, loop (returns "Video")
            - Wrapped: _intro_, -loop- (returns "Video")
            """
            # Try suffix patterns first (most common)
            suffix_match = re.search(f"([_-]?{type_key})$", name, re.IGNORECASE)
            if suffix_match:
                return name[: suffix_match.start()]

            # Try prefix patterns (intro_{name}, loop-{name})
            prefix_match = re.search(f"^{type_key}[_-]?(.*)$", name, re.IGNORECASE)
            if prefix_match:
                return prefix_match.group(1) or "Video"

            # Try wrapped patterns (_intro_, -loop-)
            wrapped_match = re.search(f"[_-]?{type_key}[_-]?(.*)", name, re.IGNORECASE)
            if wrapped_match:
                base = wrapped_match.group(1)
                # Only return if there's something after the type_key
                if base and base.strip("_-"):
                    return base.strip("_-")

            return None

        # Find all intros
        intro_candidates = {}  # base_name -> path
        for v in videos:
            base = extract_base(v.stem, "intro")
            if base is not None:
                intro_candidates[base] = v

        # Find matching loops
        for v in videos:
            base = extract_base(v.stem, "loop")
            if base is not None:
                # Direct match
                if base in intro_candidates:
                    intro = intro_candidates[base]
                    # Create immutable pair
                    display_name = base.strip(" _-") or "Video"
                    pairs.append(BatchPair(display_name, intro, v))

        # Sort by name
        return sorted(pairs, key=lambda x: x.name)

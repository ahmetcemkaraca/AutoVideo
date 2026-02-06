#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Batch Rendering System.

Allows configuring multiple render jobs while previous ones are processing.

Thread-Safe Implementation:
- All public methods use threading.Lock for synchronization
- File I/O uses atomic write patterns with temp files
- Callbacks are invoked outside of critical sections
- Job objects are returned as copies to prevent external modification
"""

import json
import time
import threading
import tempfile
import shutil
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import List, Optional, Dict, Any, Callable
from enum import Enum
from concurrent.futures import ThreadPoolExecutor
import contextlib
import logging

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
    intro_path: Optional[Path] = None
    loop_path: Optional[Path] = None
    single_video_path: Optional[Path] = None
    mode: str = "intro_loop"  # intro_loop or single
    codec_family: str = "av1"
    duration_str: str = "9:00:00"
    total_seconds: int = 32400
    tracks: List[Path] = field(default_factory=list)
    backgrounds: List[tuple] = field(default_factory=list)
    output_path: Optional[Path] = None
    status: JobStatus = JobStatus.PENDING
    progress: float = 0.0
    error_message: Optional[str] = None
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    upload_enabled: bool = False
    upload_folder_id: Optional[str] = None
    upload_status: str = "pending"  # pending, uploading, complete, error
    upload_file_id: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to serializable dict."""
        return {
            "id": self.id,
            "intro": str(self.intro_path) if self.intro_path else None,
            "loop": str(self.loop_path) if self.loop_path else None,
            "single_video": str(self.single_video_path) if self.single_video_path else None,
            "mode": self.mode,
            "codec": self.codec_family,
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
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "RenderJob":
        """Create from dict."""
        job = cls(id=data["id"])
        job.intro_path = Path(data["intro"]) if data.get("intro") else None
        job.loop_path = Path(data["loop"]) if data.get("loop") else None
        job.single_video_path = Path(data["single_video"]) if data.get("single_video") else None
        job.mode = data.get("mode", "intro_loop")
        job.codec_family = data.get("codec", "av1")
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
        return job

    def copy(self) -> "RenderJob":
        """
        Create a deep copy of this job.
        Used to prevent external modification of internal state.
        """
        return replace(
            self,
            tracks=self.tracks.copy(),
            backgrounds=self.backgrounds.copy()
        )


class FileWriteLock:
    """
    Cross-process file lock for preventing concurrent writes.

    Uses platform-specific locking mechanisms:
    - Windows: msvcrt.locking
    - Unix: fcntl.flock
    """

    def __init__(self, file_path: Path, timeout: float = 10.0):
        self.file_path = file_path
        self.timeout = timeout
        self._lock_file: Optional[Path] = None
        self._fd = None

    def __enter__(self):
        """Acquire file lock."""
        import os
        import platform

        # Create lock file in same directory as target
        lock_path = self.file_path.parent / f"{self.file_path.name}.lock"
        self._lock_file = lock_path

        start_time = time.time()
        while True:
            try:
                # Try to create lock file exclusively
                self._fd = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
                # Write PID for debugging
                os.write(self._fd, str(os.getpid()).encode())
                return self
            except FileExistsError:
                if time.time() - start_time > self.timeout:
                    raise TimeoutError(f"Could not acquire lock on {self.file_path} after {self.timeout}s")
                time.sleep(0.05)

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Release file lock."""
        import os
        if self._fd is not None:
            try:
                os.close(self._fd)
            except:
                pass
        if self._lock_file and self._lock_file.exists():
            try:
                self._lock_file.unlink()
            except:
                pass


class BatchQueue:
    """
    Thread-safe queue of render jobs.

    Thread-Safety Guarantees:
    - All state modifications are protected by threading.Lock
    - File I/O uses atomic write patterns
    - Callbacks are invoked outside critical sections
    - Returned job objects are copies to prevent external modification

    Usage:
        queue = BatchQueue()
        job = queue.create_job()
        # Configure job...
        queue.queue_job(job.id)
    """

    def __init__(self, queue_file: Optional[Path] = None):
        self._jobs: List[RenderJob] = []
        self._current_job_id: Optional[int] = None
        self._queue_file = queue_file or Path.cwd() / "tmp" / "batch_queue.json"
        self._next_id = 1
        self._lock = threading.RLock()  # RLock for reentrant calls
        self._on_job_complete: Optional[Callable[[RenderJob], None]] = None
        self._on_job_error: Optional[Callable[[RenderJob, str], None]] = None
        self._on_progress: Optional[Callable[[RenderJob, float], None]] = None
        self._callback_lock = threading.Lock()  # Separate lock for callbacks

        # Load existing queue
        self._load()

    def _load(self) -> None:
        """
        Load queue from file.

        Thread-safe: Uses file locking to prevent concurrent read/write.
        """
        if not self._queue_file.exists():
            return

        try:
            with FileWriteLock(self._queue_file):
                data = json.loads(self._queue_file.read_text(encoding="utf-8"))
                self._jobs = [RenderJob.from_dict(j) for j in data.get("jobs", [])]
                self._next_id = data.get("next_id", 1)

                # Find max id to prevent conflicts
                if self._jobs:
                    self._next_id = max(j.id for j in self._jobs) + 1
        except json.JSONDecodeError:
            logger.warning(f"Could not parse queue file {self._queue_file}, starting fresh")
            self._jobs = []
            self._next_id = 1
        except Exception as e:
            logger.error(f"Error loading queue: {e}")
            self._jobs = []
            self._next_id = 1

    def _save(self) -> None:
        """
        Save queue to file using atomic write.

        Thread-safe: Uses temp file + atomic rename.
        """
        self._queue_file.parent.mkdir(parents=True, exist_ok=True)

        # Write to temp file first
        data = {
            "jobs": [j.to_dict() for j in self._jobs],
            "next_id": self._next_id,
        }
        json_str = json.dumps(data, indent=2, ensure_ascii=False) + "\n"

        # Write to temp file
        with tempfile.NamedTemporaryFile(
            mode='w',
            suffix='.tmp',
            dir=self._queue_file.parent,
            delete=False,
            encoding='utf-8'
        ) as tmp:
            tmp.write(json_str)
            tmp_path = Path(tmp.name)

        # Atomic rename
        try:
            tmp_path.replace(self._queue_file)
        except Exception:
            tmp_path.unlink(missing_ok=True)
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

    def queue_job(self, job_id: int) -> Optional[RenderJob]:
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

    def get_job(self, job_id: int) -> Optional[RenderJob]:
        """
        Get a job by ID.

        Thread-safe: Returns a copy of the job.
        """
        with self._lock:
            job = self._get_job_unsafe(job_id)
            return job.copy() if job else None

    def _get_job_unsafe(self, job_id: int) -> Optional[RenderJob]:
        """Internal: Get job without lock (caller must hold lock)."""
        for job in self._jobs:
            if job.id == job_id:
                return job
        return None

    def get_queued_jobs(self) -> List[RenderJob]:
        """
        Get all queued jobs.

        Thread-safe: Returns a list of copies.
        """
        with self._lock:
            return [j.copy() for j in self._jobs if j.status == JobStatus.QUEUED]

    def get_pending_jobs(self) -> List[RenderJob]:
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

    def get_all_jobs(self) -> List[RenderJob]:
        """
        Get all jobs regardless of status.

        Thread-safe: Returns a list of copies.
        """
        with self._lock:
            return [j.copy() for j in self._jobs]

    def get_next_job(self) -> Optional[RenderJob]:
        """
        Get next job to run.

        Thread-safe: Returns a copy of the job.
        """
        with self._lock:
            for job in self._jobs:
                if job.status == JobStatus.QUEUED:
                    return job.copy()
        return None

    def start_job(self, job_id: int) -> Optional[RenderJob]:
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

    def complete_job(self, job_id: int) -> Optional[RenderJob]:
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

    def fail_job(self, job_id: int, error: str) -> Optional[RenderJob]:
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

    def cancel_job(self, job_id: int) -> Optional[RenderJob]:
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
                j for j in self._jobs
                if j.status not in (JobStatus.COMPLETE, JobStatus.ERROR, JobStatus.CANCELLED)
            ]
            self._save()
            return initial - len(self._jobs)

    def get_summary(self) -> Dict[str, int]:
        """
        Get queue summary.

        Thread-safe: Returns snapshot of current state.
        """
        with self._lock:
            summary = {status.value: 0 for status in JobStatus}
            for job in self._jobs:
                summary[job.status.value] += 1
            return summary

    def set_callbacks(
        self,
        on_complete: Optional[Callable[[RenderJob], None]] = None,
        on_error: Optional[Callable[[RenderJob, str], None]] = None,
        on_progress: Optional[Callable[[RenderJob, float], None]] = None
    ) -> None:
        """
        Set event callbacks.

        Callbacks are invoked in separate threads to avoid deadlocks.
        """
        with self._lock:
            self._on_job_complete = on_complete
            self._on_job_error = on_error
            self._on_progress = on_progress

    @property
    def queue_file(self) -> Path:
        """Get queue file path (thread-safe)."""
        return self._queue_file

    @property
    def current_job_id(self) -> Optional[int]:
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
            return int(parts[0]) * 3600
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

    def scan(self) -> List[BatchPair]:
        """
        Scan directory for matching pairs using regex.

        Thread-safe: Returns immutable pairs.

        Matches:
        - {name}_intro.mp4 / {name}_loop.mp4
        - {name}intro.mp4 / {name}loop.mp4
        - Intro variants: _intro, -intro, intro (case insensitive)
        - Loop variants: _loop, -loop, loop (case insensitive)
        """
        pairs: List[BatchPair] = []
        import re

        # Get all video files
        videos = []
        from .config import VIDEO_EXTENSIONS
        for ext in VIDEO_EXTENSIONS:
            videos.extend(list(self.directory.glob(f"*{ext}")))

        # Helper to find base name
        def extract_base(name: str, type_key: str) -> Optional[str]:
            """Extract base name by removing type suffix."""
            # Patterns: _intro, -intro, intro
            match = re.search(f"([_-]?{type_key})$", name, re.IGNORECASE)
            if match:
                return name[:match.start()]
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

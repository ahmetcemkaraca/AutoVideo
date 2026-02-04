#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Batch Rendering System.

Allows configuring multiple render jobs while previous ones are processing.
"""

import json
import time
import threading
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import List, Optional, Dict, Any, Callable
from enum import Enum
from queue import Queue


class JobStatus(Enum):
    """Render job status."""
    PENDING = "pending"
    CONFIGURING = "configuring"
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETE = "complete"
    ERROR = "error"
    CANCELLED = "cancelled"


@dataclass
class RenderJob:
    """Represents a single render job."""
    id: int
    intro_path: Optional[Path] = None
    loop_path: Optional[Path] = None
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


class BatchQueue:
    """
    Manages a queue of render jobs.
    
    Jobs can be configured while others are running.
    """
    
    def __init__(self, queue_file: Optional[Path] = None):
        self.jobs: List[RenderJob] = []
        self.current_job_id: Optional[int] = None
        self.queue_file = queue_file or Path.cwd() / "tmp" / "batch_queue.json"
        self.next_id = 1
        self._lock = threading.Lock()
        self._on_job_complete: Optional[Callable[[RenderJob], None]] = None
        self._on_job_error: Optional[Callable[[RenderJob, str], None]] = None
        self._on_progress: Optional[Callable[[RenderJob, float], None]] = None
        
        # Load existing queue
        self._load()
    
    def _load(self) -> None:
        """Load queue from file."""
        if self.queue_file.exists():
            try:
                data = json.loads(self.queue_file.read_text(encoding="utf-8"))
                self.jobs = [RenderJob.from_dict(j) for j in data.get("jobs", [])]
                self.next_id = data.get("next_id", 1)
                
                # Find max id
                if self.jobs:
                    self.next_id = max(j.id for j in self.jobs) + 1
            except Exception:
                self.jobs = []
    
    def _save(self) -> None:
        """Save queue to file."""
        self.queue_file.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "jobs": [j.to_dict() for j in self.jobs],
            "next_id": self.next_id,
        }
        self.queue_file.write_text(
            json.dumps(data, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8"
        )
    
    def create_job(self) -> RenderJob:
        """Create a new pending job."""
        with self._lock:
            job = RenderJob(id=self.next_id)
            job.status = JobStatus.CONFIGURING
            self.next_id += 1
            self.jobs.append(job)
            self._save()
            return job
    
    def queue_job(self, job_id: int) -> Optional[RenderJob]:
        """Mark a job as ready to run."""
        with self._lock:
            job = self.get_job(job_id)
            if job and job.status == JobStatus.CONFIGURING:
                job.status = JobStatus.QUEUED
                self._save()
                return job
        return None
    
    def get_job(self, job_id: int) -> Optional[RenderJob]:
        """Get a job by ID."""
        for job in self.jobs:
            if job.id == job_id:
                return job
        return None
    
    def get_queued_jobs(self) -> List[RenderJob]:
        """Get all queued jobs."""
        return [j for j in self.jobs if j.status == JobStatus.QUEUED]
    
    def get_pending_jobs(self) -> List[RenderJob]:
        """Get all pending/configuring jobs."""
        return [j for j in self.jobs if j.status in (JobStatus.PENDING, JobStatus.CONFIGURING)]
    
    def get_next_job(self) -> Optional[RenderJob]:
        """Get next job to run."""
        with self._lock:
            for job in self.jobs:
                if job.status == JobStatus.QUEUED:
                    return job
        return None
    
    def start_job(self, job_id: int) -> Optional[RenderJob]:
        """Mark a job as running."""
        with self._lock:
            job = self.get_job(job_id)
            if job:
                job.status = JobStatus.RUNNING
                job.started_at = time.strftime("%Y-%m-%d %H:%M:%S")
                job.progress = 0.0
                self.current_job_id = job_id
                self._save()
                return job
        return None
    
    def update_progress(self, job_id: int, progress: float) -> None:
        """Update job progress."""
        with self._lock:
            job = self.get_job(job_id)
            if job:
                job.progress = progress
                if self._on_progress:
                    self._on_progress(job, progress)
    
    def complete_job(self, job_id: int) -> Optional[RenderJob]:
        """Mark a job as complete."""
        with self._lock:
            job = self.get_job(job_id)
            if job:
                job.status = JobStatus.COMPLETE
                job.progress = 100.0
                job.completed_at = time.strftime("%Y-%m-%d %H:%M:%S")
                self.current_job_id = None
                self._save()
                if self._on_job_complete:
                    self._on_job_complete(job)
                return job
        return None
    
    def fail_job(self, job_id: int, error: str) -> Optional[RenderJob]:
        """Mark a job as failed."""
        with self._lock:
            job = self.get_job(job_id)
            if job:
                job.status = JobStatus.ERROR
                job.error_message = error
                job.completed_at = time.strftime("%Y-%m-%d %H:%M:%S")
                self.current_job_id = None
                self._save()
                if self._on_job_error:
                    self._on_job_error(job, error)
                return job
        return None
    
    def cancel_job(self, job_id: int) -> Optional[RenderJob]:
        """Cancel a job."""
        with self._lock:
            job = self.get_job(job_id)
            if job and job.status in (JobStatus.PENDING, JobStatus.CONFIGURING, JobStatus.QUEUED):
                job.status = JobStatus.CANCELLED
                self._save()
                return job
        return None
    
    def remove_job(self, job_id: int) -> bool:
        """Remove a job from queue."""
        with self._lock:
            job = self.get_job(job_id)
            if job and job.status not in (JobStatus.RUNNING,):
                self.jobs.remove(job)
                self._save()
                return True
        return False
    
    def clear_completed(self) -> int:
        """Remove all completed/error/cancelled jobs."""
        with self._lock:
            initial = len(self.jobs)
            self.jobs = [
                j for j in self.jobs 
                if j.status not in (JobStatus.COMPLETE, JobStatus.ERROR, JobStatus.CANCELLED)
            ]
            self._save()
            return initial - len(self.jobs)
    
    def get_summary(self) -> Dict[str, int]:
        """Get queue summary."""
        summary = {status.value: 0 for status in JobStatus}
        for job in self.jobs:
            summary[job.status.value] += 1
        return summary
    
    def set_callbacks(
        self,
        on_complete: Optional[Callable[[RenderJob], None]] = None,
        on_error: Optional[Callable[[RenderJob, str], None]] = None,
        on_progress: Optional[Callable[[RenderJob, float], None]] = None
    ) -> None:
        """Set event callbacks."""
        self._on_job_complete = on_complete
        self._on_job_error = on_error
        self._on_progress = on_progress


def parse_duration(dur_str: str) -> int:
    """Parse duration string to seconds."""
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

@dataclass
class BatchPair:
    """Represents a detected intro/loop pair."""
    name: str
    intro: Path
    loop: Path
    
    @property
    def is_valid(self) -> bool:
        return self.intro.exists() and self.loop.exists()


class SmartBatchDetector:
    """Detects matching intro/loop pairs in a directory."""
    
    def __init__(self, directory: Path = None):
        self.directory = directory or Path.cwd()
        
    def scan(self) -> List[BatchPair]:
        """
        Scan directory for matching pairs.
        Convention: {name}_intro.mp4 and {name}_loop.mp4
        """
        pairs: List[BatchPair] = []
        
        # Find all intros
        intros = list(self.directory.glob("*_intro.mp4"))
        
        for intro in intros:
            # Extract common name
            # pattern: name_intro.mp4 -> name
            name = intro.stem.replace("_intro", "")
            
            # Check for corresponding loop
            loop_name = f"{name}_loop.mp4"
            loop = intro.parent / loop_name
            
            if loop.exists():
                pairs.append(BatchPair(name, intro, loop))
                
        return sorted(pairs, key=lambda x: x.name)

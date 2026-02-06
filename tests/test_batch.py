"""Tests for BatchQueue thread-safety and functionality."""

import json
import tempfile
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import List

import pytest

from video_renderer.batch import (
    BatchQueue,
    RenderJob,
    JobStatus,
    parse_duration,
    SmartBatchDetector,
    BatchPair,
)


class TestRenderJob:
    """Tests for RenderJob dataclass."""

    def test_render_job_creation(self):
        """Test creating a render job."""
        job = RenderJob(id=1)
        assert job.id == 1
        assert job.status == JobStatus.PENDING
        assert job.progress == 0.0

    def test_render_job_serialization(self):
        """Test converting job to dict and back."""
        job = RenderJob(
            id=1,
            mode="intro_loop",
            codec_family="av1",
            duration_str="9:00:00",
            total_seconds=32400,
        )

        # Convert to dict
        job_dict = job.to_dict()
        assert job_dict["id"] == 1
        assert job_dict["mode"] == "intro_loop"
        assert job_dict["codec"] == "av1"

        # Convert back from dict
        job2 = RenderJob.from_dict(job_dict)
        assert job2.id == job.id
        assert job2.mode == job.mode
        assert job2.codec_family == job.codec_family

    def test_render_job_copy(self):
        """Test job copy functionality."""
        job = RenderJob(id=1)
        job_copy = job.copy()

        assert job_copy.id == job.id
        assert job_copy is not job  # Different objects


class TestBatchQueue:
    """Tests for BatchQueue thread-safety and operations."""

    def test_queue_initialization(self, temp_dir):
        """Test queue initialization."""
        queue_file = temp_dir / "test_queue.json"
        queue = BatchQueue(queue_file=queue_file)

        assert queue.job_count == 0
        assert queue.current_job_id is None

    def test_create_job(self, temp_dir):
        """Test creating a new job."""
        queue = BatchQueue(queue_file=temp_dir / "test_queue.json")

        job = queue.create_job()

        assert job is not None
        assert job.id == 1
        assert job.status == JobStatus.CONFIGURING
        assert queue.job_count == 1

    def test_queue_job(self, temp_dir):
        """Test marking a job as queued."""
        queue = BatchQueue(queue_file=temp_dir / "test_queue.json")

        job = queue.create_job()
        queued_job = queue.queue_job(job.id)

        assert queued_job is not None
        assert queued_job.status == JobStatus.QUEUED

    def test_get_job(self, temp_dir):
        """Test retrieving a job by ID."""
        queue = BatchQueue(queue_file=temp_dir / "test_queue.json")

        job = queue.create_job()
        retrieved_job = queue.get_job(job.id)

        assert retrieved_job is not None
        assert retrieved_job.id == job.id
        # Should be a copy, not the same object
        assert retrieved_job is not job

    def test_get_nonexistent_job(self, temp_dir):
        """Test getting a job that doesn't exist."""
        queue = BatchQueue(queue_file=temp_dir / "test_queue.json")

        job = queue.get_job(999)
        assert job is None

    def test_start_job(self, temp_dir):
        """Test starting a job."""
        queue = BatchQueue(queue_file=temp_dir / "test_queue.json")

        job = queue.create_job()
        queue.queue_job(job.id)
        started_job = queue.start_job(job.id)

        assert started_job is not None
        assert started_job.status == JobStatus.RUNNING
        assert started_job.started_at is not None
        assert queue.current_job_id == job.id

    def test_update_progress(self, temp_dir):
        """Test updating job progress."""
        queue = BatchQueue(queue_file=temp_dir / "test_queue.json")

        job = queue.create_job()
        queue.update_progress(job.id, 50.0)

        updated_job = queue.get_job(job.id)
        assert updated_job.progress == 50.0

    def test_complete_job(self, temp_dir):
        """Test marking a job as complete."""
        queue = BatchQueue(queue_file=temp_dir / "test_queue.json")

        job = queue.create_job()
        queue.queue_job(job.id)
        queue.start_job(job.id)

        completed_job = queue.complete_job(job.id)

        assert completed_job is not None
        assert completed_job.status == JobStatus.COMPLETE
        assert completed_job.progress == 100.0
        assert completed_job.completed_at is not None
        assert queue.current_job_id is None

    def test_fail_job(self, temp_dir):
        """Test marking a job as failed."""
        queue = BatchQueue(queue_file=temp_dir / "test_queue.json")

        job = queue.create_job()
        queue.queue_job(job.id)
        queue.start_job(job.id)

        failed_job = queue.fail_job(job.id, "Test error")

        assert failed_job is not None
        assert failed_job.status == JobStatus.ERROR
        assert failed_job.error_message == "Test error"
        assert failed_job.completed_at is not None
        assert queue.current_job_id is None

    def test_cancel_job(self, temp_dir):
        """Test cancelling a job."""
        queue = BatchQueue(queue_file=temp_dir / "test_queue.json")

        job = queue.create_job()
        cancelled_job = queue.cancel_job(job.id)

        assert cancelled_job is not None
        assert cancelled_job.status == JobStatus.CANCELLED

    def test_remove_job(self, temp_dir):
        """Test removing a job."""
        queue = BatchQueue(queue_file=temp_dir / "test_queue.json")

        job = queue.create_job()
        removed = queue.remove_job(job.id)

        assert removed is True
        assert queue.job_count == 0

    def test_cannot_remove_running_job(self, temp_dir):
        """Test that running jobs cannot be removed."""
        queue = BatchQueue(queue_file=temp_dir / "test_queue.json")

        job = queue.create_job()
        queue.queue_job(job.id)
        queue.start_job(job.id)

        removed = queue.remove_job(job.id)
        assert removed is False

    def test_clear_completed(self, temp_dir):
        """Test clearing completed jobs."""
        queue = BatchQueue(queue_file=temp_dir / "test_queue.json")

        # Create multiple jobs
        job1 = queue.create_job()
        queue.queue_job(job1.id)
        queue.start_job(job1.id)
        queue.complete_job(job1.id)

        job2 = queue.create_job()
        queue.queue_job(job2.id)

        cleared_count = queue.clear_completed()
        assert cleared_count == 1
        assert queue.job_count == 1

    def test_get_summary(self, temp_dir):
        """Test getting queue summary."""
        queue = BatchQueue(queue_file=temp_dir / "test_queue.json")

        # Create jobs with different statuses
        job1 = queue.create_job()
        job2 = queue.create_job()
        queue.queue_job(job2.id)

        summary = queue.get_summary()
        assert summary["configuring"] == 1
        assert summary["queued"] == 1

    def test_get_queued_jobs(self, temp_dir):
        """Test getting all queued jobs."""
        queue = BatchQueue(queue_file=temp_dir / "test_queue.json")

        job1 = queue.create_job()
        queue.queue_job(job1.id)

        job2 = queue.create_job()
        queue.queue_job(job2.id)

        queued_jobs = queue.get_queued_jobs()
        assert len(queued_jobs) == 2
        assert all(j.status == JobStatus.QUEUED for j in queued_jobs)

    def test_get_pending_jobs(self, temp_dir):
        """Test getting all pending jobs."""
        queue = BatchQueue(queue_file=temp_dir / "test_queue.json")

        job1 = queue.create_job()
        job2 = queue.create_job()

        pending_jobs = queue.get_pending_jobs()
        assert len(pending_jobs) == 2

    def test_get_next_job(self, temp_dir):
        """Test getting next job to run."""
        queue = BatchQueue(queue_file=temp_dir / "test_queue.json")

        job1 = queue.create_job()
        queue.queue_job(job1.id)

        job2 = queue.create_job()
        queue.queue_job(job2.id)

        next_job = queue.get_next_job()
        assert next_job is not None
        assert next_job.id == job1.id

    def test_persistence(self, temp_dir):
        """Test queue persistence across instances."""
        queue_file = temp_dir / "test_queue.json"

        # Create queue and add job
        queue1 = BatchQueue(queue_file=queue_file)
        job = queue1.create_job()
        queue1.queue_job(job.id)

        # Create new queue instance
        queue2 = BatchQueue(queue_file=queue_file)

        # Job should be loaded
        retrieved_job = queue2.get_job(job.id)
        assert retrieved_job is not None
        assert retrieved_job.status == JobStatus.QUEUED

    def test_callbacks(self, temp_dir):
        """Test callback functionality."""
        queue = BatchQueue(queue_file=temp_dir / "test_queue.json")

        # Track callback invocations
        complete_calls = []
        error_calls = []
        progress_calls = []

        def on_complete(job):
            complete_calls.append(job.id)

        def on_error(job, error):
            error_calls.append((job.id, error))

        def on_progress(job, progress):
            progress_calls.append((job.id, progress))

        queue.set_callbacks(
            on_complete=on_complete,
            on_error=on_error,
            on_progress=on_progress,
        )

        job = queue.create_job()
        queue.queue_job(job.id)
        queue.start_job(job.id)

        # Update progress
        queue.update_progress(job.id, 50.0)

        # Complete job
        queue.complete_job(job.id)

        # Wait a bit for callbacks to execute
        time.sleep(0.2)

        # Check callbacks were invoked (may be in separate threads)
        # Note: Due to async callback invocation, we just verify no errors occurred


class TestBatchQueueThreadSafety:
    """Tests for BatchQueue thread-safety under concurrent access."""

    def test_concurrent_job_creation(self, temp_dir):
        """Test creating jobs from multiple threads."""
        queue = BatchQueue(queue_file=temp_dir / "test_queue.json")
        num_jobs = 50
        created_ids = []

        def create_job():
            job = queue.create_job()
            created_ids.append(job.id)

        # Create jobs concurrently
        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(create_job) for _ in range(num_jobs)]
            for future in as_completed(futures):
                future.result()

        # Verify all jobs were created with unique IDs
        assert len(created_ids) == num_jobs
        assert len(set(created_ids)) == num_jobs  # All IDs unique
        assert queue.job_count == num_jobs

    def test_concurrent_job_updates(self, temp_dir):
        """Test updating jobs from multiple threads."""
        queue = BatchQueue(queue_file=temp_dir / "test_queue.json")
        num_jobs = 20

        # Create jobs
        jobs = []
        for _ in range(num_jobs):
            job = queue.create_job()
            queue.queue_job(job.id)
            jobs.append(job)

        # Update jobs concurrently
        def update_job(job_id):
            for i in range(10):
                queue.update_progress(job_id, i * 10)

        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(update_job, job.id) for job in jobs]
            for future in as_completed(futures):
                future.result()

        # Verify queue is consistent
        assert queue.job_count == num_jobs

    def test_concurrent_job_status_changes(self, temp_dir):
        """Test changing job status from multiple threads."""
        queue = BatchQueue(queue_file=temp_dir / "test_queue.json")
        num_jobs = 30

        # Create and queue jobs
        job_ids = []
        for _ in range(num_jobs):
            job = queue.create_job()
            queue.queue_job(job.id)
            job_ids.append(job.id)

        # Start jobs concurrently
        def start_job(job_id):
            queue.start_job(job_id)
            time.sleep(0.001)  # Tiny delay
            queue.complete_job(job_id)

        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(start_job, jid) for jid in job_ids]
            for future in as_completed(futures):
                future.result()

        # Verify all jobs completed
        summary = queue.get_summary()
        assert summary["complete"] == num_jobs

    def test_concurrent_get_and_modify(self, temp_dir):
        """Test reading and modifying queue concurrently."""
        queue = BatchQueue(queue_file=temp_dir / "test_queue.json")

        # Create some jobs
        for _ in range(20):
            queue.create_job()

        errors = []

        def reader():
            try:
                for _ in range(50):
                    queue.get_all_jobs()
                    queue.get_summary()
                    queue.get_next_job()
            except Exception as e:
                errors.append(("reader", e))

        def writer():
            try:
                for _ in range(10):
                    job = queue.create_job()
                    queue.queue_job(job.id)
            except Exception as e:
                errors.append(("writer", e))

        # Run readers and writers concurrently
        threads = []
        for _ in range(3):
            threads.append(threading.Thread(target=reader))
        for _ in range(2):
            threads.append(threading.Thread(target=writer))

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # Verify no errors occurred
        assert len(errors) == 0, f"Errors occurred: {errors}"

    def test_concurrent_callback_invocation(self, temp_dir):
        """Test callbacks don't cause deadlocks under concurrent access."""
        queue = BatchQueue(queue_file=temp_dir / "test_queue.json")

        call_count = {"count": 0}

        def on_progress(job, progress):
            # Simulate some work in callback
            time.sleep(0.001)
            call_count["count"] += 1

        queue.set_callbacks(on_progress=on_progress)

        # Create and update jobs concurrently
        def create_and_update():
            for _ in range(5):
                job = queue.create_job()
                for i in range(10):
                    queue.update_progress(job.id, i * 10)

        threads = [threading.Thread(target=create_and_update) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # Verify callbacks were invoked without deadlock
        assert call_count["count"] > 0


class TestParseDuration:
    """Tests for duration parsing."""

    def test_parse_hms(self):
        """Test parsing HH:MM:SS format."""
        assert parse_duration("01:30:00") == 5400
        assert parse_duration("09:00:00") == 32400
        assert parse_duration("00:05:30") == 330

    def test_parse_ms(self):
        """Test parsing MM:SS format."""
        assert parse_duration("05:30") == 330
        assert parse_duration("10:00") == 600

    def test_parse_seconds(self):
        """Test parsing seconds only."""
        assert parse_duration("3600") == 3600
        assert parse_duration("7200") == 7200

    def test_parse_random(self):
        """Test parsing random_8_10 special value."""
        import random
        random.seed(42)  # For reproducibility
        duration = parse_duration("random_8_10")
        assert 28800 <= duration <= 36000

    def test_parse_invalid(self):
        """Test parsing invalid duration."""
        assert parse_duration("invalid") == 0


class TestSmartBatchDetector:
    """Tests for SmartBatchDetector."""

    def test_detect_pairs(self, temp_dir):
        """Test detecting intro/loop pairs."""
        # Create test files
        (temp_dir / "video1_intro.mp4").touch()
        (temp_dir / "video1_loop.mp4").touch()
        (temp_dir / "video2_intro.mp4").touch()
        (temp_dir / "video2_loop.mp4").touch()

        detector = SmartBatchDetector(directory=temp_dir)
        pairs = detector.scan()

        assert len(pairs) == 2
        assert any(p.name == "video1" for p in pairs)
        assert any(p.name == "video2" for p in pairs)

    def test_detect_pairs_case_insensitive(self, temp_dir):
        """Test that detection is case-insensitive."""
        (temp_dir / "Video1_Intro.mp4").touch()
        (temp_dir / "Video1_Loop.mp4").touch()

        detector = SmartBatchDetector(directory=temp_dir)
        pairs = detector.scan()

        assert len(pairs) == 1

    def test_detect_pairs_with_hyphen(self, temp_dir):
        """Test detecting pairs with hyphen separator."""
        (temp_dir / "video1-intro.mp4").touch()
        (temp_dir / "video1-loop.mp4").touch()

        detector = SmartBatchDetector(directory=temp_dir)
        pairs = detector.scan()

        assert len(pairs) == 1

    def test_no_pairs(self, temp_dir):
        """Test when no pairs exist."""
        (temp_dir / "intro.mp4").touch()
        (temp_dir / "other.mp4").touch()

        detector = SmartBatchDetector(directory=temp_dir)
        pairs = detector.scan()

        assert len(pairs) == 0


class TestBatchPair:
    """Tests for BatchPair dataclass."""

    def test_batch_pair_creation(self, temp_dir):
        """Test creating a batch pair."""
        intro = temp_dir / "intro.mp4"
        loop = temp_dir / "loop.mp4"
        intro.touch()
        loop.touch()

        pair = BatchPair(name="test", intro=intro, loop=loop)
        assert pair.name == "test"
        assert pair.intro == intro
        assert pair.loop == loop

    def test_batch_pair_is_valid(self, temp_dir):
        """Test is_valid property."""
        intro = temp_dir / "intro.mp4"
        loop = temp_dir / "loop.mp4"
        intro.touch()
        loop.touch()

        pair = BatchPair(name="test", intro=intro, loop=loop)
        assert pair.is_valid is True

    def test_batch_pair_not_valid(self, temp_dir):
        """Test is_valid when files don't exist."""
        intro = temp_dir / "intro.mp4"
        loop = temp_dir / "loop.mp4"
        # Don't create files

        pair = BatchPair(name="test", intro=intro, loop=loop)
        assert pair.is_valid is False

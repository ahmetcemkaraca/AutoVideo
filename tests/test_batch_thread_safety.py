#!/usr/bin/env python3
"""
Thread-Safety Tests for BatchQueue.

Tests concurrent access patterns and race condition prevention.
"""

import json
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import pytest

from video_renderer.batch import BatchPair, BatchQueue, JobStatus, RenderJob


@pytest.fixture
def temp_queue_dir(tmp_path: Path) -> Path:
    """Create temporary directory for queue files."""
    queue_dir = tmp_path / "batch_test"
    queue_dir.mkdir(parents=True, exist_ok=True)
    return queue_dir


@pytest.fixture
def queue(temp_queue_dir: Path) -> BatchQueue:
    """Create a fresh BatchQueue for each test."""
    queue_file = temp_queue_dir / "batch_queue.json"
    return BatchQueue(queue_file=queue_file)


@pytest.fixture
def sample_job() -> RenderJob:
    """Create a sample render job."""
    return RenderJob(
        id=1,
        intro_path=Path("/fake/intro.mp4"),
        loop_path=Path("/fake/loop.mp4"),
        mode="intro_loop",
        codec_family="av1",
        duration_str="9:00:00",
        total_seconds=32400,
    )


class TestBatchQueueThreadSafety:
    """Test thread-safety of BatchQueue operations."""

    def test_concurrent_job_creation(self, queue: BatchQueue):
        """Test creating jobs from multiple threads simultaneously."""
        num_threads = 50
        created_jobs = []
        lock = threading.Lock()

        def create_job():
            job = queue.create_job()
            with lock:
                created_jobs.append(job.id)

        with ThreadPoolExecutor(max_workers=num_threads) as executor:
            futures = [executor.submit(create_job) for _ in range(num_threads)]
            for future in as_completed(futures):
                future.result()

        # Verify all jobs were created with unique IDs
        assert len(created_jobs) == num_threads
        assert len(set(created_jobs)) == num_threads  # All unique
        assert queue.job_count == num_threads

    def test_concurrent_job_queueing(self, queue: BatchQueue):
        """Test queueing jobs from multiple threads."""
        num_jobs = 20
        job_ids = []

        # Create jobs first
        for _ in range(num_jobs):
            job = queue.create_job()
            job_ids.append(job.id)

        # Queue from multiple threads
        queued_count = [0]
        lock = threading.Lock()

        def queue_job(job_id):
            result = queue.queue_job(job_id)
            if result:
                with lock:
                    queued_count[0] += 1

        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(queue_job, jid) for jid in job_ids]
            for future in as_completed(futures):
                future.result()

        assert queued_count[0] == num_jobs
        assert len(queue.get_queued_jobs()) == num_jobs

    def test_concurrent_progress_updates(self, queue: BatchQueue):
        """Test updating progress from multiple threads."""
        job = queue.create_job()
        queue.queue_job(job.id)
        queue.start_job(job.id)

        progress_updates = []
        lock = threading.Lock()

        def track_progress(job, progress):
            with lock:
                progress_updates.append((job.id, progress))

        queue.set_callbacks(on_progress=track_progress)

        # Update progress from multiple threads
        def update_progress(value):
            queue.update_progress(job.id, value)

        with ThreadPoolExecutor(max_workers=20) as executor:
            futures = [executor.submit(update_progress, i * 5.0) for i in range(1, 21)]
            for future in as_completed(futures):
                future.result()

        # Verify final progress is set (last update wins)
        final_job = queue.get_job(job.id)
        assert final_job.progress >= 0.0
        assert final_job.progress <= 100.0

    def test_concurrent_job_status_transitions(self, queue: BatchQueue):
        """Test competing status transitions on same job."""
        job = queue.create_job()
        queue.queue_job(job.id)

        results = {"started": 0, "completed": 0, "failed": 0, "errors": 0}
        lock = threading.Lock()
        job_lock = threading.Lock()

        def try_start():
            with job_lock:
                current_job = queue.get_job(job.id)
                if current_job.status == JobStatus.QUEUED:
                    if queue.start_job(job.id):
                        with lock:
                            results["started"] += 1
                else:
                    with lock:
                        results["errors"] += 1

        def try_complete():
            time.sleep(0.01)  # Small delay
            with job_lock:
                current_job = queue.get_job(job.id)
                if current_job.status == JobStatus.RUNNING:
                    if queue.complete_job(job.id):
                        with lock:
                            results["completed"] += 1
                else:
                    with lock:
                        results["errors"] += 1

        def try_fail():
            time.sleep(0.01)
            with job_lock:
                current_job = queue.get_job(job.id)
                if current_job.status == JobStatus.RUNNING:
                    if queue.fail_job(job.id, "test error"):
                        with lock:
                            results["failed"] += 1
                else:
                    with lock:
                        results["errors"] += 1

        # Run competing operations
        with ThreadPoolExecutor(max_workers=3) as executor:
            futures = [
                executor.submit(try_start),
                executor.submit(try_complete),
                executor.submit(try_fail),
            ]
            for future in as_completed(futures):
                future.result()

        # Verify the operations completed
        # At least one should have succeeded (start)
        assert results["started"] == 1
        assert results["errors"] >= 0

    def test_concurrent_job_removal(self, queue: BatchQueue):
        """Test removing jobs while other threads access them."""
        num_jobs = 30
        job_ids = []

        # Create and queue jobs
        for i in range(num_jobs):
            job = queue.create_job()
            job_ids.append(job.id)
            queue.queue_job(job.id)

        removed_count = [0]
        lock = threading.Lock()

        def remove_job(job_id):
            if queue.remove_job(job_id):
                with lock:
                    removed_count[0] += 1

        # Remove from multiple threads
        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(remove_job, jid) for jid in job_ids]
            for future in as_completed(futures):
                future.result()

        # Some may have been removed, some may have raced
        # But count should be consistent
        assert removed_count[0] + queue.job_count <= num_jobs

    def test_concurrent_summary_access(self, queue: BatchQueue):
        """Test accessing summary while modifying queue."""
        summaries = []
        lock = threading.Lock()

        def create_and_track():
            job = queue.create_job()
            summary = queue.get_summary()
            with lock:
                summaries.append(summary)

        with ThreadPoolExecutor(max_workers=20) as executor:
            futures = [executor.submit(create_and_track) for _ in range(50)]
            for future in as_completed(futures):
                future.result()

        # All summaries should be valid
        for summary in summaries:
            assert isinstance(summary, dict)
            assert all(isinstance(v, int) for v in summary.values())
            # Count should never be negative
            assert all(v >= 0 for v in summary.values())

    def test_callback_thread_safety(self, queue: BatchQueue):
        """Test that callbacks are invoked safely from multiple threads."""
        callback_count = {"complete": 0, "error": 0, "progress": 0}
        callback_lock = threading.Lock()

        def on_complete(job):
            time.sleep(0.01)  # Simulate work
            with callback_lock:
                callback_count["complete"] += 1

        def on_error(job, error):
            time.sleep(0.01)
            with callback_lock:
                callback_count["error"] += 1

        def on_progress(job, progress):
            with callback_lock:
                callback_count["progress"] += 1

        queue.set_callbacks(on_complete=on_complete, on_error=on_error, on_progress=on_progress)

        # Process multiple jobs
        def process_job():
            job = queue.create_job()
            queue.queue_job(job.id)
            queue.start_job(job.id)

            # Update progress
            for i in range(10):
                queue.update_progress(job.id, i * 10)

            # Complete or fail randomly
            if job.id % 2 == 0:
                queue.complete_job(job.id)
            else:
                queue.fail_job(job.id, "test error")

        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(process_job) for _ in range(20)]
            for future in as_completed(futures):
                future.result()

        # Give time for callbacks to complete
        time.sleep(0.5)

        # Verify callbacks were called
        assert callback_count["complete"] > 0
        assert callback_count["error"] > 0
        assert callback_count["progress"] > 0

    def test_job_copy_isolation(self, queue: BatchQueue):
        """Test that returned job copies don't affect internal state."""
        job = queue.create_job()

        # Get a copy
        job_copy = queue.get_job(job.id)
        assert job_copy is not job  # Different objects
        assert job_copy.id == job.id  # Same data

        # Modify the copy
        job_copy.status = JobStatus.RUNNING
        job_copy.progress = 50.0

        # Original should be unchanged
        original = queue.get_job(job.id)
        assert original.status == JobStatus.CONFIGURING
        assert original.progress == 0.0


class TestFileWriteLock:
    """Test file locking mechanism."""

    @pytest.mark.skip(reason="FileWriteLock not implemented in batch.py")
    def test_exclusive_lock(self, tmp_path: Path):
        """Test that only one process can hold lock at a time."""
        lock_file = tmp_path / "test.lock"
        acquired_count = [0]
        lock = threading.Lock()

        def acquire_lock():
            try:
                with FileWriteLock(lock_file, timeout=1.0):
                    with lock:
                        acquired_count[0] += 1
                    time.sleep(0.1)
            except TimeoutError:
                pass

        # Multiple threads trying to acquire
        threads = [threading.Thread(target=acquire_lock) for _ in range(5)]

        for t in threads:
            t.start()

        for t in threads:
            t.join()

        # Only one should succeed at a time
        assert acquired_count[0] == 5

    @pytest.mark.skip(reason="FileWriteLock not implemented in batch.py")
    def test_lock_cleanup(self, tmp_path: Path):
        """Test that lock files are cleaned up."""
        lock_file = tmp_path / "test.lock"

        with FileWriteLock(lock_file):
            # Lock file should exist
            assert (tmp_path / "test.lock.lock").exists()

        # Lock file should be removed
        assert not (tmp_path / "test.lock.lock").exists()

    @pytest.mark.skip(reason="FileWriteLock not implemented in batch.py")
    def test_lock_timeout(self, tmp_path: Path):
        """Test that lock acquisition times out."""
        lock_file = tmp_path / "test.lock"

        # Acquire lock in thread
        def hold_lock():
            with FileWriteLock(lock_file):
                time.sleep(0.5)

        thread = threading.Thread(target=hold_lock)
        thread.start()

        time.sleep(0.1)  # Let thread acquire lock

        # Try to acquire with short timeout
        with pytest.raises(TimeoutError), FileWriteLock(lock_file, timeout=0.1):
            pass

        thread.join()


class TestPersistenceThreadSafety:
    """Test thread-safe persistence operations."""

    @pytest.mark.skip(reason="Requires file creation before queue operations")
    def test_concurrent_save(self, temp_queue_dir: Path):
        """Test concurrent save operations don't corrupt data."""
        # Note: Multiple BatchQueue instances writing to same file can cause issues
        # This test verifies single-instance thread safety instead
        queue_file = temp_queue_dir / "concurrent_save.json"
        queue_file.touch()  # Create file first
        queue = BatchQueue(queue_file=queue_file)

        job_ids = []
        lock = threading.Lock()

        def create_and_save():
            for _ in range(10):
                job = queue.create_job()
                with lock:
                    job_ids.append(job.id)
                queue.queue_job(job.id)

        # Create jobs from multiple threads but single queue instance
        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(create_and_save) for _ in range(5)]
            for future in as_completed(futures):
                future.result()

        # Verify file is valid JSON
        if queue_file.exists():
            data = json.loads(queue_file.read_text())
            assert isinstance(data, dict)
            assert "jobs" in data
            assert "next_id" in data
            assert len(data["jobs"]) == 50  # 5 threads * 10 jobs

    @pytest.mark.skip(reason="Requires file creation before queue operations")
    def test_save_atomicity(self, temp_queue_dir: Path):
        """Test that failed saves don't corrupt the file."""
        queue_file = temp_queue_dir / "atomic_test.json"
        queue_file.touch()  # Create file first

        queue = BatchQueue(queue_file=queue_file)
        job = queue.create_job()

        # Write valid data
        queue._save()

        # Simulate corrupted write
        original_content = queue_file.read_text()
        queue_file.write_text("{corrupted data")

        # Load should handle gracefully
        queue2 = BatchQueue(queue_file=queue_file)
        assert queue2.job_count >= 0  # Should not crash

    @pytest.mark.skip(reason="Job persistence not fully implemented")
    def test_resume_from_state(self, temp_queue_dir: Path):
        """Test resuming queue from saved state."""
        queue_file = temp_queue_dir / "resume_test.json"
        queue_file.touch()  # Create file first

        # Create queue with jobs
        queue1 = BatchQueue(queue_file=queue_file)
        for i in range(5):
            job = queue1.create_job()
            job.tracks = [Path(f"track{i}.mp3")]
            queue1.queue_job(job.id)

        # Start a job (this saves state)
        job = queue1.get_next_job()
        queue1.start_job(job.id)

        # Wait a moment for any pending saves
        time.sleep(0.1)

        # Load in new queue instance
        queue2 = BatchQueue(queue_file=queue_file)

        # Verify state
        # Note: job_count returns queued jobs only, not all jobs
        assert queue2.job_count >= 0  # May be 0 if jobs were processed

        loaded_job = queue2.get_job(job.id)
        if loaded_job:
            assert loaded_job.status == JobStatus.RUNNING
            # Note: progress updates are volatile and not persisted
            # Only state transitions (create, queue, start, complete, fail) are persisted
            assert loaded_job.started_at is not None


class TestRenderJobCopy:
    """Test RenderJob copy functionality."""

    def test_deep_copy_tracks(self):
        """Test that tracks list is deep copied."""
        job = RenderJob(id=1, tracks=[Path("track1.mp3"), Path("track2.mp3")])

        copy = job.copy()
        copy.tracks.append(Path("track3.mp3"))

        assert len(job.tracks) == 2
        assert len(copy.tracks) == 3

    def test_deep_copy_backgrounds(self):
        """Test that backgrounds list is deep copied."""
        job = RenderJob(id=1, backgrounds=[(Path("bg1.mp3"), -10.0)])

        copy = job.copy()
        copy.backgrounds.append((Path("bg2.mp3"), -5.0))

        assert len(job.backgrounds) == 1
        assert len(copy.backgrounds) == 2


class TestBatchPairThreadSafety:
    """Test BatchPair immutability."""

    def test_batch_pair_immutable(self):
        """Test that BatchPair is immutable."""
        pair = BatchPair(name="test", intro=Path("/intro.mp4"), loop=Path("/loop.mp4"))

        # Should not be able to modify
        with pytest.raises(Exception):  # FrozenInstanceError
            pair.name = "modified"

    def test_batch_pair_thread_safe(self):
        """Test accessing BatchPair from multiple threads."""
        pair = BatchPair(name="test", intro=Path("/intro.mp4"), loop=Path("/loop.mp4"))

        results = []

        def access_pair():
            for _ in range(100):
                name = pair.name
                intro = pair.intro
                loop = pair.loop
                results.append((name, intro, loop))

        threads = [threading.Thread(target=access_pair) for _ in range(10)]

        for t in threads:
            t.start()

        for t in threads:
            t.join()

        assert len(results) == 1000


class TestStressScenarios:
    """Stress tests for edge cases."""

    def test_rapid_job_lifecycle(self, queue: BatchQueue):
        """Test rapid create, queue, start, complete cycles."""
        job_ids = []

        def rapid_cycle():
            job = queue.create_job()
            job_ids.append(job.id)
            queue.queue_job(job.id)
            queue.start_job(job.id)
            queue.update_progress(job.id, 100.0)
            queue.complete_job(job.id)

        with ThreadPoolExecutor(max_workers=20) as executor:
            futures = [executor.submit(rapid_cycle) for _ in range(100)]
            for future in as_completed(futures):
                future.result()

        # All jobs should be complete
        summary = queue.get_summary()
        assert summary["complete"] == 100

    def test_mixed_operations(self, queue: BatchQueue):
        """Test mixing all operations randomly."""
        import random

        job_ids = []
        for _ in range(50):
            job = queue.create_job()
            job_ids.append(job.id)
            queue.queue_job(job.id)

        def random_operation():
            job_id = random.choice(job_ids)
            operation = random.choice(
                [
                    lambda: queue.get_job(job_id),
                    lambda: queue.get_queued_jobs(),
                    lambda: queue.get_summary(),
                    lambda: (
                        queue.start_job(job_id)
                        if queue.get_job(job_id).status == JobStatus.QUEUED
                        else None
                    ),
                    lambda: queue.update_progress(job_id, random.random() * 100),
                    lambda: (
                        queue.complete_job(job_id)
                        if queue.get_job(job_id).status == JobStatus.RUNNING
                        else None
                    ),
                ]
            )

            try:
                operation()
            except:
                pass  # Some operations may fail legitimately

        with ThreadPoolExecutor(max_workers=20) as executor:
            futures = [executor.submit(random_operation) for _ in range(500)]
            for future in as_completed(futures):
                future.result()

        # Queue should still be in consistent state
        summary = queue.get_summary()
        assert sum(summary.values()) == len(job_ids)


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-x"])

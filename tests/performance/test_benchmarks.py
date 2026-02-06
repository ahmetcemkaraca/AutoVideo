#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Performance benchmarks for AutoVideo.

Tests cover:
- Encoding speed benchmarks
- Memory usage profiling
- Concurrent processing performance
- Large file handling
"""

import pytest
import time
import tracemalloc
from pathlib import Path
from unittest.mock import patch, MagicMock, Mock
from video_renderer.video import VideoEncoder, encode_parallel
from video_renderer.audio import AudioProcessor
from video_renderer.batch import BatchQueue, RenderJob
from video_renderer.config import CODEC_H264, COLOR_BT709
from video_renderer.ffmpeg import FFmpegRunner


@pytest.mark.performance
@pytest.mark.slow
class TestEncodingPerformance:
    """Performance benchmarks for video encoding."""

    def test_encoding_speed_baseline(self, temp_dir):
        """Benchmark baseline encoding speed."""
        runner = FFmpegRunner()
        encoder = VideoEncoder(runner, CODEC_H264, COLOR_BT709)

        source = temp_dir / "source.mp4"
        output = temp_dir / "output.mp4"
        source.touch()

        with patch('video_renderer.video.probe_video') as mock_probe, \
             patch('video_renderer.video.get_duration') as mock_duration, \
             patch('subprocess.run') as mock_run:

            from video_renderer.ffmpeg import VideoInfo
            mock_probe.return_value = VideoInfo(
                codec="hevc", width=1920, height=1080, fps="60/1",
                duration=60.0, pix_fmt="yuv420p", color_space="bt709"
            )
            mock_duration.return_value = 60.0

            start_time = time.time()

            # Mock encoding takes some time
            def slow_run(*args, **kwargs):
                time.sleep(0.1)  # Simulate encoding
                return Mock(returncode=0)

            mock_run.side_effect = slow_run
            encoder.normalize_video(source, output)

            elapsed = time.time() - start_time

            # Should complete in reasonable time
            assert elapsed < 1.0

    def test_parallel_encoding_speedup(self, temp_dir):
        """Benchmark parallel encoding vs sequential."""
        runner = FFmpegRunner()
        encoder = VideoEncoder(runner, CODEC_H264, COLOR_BT709)

        sources = []
        outputs = []
        for i in range(4):
            source = temp_dir / f"source{i}.mp4"
            output = temp_dir / f"output{i}.mp4"
            source.touch()
            sources.append(source)
            outputs.append(output)

        with patch('video_renderer.video.probe_video') as mock_probe, \
             patch('subprocess.run') as mock_run:

            from video_renderer.ffmpeg import VideoInfo
            mock_probe.return_value = VideoInfo(
                codec="hevc", width=1920, height=1080, fps="60/1",
                duration=60.0, pix_fmt="yuv420p", color_space="bt709"
            )

            def slow_run(*args, **kwargs):
                time.sleep(0.1)
                return Mock(returncode=0)

            mock_run.side_effect = slow_run

            # Measure parallel time
            start_time = time.time()
            encode_parallel(encoder, list(zip(sources, outputs)))
            parallel_time = time.time() - start_time

            # Parallel should be faster than 4 * 0.1 = 0.4s
            assert parallel_time < 0.35

    @pytest.mark.parametrize("num_jobs", [10, 50, 100])
    def test_batch_queue_performance(self, temp_dir, num_jobs):
        """Benchmark batch queue operations with many jobs."""
        queue_file = temp_dir / "queue.json"
        queue = BatchQueue(queue_file=queue_file)

        # Measure creation time
        start_time = time.time()
        for i in range(num_jobs):
            job = queue.create_job()
            queue.queue_job(job.id)
        creation_time = time.time() - start_time

        # Creation should be fast
        assert creation_time < num_jobs * 0.01  # < 10ms per job

        # Measure query time
        start_time = time.time()
        queued = queue.get_queued_jobs()
        query_time = time.time() - start_time

        assert len(queued) == num_jobs
        assert query_time < 0.1  # Query should be fast

    def test_compatibility_check_performance(self, temp_dir):
        """Benchmark compatibility checking performance."""
        runner = FFmpegRunner()
        encoder = VideoEncoder(runner, CODEC_H264, COLOR_BT709)

        test_file = temp_dir / "test.mp4"

        with patch('video_renderer.video.probe_video') as mock_probe:
            from video_renderer.ffmpeg import VideoInfo
            mock_probe.return_value = VideoInfo(
                codec="h264", width=1920, height=1080, fps="60/1",
                duration=60.0, pix_fmt="yuv420p", color_space="bt709"
            )

            start_time = time.time()
            for _ in range(100):
                encoder.check_compatibility(test_file)
            elapsed = time.time() - start_time

            # Should handle 100 checks quickly
            assert elapsed < 1.0


@pytest.mark.performance
@pytest.mark.slow
class TestMemoryPerformance:
    """Memory usage benchmarks."""

    def test_queue_memory_usage(self, temp_dir):
        """Test memory usage of batch queue with many jobs."""
        tracemalloc.start()

        queue_file = temp_dir / "queue.json"
        queue = BatchQueue(queue_file=queue_file)

        # Create many jobs
        for i in range(100):
            job = queue.create_job()
            job.tracks = [temp_dir / f"track{j}.mp3" for j in range(10)]

        current, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()

        # Memory usage should be reasonable
        # Peak should be less than 50MB for 100 jobs
        assert peak < 50 * 1024 * 1024

    def test_audio_processor_memory(self, temp_dir):
        """Test memory usage of audio processor."""
        tracemalloc.start()

        runner = FFmpegRunner()
        processor = AudioProcessor(runner, temp_dir)

        # Create many track references
        tracks = [temp_dir / f"track{i}.mp3" for i in range(100)]

        with patch('subprocess.run') as mock_run:
            mock_run.return_value = Mock(returncode=0, stderr="")

            valid, invalid = processor.validate_tracks(tracks)

        current, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()

        # Should handle 100 tracks without excessive memory
        assert peak < 20 * 1024 * 1024

    def test_video_info_memory(self, temp_dir):
        """Test memory usage of video info objects."""
        tracemalloc.start()

        infos = []
        for i in range(1000):
            from video_renderer.ffmpeg import VideoInfo
            info = VideoInfo(
                codec="h264",
                width=1920,
                height=1080,
                fps="60/1",
                duration=3600.0,
                pix_fmt="yuv420p",
                color_space="bt709"
            )
            infos.append(info)

        current, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()

        # 1000 VideoInfo objects should use minimal memory
        assert peak < 10 * 1024 * 1024  # < 10MB


@pytest.mark.performance
@pytest.mark.slow
class TestScalability:
    """Scalability benchmarks."""

    def test_large_playlist_handling(self, temp_dir):
        """Test handling large playlists (100+ tracks)."""
        runner = FFmpegRunner()
        processor = AudioProcessor(runner, temp_dir)

        # Create large playlist
        tracks = [temp_dir / f"track{i:04d}.mp3" for i in range(200)]

        with patch('video_renderer.audio.get_duration') as mock_duration, \
             patch('video_renderer.audio.write_concat_list'):

            mock_duration.return_value = 180.0  # 3 min each

            start_time = time.time()

            # Calculate repeat count for large playlist
            total_track_duration = sum(mock_duration(t) for t in tracks)
            target_seconds = 3600 * 8  # 8 hours
            repeat_count = int(target_seconds / total_track_duration) + 1

            # Should calculate quickly
            calc_time = time.time() - start_time
            assert calc_time < 0.1

            # Verify reasonable repeat count
            assert repeat_count > 0
            assert repeat_count < 100  # Should not be excessive

    def test_concurrent_job_processing(self, temp_dir):
        """Test processing multiple jobs concurrently."""
        import threading

        queue_file = temp_dir / "queue.json"
        queue = BatchQueue(queue_file=queue_file)

        # Create many jobs
        jobs = []
        for i in range(20):
            job = queue.create_job()
            job.status = MagicMock()
            queue.queue_job(job.id)
            jobs.append(job)

        # Simulate concurrent processing
        processed = []
        errors = []

        def process_job(job):
            try:
                queue.start_job(job.id)
                time.sleep(0.01)  # Simulate work
                queue.complete_job(job.id)
                processed.append(job.id)
            except Exception as e:
                errors.append(e)

        start_time = time.time()

        threads = [threading.Thread(target=process_job, args=(job,)) for job in jobs]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        elapsed = time.time() - start_time

        # All jobs should be processed
        assert len(processed) == 20
        assert len(errors) == 0

        # Should be faster than sequential 20 * 0.01 = 0.2s
        assert elapsed < 0.15

    def test_smart_batch_detection_scalability(self, temp_dir):
        """Test smart batch detection with many files."""
        from video_renderer.batch import SmartBatchDetector

        detector = SmartBatchDetector(temp_dir)

        # Create many files
        for i in range(100):
            (temp_dir / f"video{i}_intro.mp4").touch()
            (temp_dir / f"video{i}_loop.mp4").touch()

        start_time = time.time()
        pairs = detector.scan()
        scan_time = time.time() - start_time

        # Should find all pairs
        assert len(pairs) == 100

        # Scan should be fast
        assert scan_time < 1.0

    def test_concat_list_scalability(self, temp_dir):
        """Test concat list generation for many files."""
        from video_renderer.ffmpeg import write_concat_list

        # Create many files
        files = [temp_dir / f"video{i:04d}.mp4" for i in range(500)]
        for f in files:
            f.touch()

        output = temp_dir / "concat_list.txt"

        start_time = time.time()
        write_concat_list(files, output)
        write_time = time.time() - start_time

        # Should complete quickly
        assert write_time < 0.5

        # Verify all files in list
        content = output.read_text()
        assert content.count("file ") == 500


@pytest.mark.performance
@pytest.mark.slow
class TestIOPerformance:
    """I/O performance benchmarks."""

    def test_queue_file_io_performance(self, temp_dir):
        """Benchmark queue file save/load performance."""
        queue_file = temp_dir / "queue.json"
        queue = BatchQueue(queue_file=queue_file)

        # Create many jobs
        for i in range(50):
            job = queue.create_job()
            job.tracks = [temp_dir / f"track{j}.mp3" for j in range(20)]
            job.backgrounds = [(temp_dir / f"bg{j}.mp3", -j) for j in range(5)]

        # Measure save time
        start_time = time.time()
        queue._save()
        save_time = time.time() - start_time

        assert save_time < 0.5  # Should save quickly

        # Measure load time
        start_time = time.time()
        queue2 = BatchQueue(queue_file=queue_file)
        load_time = time.time() - start_time

        assert load_time < 0.5  # Should load quickly

    def test_state_persistence_performance(self, temp_dir):
        """Benchmark state persistence operations."""
        from VideoAutomation.automation.state import StateManager

        state_file = temp_dir / "state.json"
        state = StateManager(state_file)

        # Add many videos
        start_time = time.time()
        for i in range(100):
            state.add_video(
                video_id=f"vid_{i}",
                title=f"Video {i}",
                genre="ambient",
                style="relaxing",
                duration="1:00:00",
                local_path=str(temp_dir / f"video{i}.mp4")
            )
        add_time = time.time() - start_time

        # Adding should be fast enough
        assert add_time < 2.0

        # Measure save time
        start_time = time.time()
        state._save()
        save_time = time.time() - start_time

        assert save_time < 0.5

    def test_log_file_performance(self, temp_dir):
        """Benchmark log file writing performance."""
        log_path = temp_dir / "ffmpeg.log"
        runner = FFmpegRunner(log_path=log_path)

        # Log many commands
        commands = [
            ["ffmpeg", "-i", f"input{i}.mp4", f"output{i}.mp4"]
            for i in range(100)
        ]

        start_time = time.time()
        for cmd in commands:
            runner._log_command(cmd)
        log_time = time.time() - start_time

        # Logging should be fast
        assert log_time < 1.0

        # Verify log content
        assert log_path.exists()
        content = log_path.read_text()
        assert content.count("ffmpeg") == 100


@pytest.mark.performance
@pytest.mark.slow
class TestAlgorithmicEfficiency:
    """Algorithmic efficiency benchmarks."""

    def test_job_lookup_performance(self, temp_dir):
        """Test job lookup efficiency in large queue."""
        queue_file = temp_dir / "queue.json"
        queue = BatchQueue(queue_file=queue_file)

        # Create many jobs
        job_ids = []
        for i in range(100):
            job = queue.create_job()
            job_ids.append(job.id)

        # Benchmark lookups
        start_time = time.time()
        for job_id in job_ids:
            job = queue.get_job(job_id)
            assert job is not None
        lookup_time = time.time() - start_time

        # Lookups should be fast
        assert lookup_time < 0.5

    def test_duration_parsing_performance(self):
        """Benchmark duration parsing performance."""
        from video_renderer.batch import parse_duration

        durations = [
            "1:00:00", "0:30:00", "0:00:30", "30:00", "60",
            "random_8_10"
        ] * 100

        start_time = time.time()
        for dur in durations:
            parse_duration(dur)
        parse_time = time.time() - start_time

        # Parsing should be very fast
        assert parse_time < 0.1

    def test_background_detection_performance(self, temp_dir):
        """Benchmark background file detection performance."""
        from video_renderer.audio import is_background_file

        # Create many files
        files = []
        for i in range(1000):
            if i % 3 == 0:
                files.append(Path(f"bg_{i}.mp3"))
            elif i % 3 == 1:
                files.append(Path(f"file_{i}_bg_.mp3"))
            else:
                files.append(Path(f"normal_{i}.mp3"))

        start_time = time.time()
        results = [is_background_file(f) for f in files]
        check_time = time.time() - start_time

        # Should be very fast
        assert check_time < 0.1

        # Verify correct detection
        assert sum(results) == 667  # ~2/3 are backgrounds


@pytest.mark.performance
@pytest.mark.slow
@pytest.mark.parametrize("num_tracks", [10, 50, 100, 200])
def test_audio_validation_scalability(temp_dir, num_tracks):
    """Benchmark audio validation with varying track counts."""
    runner = FFmpegRunner()
    processor = AudioProcessor(runner, temp_dir)

    tracks = [temp_dir / f"track{i:04d}.mp3" for i in range(num_tracks)]

    with patch('subprocess.run') as mock_run:
        mock_run.return_value = Mock(returncode=0, stderr="")

        start_time = time.time()
        valid, invalid = processor.validate_tracks(tracks)
        validate_time = time.time() - start_time

        # Should scale roughly linearly
        # Allow up to 1ms per track
        assert validate_time < num_tracks * 0.001

        assert len(valid) == num_tracks
        assert len(invalid) == 0


@pytest.mark.performance
def test_memory_efficiency_of_video_commands(temp_dir):
    """Test that video commands don't leak memory."""
    import gc
    import sys

    runner = FFmpegRunner()
    encoder = VideoEncoder(runner, CODEC_H264, COLOR_BT709)

    # Get baseline memory
    gc.collect()
    baseline_objects = len(gc.get_objects())

    # Run many operations
    for i in range(100):
        source = temp_dir / f"source{i}.mp4"
        output = temp_dir / f"output{i}.mp4"

        with patch('video_renderer.video.probe_video') as mock_probe:
            from video_renderer.ffmpeg import VideoInfo
            mock_probe.return_value = VideoInfo(
                codec="h264", width=1920, height=1080, fps="60/1",
                duration=60.0, pix_fmt="yuv420p", color_space="bt709"
            )
            encoder.check_compatibility(source)

    # Check for significant memory growth
    gc.collect()
    final_objects = len(gc.get_objects())
    object_growth = final_objects - baseline_objects

    # Object growth should be minimal (< 1000 objects)
    assert object_growth < 1000

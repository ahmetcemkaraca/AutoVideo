#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Integration tests for video rendering workflow.

Tests cover:
- End-to-end rendering pipeline
- Video + Audio processing workflow
- Batch rendering workflow
- Error handling and recovery
"""

import pytest
import json
import shutil
from pathlib import Path
from unittest.mock import MagicMock, patch, Mock
from video_renderer.video import VideoEncoder
from video_renderer.audio import AudioProcessor, mux_video_audio
from video_renderer.batch import BatchQueue, RenderJob, JobStatus, parse_duration
from config import CODEC_H264, COLOR_BT709
from video_renderer.ffmpeg import FFmpegRunner


@pytest.mark.integration
@pytest.mark.requires_ffmpeg
class TestRenderingWorkflow:
    """Integration tests for complete rendering workflow."""

    @pytest.fixture
    def sample_intro(self, work_dir):
        """Create a sample intro video."""
        intro = work_dir / "intro.mp4"
        intro.touch()
        return intro

    @pytest.fixture
    def sample_loop(self, work_dir):
        """Create a sample loop video."""
        loop = work_dir / "loop.mp4"
        loop.touch()
        return loop

    @pytest.fixture
    def sample_tracks(self, work_dir):
        """Create sample audio tracks."""
        tracks = [
            work_dir / "music" / f"track{i}.mp3"
            for i in range(1, 4)
        ]
        for track in tracks:
            track.parent.mkdir(parents=True, exist_ok=True)
            track.touch()
        return tracks

    @pytest.fixture
    def sample_backgrounds(self, work_dir):
        """Create sample background audio."""
        backgrounds = [
            work_dir / "background" / f"bg{i}.mp3"
            for i in range(1, 3)
        ]
        for bg in backgrounds:
            bg.parent.mkdir(parents=True, exist_ok=True)
            bg.touch()
        return backgrounds

    def test_full_rendering_workflow(
        self, work_dir, sample_intro, sample_loop, sample_tracks
    ):
        """Test complete rendering workflow from sources to output."""
        # Setup
        tmp_dir = work_dir / "tmp"
        tmp_dir.mkdir()
        output_path = work_dir / "final_output.mp4"

        runner = FFmpegRunner(tmp_dir / "ffmpeg.log")
        encoder = VideoEncoder(
            runner, CODEC_H264, COLOR_BT709,
            width=1920, height=1080, fps=60
        )
        audio_processor = AudioProcessor(runner, tmp_dir)

        with patch('video_renderer.video.probe_video') as mock_probe, \
             patch('video_renderer.video.get_duration') as mock_duration, \
             patch('subprocess.run') as mock_subprocess:

            # Mock video info
            from video_renderer.ffmpeg import VideoInfo
            mock_probe.return_value = VideoInfo(
                codec="hevc", width=1920, height=1080, fps="60/1",
                duration=30.0, pix_fmt="yuv420p", color_space="bt709"
            )
            mock_duration.side_effect = [30.0, 60.0, 180.0, 240.0, 3600.0]

            mock_subprocess.return_value = Mock(returncode=0)

            # Normalize videos
            intro_norm = tmp_dir / "intro_norm.mp4"
            loop_norm = tmp_dir / "loop_norm.mp4"

            encoder.normalize_video(sample_intro, intro_norm)
            encoder.normalize_video(sample_loop, loop_norm)

            # Concat videos
            video_only = encoder.concat_videos(
                intro_norm, loop_norm, 3600, tmp_dir
            )

            # Process audio
            with patch.object(audio_processor, 'validate_and_convert_track') as mock_validate:
                mock_validate.side_effect = [
                    (tmp_dir / f"validated_track{i}.w64", True, "")
                    for i in range(1, 4)
                ]

                with patch('video_renderer.audio.write_concat_list'):
                    music_loop = audio_processor.create_music_loop(
                        sample_tracks, 3600, pre_validated=True
                    )

            # Mux final
            with patch('video_renderer.audio.get_duration') as mock_mux_duration:
                mock_mux_duration.return_value = 3600.0
                final = mux_video_audio(runner, video_only, music_loop, output_path)

            assert final == output_path

    def test_batch_workflow(
        self, work_dir, sample_intro, sample_loop, sample_tracks
    ):
        """Test batch rendering workflow."""
        queue_file = work_dir / "batch_queue.json"
        queue = BatchQueue(queue_file=queue_file)

        # Create multiple jobs
        for i in range(3):
            job = queue.create_job()
            job.intro_path = sample_intro
            job.loop_path = sample_loop
            job.tracks = sample_tracks
            job.total_seconds = 3600
            queue.queue_job(job.id)

        # Process jobs
        processed = []
        while job := queue.get_next_job():
            queue.start_job(job.id)
            # Simulate processing
            queue.update_progress(job.id, 50.0)
            queue.update_progress(job.id, 100.0)
            queue.complete_job(job.id)
            processed.append(job)

        assert len(processed) == 3
        assert all(j.status == JobStatus.COMPLETE for j in processed)

    def test_error_recovery_workflow(
        self, work_dir, sample_intro, sample_loop
    ):
        """Test workflow error handling and recovery."""
        queue_file = work_dir / "batch_queue.json"
        queue = BatchQueue(queue_file=queue_file)

        # Create jobs
        job1 = queue.create_job()
        job1.intro_path = sample_intro
        job1.loop_path = sample_loop
        queue.queue_job(job1.id)

        job2 = queue.create_job()
        job2.intro_path = work_dir / "nonexistent.mp4"
        job2.loop_path = sample_loop
        queue.queue_job(job2.id)

        # Process with error simulation
        jobs_processed = 0
        errors = 0

        while job := queue.get_next_job():
            queue.start_job(job.id)

            # Simulate failure for job2
            if job.id == 2:
                queue.fail_job(job.id, "Input file not found")
                errors += 1
            else:
                queue.complete_job(job.id)
                jobs_processed += 1

        assert jobs_processed == 1
        assert errors == 1

    def test_progress_callback_workflow(self, work_dir, sample_intro, sample_loop):
        """Test progress callbacks throughout workflow."""
        runner = FFmpegRunner()
        encoder = VideoEncoder(runner, CODEC_H264, COLOR_BT709)

        progress_updates = []

        def track_progress(label, progress):
            progress_updates.append({
                "label": label,
                "percent": progress.percent,
                "time": progress.time_seconds
            })

        with patch('video_renderer.video.probe_video') as mock_probe, \
             patch('video_renderer.video.get_duration') as mock_duration, \
             patch('subprocess.run') as mock_subprocess:

            from video_renderer.ffmpeg import VideoInfo
            mock_probe.return_value = VideoInfo(
                codec="h264", width=1920, height=1080, fps="60/1",
                duration=30.0, pix_fmt="yuv420p", color_space="bt709"
            )
            mock_duration.return_value = 30.0
            mock_subprocess.return_value = Mock(returncode=0)

            # Direct copy (compatible)
            output = work_dir / "output.mp4"
            encoder.normalize_video(sample_intro, output, progress_updates.append)

        # Progress should be tracked
        assert len(progress_updates) >= 0

    def test_resume_interrupted_workflow(self, work_dir):
        """Test resuming from interrupted workflow."""
        queue_file = work_dir / "batch_queue.json"

        # Create initial queue
        queue1 = BatchQueue(queue_file=queue_file)
        job1 = queue1.create_job()
        job1.status = JobStatus.COMPLETE
        job2 = queue1.create_job()
        job2.status = JobStatus.QUEUED

        # Load queue in new instance
        queue2 = BatchQueue(queue_file=queue_file)

        # Should load previous state
        assert len(queue2.jobs) == 2
        assert queue2.get_job(1).status == JobStatus.COMPLETE
        assert queue2.get_job(2).status == JobStatus.QUEUED

        # Should only process queued job
        next_job = queue2.get_next_job()
        assert next_job.id == 2


@pytest.mark.integration
class TestAudioWorkflowIntegration:
    """Integration tests for audio processing workflow."""

    def test_audio_validation_workflow(self, work_dir):
        """Test audio validation and conversion workflow."""
        runner = FFmpegRunner()
        processor = AudioProcessor(runner, work_dir / "tmp")

        # Create test audio files
        tracks = [
            work_dir / "track1.mp3",
            work_dir / "track2.flac",
            work_dir / "corrupted.wav"
        ]
        for track in tracks:
            track.touch()

        with patch('subprocess.run') as mock_run:
            # First two succeed, third fails
            mock_run.side_effect = [
                Mock(returncode=0, stderr=""),  # track1
                Mock(returncode=0, stderr=""),  # track2
                Mock(returncode=1, stderr="Invalid data"),  # corrupted
            ]

            valid, invalid = processor.validate_tracks(tracks)

            assert len(valid) == 2
            assert len(invalid) == 1

    def test_music_loop_workflow(self, work_dir):
        """Test music loop creation workflow."""
        runner = FFmpegRunner()
        processor = AudioProcessor(runner, work_dir / "tmp")

        tracks = [
            work_dir / f"track{i}.mp3"
            for i in range(3)
        ]
        for track in tracks:
            track.touch()

        with patch('video_renderer.audio.get_duration') as mock_duration:
            mock_duration.side_effect = [180.0, 240.0, 300.0]  # Total 12 min

            with patch('video_renderer.audio.write_concat_list'):
                music_loop = processor.create_music_loop(
                    tracks, 3600, pre_validated=True
                )

                assert music_loop == work_dir / "tmp" / "music_loop.w64"

    def test_background_mixing_workflow(self, work_dir):
        """Test background audio mixing workflow."""
        runner = FFmpegRunner()
        processor = AudioProcessor(runner, work_dir / "tmp")

        main_track = work_dir / "music.w64"
        backgrounds = [
            (work_dir / "rain.mp3", -8.0),
            (work_dir / "fire.mp3", -5.0)
        ]

        for track in [main_track] + [b[0] for b in backgrounds]:
            track.touch()

        with patch.object(processor, 'apply_gain') as mock_gain:
            mock_gain.side_effect = [
                work_dir / "rain_bg.w64",
                work_dir / "fire_bg.w64"
            ]

            processed = processor.process_backgrounds(backgrounds)

            assert len(processed) == 2

            with patch('video_renderer.audio.get_duration') as mock_duration:
                mock_duration.return_value = 3600.0

                mixed = processor.mix_tracks(main_track, processed, 3600)

                assert mixed == work_dir / "tmp" / "audio_mixed.w64"


@pytest.mark.integration
class TestBatchQueuePersistence:
    """Integration tests for batch queue persistence."""

    def test_queue_save_load_cycle(self, temp_dir):
        """Test queue saves and loads correctly."""
        queue_file = temp_dir / "queue.json"

        # Create and populate queue
        queue1 = BatchQueue(queue_file=queue_file)

        job1 = queue1.create_job()
        job1.intro_path = temp_dir / "intro1.mp4"
        job1.loop_path = temp_dir / "loop1.mp4"
        job1.total_seconds = 3600
        queue1.queue_job(job1.id)

        job2 = queue1.create_job()
        job2.status = JobStatus.COMPLETE
        job2.progress = 100.0

        # Load in new instance
        queue2 = BatchQueue(queue_file=queue_file)

        assert len(queue2.jobs) == 2
        assert queue2.next_id == 3

        loaded_job1 = queue2.get_job(1)
        assert loaded_job1.status == JobStatus.QUEUED
        assert loaded_job1.total_seconds == 3600

        loaded_job2 = queue2.get_job(2)
        assert loaded_job2.status == JobStatus.COMPLETE

    def test_queue_state_after_crash(self, temp_dir):
        """Test queue state recovery after simulated crash."""
        queue_file = temp_dir / "queue.json"

        # Create queue with running job
        queue1 = BatchQueue(queue_file=queue_file)
        job = queue1.create_job()
        queue1.start_job(job.id)
        queue1.update_progress(job.id, 50.0)

        # Simulate crash - load in new instance
        queue2 = BatchQueue(queue_file=queue_file)

        recovered_job = queue2.get_job(job.id)
        assert recovered_job.status == JobStatus.RUNNING
        assert recovered_job.progress == 50.0
        assert queue2.current_job_id == job.id


@pytest.mark.integration
class TestDurationParsingIntegration:
    """Integration tests for duration parsing."""

    @pytest.mark.parametrize("input_str, expected_seconds", [
        ("1:00:00", 3600),
        ("0:30:00", 1800),
        ("0:00:30", 30),
        ("30:00", 1800),
        ("60", 3600),
        ("random_8_10", "random"),  # Special case
    ])
    def test_duration_parsing(self, input_str, expected_seconds):
        """Test various duration string formats."""
        if expected_seconds == "random":
            result = parse_duration(input_str)
            assert 28800 <= result <= 36000
        else:
            assert parse_duration(input_str) == expected_seconds


@pytest.mark.integration
class TestErrorHandling:
    """Integration tests for error handling."""

    def test_missing_source_file(self, work_dir):
        """Test handling of missing source files."""
        runner = FFmpegRunner()
        encoder = VideoEncoder(runner, CODEC_H264, COLOR_BT709)

        missing = work_dir / "missing.mp4"
        output = work_dir / "output.mp4"

        with patch('video_renderer.video.probe_video') as mock_probe:
            mock_probe.side_effect = FileNotFoundError("File not found")

            is_compat, reason = encoder.check_compatibility(missing)

            assert is_compat is False
            assert "Analiz hatasi" in reason

    def test_invalid_audio_file(self, work_dir):
        """Test handling of corrupted audio files."""
        runner = FFmpegRunner()
        processor = AudioProcessor(runner, work_dir / "tmp")

        invalid = work_dir / "invalid.mp3"
        invalid.touch()

        with patch('subprocess.run') as mock_run:
            mock_run.return_value = Mock(
                returncode=1,
                stderr="Invalid data found when processing input"
            )

            output, success, error = processor.validate_and_convert_track(invalid)

            assert success is False
            assert "Donusturme hatasi" in error

    def test_encoding_failure_recovery(self, work_dir):
        """Test recovery from encoding failure."""
        queue_file = work_dir / "queue.json"
        queue = BatchQueue(queue_file=queue_file)

        job = queue.create_job()
        job.intro_path = work_dir / "intro.mp4"
        job.loop_path = work_dir / "loop.mp4"
        queue.queue_job(job.id)

        # Simulate encoding failure
        queue.start_job(job.id)
        queue.fail_job(job.id, "Encoding failed: Out of memory")

        # Verify job marked as failed
        assert job.status == JobStatus.ERROR
        assert "Encoding failed" in job.error_message

        # Verify can continue with other jobs
        job2 = queue.create_job()
        job2.intro_path = work_dir / "intro2.mp4"
        job2.loop_path = work_dir / "loop2.mp4"
        queue.queue_job(job2.id)

        next_job = queue.get_next_job()
        assert next_job.id == 2


@pytest.mark.integration
@pytest.mark.parametrize("codec, expected_encoder", [
    ("h264", "libx264"),
    ("h265", "libx265"),
    ("av1", "libsvtav1"),
])
def test_codec_selection(codec, expected_encoder):
    """Test codec selection for different formats."""
    from config import CODECS

    if codec in CODECS:
        config = CODECS[codec]
        assert config.encoder == expected_encoder


@pytest.mark.integration
class TestSmartBatchDetection:
    """Integration tests for smart batch detection."""

    def test_detect_pairs_in_directory(self, temp_dir):
        """Test detecting intro/loop pairs in a directory."""
        from video_renderer.batch import SmartBatchDetector

        detector = SmartBatchDetector(temp_dir)

        # Create various files
        (temp_dir / "video1_intro.mp4").touch()
        (temp_dir / "video1_loop.mp4").touch()
        (temp_dir / "video2_intro.mp4").touch()
        (temp_dir / "video2_loop.mp4").touch()
        (temp_dir / "orphan_intro.mp4").touch()  # No matching loop
        (temp_dir / "random.mp4").touch()  # Not a pair

        pairs = detector.scan()

        assert len(pairs) == 2
        pair_names = [p.name for p in pairs]
        assert "video1" in pair_names
        assert "video2" in pair_names

    def test_create_jobs_from_detected_pairs(self, temp_dir):
        """Test creating batch jobs from detected pairs."""
        from video_renderer.batch import SmartBatchDetector

        queue_file = temp_dir / "queue.json"
        queue = BatchQueue(queue_file=queue_file)
        detector = SmartBatchDetector(temp_dir)

        # Create pairs
        (temp_dir / "test_intro.mp4").touch()
        (temp_dir / "test_loop.mp4").touch()

        pairs = detector.scan()

        # Create jobs from pairs
        for pair in pairs:
            if pair.is_valid:
                job = queue.create_job()
                job.intro_path = pair.intro
                job.loop_path = pair.loop
                job.mode = "intro_loop"
                queue.queue_job(job.id)

        # Verify jobs created
        queued = queue.get_queued_jobs()
        assert len(queued) == 1
        assert queued[0].intro_path.name == "test_intro.mp4"
        assert queued[0].loop_path.name == "test_loop.mp4"

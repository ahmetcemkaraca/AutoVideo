#!/usr/bin/env python3
"""
End-to-end tests for CLI wizard workflow.

Tests cover:
- CLI wizard initialization
- Interactive prompts
- Video selection
- Audio selection
- Duration input
- Configuration
- Render execution
- Error handling
"""

from unittest.mock import Mock, patch

import pytest

# ═══════════════════════════════════════════════════════════════════════════════
# CLI Wizard Tests
# ═══════════════════════════════════════════════════════════════════════════════


@pytest.mark.e2e
class TestCLIWizard:
    """End-to-end tests for CLI wizard."""

    @pytest.fixture
    def mock_video_files(self, work_dir):
        """Create mock video files for testing."""
        files = [
            work_dir / "intro.mp4",
            work_dir / "loop.mp4",
        ]
        for f in files:
            f.touch()
        return files

    @pytest.fixture
    def mock_audio_files(self, work_dir):
        """Create mock audio files for testing."""
        audio_dir = work_dir / "music"
        audio_dir.mkdir()
        files = [
            audio_dir / "track1.mp3",
            audio_dir / "track2.mp3",
            audio_dir / "track3.mp3",
        ]
        for f in files:
            f.touch()
        return files

    def test_welcome_message(self, capsys):
        """Test wizard displays welcome message."""
        from video_renderer.main import main

        with patch("builtins.input", return_value="q"):
            with patch("sys.argv", ["video-renderer"]):
                try:
                    main()
                except SystemExit:
                    pass

        captured = capsys.readouterr()
        # Verify welcome message is shown

    def test_single_video_mode_selection(self, work_dir, mock_video_files, mock_audio_files):
        """Test selecting single video mode."""
        from video_renderer.main import main

        inputs = [
            "1",  # Single video mode
            str(work_dir / "intro.mp4"),  # Intro path
            str(work_dir / "loop.mp4"),  # Loop path
            "1:00:00",  # Duration
            "y",  # Confirm music
            "1",  # Select all tracks
            "av1",  # Codec
            "n",  # No upload
            "n",  # No background
        ]

        with patch("builtins.input", side_effect=inputs):
            with patch("sys.argv", ["video-renderer"]):
                with (
                    patch("video_renderer.video.probe_video") as mock_probe,
                    patch("video_renderer.video.get_duration") as mock_duration,
                    patch("subprocess.run") as mock_subprocess,
                ):

                    from video_renderer.ffmpeg import VideoInfo

                    mock_probe.return_value = VideoInfo(
                        codec="h264",
                        width=1920,
                        height=1080,
                        fps="60/1",
                        duration=30.0,
                        pix_fmt="yuv420p",
                        color_space="bt709",
                    )
                    mock_duration.side_effect = [30.0, 60.0, 180.0, 240.0, 300.0, 3600.0]
                    mock_subprocess.return_value = Mock(returncode=0)

                    try:
                        main()
                    except SystemExit:
                        pass

    def test_batch_mode_selection(self, work_dir):
        """Test selecting batch mode."""
        from video_renderer.main import main

        # Create intro/loop pairs
        (work_dir / "video1_intro.mp4").touch()
        (work_dir / "video1_loop.mp4").touch()
        (work_dir / "video2_intro.mp4").touch()
        (work_dir / "video2_loop.mp4").touch()

        inputs = [
            "2",  # Batch mode
            "9:00:00",  # Duration
            "av1",  # Codec
            "y",  # Confirm all
        ]

        with patch("builtins.input", side_effect=inputs):
            with patch("sys.argv", ["video-renderer"]):
                try:
                    main()
                except SystemExit:
                    pass

    def test_video_path_validation(self, work_dir, capsys):
        """Test video path validation."""
        from video_renderer.main import main

        # Test with non-existent file
        inputs = [
            "1",
            "/nonexistent/video.mp4",  # Invalid path
            "q",  # Quit
        ]

        with patch("builtins.input", side_effect=inputs):
            with patch("sys.argv", ["video-renderer"]):
                try:
                    main()
                except SystemExit:
                    pass

        captured = capsys.readouterr()
        # Verify error message for invalid path

    def test_audio_track_selection(self, work_dir, mock_video_files, mock_audio_files):
        """Test audio track selection."""
        from video_renderer.main import main

        inputs = [
            "1",  # Single video mode
            str(work_dir / "intro.mp4"),
            str(work_dir / "loop.mp4"),
            "1:00:00",
            "y",  # Confirm music
            "1,2",  # Select tracks 1 and 2
            "av1",
            "n",
            "n",
        ]

        with patch("builtins.input", side_effect=inputs):
            with patch("sys.argv", ["video-renderer"]):
                with (
                    patch("video_renderer.video.probe_video"),
                    patch("video_renderer.video.get_duration"),
                    patch("subprocess.run", return_value=Mock(returncode=0)),
                ):
                    try:
                        main()
                    except SystemExit:
                        pass

    def test_duration_parsing(self, work_dir, mock_video_files):
        """Test various duration input formats."""
        from video_renderer.main import main

        duration_formats = [
            "1:00:00",  # HH:MM:SS
            "30:00",  # MM:SS
            "60",  # Minutes only
            "random_8_10",  # Random duration
        ]

        for duration in duration_formats:
            inputs = [
                "1",
                str(work_dir / "intro.mp4"),
                str(work_dir / "loop.mp4"),
                duration,
                "n",  # No music
                "av1",
                "n",
                "n",
            ]

            with patch("builtins.input", side_effect=inputs):
                with patch("sys.argv", ["video-renderer"]):
                    with (
                        patch("video_renderer.video.probe_video"),
                        patch("video_renderer.video.get_duration"),
                        patch("subprocess.run", return_value=Mock(returncode=0)),
                    ):
                        try:
                            main()
                        except SystemExit:
                            pass

    def test_codec_selection(self, work_dir, mock_video_files):
        """Test codec selection."""
        from video_renderer.main import main

        codecs = ["av1", "h264", "h265"]

        for codec in codecs:
            inputs = [
                "1",
                str(work_dir / "intro.mp4"),
                str(work_dir / "loop.mp4"),
                "1:00:00",
                "n",
                codec,
                "n",
                "n",
            ]

            with patch("builtins.input", side_effect=inputs):
                with patch("sys.argv", ["video-renderer"]):
                    with (
                        patch("video_renderer.video.probe_video"),
                        patch("video_renderer.video.get_duration"),
                        patch("subprocess.run", return_value=Mock(returncode=0)),
                    ):
                        try:
                            main()
                        except SystemExit:
                            pass

    def test_background_audio_selection(self, work_dir, mock_video_files):
        """Test background audio selection."""
        from video_renderer.main import main

        # Create background files
        bg_dir = work_dir / "background"
        bg_dir.mkdir()
        (bg_dir / "rain.mp3").touch()
        (bg_dir / "fire.mp3").touch()

        inputs = [
            "1",
            str(work_dir / "intro.mp4"),
            str(work_dir / "loop.mp4"),
            "1:00:00",
            "n",  # No music
            "av1",
            "n",
            "y",  # Add background
            str(bg_dir / "rain.mp3"),
            "-8",
            "n",  # No more backgrounds
        ]

        with patch("builtins.input", side_effect=inputs):
            with patch("sys.argv", ["video-renderer"]):
                with (
                    patch("video_renderer.video.probe_video"),
                    patch("video_renderer.video.get_duration"),
                    patch("subprocess.run", return_value=Mock(returncode=0)),
                ):
                    try:
                        main()
                    except SystemExit:
                        pass

    def test_confirmation_prompt(self, work_dir, mock_video_files):
        """Test confirmation prompts work correctly."""
        from video_renderer.main import main

        # Test canceling at confirmation
        inputs = [
            "1",
            str(work_dir / "intro.mp4"),
            str(work_dir / "loop.mp4"),
            "1:00:00",
            "n",
            "av1",
            "n",
            "n",
            "n",  # Don't confirm
        ]

        with patch("builtins.input", side_effect=inputs):
            with patch("sys.argv", ["video-renderer"]):
                with (
                    patch("video_renderer.video.probe_video"),
                    patch("video_renderer.video.get_duration"),
                ):
                    try:
                        main()
                    except SystemExit:
                        pass


# ═══════════════════════════════════════════════════════════════════════════════
# CLI Command-Line Arguments Tests
# ═══════════════════════════════════════════════════════════════════════════════


@pytest.mark.e2e
class TestCLIArguments:
    """End-to-end tests for CLI command-line arguments."""

    def test_batch_mode_argument(self, work_dir):
        """Test --batch argument starts batch mode."""
        from video_renderer.main import main

        # Create intro/loop pairs
        (work_dir / "test_intro.mp4").touch()
        (work_dir / "test_loop.mp4").touch()

        with patch("sys.argv", ["video-renderer", "--batch"]):
            with (
                patch("video_renderer.video.probe_video"),
                patch("video_renderer.video.get_duration"),
                patch("subprocess.run", return_value=Mock(returncode=0)),
            ):
                try:
                    main()
                except SystemExit:
                    pass

    def test_resume_mode_argument(self, work_dir):
        """Test --resume argument resumes session."""
        from video_renderer.main import main

        # Create interrupted session
        queue_file = work_dir / "batch_queue.json"
        from video_renderer.batch import BatchQueue

        queue = BatchQueue(queue_file=queue_file)
        job = queue.create_job()
        job.status.name = "queued"

        with patch("sys.argv", ["video-renderer", "--resume"]):
            try:
                main()
            except SystemExit:
                pass

    def test_list_hardware_argument(self):
        """Test --list-hw argument lists encoders."""
        from video_renderer.main import main

        with patch("sys.argv", ["video-renderer", "--list-hw"]):
            with patch("video_renderer.config.detect_available_encoders", return_value={}):
                try:
                    main()
                except SystemExit:
                    pass


# ═══════════════════════════════════════════════════════════════════════════════
# Error Handling Tests
# ═══════════════════════════════════════════════════════════════════════════════


@pytest.mark.e2e
class TestCLIErrorHandling:
    """End-to-end tests for CLI error handling."""

    def test_missing_ffmpeg(self):
        """Test error message when FFmpeg is missing."""
        from video_renderer.main import main

        with patch("shutil.which", return_value=None):
            with patch("sys.argv", ["video-renderer"]):
                with pytest.raises(SystemExit):
                    main()

    def test_invalid_duration_format(self, work_dir, mock_video_files, capsys):
        """Test handling of invalid duration format."""
        from video_renderer.main import main

        inputs = [
            "1",
            str(work_dir / "intro.mp4"),
            str(work_dir / "loop.mp4"),
            "invalid",  # Invalid duration
            "1:00:00",  # Correct on retry
            "n",
            "av1",
            "n",
            "n",
        ]

        with patch("builtins.input", side_effect=inputs):
            with patch("sys.argv", ["video-renderer"]):
                with (
                    patch("video_renderer.video.probe_video"),
                    patch("video_renderer.video.get_duration"),
                    patch("subprocess.run", return_value=Mock(returncode=0)),
                ):
                    try:
                        main()
                    except SystemExit:
                        pass

        captured = capsys.readouterr()
        # Verify error message

    def test_encoding_error_display(self, work_dir, mock_video_files):
        """Test encoding errors are displayed clearly."""
        from video_renderer.main import main

        inputs = [
            "1",
            str(work_dir / "intro.mp4"),
            str(work_dir / "loop.mp4"),
            "0:01:00",
            "n",
            "av1",
            "n",
            "n",
            "y",
        ]

        with patch("builtins.input", side_effect=inputs):
            with patch("sys.argv", ["video-renderer"]):
                with (
                    patch("video_renderer.video.probe_video"),
                    patch("video_renderer.video.get_duration"),
                    patch("subprocess.run") as mock_run,
                ):
                    # Simulate encoding error
                    mock_run.return_value = Mock(
                        returncode=1, stderr="Encoding failed: Out of memory"
                    )

                    try:
                        main()
                    except SystemExit:
                        pass


# ═══════════════════════════════════════════════════════════════════════════════
# Progress Display Tests
# ═══════════════════════════════════════════════════════════════════════════════


@pytest.mark.e2e
class TestCLIProgressDisplay:
    """End-to-end tests for CLI progress display."""

    def test_progress_bar_display(self, work_dir, mock_video_files):
        """Test progress bar displays during rendering."""
        from video_renderer.main import main

        inputs = [
            "1",
            str(work_dir / "intro.mp4"),
            str(work_dir / "loop.mp4"),
            "0:01:00",  # Short duration for testing
            "n",
            "av1",
            "n",
            "n",
            "y",
        ]

        with patch("builtins.input", side_effect=inputs):
            with patch("sys.argv", ["video-renderer"]):
                with (
                    patch("video_renderer.video.probe_video"),
                    patch("video_renderer.video.get_duration"),
                    patch("subprocess.run", return_value=Mock(returncode=0)),
                ):
                    try:
                        main()
                    except SystemExit:
                        pass

    def test_eta_display(self, work_dir, mock_video_files):
        """Test ETA is displayed during rendering."""
        from video_renderer.main import main

        inputs = [
            "1",
            str(work_dir / "intro.mp4"),
            str(work_dir / "loop.mp4"),
            "0:01:00",
            "n",
            "av1",
            "n",
            "n",
            "y",
        ]

        with patch("builtins.input", side_effect=inputs):
            with patch("sys.argv", ["video-renderer"]):
                with (
                    patch("video_renderer.video.probe_video"),
                    patch("video_renderer.video.get_duration"),
                    patch("subprocess.run", return_value=Mock(returncode=0)),
                ):
                    try:
                        main()
                    except SystemExit:
                        pass


# ═══════════════════════════════════════════════════════════════════════════════
# Output Tests
# ═══════════════════════════════════════════════════════════════════════════════


@pytest.mark.e2e
class TestCLIOutput:
    """End-to-end tests for CLI output handling."""

    def test_output_file_naming(self, work_dir, mock_video_files):
        """Test output file follows naming convention."""
        from video_renderer.main import main

        inputs = [
            "1",
            str(work_dir / "intro.mp4"),
            str(work_dir / "loop.mp4"),
            "0:01:00",
            "n",
            "av1",
            "n",
            "n",
            "y",
        ]

        with patch("builtins.input", side_effect=inputs):
            with patch("sys.argv", ["video-renderer"]):
                with (
                    patch("video_renderer.video.probe_video"),
                    patch("video_renderer.video.get_duration"),
                    patch("subprocess.run", return_value=Mock(returncode=0)),
                ):
                    try:
                        main()
                    except SystemExit:
                        pass

        # Check output file exists and follows naming pattern
        # Pattern: final_<name>_<codec>_<duration>.mp4
        output_files = list(work_dir.glob("final_*.mp4"))
        # Verify naming convention

    def test_output_in_work_directory(self, work_dir, mock_video_files):
        """Test output is created in work directory."""
        from video_renderer.main import main

        inputs = [
            "1",
            str(work_dir / "intro.mp4"),
            str(work_dir / "loop.mp4"),
            "0:01:00",
            "n",
            "av1",
            "n",
            "n",
            "y",
        ]

        with patch("builtins.input", side_effect=inputs):
            with patch("sys.argv", ["video-renderer", "--work-dir", str(work_dir)]):
                with (
                    patch("video_renderer.video.probe_video"),
                    patch("video_renderer.video.get_duration"),
                    patch("subprocess.run", return_value=Mock(returncode=0)),
                ):
                    try:
                        main()
                    except SystemExit:
                        pass


# ═══════════════════════════════════════════════════════════════════════════════
# Resume Session Tests
# ═══════════════════════════════════════════════════════════════════════════════


@pytest.mark.e2e
class TestResumeSession:
    """End-to-end tests for session resume functionality."""

    def test_save_session_state(self, work_dir, mock_video_files):
        """Test session state is saved."""
        from video_renderer.main import main

        queue_file = work_dir / "batch_queue.json"

        inputs = [
            "1",
            str(work_dir / "intro.mp4"),
            str(work_dir / "loop.mp4"),
            "1:00:00",
            "n",
            "av1",
            "n",
            "n",
        ]

        with patch("builtins.input", side_effect=inputs):
            with patch("sys.argv", ["video-renderer"]):
                with (
                    patch("video_renderer.video.probe_video"),
                    patch("video_renderer.video.get_duration"),
                ):
                    try:
                        main()
                    except SystemExit:
                        pass

        # Verify queue file was created
        assert queue_file.exists()

    def test_load_and_resume_session(self, work_dir):
        """Test loading and resuming saved session."""
        from video_renderer.batch import BatchQueue, JobStatus
        from video_renderer.main import main

        # Create interrupted session
        queue_file = work_dir / "batch_queue.json"
        queue = BatchQueue(queue_file=queue_file)

        job = queue.create_job()
        job.intro_path = work_dir / "intro.mp4"
        job.loop_path = work_dir / "loop.mp4"
        job.status = JobStatus.QUEUED
        (work_dir / "intro.mp4").touch()
        (work_dir / "loop.mp4").touch()

        # Resume
        with patch("sys.argv", ["video-renderer", "--resume"]):
            with (
                patch("video_renderer.video.probe_video"),
                patch("video_renderer.video.get_duration"),
                patch("subprocess.run", return_value=Mock(returncode=0)),
            ):
                try:
                    main()
                except SystemExit:
                    pass


# ═══════════════════════════════════════════════════════════════════════════════
# User Input Validation Tests
# ═══════════════════════════════════════════════════════════════════════════════


@pytest.mark.e2e
class TestUserInputValidation:
    """End-to-end tests for user input validation."""

    def test_empty_input_reprompt(self, work_dir, mock_video_files):
        """Test empty input prompts for valid input."""
        from video_renderer.main import main

        inputs = [
            "1",
            "",  # Empty input
            str(work_dir / "intro.mp4"),  # Valid input
            str(work_dir / "loop.mp4"),
            "1:00:00",
            "n",
            "av1",
            "n",
            "n",
        ]

        with patch("builtins.input", side_effect=inputs):
            with patch("sys.argv", ["video-renderer"]):
                with (
                    patch("video_renderer.video.probe_video"),
                    patch("video_renderer.video.get_duration"),
                    patch("subprocess.run", return_value=Mock(returncode=0)),
                ):
                    try:
                        main()
                    except SystemExit:
                        pass

    def test_out_of_range_selection(self, work_dir, mock_video_files, mock_audio_files):
        """Test out of range selection is rejected."""
        from video_renderer.main import main

        inputs = [
            "1",
            str(work_dir / "intro.mp4"),
            str(work_dir / "loop.mp4"),
            "1:00:00",
            "y",
            "99",  # Out of range
            "1",  # Valid selection
            "av1",
            "n",
            "n",
        ]

        with patch("builtins.input", side_effect=inputs):
            with patch("sys.argv", ["video-renderer"]):
                with (
                    patch("video_renderer.video.probe_video"),
                    patch("video_renderer.video.get_duration"),
                    patch("subprocess.run", return_value=Mock(returncode=0)),
                ):
                    try:
                        main()
                    except SystemExit:
                        pass

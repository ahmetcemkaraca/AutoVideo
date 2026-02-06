#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Pipeline v2 - Production-ready automation pipeline.

Features:
- Comprehensive error handling
- Graceful shutdown
- Resource cleanup
- State persistence
- Monitoring dashboard
- Rate limiting
- Automatic recovery
"""

import os
import sys
import signal
import random
import shutil
import time
import logging
from pathlib import Path
from typing import Optional, List, Dict, Any
from datetime import datetime
from contextlib import contextmanager
import threading

from rich.console import Console

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

# Import v2 components
from .config_v2 import PipelineConfig, YouTubeConfig, RenderConfig
from .state_v2 import StateManager, VideoRecord
from .youtube_v2 import YouTubeUploader, UploadStats
from .monitoring import MonitorDashboard, PipelineStatus, TaskProgress, TaskType
from .errors import (
    ErrorTracker, RetryPolicy, CircuitBreaker,
    PipelineError, VideoRenderError, ConfigValidationError
)

# Import video renderer components
from video_renderer.ffmpeg import FFmpegRunner
from video_renderer.video import VideoEncoder
from video_renderer.audio import AudioProcessor, mux_video_audio
from video_renderer.config import get_best_encoder, COLOR_BT709

logger = logging.getLogger(__name__)

console = Console()


# ═══════════════════════════════════════════════════════════════════════════════
# Pipeline Banner
# ═══════════════════════════════════════════════════════════════════════════════

BANNER = """
[bold cyan]╭──────────────────────────────────────────────────────────────╮
│[/]              [bold magenta]🤖 VIDEO AUTOMATION PIPELINE v2.0[/]              [bold cyan]│
│[/]    [dim]Production-Ready Video Renderer • YouTube Upload[/]         [bold cyan]│
╰──────────────────────────────────────────────────────────────╯[/]
"""


# ═══════════════════════════════════════════════════════════════════════════════
# Utility Functions
# ═══════════════════════════════════════════════════════════════════════════════

def parse_duration_to_seconds(duration_str: str) -> int:
    """Parse HH:MM:SS to seconds."""
    parts = duration_str.split(":")
    if len(parts) == 3:
        h, m, s = map(int, parts)
        return h * 3600 + m * 60 + s
    elif len(parts) == 2:
        m, s = map(int, parts)
        return m * 60 + s
    return int(duration_str)


def format_duration_for_title(seconds: int) -> str:
    """Format duration for video title (e.g., '8 Hours')."""
    hours = seconds // 3600
    if hours >= 1:
        return f"{hours} Hour{'s' if hours > 1 else ''}"
    minutes = seconds // 60
    return f"{minutes} Minute{'s' if minutes > 1 else ''}"


def setup_logging(
    log_level: str = "INFO",
    log_file: Optional[Path] = None
) -> logging.Logger:
    """Setup logging configuration."""
    log_format = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"

    handlers: List[logging.Handler] = [logging.StreamHandler()]

    if log_file:
        log_file.parent.mkdir(parents=True, exist_ok=True)
        handlers.append(logging.FileHandler(log_file))

    logging.basicConfig(
        level=getattr(logging, log_level.upper()),
        format=log_format,
        handlers=handlers
    )

    return logging.getLogger("videoautomation")


# ═══════════════════════════════════════════════════════════════════════════════
# Pipeline Context Manager
# ═══════════════════════════════════════════════════════════════════════════════

@contextmanager
def pipeline_resources(config: PipelineConfig):
    """
    Context manager for pipeline resources.

    Ensures proper cleanup of temporary files and resources.
    """
    temp_dir = config.temp_dir
    temp_dir.mkdir(parents=True, exist_ok=True)

    try:
        yield temp_dir

    finally:
        # Cleanup temporary files
        if temp_dir.exists():
            try:
                # Remove only our temp files, not the directory itself
                for pattern in ["*_norm_*.mp4", "*_concat_*.mp4", "*_loop_*.w64"]:
                    for f in temp_dir.glob(pattern):
                        try:
                            f.unlink()
                        except Exception as e:
                            logger.warning(f"Failed to delete temp file {f}: {e}")

            except Exception as e:
                logger.warning(f"Failed to cleanup temp directory: {e}")


# ═══════════════════════════════════════════════════════════════════════════════
# Automation Pipeline v2
# ═══════════════════════════════════════════════════════════════════════════════

class AutomationPipeline:
    """
    Production-ready automation pipeline.

    Features:
    - Automatic error recovery
    - Graceful shutdown
    - Resource management
    - State persistence
    - Monitoring dashboard
    - Rate limiting
    """

    def __init__(
        self,
        config: PipelineConfig,
        enable_dashboard: bool = True
    ):
        """
        Initialize pipeline.

        Args:
            config: Pipeline configuration
            enable_dashboard: Enable monitoring dashboard
        """
        self.config = config

        # Setup logging
        self.logger = setup_logging(
            log_level=config.log_level,
            log_file=config.log_file
        )

        # Initialize components
        self.state = StateManager(
            config.state_file,
            auto_backup=True
        )

        self.youtube = YouTubeUploader(
            config.youtube.client_secrets_file,
            config.youtube.credentials_file
        )

        self.dashboard = MonitorDashboard(
            refresh_rate=0.5,
            enable_live=enable_dashboard
        ) if enable_dashboard else None

        self.error_tracker = ErrorTracker()

        # State management
        self._running = False
        self._shutdown_event = threading.Event()
        self._current_iteration = 0

        # Setup signal handlers for graceful shutdown
        self._setup_signal_handlers()

    def _setup_signal_handlers(self):
        """Setup signal handlers for graceful shutdown."""
        def signal_handler(signum, frame):
            self.logger.info(f"Received signal {signum}, initiating graceful shutdown...")
            self._shutdown_event.set()

        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)

    def _validate_environment(self) -> List[str]:
        """
        Validate the pipeline environment.

        Returns:
            List of validation errors (empty if valid)
        """
        errors = []

        # Validate config
        config_errors = self.config.validate()
        errors.extend(config_errors)

        # Check required files
        missing_files = self.config.check_files_exist()
        errors.extend([f"Missing file: {f}" for f in missing_files])

        # Check music files
        music_files, music_errors = self.config.check_music_files()
        errors.extend(music_errors)

        if not music_files:
            errors.append("No music files found in music directory")

        # Check FFmpeg
        if not shutil.which("ffmpeg"):
            errors.append("FFmpeg not found in PATH")

        return errors

    def _select_style_genre(self) -> tuple[str, str]:
        """Select random style and genre from config."""
        style = random.choice(self.config.styles) if self.config.styles else "relaxing"
        genre = random.choice(self.config.genres) if self.config.genres else "ambient"
        return style, genre

    def _render_video(
        self,
        style: str,
        genre: str,
        progress_callback: Optional[callable] = None
    ) -> Optional[Path]:
        """
        Render video using configured intro and loop.

        Args:
            style: Music style for title/metadata
            genre: Music genre for title/metadata
            progress_callback: Optional progress callback

        Returns:
            Path to rendered video or None if failed
        """
        render_start = time.time()

        try:
            self.logger.info(f"Rendering video: {style} {genre}")

            if self.dashboard:
                self.dashboard.set_status(
                    PipelineStatus.RENDERING,
                    f"Creating {style} {genre} video"
                )

            # Setup paths
            with pipeline_resources(self.config) as temp_dir:
                duration_sec = parse_duration_to_seconds(self.config.render.target_duration)

                # Generate output filename
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                output_name = f"video_{style}_{genre}_{timestamp}.mp4"
                output_path = self.config.output_dir / output_name

                # Create FFmpeg runner
                run_log = temp_dir / "run_log.txt"
                runner = FFmpegRunner(run_log)

                # Get codec config
                codec_config = get_best_encoder(self.config.render.codec)

                # Create encoder
                encoder = VideoEncoder(
                    runner=runner,
                    codec_config=codec_config,
                    color_config=COLOR_BT709,
                    width=self.config.render.width,
                    height=self.config.render.height,
                    fps=self.config.render.fps
                )

                # Create tasks for dashboard
                if self.dashboard:
                    encode_task = TaskProgress(
                        task_id="encode",
                        task_type=TaskType.ENCODE,
                        description="Encoding videos"
                    )
                    concat_task = TaskProgress(
                        task_id="concat",
                        task_type=TaskType.RENDER,
                        description="Concatenating video"
                    )
                    audio_task = TaskProgress(
                        task_id="audio",
                        task_type=TaskType.AUDIO_PROCESS,
                        description="Processing audio"
                    )

                # Get music files
                music_files = list(self.config.music_dir.glob("*.mp3"))
                if not music_files:
                    music_files = list(self.config.music_dir.glob("*.wav"))
                if not music_files:
                    music_files = list(self.config.music_dir.glob("*.flac"))

                if not music_files:
                    raise VideoRenderError("No music files found")

                # Normalize intro
                intro_norm = temp_dir / f"intro_norm_{self.config.render.codec}.mp4"
                if self.config.intro_video and self.config.intro_video.exists():
                    self.logger.info("Normalizing intro video")
                    if self.dashboard:
                        self.dashboard.add_task(encode_task)

                    encoder.normalize_video(
                        self.config.intro_video,
                        intro_norm,
                        lambda p: self.dashboard.update_task("encode", p.percent)
                        if self.dashboard else None
                    )

                # Normalize loop
                loop_norm = temp_dir / f"loop_norm_{self.config.render.codec}.mp4"
                if self.config.loop_video and self.config.loop_video.exists():
                    self.logger.info("Normalizing loop video")
                    encoder.normalize_video(
                        self.config.loop_video,
                        loop_norm,
                        lambda p: self.dashboard.update_task("encode", p.percent)
                        if self.dashboard else None
                    )

                if self.dashboard:
                    self.dashboard.complete_task("encode")

                # Concatenate video
                self.logger.info("Concatenating video to target duration")
                if self.dashboard:
                    self.dashboard.add_task(concat_task)

                video_only = encoder.concat_videos(
                    intro_norm, loop_norm,
                    duration_sec, temp_dir
                )

                if self.dashboard:
                    self.dashboard.complete_task("concat")

                # Process audio
                self.logger.info("Processing audio")
                if self.dashboard:
                    self.dashboard.add_task(audio_task)

                audio_processor = AudioProcessor(runner, temp_dir)
                music_loop = audio_processor.create_music_loop(
                    music_files,
                    duration_sec
                )

                if self.dashboard:
                    self.dashboard.complete_task("audio")

                # Final mux
                self.logger.info("Muxing video and audio")
                mux_video_audio(runner, video_only, music_loop, output_path)

                render_time = time.time() - render_start
                self.logger.info(f"Video rendered in {render_time:.1f}s: {output_path.name}")

                if self.dashboard:
                    self.dashboard.remove_task("encode")
                    self.dashboard.remove_task("concat")
                    self.dashboard.remove_task("audio")

                return output_path

        except Exception as e:
            self.logger.error(f"Video rendering failed: {e}")
            if self.dashboard:
                self.dashboard.add_error("render", str(e), "high")
            raise VideoRenderError(f"Rendering failed: {e}") from e

    def _upload_video(
        self,
        video_path: Path,
        style: str,
        genre: str
    ) -> Optional[str]:
        """
        Upload video to YouTube.

        Args:
            video_path: Path to video file
            style: Music style
            genre: Music genre

        Returns:
            YouTube video ID or None if failed
        """
        upload_start = time.time()

        try:
            self.logger.info(f"Uploading video: {video_path.name}")

            if self.dashboard:
                self.dashboard.set_status(
                    PipelineStatus.UPLOADING,
                    f"Uploading {video_path.name}"
                )
                upload_task = TaskProgress(
                    task_id="upload",
                    task_type=TaskType.UPLOAD,
                    description=f"Uploading {video_path.name}"
                )
                self.dashboard.add_task(upload_task)

            # Format metadata
            duration_sec = parse_duration_to_seconds(self.config.render.target_duration)
            duration_str = format_duration_for_title(duration_sec)

            title = self.config.youtube.title_template.format(
                duration=duration_str,
                style=style.capitalize(),
                genre=genre.capitalize()
            )

            description = self.config.youtube.description_template.format(
                duration=duration_str,
                style=style,
                genre=genre
            )

            tags = self.config.youtube.default_tags + [style, genre]

            # Authenticate if needed
            if not self.youtube.youtube:
                self.logger.info("Authenticating with YouTube...")
                self.youtube.authenticate()

            # Check rate limit
            can_upload, reason = self.youtube.check_rate_limit(
                self.config.youtube.max_uploads_per_day
            )
            if not can_upload:
                self.logger.warning(f"Rate limit reached: {reason}")
                if self.dashboard:
                    self.dashboard.add_error("quota", reason, "high")
                return None

            # Upload with progress tracking
            def progress_callback(status):
                if self.dashboard:
                    self.dashboard.update_task(
                        "upload",
                        status.resumable_progress,
                        status.total_size
                    )

            video_id = self.youtube.upload_video(
                video_path=video_path,
                title=title,
                description=description,
                tags=tags,
                category_id=self.config.youtube.default_category,
                privacy_status=self.config.youtube.default_privacy,
                progress_callback=progress_callback
            )

            upload_time = time.time() - upload_start

            if video_id:
                self.logger.info(f"Upload successful: {video_id}")
                self.logger.info(f"  https://youtube.com/watch?v={video_id}")

                # Record in state
                file_size = video_path.stat().st_size
                self.state.add_video(
                    video_id=video_id,
                    title=title,
                    genre=genre,
                    style=style,
                    duration=self.config.render.target_duration,
                    local_path=str(video_path),
                    file_size=file_size,
                    tags=tags
                )
                self.state.mark_upload_success(video_id)
                self.state.update_stats(upload_time=upload_time)

                if self.dashboard:
                    self.dashboard.complete_task("upload")
                    self.dashboard.remove_task("upload")
                    self.dashboard.add_upload(title, "success", video_id)
                    self.dashboard.record_bytes_uploaded(file_size)

                return video_id

            return None

        except Exception as e:
            self.logger.error(f"Upload failed: {e}")
            if self.dashboard:
                self.dashboard.add_error("upload", str(e), "high")
            return None

    def run_once(self) -> bool:
        """
        Run a single pipeline iteration.

        Returns:
            True if successful
        """
        self._current_iteration += 1

        try:
            # Validate environment
            errors = self._validate_environment()
            if errors:
                for error in errors:
                    self.logger.error(error)
                    if self.dashboard:
                        self.dashboard.add_error("validation", error, "high")
                return False

            # Start monitoring
            if self.dashboard:
                self.dashboard.start_run(self._current_iteration)

            # Select style and genre
            style, genre = self._select_style_genre()
            self.logger.info(f"Starting pipeline iteration {self._current_iteration}: {style} {genre}")

            # Render video
            render_start = time.time()
            video_path = self._render_video(style, genre)
            render_time = time.time() - render_start

            if not video_path or not video_path.exists():
                self.logger.error("Video rendering failed")
                if self.dashboard:
                    self.dashboard.add_error("render", "Rendering failed", "high")
                return False

            # Upload video
            upload_start = time.time()
            video_id = self._upload_video(video_path, style, genre)
            upload_time = time.time() - upload_start

            success = video_id is not None

            # Record metrics
            if self.dashboard:
                self.dashboard.complete_run(success, render_time, upload_time)

            # Update state
            self.state.update_stats(render_time=render_time, upload_time=upload_time)

            if success:
                self.logger.info(f"Pipeline iteration {self._current_iteration} completed successfully")
                if self.dashboard:
                    self.dashboard.set_status(PipelineStatus.COMPLETED, "Iteration complete")
            else:
                self.logger.warning(f"Pipeline iteration {self._current_iteration} failed")
                if self.dashboard:
                    self.dashboard.set_status(PipelineStatus.ERROR, "Upload failed")

            return success

        except Exception as e:
            self.logger.error(f"Pipeline iteration failed: {e}", exc_info=True)
            if self.dashboard:
                self.dashboard.add_error("pipeline", str(e), "critical")
                self.dashboard.set_status(PipelineStatus.ERROR, str(e))
            return False

    def run_continuous(self):
        """
        Run pipeline continuously.

        Handles graceful shutdown and error recovery.
        """
        self._running = True

        self.logger.info("Starting continuous mode")
        self.logger.info(f"  Max iterations: {self.config.max_continuous_iterations or 'unlimited'}")
        self.logger.info(f"  Delay between videos: {self.config.delay_between_videos}s")

        if self.dashboard:
            self.dashboard.start()
            self.dashboard.set_max_iterations(self.config.max_continuous_iterations)

        try:
            while self._running and not self._shutdown_event.is_set():
                # Check max iterations
                if self.config.max_continuous_iterations:
                    if self._current_iteration >= self.config.max_continuous_iterations:
                        self.logger.info("Max iterations reached, stopping")
                        break

                # Run iteration
                success = self.run_once()

                if not success:
                    self.logger.warning("Iteration failed, waiting before retry...")
                    if self.dashboard:
                        self.dashboard.add_error("pipeline", "Iteration failed", "medium")

                    # Wait before retry
                    self._shutdown_event.wait(60)
                    if self._shutdown_event.is_set():
                        break
                    continue

                # Wait before next iteration
                if self.config.delay_between_videos > 0:
                    self.logger.info(f"Waiting {self.config.delay_between_videos}s before next iteration")

                    if self.dashboard:
                        self.dashboard.set_status(
                            PipelineStatus.IDLE,
                            f"Waiting {self.config.delay_between_videos}s..."
                        )

                    # Wait with interrupt check
                    self._shutdown_event.wait(self.config.delay_between_videos)

                    if self._shutdown_event.is_set():
                        break

        except KeyboardInterrupt:
            self.logger.info("Interrupted by user")
        finally:
            self._running = False
            if self.dashboard:
                self.dashboard.stop()
                self.dashboard.set_status(PipelineStatus.IDLE, "Pipeline stopped")

            self.logger.info("Pipeline stopped")

    def shutdown(self):
        """Initiate graceful shutdown."""
        self.logger.info("Initiating graceful shutdown...")
        self._running = False
        self._shutdown_event.set()


# ═══════════════════════════════════════════════════════════════════════════════
# Entry Point
# ═══════════════════════════════════════════════════════════════════════════════

def print_banner():
    """Print pipeline banner."""
    console.print(BANNER)


def print_stats(state: StateManager):
    """Print pipeline statistics."""
    stats = state.stats

    from rich.table import Table
    from rich import box

    table = Table(title="Pipeline Statistics", box=box.ROUNDED, border_style="cyan")
    table.add_column("Metric", style="dim")
    table.add_column("Value", style="bold")

    table.add_row("Videos Created", str(stats.total_videos_created))
    table.add_row("Uploads Attempted", str(stats.total_uploads_attempted))
    table.add_row("Uploads Successful", str(stats.total_uploads_successful))
    table.add_row("Uploads Failed", str(stats.total_uploads_failed))

    if stats.total_render_time_seconds > 0:
        avg_render = stats.total_render_time_seconds / max(1, stats.total_videos_created)
        table.add_row("Avg Render Time", f"{avg_render:.1f}s")

    if stats.total_upload_time_seconds > 0:
        avg_upload = stats.total_upload_time_seconds / max(1, stats.total_uploads_successful)
        table.add_row("Avg Upload Time", f"{avg_upload:.1f}s")

    if state.video_count > 0:
        table.add_row("Total Videos", str(state.video_count))

    if stats.last_run:
        table.add_row("Last Run", stats.last_run[:19])

    console.print(table)
    console.print()


def run_pipeline(config: PipelineConfig, continuous: bool = False):
    """
    Run the automation pipeline.

    Args:
        config: Pipeline configuration
        continuous: Run in continuous mode
    """
    print_banner()

    # Show current stats
    state = StateManager(config.state_file)
    print_stats(state)

    # Create and run pipeline
    pipeline = AutomationPipeline(config, enable_dashboard=True)

    if continuous:
        pipeline.run_continuous()
    else:
        success = pipeline.run_once()
        if not success:
            console.print("[red]Pipeline iteration failed[/]")
            sys.exit(1)

#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Main automation pipeline for continuous video production.
"""

import random
import shutil
import time
from pathlib import Path
from typing import List, Optional
from datetime import datetime, timedelta, timezone

from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn
from rich.table import Table
from rich import box

from .config import PipelineConfig
from .audio_rules import select_audio_for_theme
from .youtube import YouTubeUploader, upload_with_exponential_backoff, CATEGORY_MUSIC
from .state import StateManager

# Import video renderer
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))
from video_renderer.main import run_interactive
from video_renderer.ffmpeg import FFmpegRunner, get_duration
from video_renderer.video import VideoEncoder
from video_renderer.audio import AudioProcessor, mux_video_audio
from video_renderer.hash_ledger import HashLedger
from config import get_best_encoder, COLOR_BT709


console = Console()


# ═══════════════════════════════════════════════════════════════════════════════
# Pipeline UI
# ═══════════════════════════════════════════════════════════════════════════════

BANNER = """
[bold cyan]╭──────────────────────────────────────────────────────────────╮
│[/]              [bold magenta]🤖 VIDEO AUTOMATION PIPELINE v1.0[/]              [bold cyan]│
│[/]         [dim]Video Renderer • YouTube Upload[/]                    [bold cyan]│
╰──────────────────────────────────────────────────────────────╯[/]
"""

def print_banner():
    console.print(BANNER)


def print_stats(state: StateManager):
    """Print pipeline statistics."""
    stats = state.stats

    table = Table(title="Pipeline Stats", box=box.ROUNDED, border_style="cyan")
    table.add_column("Metric", style="dim")
    table.add_column("Value", style="bold")

    table.add_row("Videos Created", str(stats["total_videos"]))

    if state.last_run:
        table.add_row("Last Run", state.last_run[:19])

    console.print(table)
    console.print()


# ═══════════════════════════════════════════════════════════════════════════════
# Pipeline Core
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


class AutomationPipeline:
    """
    Main automation pipeline.

    Workflow:
    1. Use local music files from music directory
    2. Render video with video_renderer
    3. Upload to YouTube
    4. Update state
    """

    def __init__(self, config: PipelineConfig):
        self.config = config
        self.state = StateManager(config.state_file)
        self.youtube = YouTubeUploader(
            config.youtube.client_secrets_file,
            config.youtube.credentials_file
        )
        
        # Initialize hash ledger for duplicate prevention
        ledger_file = config.work_dir / "hash_ledger.json" if config.work_dir else None
        self.hash_ledger = HashLedger(ledger_file=ledger_file) if ledger_file else None

        # Create directories
        config.music_dir.mkdir(parents=True, exist_ok=True)
        config.output_dir.mkdir(parents=True, exist_ok=True)

    def _get_track_files(self) -> List[Path]:
        """Get available music files from music directory."""
        track_files = list(self.config.music_dir.glob("*.mp3"))
        if not track_files:
            track_files = list(self.config.music_dir.glob("*.wav"))
        if not track_files:
            track_files = list(self.config.music_dir.glob("*.flac"))
        return track_files

    def _select_style(self) -> tuple:
        """Select random style and genre from config."""
        if self.config.styles:
            style = random.choice(self.config.styles)
        else:
            style = "relaxing"
        if self.config.genres:
            genre = random.choice(self.config.genres)
        else:
            genre = "ambient"
        return style, genre

    def _scheduled_publish_at(self) -> str:
        """Calculate the scheduled publish timestamp in UTC."""
        scheduled = datetime.now(timezone.utc) + timedelta(days=self.config.youtube.publish_days)
        return scheduled.replace(microsecond=0).isoformat().replace("+00:00", "Z")

    def _render_video(self, style: str, genre: str) -> Optional[Path]:
        """Render video using video_renderer."""
        console.print("[cyan]🎬 Rendering video...[/]")

        # Check for duplicate source videos
        if self.hash_ledger and self.config.intro_video and self.config.loop_video:
            if self.hash_ledger.is_registered(
                intro_path=self.config.intro_video,
                loop_path=self.config.loop_video
            ):
                console.print("[yellow]⚠ Source videos already rendered, skipping duplicate...[/]")
                existing = self.hash_ledger.get_pair(
                    self.config.intro_video,
                    self.config.loop_video
                )
                if existing and existing.output_path:
                    console.print(f"[dim]  Previous output: {existing.output_path}[/]")
                return None

        # Check music directory
        track_files = self._get_track_files()
        if not track_files:
            console.print("[red]✗ No music files found in music directory![/]")
            return None

        console.print(f"[dim]  Found {len(track_files)} music file(s)[/]")

        # Setup paths
        tmp_dir = self.config.work_dir / "tmp"
        tmp_dir.mkdir(parents=True, exist_ok=True)

        duration_sec = parse_duration_to_seconds(self.config.target_duration)

        # Generate output filename
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_name = f"video_{style}_{genre}_{timestamp}.mp4"
        output_path = self.config.output_dir / output_name

        # Create FFmpeg runner
        run_log = tmp_dir / "run_log.txt"
        runner = FFmpegRunner(run_log)

        # Get codec config
        codec_config = get_best_encoder(self.config.codec)

        # Encode intro/loop if provided
        intro_norm = tmp_dir / f"intro_norm_{self.config.codec}.mp4"
        loop_norm = tmp_dir / f"loop_norm_{self.config.codec}.mp4"

        encoder = VideoEncoder(
            runner=runner,
            codec_config=codec_config,
            color_config=COLOR_BT709,
            width=1920,
            height=1080,
            fps=60
        )

        with Progress(
            SpinnerColumn(),
            TextColumn("[bold cyan]{task.description}[/]"),
            BarColumn(),
            TaskProgressColumn(),
            console=console
        ) as progress:
            # Encode intro
            if self.config.intro_video and self.config.intro_video.exists():
                task = progress.add_task("Encoding intro...", total=100)

                def update_intro(p):
                    progress.update(task, completed=p.percent)

                encoder.normalize_video(self.config.intro_video, intro_norm, update_intro)
                progress.update(task, completed=100)

            # Encode loop
            if self.config.loop_video and self.config.loop_video.exists():
                task = progress.add_task("Encoding loop...", total=100)

                def update_loop(p):
                    progress.update(task, completed=p.percent)

                encoder.normalize_video(self.config.loop_video, loop_norm, update_loop)
                progress.update(task, completed=100)

            # Concat video
            task = progress.add_task("Concatenating video...", total=100)
            video_only = encoder.concat_videos(
                intro_norm, loop_norm,
                duration_sec, tmp_dir
            )
            progress.update(task, completed=100)

            audio_selection = select_audio_for_theme(
                track_files,
                theme=self.config.theme,
                visual_inspection_enabled=False,
            )

            if audio_selection.theme:
                console.print(f"[dim]  Theme rules applied: {audio_selection.theme}[/]")
            if audio_selection.music_db is not None:
                console.print(f"[dim]  Background music gain: {audio_selection.music_db} dB[/]")
            if audio_selection.background_profile:
                console.print(f"[dim]  Background profile: {audio_selection.background_profile}[/]")

            # Process audio
            audio_processor = AudioProcessor(runner, tmp_dir)

            task = progress.add_task("Processing audio...", total=100)
            music_loop = audio_processor.create_music_loop(track_files, duration_sec)
            progress.update(task, completed=100)

            # Final mux
            task = progress.add_task("Final mux...", total=100)
            mux_video_audio(runner, video_only, music_loop, output_path)
            progress.update(task, completed=100)

        console.print(f"[green]✓ Video rendered: {output_path.name}[/]")
        
        # Register successful render in hash ledger
        if self.hash_ledger and self.config.intro_video and self.config.loop_video:
            self.hash_ledger.register(
                intro_path=self.config.intro_video,
                loop_path=self.config.loop_video,
                output_path=output_path
            )
            console.print(f"[dim]  Registered source hash in ledger[/]")
        
        return output_path

    def _upload_video(
        self,
        video_path: Path,
        style: str,
        genre: str,
        scheduled_publish_at: Optional[str] = None,
    ) -> Optional[str]:
        """Upload video to YouTube."""
        console.print("[cyan]📤 Uploading to YouTube...[/]")

        duration_sec = parse_duration_to_seconds(self.config.target_duration)
        duration_str = format_duration_for_title(duration_sec)

        # Format title and description
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
        if scheduled_publish_at is None:
            scheduled_publish_at = self._scheduled_publish_at()

        # Authenticate if needed
        if not self.youtube.youtube:
            self.youtube.authenticate()

        with Progress(
            SpinnerColumn(),
            TextColumn("[bold cyan]Uploading...[/]"),
            BarColumn(),
            TaskProgressColumn(),
            console=console
        ) as progress:
            task = progress.add_task("Uploading...", total=100)

            def update_progress(uploaded, total):
                if total > 0:
                    percent = (uploaded / total) * 100
                    progress.update(task, completed=percent)

            video_id = upload_with_exponential_backoff(
                self.youtube,
                video_path,
                title,
                description,
                tags,
                category_id=self.config.youtube.default_category,
                privacy_status="private",
                scheduled_publish_at=scheduled_publish_at,
                progress_callback=update_progress
            )

        if video_id:
            console.print(f"[green]✓ Uploaded! Video ID: {video_id}[/]")
            console.print(f"[dim]  https://youtube.com/watch?v={video_id}[/]")
            console.print(f"[dim]  Scheduled publish: {scheduled_publish_at}[/]")

        return video_id

    def run_once(self) -> bool:
        """
        Run one iteration of the pipeline.

        Returns:
            True if successful
        """
        try:
            # Select style/genre
            style, genre = self._select_style()
            console.print(f"\n[bold magenta]▶ Starting pipeline: {style} {genre}[/]\n")

            # Check music files
            track_files = self._get_track_files()
            if len(track_files) < 1:
                console.print("[red]✗ No music files found in music directory![/]")
                console.print("[dim]  Please add MP3/WAV/FLAC files to the music/ directory.[/]")
                return False

            # Render video
            video_path = self._render_video(style, genre)

            if not video_path or not video_path.exists():
                console.print("[red]✗ Video rendering failed[/]")
                return False

            # Upload to YouTube
            scheduled_publish_at = self._scheduled_publish_at()
            video_id = self._upload_video(video_path, style, genre, scheduled_publish_at)

            if video_id:
                # Record video
                self.state.add_video(
                    video_id=video_id,
                    title=f"{style} {genre}",
                    scheduled_publish_at=scheduled_publish_at,
                    genre=genre,
                    style=style,
                    duration=self.config.target_duration,
                    local_path=str(video_path)
                )
                self.state.mark_video_scheduled(video_id, scheduled_publish_at)

            console.print("\n[bold green]✓ Pipeline iteration complete![/]\n")
            return True

        except Exception as e:
            console.print(f"[red]✗ Pipeline error: {e}[/]")
            return False

    def run_continuous(self):
        """Run pipeline continuously."""
        console.print("[bold cyan]🔄 Starting continuous mode...[/]")
        console.print(f"[dim]   Delay between videos: {self.config.delay_between_videos}s[/]\n")

        iteration = 0

        while True:
            iteration += 1
            console.print(f"\n[bold]═══ Iteration {iteration} ═══[/]\n")

            success = self.run_once()

            if not success:
                console.print("[yellow]Retrying in 60 seconds...[/]")
                time.sleep(60)
                continue

            # Wait before next iteration
            console.print(f"[dim]Waiting {self.config.delay_between_videos}s before next video...[/]")
            time.sleep(self.config.delay_between_videos)


# ═══════════════════════════════════════════════════════════════════════════════
# Entry Point
# ═══════════════════════════════════════════════════════════════════════════════

def run_pipeline(config: PipelineConfig, continuous: bool = False):
    """Run the automation pipeline."""
    print_banner()

    pipeline = AutomationPipeline(config)
    print_stats(pipeline.state)

    if continuous:
        pipeline.run_continuous()
    else:
        pipeline.run_once()

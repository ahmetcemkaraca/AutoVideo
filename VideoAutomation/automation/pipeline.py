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
from datetime import datetime

from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn
from rich.table import Table
from rich import box

from .config import PipelineConfig
from .jamendo import JamendoClient, JamendoTrack, download_tracks_batch
from .youtube import YouTubeUploader, upload_with_exponential_backoff, CATEGORY_MUSIC
from .state import StateManager, filter_unused_tracks

# Import video renderer
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))
from video_renderer.main import run_interactive
from video_renderer.ffmpeg import FFmpegRunner, get_duration
from video_renderer.video import VideoEncoder
from video_renderer.audio import AudioProcessor, mux_video_audio
from video_renderer.config import get_best_encoder, COLOR_BT709


console = Console()


# ═══════════════════════════════════════════════════════════════════════════════
# Pipeline UI
# ═══════════════════════════════════════════════════════════════════════════════

BANNER = """
[bold cyan]╭──────────────────────────────────────────────────────────────╮
│[/]              [bold magenta]🤖 VIDEO AUTOMATION PIPELINE v1.0[/]              [bold cyan]│
│[/]         [dim]Jamendo Music • Video Renderer • YouTube Upload[/]       [bold cyan]│
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
    table.add_row("Tracks Used", str(stats["total_tracks"]))
    table.add_row("Unique Tracks", str(stats["unique_tracks"]))
    
    if state.last_run:
        table.add_row("Last Run", state.last_run[:19])
    
    console.print(table)
    console.print()


def print_track_list(tracks: List[JamendoTrack], title: str = "Downloaded Tracks"):
    """Print list of tracks."""
    table = Table(title=title, box=box.ROUNDED, border_style="green")
    table.add_column("#", style="dim", width=3)
    table.add_column("Track", max_width=30)
    table.add_column("Artist", max_width=20)
    table.add_column("Duration", width=8)
    
    for i, track in enumerate(tracks, 1):
        mins = track.duration // 60
        secs = track.duration % 60
        table.add_row(str(i), track.name[:30], track.artist_name[:20], f"{mins}:{secs:02d}")
    
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
    1. Search Jamendo for unused tracks
    2. Download tracks
    3. Render video with video_renderer
    4. Upload to YouTube
    5. Update state
    """
    
    def __init__(self, config: PipelineConfig):
        self.config = config
        self.state = StateManager(config.state_file)
        self.jamendo = JamendoClient(config.jamendo.api_key)
        self.youtube = YouTubeUploader(
            config.youtube.client_secrets_file,
            config.youtube.credentials_file
        )
        
        # Create directories
        config.music_dir.mkdir(parents=True, exist_ok=True)
        config.output_dir.mkdir(parents=True, exist_ok=True)
    
    def _select_mood_genre(self) -> tuple:
        """Select random mood and genre from config."""
        mood = random.choice(self.config.jamendo.moods)
        genre = random.choice(self.config.jamendo.genres)
        return mood, genre
    
    def _search_tracks(self, mood: str, genre: str, count: int) -> List[JamendoTrack]:
        """Search for unused tracks."""
        console.print(f"[cyan]🔍 Searching for {mood} {genre} tracks...[/]")
        
        # Search with larger limit to have room after filtering
        tracks = self.jamendo.search_by_mood_genre(
            mood=mood,
            genre=genre,
            limit=count * 3,  # Get more to filter
            min_duration=120,
        )
        
        # Filter out used tracks
        unused = filter_unused_tracks(tracks, self.state)
        
        console.print(f"[green]✓ Found {len(unused)} unused tracks (from {len(tracks)} total)[/]")
        
        return unused[:count]
    
    def _download_tracks(self, tracks: List[JamendoTrack]) -> List[Path]:
        """Download tracks to music directory."""
        # Clear music directory
        for f in self.config.music_dir.iterdir():
            if f.is_file():
                f.unlink()
        
        console.print(f"[cyan]⬇️  Downloading {len(tracks)} tracks...[/]")
        
        with Progress(
            SpinnerColumn(),
            TextColumn("[bold cyan]{task.description}[/]"),
            BarColumn(),
            TaskProgressColumn(),
            console=console
        ) as progress:
            task = progress.add_task("Downloading...", total=len(tracks))
            
            def on_complete(idx, track, path):
                progress.update(task, advance=1, description=f"Downloaded: {track.name[:30]}")
            
            paths = download_tracks_batch(
                self.jamendo,
                tracks,
                self.config.music_dir,
                delay_between=0.5,
                on_complete=on_complete
            )
        
        return paths
    
    def _render_video(self, mood: str, genre: str) -> Optional[Path]:
        """Render video using video_renderer."""
        console.print("[cyan]🎬 Rendering video...[/]")
        
        # Setup paths
        tmp_dir = self.config.work_dir / "tmp"
        tmp_dir.mkdir(parents=True, exist_ok=True)
        
        duration_sec = parse_duration_to_seconds(self.config.target_duration)
        
        # Generate output filename
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_name = f"video_{mood}_{genre}_{timestamp}.mp4"
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
            
            # Process audio
            audio_processor = AudioProcessor(runner, tmp_dir)
            track_files = list(self.config.music_dir.glob("*.mp3"))
            
            task = progress.add_task("Processing audio...", total=100)
            music_loop = audio_processor.create_music_loop(track_files, duration_sec)
            progress.update(task, completed=100)
            
            # Final mux
            task = progress.add_task("Final mux...", total=100)
            mux_video_audio(runner, video_only, music_loop, output_path)
            progress.update(task, completed=100)
        
        console.print(f"[green]✓ Video rendered: {output_path.name}[/]")
        return output_path
    
    def _upload_video(
        self,
        video_path: Path,
        mood: str,
        genre: str,
        track_names: List[str]
    ) -> Optional[str]:
        """Upload video to YouTube."""
        console.print("[cyan]📤 Uploading to YouTube...[/]")
        
        duration_sec = parse_duration_to_seconds(self.config.target_duration)
        duration_str = format_duration_for_title(duration_sec)
        
        # Format title and description
        title = self.config.youtube.title_template.format(
            duration=duration_str,
            mood=mood.capitalize(),
            genre=genre.capitalize()
        )
        
        # Build track credits
        track_credits = "\n".join([f"  • {name}" for name in track_names[:10]])
        
        description = self.config.youtube.description_template.format(
            duration=duration_str,
            mood=mood,
            genre=genre
        )
        description += f"\n\n🎵 Tracks used:\n{track_credits}"
        
        tags = self.config.youtube.default_tags + [mood, genre]
        
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
                progress_callback=update_progress
            )
        
        if video_id:
            console.print(f"[green]✓ Uploaded! Video ID: {video_id}[/]")
            console.print(f"[dim]  https://youtube.com/watch?v={video_id}[/]")
        
        return video_id
    
    def run_once(self) -> bool:
        """
        Run one iteration of the pipeline.
        
        Returns:
            True if successful
        """
        try:
            # Select mood/genre
            mood, genre = self._select_mood_genre()
            console.print(f"\n[bold magenta]▶ Starting pipeline: {mood} {genre}[/]\n")
            
            # Search and download tracks
            tracks = self._search_tracks(mood, genre, self.config.tracks_per_video)
            
            if len(tracks) < 3:
                console.print("[yellow]⚠ Not enough unused tracks found. Trying different genre...[/]")
                return False
            
            print_track_list(tracks)
            
            # Download tracks
            self._download_tracks(tracks)
            
            # Mark tracks as used
            for track in tracks:
                self.state.mark_track_used(track.id, track.name, track.artist_name)
            
            # Render video
            video_path = self._render_video(mood, genre)
            
            if not video_path or not video_path.exists():
                console.print("[red]✗ Video rendering failed[/]")
                return False
            
            # Upload to YouTube
            track_names = [f"{t.artist_name} - {t.name}" for t in tracks]
            video_id = self._upload_video(video_path, mood, genre, track_names)
            
            if video_id:
                # Record video
                self.state.add_video(
                    video_id=video_id,
                    title=f"{mood} {genre}",
                    track_ids=[t.id for t in tracks],
                    genre=genre,
                    mood=mood,
                    duration=self.config.target_duration,
                    local_path=str(video_path)
                )
            
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

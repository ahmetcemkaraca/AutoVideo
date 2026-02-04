#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Scheduler for video set rotation on single YouTube stream.
"""

import random
import time
from pathlib import Path
from typing import List, Optional, Tuple

from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TimeElapsedColumn
from rich.table import Table
from rich import box

from .config import GlobalConfig, VideoSet, PlaylistConfig
from .state import StateManager
from .mixer import AudioMixer, create_looped_concat_file, build_segment_stream_args
from .streamer import StreamManager, StreamStatus

console = Console()


# ═══════════════════════════════════════════════════════════════════════════════
# UI Helpers
# ═══════════════════════════════════════════════════════════════════════════════

BANNER = """
[bold cyan]╭──────────────────────────────────────────────────────────────╮
│[/]              [bold magenta]📺 YOUTUBE LIVESTREAM v1.0[/]                    [bold cyan]│
│[/]         [dim]Single stream, rotating video sets[/]                [bold cyan]│
╰──────────────────────────────────────────────────────────────╯[/]
"""

def print_banner():
    console.print(BANNER)


def print_video_sets(sets: List[VideoSet]):
    """Print available video sets."""
    table = Table(title="Video Sets", box=box.ROUNDED, border_style="cyan")
    table.add_column("#", style="dim", width=3)
    table.add_column("Name", style="bold")
    table.add_column("Playlists", justify="center")
    table.add_column("Music", justify="right")
    table.add_column("BG", justify="right")
    
    for i, vs in enumerate(sets, 1):
        playlists = vs.load_playlists()
        music_count = len(list(vs.music_dir.glob("*.*"))) if vs.music_dir.exists() else 0
        bg_count = len(list(vs.bg_dir.glob("*.*"))) if vs.bg_dir.exists() else 0
        
        table.add_row(str(i), vs.name, str(len(playlists)), str(music_count), str(bg_count))
    
    console.print(table)
    console.print()


def print_now_playing(video_set: VideoSet, playlist: PlaylistConfig, duration_min: int, segment: int):
    """Print current playing info."""
    console.print(Panel(
        f"[bold cyan]Video Set:[/] {video_set.name}\n"
        f"[bold green]Playlist:[/] {playlist.name}\n"
        f"[bold magenta]Duration:[/] {duration_min} minutes\n"
        f"[dim]Tracks: {len(playlist.tracks)} | Backgrounds: {len(playlist.backgrounds)}[/]",
        title=f"[bold]▶ Segment {segment}[/]",
        border_style="green"
    ))


# ═══════════════════════════════════════════════════════════════════════════════
# Scheduler
# ═══════════════════════════════════════════════════════════════════════════════

class LivestreamScheduler:
    """
    Manages single-stream video set rotation.
    
    Flow:
    1. Play intro for video set
    2. Loop video + music + bg for duration
    3. Switch to next video set
    4. Repeat forever
    """
    
    def __init__(self, config: GlobalConfig):
        self.config = config
        self.state = StateManager(config.state_file)
        self.video_sets = config.discover_video_sets()
        self.stream_manager = StreamManager()
        self.tmp_dir = config.content_dir.parent / "tmp"
        self.tmp_dir.mkdir(parents=True, exist_ok=True)
        
        self._should_stop = False
    
    def get_next_video_set(self) -> Tuple[VideoSet, int]:
        """Get next video set to stream."""
        if not self.video_sets:
            raise ValueError("No video sets found")
        
        idx = self.state.get_current_channel_index() % len(self.video_sets)
        return self.video_sets[idx], idx
    
    def get_next_playlist(self, video_set: VideoSet) -> Tuple[PlaylistConfig, int]:
        """Get next playlist for a video set."""
        playlists = video_set.load_playlists()
        if not playlists:
            raise ValueError(f"No playlists in {video_set.name}")
        
        ch_state = self.state.get_channel_state(video_set.name)
        idx = ch_state.current_playlist_index % len(playlists)
        return playlists[idx], idx
    
    def get_segment_duration(self) -> int:
        """Get random duration between min and max."""
        return random.randint(
            self.config.min_duration_minutes,
            self.config.max_duration_minutes
        )
    
    def prepare_segment(
        self,
        video_set: VideoSet,
        playlist: PlaylistConfig,
        duration_minutes: int,
        with_intro: bool = True
    ) -> List[str]:
        """Prepare FFmpeg arguments for streaming."""
        duration_seconds = duration_minutes * 60
        
        # Get track files
        track_files = playlist.get_track_files(video_set.music_dir)
        if not track_files:
            # Fallback: all music files
            for ext in [".mp3", ".wav", ".flac", ".m4a"]:
                track_files.extend(video_set.music_dir.glob(f"*{ext}"))
        
        if not track_files:
            raise ValueError(f"No music in {video_set.name}")
        
        # Create music concat
        mixer = AudioMixer(self.tmp_dir)
        music_concat = mixer.create_music_concat(track_files)
        
        # Get backgrounds
        bg_files = playlist.get_background_files(video_set.bg_dir)
        bg_concat = None
        bg_gain = -8.0
        
        if bg_files:
            bg_path, bg_gain = bg_files[0]
            bg_concat = self.tmp_dir / "bg_concat.txt"
            create_looped_concat_file([bg_path], bg_concat)
        
        # Build FFmpeg args
        # with_intro: first play intro, then loop
        if with_intro:
            from .mixer import build_ffmpeg_stream_args
            return build_ffmpeg_stream_args(
                intro_video=video_set.intro_video,
                loop_video=video_set.loop_video,
                music_concat=music_concat,
                bg_concat=bg_concat,
                bg_gain_db=bg_gain,
                rtmp_url=self.config.stream.full_rtmp_url,
                video_bitrate=self.config.stream.video_bitrate,
                audio_bitrate=self.config.stream.audio_bitrate,
                resolution=self.config.stream.resolution,
                fps=self.config.stream.fps,
                preset=self.config.stream.preset,
                duration_seconds=duration_seconds,
            )
        else:
            return build_segment_stream_args(
                loop_video=video_set.loop_video,
                music_concat=music_concat,
                bg_concat=bg_concat,
                bg_gain_db=bg_gain,
                rtmp_url=self.config.stream.full_rtmp_url,
                duration_seconds=duration_seconds,
                video_bitrate=self.config.stream.video_bitrate,
                audio_bitrate=self.config.stream.audio_bitrate,
                resolution=self.config.stream.resolution,
                fps=self.config.stream.fps,
                preset=self.config.stream.preset,
            )
    
    def stream_segment(
        self,
        video_set: VideoSet,
        playlist: PlaylistConfig,
        duration_minutes: int,
        with_intro: bool = True
    ) -> bool:
        """Stream a single segment."""
        try:
            args = self.prepare_segment(video_set, playlist, duration_minutes, with_intro)
            
            console.print(f"\n[cyan]🎬 Starting segment ({duration_minutes} min)...[/]")
            if with_intro:
                console.print(f"[dim]   Playing intro → loop[/]")
            
            with Progress(
                SpinnerColumn(),
                TextColumn("[bold cyan]{task.description}[/]"),
                BarColumn(),
                TimeElapsedColumn(),
                console=console
            ) as progress:
                task = progress.add_task(
                    f"Streaming: {video_set.name}",
                    total=duration_minutes * 60
                )
                
                def on_status(status: StreamStatus):
                    progress.update(task, completed=status.duration_seconds)
                
                success = self.stream_manager.stream_segment(
                    args,
                    duration_minutes * 60,
                    on_status=on_status,
                )
            
            return success
            
        except Exception as e:
            console.print(f"[red]Stream error: {e}[/]")
            return False
    
    def run(self):
        """Run infinite livestream."""
        print_banner()
        
        if not self.video_sets:
            console.print("[red]No video sets found! Add sets to content/ directory.[/]")
            return
        
        print_video_sets(self.video_sets)
        console.print("[bold green]▶ Starting infinite livestream...[/]\n")
        
        segment_number = 0
        
        while not self._should_stop:
            try:
                segment_number += 1
                
                # Get video set and playlist
                video_set, vs_idx = self.get_next_video_set()
                playlist, pl_idx = self.get_next_playlist(video_set)
                duration = self.get_segment_duration()
                
                console.print(f"\n[bold]{'═' * 50}[/]")
                print_now_playing(video_set, playlist, duration, segment_number)
                
                # Stream with intro (each video set starts with its intro)
                success = self.stream_segment(video_set, playlist, duration, with_intro=True)
                
                if success:
                    # Advance to next playlist for this set
                    self.state.advance_playlist(video_set.name, len(video_set.load_playlists()))
                    self.state.record_rotation()
                    
                    # Move to next video set
                    next_idx = (vs_idx + 1) % len(self.video_sets)
                    self.state.set_current_channel_index(next_idx)
                    
                    console.print(f"[green]✓ Segment complete[/]")
                    console.print(f"[dim]   Next: {self.video_sets[next_idx].name}[/]")
                else:
                    console.print("[yellow]⚠ Segment failed. Retrying...[/]")
                    time.sleep(5)
                    
            except KeyboardInterrupt:
                console.print("\n[yellow]Interrupted.[/]")
                break
            except Exception as e:
                console.print(f"[red]Error: {e}[/]")
                time.sleep(10)
        
        self.stream_manager.stop()
        console.print("\n[bold]Stream ended.[/]")
    
    def stop(self):
        self._should_stop = True
        self.stream_manager.stop()

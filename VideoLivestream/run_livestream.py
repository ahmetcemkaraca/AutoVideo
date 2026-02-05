#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
YouTube Livestream - CLI Entry Point

Tek YouTube kanalında sonsuz canlı yayın.
Video setleri (intro+loop+music+bg) 1-3 saat aralıklarla değişir.

Usage:
    python run_livestream.py --init        # Config + örnek set oluştur
    python run_livestream.py --generate    # Playlist JSON'ları oluştur
    python run_livestream.py               # YAYIN BAŞLAT
"""

import argparse
import sys
from pathlib import Path
import os

# Ensure project root is in path
project_root = Path(__file__).parent.absolute()
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from livestream.config import GlobalConfig, DEFAULT_CONFIG, generate_playlists
from livestream.scheduler import LivestreamScheduler, print_banner, print_video_sets
from livestream.state import StateManager

from rich.console import Console

console = Console()


def init_config(path: Path):
    """Create sample configuration."""
    if path.exists():
        console.print(f"[yellow]Config exists: {path}[/]")
        return
    
    path.write_text(DEFAULT_CONFIG, encoding="utf-8")
    console.print(f"[green]✓ Created: {path}[/]")


def create_sample_set(content_dir: Path):
    """Create sample video set structure."""
    sample = content_dir / "sample_set"
    sample.mkdir(parents=True, exist_ok=True)
    (sample / "music").mkdir(exist_ok=True)
    (sample / "bg").mkdir(exist_ok=True)
    (sample / "playlists").mkdir(exist_ok=True)
    
    console.print(f"[green]✓ Created sample set: {sample}[/]")
    console.print("[dim]   Add: intro.mp4, loop.mp4, music/*.mp3, bg/*.mp3[/]")


def generate_all_playlists(config: GlobalConfig):
    """Generate playlists for all video sets."""
    sets = config.discover_video_sets()
    
    if not sets:
        console.print("[yellow]No video sets found.[/]")
        return
    
    for vs in sets:
        console.print(f"[cyan]Generating for: {vs.name}[/]")
        count = generate_playlists(vs, count=10)
        console.print(f"[green]  ✓ {count} playlists[/]")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="YouTube Livestream - Rotating Video Sets",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python run_livestream.py --init        # Setup
  python run_livestream.py --generate    # Create playlists
  python run_livestream.py               # Start streaming
        """
    )
    
    parser.add_argument("--config", "-c", type=Path, default=Path("config.json"))
    parser.add_argument("--init", action="store_true", help="Create config + sample set")
    parser.add_argument("--generate", "-g", action="store_true", help="Generate playlists")
    parser.add_argument("--list", "-l", action="store_true", help="List video sets")
    parser.add_argument("--stats", action="store_true", help="Show statistics")
    parser.add_argument("--dry-run", action="store_true", help="Show what would stream")
    
    args = parser.parse_args()
    
    # --init
    if args.init:
        print_banner()
        init_config(args.config)
        create_sample_set(Path("./content"))
        return 0
    
    # Load config
    if not args.config.exists():
        console.print(f"[red]Config not found: {args.config}[/]")
        console.print("[dim]Run: python run_livestream.py --init[/]")
        return 1
    
    try:
        config = GlobalConfig.from_file(args.config)
    except Exception as e:
        console.print(f"[red]Config error: {e}[/]")
        return 1
    
    # --generate
    if args.generate:
        print_banner()
        generate_all_playlists(config)
        return 0
    
    # --list
    if args.list:
        print_banner()
        sets = config.discover_video_sets()
        print_video_sets(sets)
        return 0
    
    # --stats
    if args.stats:
        print_banner()
        state = StateManager(config.state_file)
        stats = state.stats
        console.print(f"Total segments: {stats['total_segments']}")
        console.print(f"Started: {stats['started_at'] or 'Never'}")
        console.print(f"Last rotation: {stats['last_rotation'] or 'Never'}")
        return 0
    
    # --dry-run
    if args.dry_run:
        print_banner()
        scheduler = LivestreamScheduler(config)
        if not scheduler.video_sets:
            console.print("[red]No video sets[/]")
            return 1
        vs, _ = scheduler.get_next_video_set()
        pl, _ = scheduler.get_next_playlist(vs)
        dur = scheduler.get_segment_duration()
        console.print(f"[bold]Would stream:[/]")
        console.print(f"  Set: {vs.name}")
        console.print(f"  Playlist: {pl.name}")
        console.print(f"  Duration: {dur} min")
        return 0
    
    # Validate
    if not config.stream.stream_key or config.stream.stream_key == "YOUR_YOUTUBE_STREAM_KEY":
        console.print("[red]YouTube stream key not set in config.json[/]")
        return 1
        
    if len(config.stream.stream_key) < 10:
        console.print("[red]Invalid YouTube stream key (too short)[/]")
        return 1
    
    sets = config.discover_video_sets()
    if not sets:
        console.print("[red]No video sets in content/ directory[/]")
        return 1
    
    # Run
    try:
        scheduler = LivestreamScheduler(config)
        scheduler.run()
        return 0
    except KeyboardInterrupt:
        console.print("\n[yellow]Stopped.[/]")
        return 130


if __name__ == "__main__":
    sys.exit(main())

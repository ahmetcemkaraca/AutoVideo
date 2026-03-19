#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Video Automation - CLI Entry Point

Automated video production pipeline:
1. Use local music files from music directory
2. Render video with intro+loop
3. Upload to YouTube

Usage:
    python run_automation.py --config config.json
    python run_automation.py --config config.json --continuous
    python run_automation.py --init  # Create sample config
"""

import argparse
import sys
from pathlib import Path

from automation.config import PipelineConfig, DEFAULT_CONFIG_TEMPLATE
from automation.pipeline import run_pipeline, print_banner
from automation.state import StateManager

from rich.console import Console

console = Console()


def init_config(path: Path):
    """Create sample configuration file."""
    if path.exists():
        console.print(f"[yellow]Config file already exists: {path}[/]")
        return

    path.write_text(DEFAULT_CONFIG_TEMPLATE, encoding="utf-8")
    console.print(f"[green]✓ Created sample config: {path}[/]")
    console.print("[dim]  Edit this file with your settings and add music files to the music/ directory.[/]")


def validate_config(config: PipelineConfig) -> bool:
    """Validate configuration before running."""
    errors = []

    if not Path(config.youtube.client_secrets_file).exists():
        errors.append(f"YouTube client secrets file not found: {config.youtube.client_secrets_file}")

    if config.intro_video and not config.intro_video.exists():
        errors.append(f"Intro video not found: {config.intro_video}")

    if config.loop_video and not config.loop_video.exists():
        errors.append(f"Loop video not found: {config.loop_video}")

    # Check music directory
    if not config.music_dir.exists():
        errors.append(f"Music directory not found: {config.music_dir}")
    else:
        music_files = list(config.music_dir.glob("*.mp3")) + list(config.music_dir.glob("*.wav")) + list(config.music_dir.glob("*.flac"))
        if not music_files:
            errors.append(f"No music files found in: {config.music_dir}")

    if errors:
        console.print("[bold red]Configuration errors:[/]")
        for err in errors:
            console.print(f"  [red]• {err}[/]")
        return False

    return True


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Video Automation Pipeline",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python run_automation.py --init                    # Create sample config
  python run_automation.py --config config.json     # Run once
  python run_automation.py --config config.json -c  # Run continuously
  python run_automation.py --config config.json --publish-days 5
  python run_automation.py --stats                   # Show statistics
        """
    )

    parser.add_argument(
        "--config", "-f",
        type=Path,
        default=Path("config.json"),
        help="Path to configuration file"
    )

    parser.add_argument(
        "--init",
        action="store_true",
        help="Create sample configuration file"
    )

    parser.add_argument(
        "--continuous", "-c",
        action="store_true",
        help="Run continuously (loop forever)"
    )

    parser.add_argument(
        "--stats",
        action="store_true",
        help="Show pipeline statistics"
    )

    parser.add_argument(
        "--auth-youtube",
        action="store_true",
        help="Authenticate with YouTube (run once to setup)"
    )

    parser.add_argument(
        "--publish-days",
        type=int,
        default=None,
        help="Override scheduled publish delay in days"
    )

    parser.add_argument(
        "--theme",
        type=str,
        default=None,
        help="Apply deterministic audio rules for a theme such as jazz, medieval, or lofi"
    )

    parser.add_argument(
        "--sync",
        action="store_true",
        help="Sync assets from Google Drive folder before running"
    )

    parser.add_argument(
        "--sync-force",
        action="store_true",
        help="Force re-download all files during sync"
    )

    parser.add_argument(
        "--cleanup",
        action="store_true",
        help="Clean up temporary files before running"
    )

    parser.add_argument(
        "--cleanup-dry-run",
        action="store_true",
        help="Show what would be cleaned without deleting"
    )

    args = parser.parse_args()

    # Handle --init
    if args.init:
        print_banner()
        init_config(args.config)
        return 0

    # Load config
    if not args.config.exists():
        console.print(f"[red]Config file not found: {args.config}[/]")
        console.print("[dim]Run with --init to create a sample config file.[/]")
        return 1

    try:
        config = PipelineConfig.from_file(args.config)
    except Exception as e:
        console.print(f"[red]Error loading config: {e}[/]")
        return 1

    if args.publish_days is not None:
        if args.publish_days < 0:
            console.print("[red]publish-days must be zero or greater[/]")
            return 1
        config.youtube.scheduled_publish_days = args.publish_days

    if args.theme is not None:
        config.theme = args.theme.lower()

    # Handle --sync
    if args.sync:
        print_banner()
        console.print("[cyan]🔄 Syncing assets from Google Drive...[/]")
        
        from video_renderer.drive_sync import DriveSyncService
        
        folder_id = getattr(config, 'drive_folder_id', None)
        if not folder_id:
            folder_id = "1KIzD1pnY6Kat-HIIAsCcGH_uqNXQnzp6"
        
        work_dir = config.work_dir or Path.cwd()
        sync_service = DriveSyncService(
            root_folder_id=folder_id,
            base_dir=work_dir
        )
        
        result = sync_service.sync()
        
        console.print(f"[green]✓ Sync complete:[/]")
        console.print(f"  [dim]Downloaded: {len(result.downloaded)} files[/]")
        console.print(f"  [dim]Skipped: {len(result.skipped)} files[/]")
        
        if result.errors:
            console.print(f"[yellow]  Errors: {len(result.errors)}[/]")
            for err in result.errors:
                console.print(f"    [red]• {err}[/]")
        
        if not args.continuous:
            return 0 if not result.errors else 1

    # Handle --cleanup
    if args.cleanup or args.cleanup_dry_run:
        print_banner()
        console.print("[cyan]🧹 Cleaning up temporary files...[/]")
        
        from video_renderer.ffmpeg import cleanup_temp_files, get_tmp_dir_size
        
        tmp_dir = (config.work_dir or Path.cwd()) / "tmp"
        
        if args.cleanup_dry_run:
            result = cleanup_temp_files(
                tmp_dir=tmp_dir,
                min_age_hours=0,
                dry_run=True
            )
            console.print(f"[yellow]DRY RUN - No files deleted[/]")
        else:
            result = cleanup_temp_files(
                tmp_dir=tmp_dir,
                min_age_hours=1.0
            )
        
        console.print(f"[green]✓ Cleanup complete:[/]")
        console.print(f"  [dim]Files: {len(result.deleted_files)}[/]")
        console.print(f"  [dim]Size: {result.deleted_size_mb:.1f} MB[/]")
        
        if result.skipped_files:
            console.print(f"  [dim]Skipped: {len(result.skipped_files)} files (too recent)[/]")
        
        if result.errors:
            console.print(f"[yellow]  Errors: {len(result.errors)}[/]")
            for err in result.errors:
                console.print(f"    [red]• {err}[/]")
        
        return 0

    # Handle --stats
    if args.stats:
        print_banner()
        state = StateManager(config.state_file)
        from automation.pipeline import print_stats
        print_stats(state)
        return 0

    # Handle --auth-youtube
    if args.auth_youtube:
        print_banner()
        console.print("[cyan]🔐 Authenticating with YouTube...[/]")

        from automation.youtube import YouTubeUploader
        uploader = YouTubeUploader(
            config.youtube.client_secrets_file,
            config.youtube.credentials_file
        )

        try:
            uploader.authenticate()
            channel = uploader.get_channel_info()
            if channel:
                title = channel.get("snippet", {}).get("title", "Unknown")
                console.print(f"[green]✓ Authenticated as: {title}[/]")
            return 0
        except Exception as e:
            console.print(f"[red]Authentication failed: {e}[/]")
            return 1

    # Validate config
    if not validate_config(config):
        return 1

    # Run pipeline
    try:
        run_pipeline(config, continuous=args.continuous)
        return 0
    except KeyboardInterrupt:
        console.print("\n[yellow]Interrupted by user.[/]")
        return 130
    except Exception as e:
        console.print(f"[red]Pipeline error: {e}[/]")
        return 1


if __name__ == "__main__":
    sys.exit(main())

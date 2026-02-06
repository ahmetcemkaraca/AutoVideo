#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Video Automation v2 - CLI Entry Point

Production-ready automated video production pipeline:
1. Use local music files from music directory
2. Render video with intro+loop
3. Upload to YouTube with comprehensive error handling

Usage:
    python run_automation_v2.py --config config.json
    python run_automation_v2.py --config config.json --continuous
    python run_automation_v2.py --init  # Create sample config
"""

import argparse
import sys
import logging
from pathlib import Path
from typing import Optional

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich import box

# Import v2 components
from automation.config_v2 import (
    PipelineConfig, DEFAULT_CONFIG_TEMPLATE, validate_with_schema
)
from automation.pipeline_v2 import (
    run_pipeline, print_banner, print_stats, BANNER
)
from automation.state_v2 import StateManager

console = Console()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def init_config(path: Path, use_v2: bool = True):
    """
    Create sample configuration file.

    Args:
        path: Path where config should be created
        use_v2: Create v2 config with all features
    """
    if path.exists():
        console.print(f"[yellow]Config file already exists: {path}[/]")
        response = console.input("[dim]Overwrite? [y/N]: [/]")
        if response.lower() != 'y':
            return

    if use_v2:
        path.write_text(DEFAULT_CONFIG_TEMPLATE, encoding="utf-8")
    else:
        # Create minimal v1-compatible config
        minimal_template = """{
  "work_dir": ".",
  "intro_video": "intro.mp4",
  "loop_video": "loop.mp4",
  "target_duration": "08:00:00",
  "codec": "av1",
  "continuous_mode": false,
  "delay_between_videos": 300,
  "styles": ["relaxing", "calm", "peaceful", "meditative"],
  "genres": ["ambient", "classical", "electronic", "jazz", "chillout"],
  "youtube": {
    "client_secrets_file": "client_secrets.json",
    "title_template": "{duration} {style} Music | {genre}",
    "description_template": "🎵 {duration} of {style} {genre} music...",
    "tags": ["relaxing music", "ambient"]
  }
}
"""
        path.write_text(minimal_template, encoding="utf-8")

    console.print(f"[green]✓ Created config: {path}[/]")
    console.print("[dim]  Edit this file with your settings and add music files to the music/ directory.[/]")


def validate_config(config: PipelineConfig, verbose: bool = True) -> tuple[bool, list[str]]:
    """
    Validate configuration before running.

    Returns:
        Tuple of (is_valid, list_of_errors)
    """
    errors = []

    # Run config validation
    config_errors = config.validate()
    errors.extend(config_errors)

    # Check required files
    missing_files = config.check_files_exist()
    errors.extend([f"Missing file: {f}" for f in missing_files])

    # Check music files
    music_files, music_errors = config.check_music_files()
    errors.extend(music_errors)

    # Validate with JSON schema
    try:
        import jsonschema
    except ImportError:
        pass
    else:
        with open(config.work_dir / "config.json", "r") as f:
            import json
            config_data = json.load(f)
            schema_valid, schema_errors = validate_with_schema(config_data)
            errors.extend(schema_errors)

    is_valid = len(errors) == 0

    if verbose and not is_valid:
        console.print("[bold red]Configuration validation failed:[/]")
        for i, error in enumerate(errors, 1):
            console.print(f"  [red]{i}. {error}[/]")

    return is_valid, errors


def repair_config(path: Path) -> bool:
    """
    Attempt to repair a corrupted configuration file.

    Returns:
        True if repair was successful
    """
    console.print(f"[yellow]Attempting to repair config: {path}[/]")

    try:
        # Try to load as JSON
        import json

        with open(path, "r") as f:
            data = json.load(f)

        # Check for version
        if "version" not in data:
            console.print("[dim]  Adding version field...[/]")
            data["version"] = 2
            data["format_version"] = "2.0"

        # Ensure render config exists
        if "render" not in data:
            console.print("[dim]  Adding render config...[/]")
            data["render"] = {
                "codec": data.get("codec", "av1"),
                "target_duration": data.get("target_duration", "08:00:00"),
                "width": 1920,
                "height": 1080,
                "fps": 60
            }

        # Backup original
        backup_path = path.with_suffix(".json.backup")
        import shutil
        shutil.copy2(path, backup_path)
        console.print(f"[dim]  Backed up original to: {backup_path}[/]")

        # Write repaired config
        with open(path, "w") as f:
            json.dump(data, f, indent=2)

        console.print("[green]✓ Config repaired successfully[/]")
        return True

    except Exception as e:
        console.print(f"[red]Failed to repair config: {e}[/]")
        return False


def show_dashboard(config: PipelineConfig):
    """Show monitoring dashboard with current state."""
    print_banner()

    state = StateManager(config.state_file)

    # Create stats table
    stats = state.stats

    stats_table = Table(title="Pipeline Statistics", box=box.ROUNDED, border_style="cyan")
    stats_table.add_column("Metric", style="dim")
    stats_table.add_column("Value", style="bold")

    stats_table.add_row("Total Videos Created", str(stats.total_videos_created))
    stats_table.add_row("Uploads Attempted", str(stats.total_uploads_attempted))
    stats_table.add_row("Uploads Successful", str(stats.total_uploads_successful))
    stats_table.add_row("Uploads Failed", str(stats.total_uploads_failed))

    if stats.total_render_time_seconds > 0:
        avg = stats.total_render_time_seconds / max(1, stats.total_videos_created)
        stats_table.add_row("Avg Render Time", f"{avg:.1f}s")

    if stats.total_upload_time_seconds > 0:
        avg = stats.total_upload_time_seconds / max(1, stats.total_uploads_successful)
        stats_table.add_row("Avg Upload Time", f"{avg:.1f}s")

    stats_table.add_row("Consecutive Failures", str(stats.consecutive_failures))
    stats_table.add_row("Consecutive Successes", str(stats.consecutive_successes))

    if stats.last_run:
        stats_table.add_row("Last Run", stats.last_run[:19])
    if stats.last_success:
        stats_table.add_row("Last Success", stats.last_success[:19])
    if stats.last_failure:
        stats_table.add_row("Last Failure", stats.last_failure[:19])

    console.print(stats_table)

    # Show recent videos
    videos = state.get_all_videos()
    if videos:
        video_table = Table(title="Recent Videos", box=box.SIMPLE)
        video_table.add_column("Created", style="dim")
        video_table.add_column("Title")
        video_table.add_column("Status", style="bold")

        # Show last 10
        for video_id, video in sorted(
            videos.items(),
            key=lambda x: x[1].created_at,
            reverse=True
        )[:10]:
            created = video.created_at[:19]
            title = video.title[:40]

            if video.uploaded_at:
                status = "[green]Uploaded[/]"
            elif video.last_error:
                status = "[red]Failed[/]"
            else:
                status = "[yellow]Pending[/]"

            video_table.add_row(created, title, status)

        console.print()
        console.print(video_table)

    # Show health status
    health_color = "green" if state.is_healthy else "red"
    health_status = "Healthy" if state.is_healthy else "Unhealthy"

    console.print()
    console.print(Panel(
        f"[bold {health_color}]{health_status}[/] - {state.video_count} videos tracked",
        title="State Health",
        border_style=health_color
    ))


def export_state(config: PipelineConfig, output_path: Path):
    """Export state to JSON file."""
    state = StateManager(config.state_file)
    json_data = state.export_json()

    output_path.write_text(json_data, encoding="utf-8")
    console.print(f"[green]✓ State exported to: {output_path}[/]")


def import_state(config: PipelineConfig, input_path: Path, merge: bool = False):
    """Import state from JSON file."""
    state = StateManager(config.state_file)
    json_data = input_path.read_text(encoding="utf-8")

    state.import_json(json_data, merge=merge)
    console.print(f"[green]✓ State imported from: {input_path}[/]")


def main() -> int:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Video Automation Pipeline v2 - Production Ready",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Initialize configuration
  python run_automation_v2.py --init

  # Validate configuration
  python run_automation_v2.py --validate

  # Run single iteration
  python run_automation_v2.py --config config.json

  # Run continuously
  python run_automation_v2.py --config config.json --continuous

  # Show statistics
  python run_automation_v2.py --stats

  # Authenticate with YouTube
  python run_automation_v2.py --auth-youtube

  # Export/Import state
  python run_automation_v2.py --export-state backup.json
  python run_automation_v2.py --import-state backup.json
        """
    )

    parser.add_argument(
        "--config", "-f",
        type=Path,
        default=Path("config.json"),
        help="Path to configuration file (default: config.json)"
    )

    parser.add_argument(
        "--init",
        action="store_true",
        help="Create sample configuration file"
    )

    parser.add_argument(
        "--validate",
        action="store_true",
        help="Validate configuration and exit"
    )

    parser.add_argument(
        "--repair",
        action="store_true",
        help="Attempt to repair configuration file"
    )

    parser.add_argument(
        "--continuous", "-c",
        action="store_true",
        help="Run continuously (loop forever)"
    )

    parser.add_argument(
        "--max-iterations",
        type=int,
        help="Maximum iterations in continuous mode"
    )

    parser.add_argument(
        "--stats",
        action="store_true",
        help="Show pipeline statistics and exit"
    )

    parser.add_argument(
        "--dashboard",
        action="store_true",
        help="Show monitoring dashboard"
    )

    parser.add_argument(
        "--auth-youtube",
        action="store_true",
        help="Authenticate with YouTube (run once to setup)"
    )

    parser.add_argument(
        "--export-state",
        type=Path,
        metavar="PATH",
        help="Export state to JSON file"
    )

    parser.add_argument(
        "--import-state",
        type=Path,
        metavar="PATH",
        help="Import state from JSON file"
    )

    parser.add_argument(
        "--merge-state",
        action="store_true",
        help="Merge imported state instead of replacing"
    )

    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable verbose output"
    )

    args = parser.parse_args()

    # Handle --init
    if args.init:
        print_banner()
        init_config(args.config)
        return 0

    # Check config exists
    if not args.config.exists():
        console.print(f"[red]Config file not found: {args.config}[/]")
        console.print("[dim]Run with --init to create a sample config file.[/]")
        return 1

    # Load config
    try:
        config = PipelineConfig.from_file(args.config)
    except Exception as e:
        console.print(f"[red]Error loading config: {e}[/]")

        # Offer to repair
        if args.repair or console.input("[dim]Attempt repair? [y/N]: [/]").lower() == 'y':
            if repair_config(args.config):
                # Retry loading
                try:
                    config = PipelineConfig.from_file(args.config)
                except Exception as e2:
                    console.print(f"[red]Still failed after repair: {e2}[/]")
                    return 1
            else:
                return 1
        else:
            return 1

    # Override max iterations if specified
    if args.max_iterations:
        config.max_continuous_iterations = args.max_iterations

    # Handle --validate
    if args.validate:
        is_valid, errors = validate_config(config, verbose=True)
        return 0 if is_valid else 1

    # Handle --stats/--dashboard
    if args.stats or args.dashboard:
        show_dashboard(config)
        return 0

    # Handle --auth-youtube
    if args.auth_youtube:
        print_banner()
        console.print("[cyan]🔐 Authenticating with YouTube...[/]")

        from automation.youtube_v2 import YouTubeUploader
        uploader = YouTubeUploader(
            config.youtube.client_secrets_file,
            config.youtube.credentials_file
        )

        try:
            uploader.authenticate()
            channel = uploader.get_channel_info()
            if channel:
                title = channel.get("snippet", {}).get("title", "Unknown")
                subs = channel.get("statistics", {}).get("subscriberCount", "N/A")
                console.print(f"[green]✓ Authenticated as: {title}[/]")
                console.print(f"[dim]  Subscribers: {subs}[/]")
            return 0
        except Exception as e:
            console.print(f"[red]Authentication failed: {e}[/]")
            logger.exception("Authentication failed")
            return 1

    # Handle --export-state
    if args.export_state:
        export_state(config, args.export_state)
        return 0

    # Handle --import-state
    if args.import_state:
        import_state(config, args.import_state, args.merge_state)
        return 0

    # Validate config before running
    is_valid, errors = validate_config(config, verbose=not args.verbose)
    if not is_valid:
        console.print("[red]Configuration validation failed. Run with --validate for details.[/]")
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
        logger.exception("Pipeline failed")
        return 1


if __name__ == "__main__":
    sys.exit(main())

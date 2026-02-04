#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Video Automation - CLI Entry Point

Automated video production pipeline:
1. Search Jamendo for royalty-free music
2. Download unused tracks
3. Render video with intro+loop
4. Upload to YouTube

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
    console.print("[dim]  Edit this file with your API keys and settings.[/]")


def validate_config(config: PipelineConfig) -> bool:
    """Validate configuration before running."""
    errors = []
    
    if not config.jamendo.api_key or config.jamendo.api_key == "YOUR_JAMENDO_API_KEY":
        errors.append("Jamendo API key is not set")
    
    if not Path(config.youtube.client_secrets_file).exists():
        errors.append(f"YouTube client secrets file not found: {config.youtube.client_secrets_file}")
    
    if config.intro_video and not config.intro_video.exists():
        errors.append(f"Intro video not found: {config.intro_video}")
    
    if config.loop_video and not config.loop_video.exists():
        errors.append(f"Loop video not found: {config.loop_video}")
    
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

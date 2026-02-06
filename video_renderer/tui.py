#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Rich Terminal UI components for video renderer.
"""

from pathlib import Path
from typing import List, Optional, Tuple, Any, Callable

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.progress import (
    Progress,
    SpinnerColumn,
    BarColumn,
    TextColumn,
    TimeRemainingColumn,
    TaskProgressColumn,
    MofNCompleteColumn,
    ProgressColumn,
    Task,
)
from rich.prompt import Prompt, IntPrompt, Confirm
from rich.text import Text
from rich.style import Style
from rich.theme import Theme
from rich import box

from .ffmpeg import VideoInfo

# ═══════════════════════════════════════════════════════════════════════════════
# Theme & Console
# ═══════════════════════════════════════════════════════════════════════════════

CUSTOM_THEME = Theme(
    {
        "info": "cyan",
        "warning": "yellow",
        "error": "bold red",
        "success": "bold green",
        "highlight": "bold magenta",
        "muted": "dim white",
        "header": "bold cyan",
        "value": "bold white",
        "codec.av1": "bold green",
        "codec.h264": "bold yellow",
        "codec.h265": "bold blue",
        "codec.unknown": "dim white",
    }
)

console = Console(theme=CUSTOM_THEME)


# ═══════════════════════════════════════════════════════════════════════════════
# Header & Banner
# ═══════════════════════════════════════════════════════════════════════════════

BANNER = """
[bold cyan]╭──────────────────────────────────────────────────────────────╮
│[/]                    [bold magenta]🎬 VIDEO RENDERER v2.0[/]                    [bold cyan]│
│[/]              [dim]Ubuntu • FFmpeg • Rich Terminal UI[/]              [bold cyan]│
╰──────────────────────────────────────────────────────────────╯[/]
"""


def print_header():
    """Print the application header."""
    console.print(BANNER)


def print_working_directory(path: Path):
    """Print current working directory info."""
    console.print(f"[muted]📁 Calisma dizini:[/] [value]{path.as_posix()}[/]")
    console.print()


# ═══════════════════════════════════════════════════════════════════════════════
# Tables
# ═══════════════════════════════════════════════════════════════════════════════


def format_duration(seconds: float) -> str:
    """Format seconds as HH:MM:SS or MM:SS."""
    minutes, secs = divmod(int(seconds), 60)
    hours, minutes = divmod(minutes, 60)
    if hours > 0:
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"
    return f"{minutes:02d}:{secs:02d}"


def get_codec_style(codec: str) -> str:
    """Get style for codec name."""
    codec_lower = codec.lower()
    if "av1" in codec_lower:
        return "codec.av1"
    elif "h264" in codec_lower or "avc" in codec_lower:
        return "codec.h264"
    elif "h265" in codec_lower or "hevc" in codec_lower:
        return "codec.h265"
    return "codec.unknown"


def print_video_table(videos: List[Tuple[Path, VideoInfo]], title: str = "Video Dosyalari"):
    """Print a table of video files with info."""
    table = Table(
        title=f"[header]{title}[/]",
        box=box.ROUNDED,
        header_style="bold cyan",
        border_style="cyan",
        show_lines=False,
    )

    table.add_column("#", justify="right", style="dim", width=3)
    table.add_column("Dosya", style="value", max_width=30)
    table.add_column("Codec", justify="center", width=8)
    table.add_column("Cozunurluk", justify="center", width=12)
    table.add_column("FPS", justify="center", width=8)
    table.add_column("Sure", justify="center", width=10)

    for i, (path, info) in enumerate(videos, start=1):
        codec_style = get_codec_style(info.codec)
        fps_display = info.fps.split("/")[0] if "/" in info.fps else info.fps

        table.add_row(
            str(i),
            path.name,
            f"[{codec_style}]{info.codec.upper()}[/]",
            f"{info.width}x{info.height}",
            fps_display,
            format_duration(info.duration),
        )

    console.print(table)
    console.print()


def print_audio_table(files: List[Path], title: str = "Ses Dosyalari"):
    """Print a table of audio files."""
    table = Table(
        title=f"[header]{title}[/]",
        box=box.ROUNDED,
        header_style="bold cyan",
        border_style="cyan",
    )

    table.add_column("#", justify="right", style="dim", width=3)
    table.add_column("Dosya", style="value")
    table.add_column("Tur", justify="center", width=10)

    for i, path in enumerate(files, start=1):
        file_type = "BG" if path.stem.lower().startswith("bg") else "Track"
        style = "warning" if file_type == "BG" else "info"
        table.add_row(str(i), path.name, f"[{style}]{file_type}[/]")

    console.print(table)
    console.print()


def print_video_info_panel(label: str, path: Path, info: VideoInfo):
    """Print detailed video info in a panel."""
    lines = [
        f"[muted]Codec:[/] [{get_codec_style(info.codec)}]{info.codec.upper()}[/]",
        f"[muted]Cozunurluk:[/] [value]{info.width}x{info.height}[/]",
        f"[muted]FPS:[/] [value]{info.fps}[/]",
        f"[muted]Pixel Format:[/] [value]{info.pix_fmt}[/]",
        f"[muted]Sure:[/] [value]{format_duration(info.duration)}[/]",
    ]

    if info.color_space:
        lines.append(f"[muted]Color Space:[/] [value]{info.color_space}[/]")
    if info.profile:
        lines.append(f"[muted]Profile:[/] [value]{info.profile}[/]")

    content = "\n".join(lines)
    panel = Panel(
        content,
        title=f"[header]{label}[/] [muted]({path.name})[/]",
        border_style="cyan",
        box=box.ROUNDED,
    )
    console.print(panel)


# ═══════════════════════════════════════════════════════════════════════════════
# Prompts
# ═══════════════════════════════════════════════════════════════════════════════


def ask_text(prompt: str, default: Optional[str] = None) -> str:
    """Ask for text input."""
    return Prompt.ask(f"[highlight]?[/] {prompt}", default=default, console=console)


def ask_int(prompt: str, min_val: int, max_val: int, default: Optional[int] = None) -> int:
    """Ask for integer input within range."""
    while True:
        try:
            value = IntPrompt.ask(f"[highlight]?[/] {prompt}", default=default, console=console)
            if value < min_val or value > max_val:
                console.print(f"[error]Aralik: {min_val}-{max_val}[/]")
                continue
            return value
        except ValueError:
            console.print("[error]Gecersiz sayi.[/]")


def ask_confirm(prompt: str, default: bool = True) -> bool:
    """Ask for yes/no confirmation."""
    return Confirm.ask(f"[highlight]?[/] {prompt}", default=default, console=console)


def ask_choice(prompt: str, options: List[str], default: int = 1) -> int:
    """
    Ask user to choose from options.
    Returns 1-based index.
    """
    console.print()
    for i, opt in enumerate(options, start=1):
        marker = "●" if i == default else "○"
        style = "highlight" if i == default else "muted"
        console.print(f"  [{style}]{marker}[/] [value]{i})[/] {opt}")
    console.print()

    return ask_int(prompt, 1, len(options), default)


def ask_multiple_choice(
    prompt: str, options: List[str], min_count: int = 1, max_count: Optional[int] = None
) -> List[int]:
    """
    Ask user to select multiple options.
    Returns list of 1-based indices.
    """
    if max_count is None:
        max_count = len(options)

    console.print()
    for i, opt in enumerate(options, start=1):
        console.print(f"  [muted]○[/] [value]{i})[/] {opt}")
    console.print()

    selected: List[int] = []
    used = set()

    count = ask_int(f"Kac adet secilecek? ({min_count}-{max_count})", min_count, max_count)

    for k in range(count):
        while True:
            idx = ask_int(f"{k+1}/{count} secim", 1, len(options))
            if idx in used:
                console.print("[warning]Bu zaten secildi.[/]")
                continue
            used.add(idx)
            selected.append(idx)
            break

    return selected


def ask_duration_components(default_hours: int = 8) -> int:
    """Ask for duration in H, M, S components."""
    console.print()
    print_info("Sureyi belirleyin:")

    h = ask_int("Saat", 0, 999, default_hours)
    m = ask_int("Dakika", 0, 59, 0)
    s = ask_int("Saniye", 0, 59, 0)

    total = h * 3600 + m * 60 + s
    if total <= 0:
        print_warning("Sure 0 olamaz, varsayilan 8 saat kullanilacak.")
        return default_hours * 3600

    return total


def create_progress_bar() -> Progress:
    """Create a styled progress bar."""
    return Progress(
        SpinnerColumn(),
        TextColumn("[bold cyan]{task.description}[/]"),
        BarColumn(bar_width=40, style="cyan", complete_style="green"),
        TaskProgressColumn(),
        TimeRemainingColumn(),
        console=console,
        transient=False,
    )


class FFmpegSpeedColumn(ProgressColumn):
    """Renders FFmpeg speed (e.g. 5.2x)."""

    def render(self, task: Task) -> Text:
        speed = task.fields.get("speed")
        if speed is None:
            return Text("", style="dim")
        if speed > 999:
            return Text(">999x", style="bold green")
        return Text(f"{speed:.1f}x", style="bold yellow")


class MultiStepProgress:
    """
    Multi-step progress display for rendering pipeline.
    """

    def __init__(self, steps: List[str]):
        self.steps = steps
        self.current_step = 0
        self.progress = Progress(
            SpinnerColumn(),
            TextColumn("[bold cyan]{task.description}[/]"),
            BarColumn(bar_width=40, style="cyan", complete_style="green"),
            TaskProgressColumn(),
            FFmpegSpeedColumn(),
            TimeRemainingColumn(),
            console=console,
        )
        self.tasks = {}

    def __enter__(self):
        self.progress.__enter__()
        for i, step in enumerate(self.steps):
            prefix = f"[{i+1}/{len(self.steps)}]"
            self.tasks[i] = self.progress.add_task(f"{prefix} {step}", total=100)
        return self

    def __exit__(self, *args):
        self.progress.__exit__(*args)

    def update(self, step_index: int, percent: float, description: Optional[str] = None, **kwargs):
        """Update progress for a specific step."""
        if step_index in self.tasks:
            task_id = self.tasks[step_index]
            update_kwargs = {"completed": percent}
            if description:
                prefix = f"[{step_index+1}/{len(self.steps)}]"
                update_kwargs["description"] = f"{prefix} {description}"
            self.progress.update(task_id, **update_kwargs, **kwargs)

    def complete_step(self, step_index: int):
        """Mark a step as complete."""
        if step_index in self.tasks:
            self.progress.update(self.tasks[step_index], completed=100)


# ═══════════════════════════════════════════════════════════════════════════════
# Status & Messages
# ═══════════════════════════════════════════════════════════════════════════════


def print_success(message: str):
    """Print a success message."""
    console.print(f"[success]✓[/] {message}")


def print_error(message: str):
    """Print an error message."""
    console.print(f"[error]✗ {message}[/]")


def print_warning(message: str):
    """Print a warning message."""
    console.print(f"[warning]⚠ {message}[/]")


def print_info(message: str):
    """Print an info message."""
    console.print(f"[info]ℹ[/] {message}")


def print_summary(
    intro: Optional[Path],
    loop: Optional[Path],
    codec: str,
    duration: str,
    tracks: List[Path],
    backgrounds: List[Tuple[Path, float]],
    output: Path,
    post_action: str,
    single_video: Optional[Path] = None,
):
    """Print render summary before confirmation."""
    if single_video:
        header = f"[muted]Video:[/] [value]{single_video.name}[/]"
    else:
        header = f"[muted]Intro:[/] [value]{intro.name}[/]\n[muted]Loop:[/] [value]{loop.name}[/]"

    content = f"""{header}
[muted]Codec:[/] [{get_codec_style(codec)}]{codec.upper()}[/]
[muted]Sure:[/] [value]{duration}[/]
[muted]Track:[/] [value]{len(tracks)} adet[/]
[muted]BG:[/] [value]{len(backgrounds)} adet[/]
[muted]Cikti:[/] [value]{output.name}[/]
[muted]Kaynak aksiyonu:[/] [value]{post_action}[/]"""

    panel = Panel(
        content,
        title="[header]📋 OZET[/]",
        border_style="magenta",
        box=box.ROUNDED,
    )
    console.print()
    console.print(panel)
    console.print()


def print_completion(output_path: Path, duration_seconds: float):
    """Print completion message."""
    duration_str = format_duration(duration_seconds)

    content = f"""[success]✓ Render tamamlandi![/]

[muted]Dosya:[/] [value]{output_path.name}[/]
[muted]Konum:[/] [value]{output_path.parent.as_posix()}[/]
[muted]Sure:[/] [value]{duration_str}[/]"""

    panel = Panel(
        content,
        title="[header]🎉 TAMAMLANDI[/]",
        border_style="green",
        box=box.DOUBLE,
    )
    console.print()
    console.print(panel)

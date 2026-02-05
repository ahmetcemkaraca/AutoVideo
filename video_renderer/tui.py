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
    Progress, SpinnerColumn, BarColumn, TextColumn,
    TimeRemainingColumn, TaskProgressColumn, MofNCompleteColumn,
    ProgressColumn, Task
)
from rich.prompt import Prompt, IntPrompt, Confirm
from rich.text import Text
from rich.style import Style

# ... imports ...


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
    single_video: Optional[Path] = None
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

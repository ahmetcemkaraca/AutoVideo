#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Monitoring dashboard for VideoAutomation pipeline.

Features:
- Real-time pipeline status display
- Progress tracking for renders and uploads
- Error reporting and categorization
- Statistics and metrics display
- Rich TUI dashboard
"""

import time
import threading
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from enum import Enum
import logging

from rich.console import Console
from rich.layout import Layout
from rich.panel import Panel
from rich.progress import Progress, BarColumn, TaskID, TaskProgressColumn
from rich.table import Table
from rich.text import Text
from rich.live import Live
from rich.align import Align
from rich.columns import Columns
from rich import box

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════════════
# Status Enums
# ═══════════════════════════════════════════════════════════════════════════════

class PipelineStatus(Enum):
    """Current pipeline status."""
    IDLE = "idle"
    INITIALIZING = "initializing"
    RENDERING = "rendering"
    UPLOADING = "uploading"
    COMPLETED = "completed"
    ERROR = "error"
    PAUSED = "paused"


class TaskType(Enum):
    """Types of tasks being tracked."""
    RENDER = "render"
    UPLOAD = "upload"
    AUDIO_PROCESS = "audio_process"
    ENCODE = "encode"


# ═══════════════════════════════════════════════════════════════════════════════
# Data Models
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class TaskProgress:
    """Progress tracking for a task."""
    task_id: str
    task_type: TaskType
    description: str
    current: float = 0.0
    total: float = 100.0
    unit: str = "%"
    started_at: datetime = field(default_factory=datetime.now)
    completed: bool = False
    error: Optional[str] = None

    @property
    def percent(self) -> float:
        """Get progress as percentage."""
        if self.total == 0:
            return 0.0
        return min(100.0, (self.current / self.total) * 100)

    @property
    def elapsed(self) -> timedelta:
        """Get elapsed time."""
        return datetime.now() - self.started_at


@dataclass
class ErrorRecord:
    """Record of an error."""
    timestamp: datetime = field(default_factory=datetime.now)
    category: str = ""
    message: str = ""
    severity: str = "medium"
    resolved: bool = False


@dataclass
class PipelineMetrics:
    """Pipeline performance metrics."""
    total_runs: int = 0
    successful_runs: int = 0
    failed_runs: int = 0
    total_render_time: float = 0.0
    total_upload_time: float = 0.0
    total_bytes_uploaded: int = 0
    last_run_time: Optional[datetime] = None
    current_run_start: Optional[datetime] = None

    @property
    def success_rate(self) -> float:
        """Get success rate as percentage."""
        if self.total_runs == 0:
            return 0.0
        return (self.successful_runs / self.total_runs) * 100

    @property
    def avg_render_time(self) -> float:
        """Get average render time in seconds."""
        if self.successful_runs == 0:
            return 0.0
        return self.total_render_time / self.successful_runs

    @property
    def avg_upload_time(self) -> float:
        """Get average upload time in seconds."""
        if self.successful_runs == 0:
            return 0.0
        return self.total_upload_time / self.successful_runs


# ═══════════════════════════════════════════════════════════════════════════════
# Monitoring Dashboard
# ═══════════════════════════════════════════════════════════════════════════════

class MonitorDashboard:
    """
    Rich-based monitoring dashboard for the automation pipeline.

    Provides real-time visualization of:
    - Pipeline status
    - Active tasks and progress
    - Error history
    - Performance metrics
    - Recent uploads
    """

    def __init__(
        self,
        refresh_rate: float = 0.5,
        enable_live: bool = True
    ):
        """
        Initialize dashboard.

        Args:
            refresh_rate: Dashboard refresh rate in seconds
            enable_live: Enable live updates (False for manual updates)
        """
        self.console = Console()
        self.refresh_rate = refresh_rate
        self.enable_live = enable_live

        self.status = PipelineStatus.IDLE
        self.status_message = "Ready"
        self.current_iteration = 0
        self.max_iterations: Optional[int] = None

        self.tasks: Dict[str, TaskProgress] = {}
        self.errors: List[ErrorRecord] = []
        self.metrics = PipelineMetrics()
        self.recent_uploads: List[Dict[str, Any]] = []

        self._lock = threading.Lock()
        self._live: Optional[Live] = None

    def start(self):
        """Start the live dashboard."""
        if not self.enable_live:
            return

        self._live = Live(
            self._render_dashboard(),
            console=self.console,
            refresh_per_second=1.0 / self.refresh_rate
        )
        self._live.start()

    def stop(self):
        """Stop the live dashboard."""
        if self._live:
            self._live.stop()
            self._live = None

    def update(self):
        """Manually update the dashboard (for non-live mode)."""
        if not self.enable_live:
            self.console.clear()
            self.console.print(self._render_dashboard())

    def _render_dashboard(self) -> Layout:
        """Render the complete dashboard layout."""
        layout = Layout()

        # Header
        layout.split_column(
            Layout(name="header", size=3),
            Layout(name="body"),
            Layout(name="footer", size=3)
        )

        layout["header"].update(self._render_header())

        # Body split
        layout["body"].split_row(
            Layout(name="left", ratio=2),
            Layout(name="right", ratio=1)
        )

        layout["left"].split_column(
            Layout(name="status", size=8),
            Layout(name="tasks", size=10),
            Layout(name="uploads")
        )

        layout["right"].split_column(
            Layout(name="metrics", size=12),
            Layout(name="errors")
        )

        # Update sections
        layout["status"].update(self._render_status())
        layout["tasks"].update(self._render_tasks())
        layout["uploads"].update(self._render_uploads())
        layout["metrics"].update(self._render_metrics())
        layout["errors"].update(self._render_errors())
        layout["footer"].update(self._render_footer())

        return layout

    def _render_header(self) -> Panel:
        """Render header panel."""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        header_text = Text()
        header_text.append("🤖 ", style="bold magenta")
        header_text.append("VideoAutomation Pipeline", style="bold cyan")
        header_text.append(f"  |  {timestamp}", style="dim")

        return Panel(
            Align.center(header_text),
            style="on #1a1a1a",
            border_style="cyan"
        )

    def _render_status(self) -> Panel:
        """Render pipeline status panel."""
        # Status table
        table = Table(show_header=False, box=box.SIMPLE, padding=(0, 1))
        table.add_column("Property", style="dim")
        table.add_column("Value")

        # Status with color
        status_style = {
            PipelineStatus.IDLE: "dim",
            PipelineStatus.INITIALIZING: "yellow",
            PipelineStatus.RENDERING: "cyan",
            PipelineStatus.UPLOADING: "blue",
            PipelineStatus.COMPLETED: "green",
            PipelineStatus.ERROR: "red",
            PipelineStatus.PAUSED: "yellow"
        }.get(self.status, "white")

        status_emoji = {
            PipelineStatus.IDLE: "💤",
            PipelineStatus.INITIALIZING: "⚙️",
            PipelineStatus.RENDERING: "🎬",
            PipelineStatus.UPLOADING: "📤",
            PipelineStatus.COMPLETED: "✅",
            PipelineStatus.ERROR: "❌",
            PipelineStatus.PAUSED: "⏸️"
        }.get(self.status, "📊")

        table.add_row("Status", Text(f"{status_emoji} {self.status.value}", style=status_style))
        table.add_row("Message", self.status_message)

        # Iteration info
        if self.max_iterations:
            table.add_row("Iteration", f"{self.current_iteration} / {self.max_iterations}")
        else:
            table.add_row("Iteration", str(self.current_iteration))

        # Current run time
        if self.metrics.current_run_start:
            elapsed = (datetime.now() - self.metrics.current_run_start).total_seconds()
            table.add_row("Run Time", self._format_duration(elapsed))

        return Panel(table, title="Pipeline Status", border_style="cyan")

    def _render_tasks(self) -> Panel:
        """Render active tasks panel."""
        if not self.tasks:
            return Panel(Text("No active tasks", style="dim"), title="Active Tasks")

        table = Table(box=box.SIMPLE)
        table.add_column("Task", style="cyan")
        table.add_column("Progress")
        table.add_column("Time", style="dim")

        for task in self.tasks.values():
            # Progress bar
            percent = task.percent
            bar_width = 20
            filled = int(bar_width * percent / 100)
            bar = "█" * filled + "░" * (bar_width - filled)

            # Color based on type
            color = {
                TaskType.RENDER: "cyan",
                TaskType.UPLOAD: "blue",
                TaskType.AUDIO_PROCESS: "green",
                TaskType.ENCODE: "yellow"
            }.get(task.task_type, "white")

            table.add_row(
                task.description[:30],
                Text(f"{bar} {percent:.1f}%", style=color),
                self._format_duration(task.elapsed.total_seconds())
            )

        return Panel(table, title="Active Tasks", border_style="green")

    def _render_uploads(self) -> Panel:
        """Render recent uploads panel."""
        if not self.recent_uploads:
            return Panel(Text("No uploads yet", style="dim"), title="Recent Uploads")

        table = Table(box=box.SIMPLE)
        table.add_column("Time", style="dim")
        table.add_column("Title")
        table.add_column("Status", style="bold")

        for upload in self.recent_uploads[-5:]:  # Show last 5
            timestamp = upload.get("timestamp", "")
            if isinstance(timestamp, datetime):
                timestamp = timestamp.strftime("%H:%M:%S")

            title = upload.get("title", "")[:30]
            status = upload.get("status", "unknown")

            status_style = "green" if status == "success" else "red"

            table.add_row(timestamp, title, Text(status, style=status_style))

        return Panel(table, title="Recent Uploads", border_style="blue")

    def _render_metrics(self) -> Panel:
        """Render performance metrics panel."""
        table = Table(show_header=False, box=box.SIMPLE)
        table.add_column("Metric", style="dim")
        table.add_column("Value", style="bold")

        table.add_row("Total Runs", str(self.metrics.total_runs))
        table.add_row("Success Rate", f"{self.metrics.success_rate:.1f}%")

        if self.metrics.avg_render_time > 0:
            table.add_row("Avg Render", self._format_duration(self.metrics.avg_render_time))

        if self.metrics.avg_upload_time > 0:
            table.add_row("Avg Upload", self._format_duration(self.metrics.avg_upload_time))

        # Bytes uploaded
        if self.metrics.total_bytes_uploaded > 0:
            gb = self.metrics.total_bytes_uploaded / (1024**3)
            table.add_row("Total Uploaded", f"{gb:.2f} GB")

        return Panel(table, title="Metrics", border_style="yellow")

    def _render_errors(self) -> Panel:
        """Render error history panel."""
        if not self.errors:
            return Panel(Text("No errors", style="dim green"), title="Error Log")

        table = Table(box=box.SIMPLE)
        table.add_column("Time", style="dim")
        table.add_column("Severity")
        table.add_column("Message")

        for error in self.errors[-5:]:  # Show last 5
            timestamp = error.timestamp.strftime("%H:%M:%S")

            severity_color = {
                "low": "dim",
                "medium": "yellow",
                "high": "red",
                "critical": "bold red"
            }.get(error.severity, "white")

            table.add_row(
                timestamp,
                Text(error.severity, style=severity_color),
                error.message[:40]
            )

        return Panel(table, title="Recent Errors", border_style="red")

    def _render_footer(self) -> Panel:
        """Render footer panel."""
        footer_text = Text()

        # Status indicators
        if self.status == PipelineStatus.ERROR:
            footer_text.append("⚠️ Errors detected. Check log for details.", style="red")
        elif self.status == PipelineStatus.IDLE:
            footer_text.append("Ready. Press Ctrl+C to exit.", style="dim")
        elif self.status in [PipelineStatus.RENDERING, PipelineStatus.UPLOADING]:
            footer_text.append("Pipeline running... ", style="cyan")
            footer_text.append("Ctrl+C to stop", style="dim")
        else:
            footer_text.append("Pipeline operational.", style="green")

        return Panel(
            Align.center(footer_text),
            style="on #1a1a1a",
            border_style="dim"
        )

    @staticmethod
    def _format_duration(seconds: float) -> str:
        """Format duration as H:M:S."""
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)

        if hours > 0:
            return f"{hours}h {minutes}m {secs}s"
        elif minutes > 0:
            return f"{minutes}m {secs}s"
        else:
            return f"{secs}s"

    # ═══════════════════════════════════════════════════════════════════════════════
    # Public API
    # ═══════════════════════════════════════════════════════════════════════════════

    def set_status(self, status: PipelineStatus, message: str = ""):
        """Update pipeline status."""
        with self._lock:
            self.status = status
            if message:
                self.status_message = message

    def add_task(self, task: TaskProgress):
        """Add or update a task."""
        with self._lock:
            self.tasks[task.task_id] = task

    def update_task(self, task_id: str, current: float, total: Optional[float] = None):
        """Update task progress."""
        with self._lock:
            if task_id in self.tasks:
                self.tasks[task_id].current = current
                if total is not None:
                    self.tasks[task_id].total = total

    def complete_task(self, task_id: str, error: Optional[str] = None):
        """Mark task as complete."""
        with self._lock:
            if task_id in self.tasks:
                self.tasks[task_id].completed = True
                self.tasks[task_id].error = error

    def remove_task(self, task_id: str):
        """Remove a task."""
        with self._lock:
            self.tasks.pop(task_id, None)

    def add_error(self, category: str, message: str, severity: str = "medium"):
        """Add an error record."""
        with self._lock:
            error = ErrorRecord(
                category=category,
                message=message,
                severity=severity
            )
            self.errors.append(error)

            # Keep only last 50 errors
            if len(self.errors) > 50:
                self.errors = self.errors[-50:]

    def add_upload(self, title: str, status: str, video_id: Optional[str] = None):
        """Record an upload."""
        with self._lock:
            upload = {
                "timestamp": datetime.now(),
                "title": title,
                "status": status,
                "video_id": video_id
            }
            self.recent_uploads.append(upload)

            # Keep only last 20 uploads
            if len(self.recent_uploads) > 20:
                self.recent_uploads = self.recent_uploads[-20:]

    def start_run(self, iteration: int = 1):
        """Record start of a pipeline run."""
        with self._lock:
            self.current_iteration = iteration
            self.metrics.current_run_start = datetime.now()

    def complete_run(self, success: bool, render_time: float = 0.0, upload_time: float = 0.0):
        """Record completion of a pipeline run."""
        with self._lock:
            self.metrics.total_runs += 1
            self.metrics.current_run_start = None
            self.metrics.last_run_time = datetime.now()

            if success:
                self.metrics.successful_runs += 1
                self.metrics.total_render_time += render_time
                self.metrics.total_upload_time += upload_time
            else:
                self.metrics.failed_runs += 1

    def record_bytes_uploaded(self, bytes_count: int):
        """Record uploaded bytes."""
        with self._lock:
            self.metrics.total_bytes_uploaded += bytes_count

    def set_max_iterations(self, max_iter: Optional[int]):
        """Set maximum iterations for display."""
        with self._lock:
            self.max_iterations = max_iter

    def clear_errors(self):
        """Clear error history."""
        with self._lock:
            self.errors.clear()

    def get_summary(self) -> Dict[str, Any]:
        """Get dashboard summary."""
        with self._lock:
            return {
                "status": self.status.value,
                "iteration": self.current_iteration,
                "total_runs": self.metrics.total_runs,
                "success_rate": self.metrics.success_rate,
                "active_tasks": len([t for t in self.tasks.values() if not t.completed]),
                "recent_errors": len(self.errors),
                "last_run": self.metrics.last_run_time.isoformat() if self.metrics.last_run_time else None
            }


# ═══════════════════════════════════════════════════════════════════════════════
# CLI Logger Adapter
# ═══════════════════════════════════════════════════════════════════════════════

class DashboardLogHandler(logging.Handler):
    """Custom logging handler that sends logs to the dashboard."""

    def __init__(self, dashboard: MonitorDashboard):
        super().__init__()
        self.dashboard = dashboard

    def emit(self, record: logging.LogRecord):
        """Emit a log record to the dashboard."""
        if record.levelno >= logging.ERROR:
            severity = "critical" if record.levelno >= logging.CRITICAL else "high"
            self.dashboard.add_error(
                category="logging",
                message=record.getMessage(),
                severity=severity
            )

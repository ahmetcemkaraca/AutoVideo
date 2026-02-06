#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Monitor ve Dashboard modülü.

Pipeline durumunu gerçek zamanlı olarak izler ve dashboard gösterir.
"""

import time
import threading
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field
from collections import deque
import logging

from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.live import Live
from rich.layout import Layout
from rich.align import Align
from rich.text import Text
from rich import box

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════════════
# Metrics
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class PipelineMetrics:
    """Pipeline metrikleri."""

    # Video metrics
    total_videos_created: int = 0
    videos_upload_success: int = 0
    videos_upload_failed: int = 0
    videos_render_success: int = 0
    videos_render_failed: int = 0

    # Performance metrics
    last_render_time: Optional[float] = None  # Saniye
    last_upload_time: Optional[float] = None  # Saniye
    avg_render_time: float = 0.0
    avg_upload_time: float = 0.0

    # Error metrics
    total_errors: int = 0
    last_error: Optional[str] = None
    last_error_time: Optional[datetime] = None

    # Status
    current_status: str = "Idle"  # Idle, Rendering, Uploading, Error
    current_action: str = ""
    current_progress: float = 0.0

    # Timestamps
    pipeline_start_time: Optional[datetime] = None
    last_activity_time: Optional[datetime] = None

    # Rate limiting
    api_calls_today: int = 0
    api_calls_hour: int = 0


@dataclass
class SystemMetrics:
    """Sistem metrikleri."""

    cpu_percent: float = 0.0
    memory_percent: float = 0.0
    disk_free_gb: float = 0.0
    uptime_seconds: float = 0.0


# ═══════════════════════════════════════════════════════════════════════════════
# Event Log
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class Event:
    """Olay kaydı."""
    timestamp: datetime
    level: str  # INFO, WARNING, ERROR, SUCCESS
    message: str
    details: Dict[str, Any] = field(default_factory=dict)


class EventLog:
    """Olay logu."""

    def __init__(self, max_size: int = 100):
        """
        Args:
            max_size: Maksimum olay sayısı
        """
        self.events: deque[Event] = deque(maxlen=max_size)
        self._lock = threading.Lock()

    def add(self, level: str, message: str, **details):
        """Olay ekle."""
        with self._lock:
            self.events.append(Event(
                timestamp=datetime.now(),
                level=level,
                message=message,
                details=details
            ))

    def get_recent(self, count: int = 10) -> List[Event]:
        """Son N olayı al."""
        with self._lock:
            return list(self.events)[-count:]


# ═══════════════════════════════════════════════════════════════════════════════
# Monitor
# ═══════════════════════════════════════════════════════════════════════════════

class PipelineMonitor:
    """
    Pipeline monitor sınıfı.

    Pipeline durumunu izler, metrik toplar ve dashboard gösterir.
    """

    def __init__(self, update_interval: float = 1.0):
        """
        Args:
            update_interval: Dashboard güncelleme aralığı (saniye)
        """
        self.console = Console()
        self.update_interval = update_interval

        self.metrics = PipelineMetrics()
        self.system_metrics = SystemMetrics()
        self.event_log = EventLog()

        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()

    def start(self):
        """Monitor'u başlat."""
        if self._running:
            return

        self._running = True
        self.metrics.pipeline_start_time = datetime.now()

        self._thread = threading.Thread(target=self._update_loop, daemon=True)
        self._thread.start()

        self.event_log.add("INFO", "Monitor started")

    def stop(self):
        """Monitor'u durdur."""
        self._running = False
        if self._thread:
            self._thread.join(timeout=5)

        self.event_log.add("INFO", "Monitor stopped")

    def _update_loop(self):
        """Güncelleme döngüsü."""
        while self._running:
            self._update_system_metrics()
            time.sleep(self.update_interval)

    def _update_system_metrics(self):
        """Sistem metriklerini güncelle."""
        try:
            import psutil
            self.system_metrics.cpu_percent = psutil.cpu_percent()
            self.system_metrics.memory_percent = psutil.virtual_memory().percent

            work_dir = Path.cwd()
            import shutil
            total, used, free = shutil.disk_usage(work_dir)
            self.system_metrics.disk_free_gb = free / (1024 ** 3)

            if self.metrics.pipeline_start_time:
                self.system_metrics.uptime_seconds = (
                    datetime.now() - self.metrics.pipeline_start_time
                ).total_seconds()

        except ImportError:
            # psutil kurulu değil
            pass
        except Exception:
            pass

    # ═══════════════════════════════════════════════════════════════════════════════
    # Metric Update Methods
    # ═══════════════════════════════════════════════════════════════════════════════

    def update_status(self, status: str, action: str = "", progress: float = 0.0):
        """Durumu güncelle."""
        with self._lock:
            self.metrics.current_status = status
            self.metrics.current_action = action
            self.metrics.current_progress = progress
            self.metrics.last_activity_time = datetime.now()

    def video_render_start(self):
        """Video rendering başladı."""
        with self._lock:
            self.metrics.current_status = "Rendering"
            self.event_log.add("INFO", "Video rendering started")

    def video_render_complete(self, duration: float, success: bool):
        """Video rendering tamamlandı."""
        with self._lock:
            if success:
                self.metrics.videos_render_success += 1
                self.metrics.total_videos_created += 1

                # Ortalama hesapla
                if self.metrics.videos_render_success > 0:
                    total = self.metrics.avg_render_time * (self.metrics.videos_render_success - 1)
                    self.metrics.avg_render_time = (total + duration) / self.metrics.videos_render_success

                self.event_log.add("SUCCESS", f"Video rendered in {duration:.1f}s")
            else:
                self.metrics.videos_render_failed += 1
                self.event_log.add("ERROR", "Video rendering failed")

            self.metrics.last_render_time = duration

    def video_upload_start(self):
        """Video upload başladı."""
        with self._lock:
            self.metrics.current_status = "Uploading"
            self.event_log.add("INFO", "Video upload started")

    def video_upload_complete(self, duration: float, success: bool, video_id: Optional[str] = None):
        """Video upload tamamlandı."""
        with self._lock:
            if success:
                self.metrics.videos_upload_success += 1
                self.metrics.api_calls_today += 1
                self.metrics.api_calls_hour += 1

                # Ortalama hesapla
                if self.metrics.videos_upload_success > 0:
                    total = self.metrics.avg_upload_time * (self.metrics.videos_upload_success - 1)
                    self.metrics.avg_upload_time = (total + duration) / self.metrics.videos_upload_success

                msg = f"Video uploaded in {duration:.1f}s"
                if video_id:
                    msg += f" (ID: {video_id})"
                self.event_log.add("SUCCESS", msg)
            else:
                self.metrics.videos_upload_failed += 1
                self.event_log.add("ERROR", "Video upload failed")

            self.metrics.last_upload_time = duration

    def log_error(self, error: str):
        """Hata logla."""
        with self._lock:
            self.metrics.total_errors += 1
            self.metrics.last_error = error
            self.metrics.last_error_time = datetime.now()
            self.event_log.add("ERROR", error)

    def log_warning(self, warning: str):
        """Uyarı logla."""
        with self._lock:
            self.event_log.add("WARNING", warning)

    def log_info(self, message: str, **details):
        """Bilgi logla."""
        with self._lock:
            self.event_log.add("INFO", message, **details)

    # ═══════════════════════════════════════════════════════════════════════════════
    # Dashboard
    # ═══════════════════════════════════════════════════════════════════════════════

    def create_dashboard(self) -> Layout:
        """Dashboard layout'ı oluştur."""
        layout = Layout()

        layout.split_column(
            Layout(name="header", size=3),
            Layout(name="main"),
            Layout(name="footer", size=3),
        )

        layout["main"].split_row(
            Layout(name="stats"),
            Layout(name="events"),
        )

        return layout

    def render_header(self) -> Panel:
        """Header render et."""
        uptime = self.system_metrics.uptime_seconds
        hours = int(uptime // 3600)
        minutes = int((uptime % 3600) // 60)

        header_text = Text()
        header_text.append("🤖 VideoAutomation Pipeline Monitor", style="bold cyan")
        header_text.append(f" | Uptime: {hours}h {minutes}m", style="dim")

        return Panel(
            Align.center(header_text),
            box=box.ROUNDED,
            style="cyan"
        )

    def render_stats(self) -> Panel:
        """İstatistikleri render et."""
        table = Table(title="Pipeline Statistics", box=box.ROUNDED, border_style="cyan")
        table.add_column("Metric", style="dim")
        table.add_column("Value", style="bold")

        # Video stats
        table.add_row("Videos Created", str(self.metrics.total_videos_created))
        table.add_row("Render Success", str(self.metrics.videos_render_success))
        table.add_row("Render Failed", str(self.metrics.videos_render_failed))
        table.add_row("", "")
        table.add_row("Upload Success", str(self.metrics.videos_upload_success))
        table.add_row("Upload Failed", str(self.metrics.videos_upload_failed))
        table.add_row("", "")
        table.add_row("Avg Render Time", f"{self.metrics.avg_render_time:.1f}s")
        table.add_row("Avg Upload Time", f"{self.metrics.avg_upload_time:.1f}s")
        table.add_row("", "")
        table.add_row("Total Errors", str(self.metrics.total_errors))
        table.add_row("", "")
        table.add_row("Status", self.metrics.current_status)
        table.add_row("Action", self.metrics.current_action)

        # Progress bar
        if self.metrics.current_progress > 0:
            progress = int(self.metrics.current_progress)
            bar = "█" * (progress // 5) + "░" * (20 - progress // 5)
            table.add_row("Progress", f"{bar} {progress:.0f}%")

        return Panel(table, border_style="cyan")

    def render_events(self) -> Panel:
        """Olayları render et."""
        table = Table(title="Recent Events", box=box.ROUNDED, border_style="cyan")
        table.add_column("Time", style="dim")
        table.add_column("Level")
        table.add_column("Message")

        events = self.event_log.get_recent(15)
        for event in reversed(events):
            time_str = event.timestamp.strftime("%H:%M:%S")

            level_style = {
                "INFO": "dim",
                "WARNING": "yellow",
                "ERROR": "red",
                "SUCCESS": "green",
            }.get(event.level, "")

            level = Text(event.level, style=level_style)
            message = Text(event.message)

            table.add_row(time_str, level, message)

        return Panel(table, border_style="cyan")

    def render_system(self) -> Panel:
        """Sistem metriklerini render et."""
        table = Table(box=box.SIMPLE)
        table.add_column("Metric", style="dim")
        table.add_column("Value", style="bold")

        table.add_row("CPU", f"{self.system_metrics.cpu_percent:.0f}%")
        table.add_row("Memory", f"{self.system_metrics.memory_percent:.0f}%")
        table.add_row("Disk Free", f"{self.system_metrics.disk_free_gb:.1f} GB")
        table.add_row("API Calls (Today)", str(self.metrics.api_calls_today))

        return Panel(table, title="System", border_style="cyan")

    def render_footer(self) -> Panel:
        """Footer render et."""
        footer_text = Text()
        footer_text.append("Press Ctrl+C to exit | ", style="dim")
        footer_text.append("Status: ", style="dim")
        footer_text.append(self.metrics.current_status, style="bold cyan")

        return Panel(Align.center(footer_text), box=box.ROUNDED)

    def display_dashboard(self):
        """Dashboard'u göster."""
        layout = self.create_dashboard()

        layout["header"].update(self.render_header())
        layout["stats"].update(self.render_stats())
        layout["events"].update(self.render_events())
        layout["footer"].update(self.render_footer())

        return layout

    def run_interactive(self):
        """İnteraktif dashboard modu."""
        self.start()

        try:
            with Live(self.display_dashboard(), console=self.console, refresh_per_second=1) as live:
                while self._running:
                    time.sleep(self.update_interval)
                    live.update(self.display_dashboard())
        except KeyboardInterrupt:
            self.console.print("\n[yellow]Dashboard stopped[/]")
        finally:
            self.stop()

    def get_metrics_dict(self) -> Dict[str, Any]:
        """Metrikleri dict olarak al."""
        with self._lock:
            return {
                "pipeline": {
                    "total_videos_created": self.metrics.total_videos_created,
                    "videos_upload_success": self.metrics.videos_upload_success,
                    "videos_upload_failed": self.metrics.videos_upload_failed,
                    "videos_render_success": self.metrics.videos_render_success,
                    "videos_render_failed": self.metrics.videos_render_failed,
                    "avg_render_time": self.metrics.avg_render_time,
                    "avg_upload_time": self.metrics.avg_upload_time,
                    "total_errors": self.metrics.total_errors,
                    "current_status": self.metrics.current_status,
                    "current_action": self.metrics.current_action,
                    "current_progress": self.metrics.current_progress,
                    "uptime_seconds": self.system_metrics.uptime_seconds,
                },
                "system": {
                    "cpu_percent": self.system_metrics.cpu_percent,
                    "memory_percent": self.system_metrics.memory_percent,
                    "disk_free_gb": self.system_metrics.disk_free_gb,
                    "api_calls_today": self.metrics.api_calls_today,
                }
            }

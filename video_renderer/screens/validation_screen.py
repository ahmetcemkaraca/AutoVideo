#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Validation Screen - Display video and audio validation results with color-coded status.
"""

import json
import os
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Literal

from textual.app import ComposeResult
from textual.screen import Screen
from textual.widgets import (
    Static,
    Button,
    Footer,
    DataTable,
    Label,
    Content,
)
from textual.containers import Container, Vertical, Horizontal, VerticalScroll
from textual.data import DataTable


# ═══════════════════════════════════════════════════════════════════════════════
# Validation Result Data Types
# ═══════════════════════════════════════════════════════════════════════════════


class ValidationResult:
    """Represents a validation check result."""

    def __init__(
        self,
        status: Literal["pass", "fail", "warning"],
        category: str,
        item_name: str,
        message: str,
        details: Optional[Dict] = None,
    ):
        self.status = status
        self.category = category
        self.item_name = item_name
        self.message = message
        self.details = details or {}
        self.timestamp = datetime.now()


class ValidationReport:
    """Complete validation report for a file."""

    def __init__(self, file_path: Path):
        self.file_path = file_path
        self.file_name = file_path.name
        self.results: List[ValidationResult] = []
        self.video_info: Optional[Dict] = None
        self.audio_info: Optional[Dict] = None
        self.raw_ffprobe: Optional[str] = None
        self.timestamp = datetime.now()

    def add_result(self, result: ValidationResult) -> None:
        """Add a validation result."""
        self.results.append(result)

    @property
    def pass_count(self) -> int:
        return sum(1 for r in self.results if r.status == "pass")

    @property
    def fail_count(self) -> int:
        return sum(1 for r in self.results if r.status == "fail")

    @property
    def warning_count(self) -> int:
        return sum(1 for r in self.results if r.status == "warning")

    @property
    def overall_status(self) -> Literal["pass", "fail", "warning"]:
        if self.fail_count > 0:
            return "fail"
        if self.warning_count > 0:
            return "warning"
        return "pass"

    def to_dict(self) -> Dict:
        """Export report to dictionary."""
        return {
            "file_path": str(self.file_path),
            "file_name": self.file_name,
            "timestamp": self.timestamp.isoformat(),
            "overall_status": self.overall_status,
            "summary": {
                "pass": self.pass_count,
                "fail": self.fail_count,
                "warning": self.warning_count,
            },
            "video_info": self.video_info,
            "audio_info": self.audio_info,
            "results": [
                {
                    "status": r.status,
                    "category": r.category,
                    "item_name": r.item_name,
                    "message": r.message,
                    "details": r.details,
                    "timestamp": r.timestamp.isoformat(),
                }
                for r in self.results
            ],
        }


# ═══════════════════════════════════════════════════════════════════════════════
# Validation Screen
# ═══════════════════════════════════════════════════════════════════════════════


class ValidationScreen(Screen):
    """
    Screen for displaying video and audio validation results.

    Features:
    - Color-coded validation results (green=pass, red=fail, yellow=warning)
    - Summary header with pass/fail/warning counts
    - Video and audio info tables
    - Expandable detailed information sections
    - Export report to JSON or text
    - Open file in default player
    - View raw ffprobe output
    """

    BINDINGS = [
        ("e", "export_json", "JSON Export"),
        ("t", "export_text", "Text Export"),
        ("p", "open_player", "Oynatıcıda Aç"),
        ("f", "show_ffprobe", "FFprobe Çıktısı"),
        ("q", "quit", "Çıkış"),
        ("escape", "go_back", "Geri"),
    ]

    def __init__(self, report: ValidationReport, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.report = report
        self._ffprobe_visible = False

    def compose(self) -> ComposeResult:
        """Compose the validation screen UI."""

        # Status banner
        status_class = f"status-{self.report.overall_status}"
        status_text = {
            "pass": "✅ BAŞARILI",
            "fail": "❌ BAŞARISIZ",
            "warning": "⚠️ UYARI",
        }[self.report.overall_status]

        yield Container(
            Static(f"📋 Doğrulama Raporu: {self.report.file_name}", classes="title"),
            Static(status_text, classes=f"title {status_class}"),
            classes="banner",
        )

        # Summary panel
        with Container(classes="panel"):
            yield Static("📊 Özet", classes="panel-title")
            with Horizontal(classes="summary-row"):
                yield Static("Durum:", classes="summary-label")
                yield Static(
                    status_text,
                    classes=f"summary-value {status_class}",
                )
            with Horizontal(classes="summary-row"):
                yield Static("Dosya:", classes="summary-label")
                yield Static(str(self.report.file_path), classes="summary-value")
            with Horizontal(classes="summary-row"):
                yield Static("Başarılı:", classes="summary-label")
                yield Static(f"{self.report.pass_count}", classes="summary-value success-text")
            with Horizontal(classes="summary-row"):
                yield Static("Başarısız:", classes="summary-label")
                yield Static(f"{self.report.fail_count}", classes="summary-value error-text")
            with Horizontal(classes="summary-row"):
                yield Static("Uyarı:", classes="summary-label")
                yield Static(f"{self.report.warning_count}", classes="summary-value warning-text")

        # Video info panel (if available)
        if self.report.video_info:
            with Container(classes="panel"):
                yield Static("🎬 Video Bilgisi", classes="panel-title")
                yield DataTable(id="video_table")

        # Audio info panel (if available)
        if self.report.audio_info:
            with Container(classes="panel"):
                yield Static("🎵 Ses Bilgisi", classes="panel-title")
                yield DataTable(id="audio_table")

        # Validation results table
        with Container(classes="panel"):
            yield Static("🔍 Doğrulama Sonuçları", classes="panel-title")
            yield DataTable(id="results_table")

        # FFprobe output (hidden by default)
        with VerticalScroll(id="ffprobe_container", classes="hidden log-panel"):
            yield Static("📄 FFprobe Çıktısı", classes="panel-title")
            yield Content(id="ffprobe_content")

        # Action buttons
        with Horizontal(classes="action-bar"):
            yield Button("📂 Dosya Yolu", id="show_path", classes="-secondary")
            yield Button("▶️ Oynatıcıda Aç", id="open_player", classes="-secondary")
            yield Button("📄 FFprobe", id="toggle_ffprobe", classes="-secondary")
            yield Button("💾 JSON Export", id="export_json", classes="-secondary")
            yield Button("📝 Text Export", id="export_text", classes="-secondary")
            yield Button("← Geri", id="back", classes="-primary")

        yield Footer()

    def on_mount(self) -> None:
        """Initialize tables when screen is mounted."""
        self._populate_video_table()
        self._populate_audio_table()
        self._populate_results_table()
        self._update_ffprobe_display()

    def _populate_video_table(self) -> None:
        """Populate video information table."""
        if not self.report.video_info:
            return

        try:
            table = self.query_one("#video_table", DataTable)
            table.border_title = None

            # Add columns
            table.add_column("Özellik", width=20)
            table.add_column("Değer", width=40)

            # Add rows
            video = self.report.video_info
            rows = [
                ("Codec", video.get("codec", "N/A")),
                ("Çözünürlük", f"{video.get('width', 0)}x{video.get('height', 0)}"),
                ("FPS", video.get("fps", "N/A")),
                ("Süre", self._format_duration(video.get("duration", 0))),
                ("Pixel Format", video.get("pix_fmt", "N/A")),
            ]

            # Add color space info if available
            if video.get("color_space"):
                rows.append(("Color Space", video["color_space"]))
            if video.get("color_primaries"):
                rows.append(("Color Primaries", video["color_primaries"]))

            for label, value in rows:
                table.add_row(label, str(value))

        except Exception:
            pass

    def _populate_audio_table(self) -> None:
        """Populate audio information table."""
        if not self.report.audio_info:
            return

        try:
            table = self.query_one("#audio_table", DataTable)
            table.border_title = None

            # Add columns
            table.add_column("Özellik", width=20)
            table.add_column("Değer", width=40)

            # Add rows
            audio = self.report.audio_info
            rows = [
                ("Codec", audio.get("codec", "N/A")),
                ("Bitrate", f"{audio.get('bitrate', 0)} kbps"),
                ("Kanallar", audio.get("channels", "N/A")),
                ("Sample Rate", f"{audio.get('sample_rate', 0)} Hz"),
                ("Süre", self._format_duration(audio.get("duration", 0))),
            ]

            for label, value in rows:
                table.add_row(label, str(value))

        except Exception:
            pass

    def _populate_results_table(self) -> None:
        """Populate validation results table."""
        try:
            table = self.query_one("#results_table", DataTable)
            table.border_title = None

            # Add columns
            table.add_column("Durum", width=10)
            table.add_column("Kategori", width=15)
            table.add_column("Öğe", width=20)
            table.add_column("Mesaj", width=50)

            # Add rows
            for result in self.report.results:
                status_symbol = {
                    "pass": "✅",
                    "fail": "❌",
                    "warning": "⚠️",
                }[result.status]

                status_class = {
                    "pass": "success-text",
                    "fail": "error-text",
                    "warning": "warning-text",
                }[result.status]

                table.add_row(
                    f"{status_symbol} {result.status.upper()}",
                    result.category,
                    result.item_name,
                    result.message,
                )

        except Exception:
            pass

    def _update_ffprobe_display(self) -> None:
        """Update ffprobe output display."""
        if self._ffprobe_visible and self.report.raw_ffprobe:
            try:
                content = self.query_one("#ffprobe_content", Content)
                content.update(self.report.raw_ffprobe)
                self.query_one("#ffprobe_container", VerticalScroll).remove_class("hidden")
            except Exception:
                pass
        else:
            try:
                self.query_one("#ffprobe_container", VerticalScroll).add_class("hidden")
            except Exception:
                pass

    def _format_duration(self, seconds: float) -> str:
        """Format duration in seconds to HH:MM:SS."""
        hours, remainder = divmod(int(seconds), 3600)
        minutes, secs = divmod(remainder, 60)
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button press events."""
        button_id = event.button.id

        if button_id == "show_path":
            self._show_file_path()
        elif button_id == "open_player":
            self.action_open_player()
        elif button_id == "toggle_ffprobe":
            self._ffprobe_visible = not self._ffprobe_visible
            self._update_ffprobe_display()
            # Update button label
            label = "FFprobe Gizle" if self._ffprobe_visible else "📄 FFprobe"
            event.button.label = label
        elif button_id == "export_json":
            self.action_export_json()
        elif button_id == "export_text":
            self.action_export_text()
        elif button_id == "back":
            self.action_go_back()

    def _show_file_path(self) -> None:
        """Show the file path in a notification."""
        self.app.notify(
            f"Dosya Yolu:\n{self.report.file_path.as_posix()}",
            title="Dosya Konumu",
            severity="information",
        )

    def action_open_player(self) -> None:
        """Open the video file in the default player."""
        try:
            import platform

            system = platform.system()
            file_path = self.report.file_path

            if not file_path.exists():
                self.app.notify(
                    f"Dosya bulunamadı: {file_path.name}",
                    severity="error",
                )
                return

            if system == "Windows":
                os.startfile(file_path)  # type: ignore
            elif system == "Darwin":  # macOS
                subprocess.run(["open", str(file_path)], check=True)
            else:  # Linux and others
                subprocess.run(["xdg-open", str(file_path)], check=True)

            self.app.notify(
                f"Varsayılan oynatıcıda açılıyor: {file_path.name}",
                severity="information",
            )

        except Exception as e:
            self.app.notify(
                f"Dosya açılamadı: {str(e)}",
                severity="error",
            )

    def action_export_json(self) -> None:
        """Export validation report to JSON file."""
        try:
            output_dir = Path.cwd() / "tmp" / "validation_reports"
            output_dir.mkdir(parents=True, exist_ok=True)

            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"validation_{self.report.file_name}_{timestamp}.json"
            output_path = output_dir / filename

            with open(output_path, "w", encoding="utf-8") as f:
                json.dump(self.report.to_dict(), f, indent=2, ensure_ascii=False)

            self.app.notify(
                f"Rapor kaydedildi: {output_path.name}",
                title="JSON Export",
                severity="success",
            )

        except Exception as e:
            self.app.notify(
                f"Export hatası: {str(e)}",
                severity="error",
            )

    def action_export_text(self) -> None:
        """Export validation report to text file."""
        try:
            output_dir = Path.cwd() / "tmp" / "validation_reports"
            output_dir.mkdir(parents=True, exist_ok=True)

            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"validation_{self.report.file_name}_{timestamp}.txt"
            output_path = output_dir / filename

            lines = [
                "=" * 60,
                "DOĞRULAMA RAPORU",
                "=" * 60,
                f"Dosya: {self.report.file_name}",
                f"Konum: {self.report.file_path.as_posix()}",
                f"Tarih: {self.report.timestamp.strftime('%Y-%m-%d %H:%M:%S')}",
                f"Durum: {self.report.overall_status.upper()}",
                "",
                "-" * 60,
                "ÖZET",
                "-" * 60,
                f"Başarılı: {self.report.pass_count}",
                f"Başarısız: {self.report.fail_count}",
                f"Uyarı: {self.report.warning_count}",
                "",
            ]

            # Video info
            if self.report.video_info:
                lines.extend([
                    "-" * 60,
                    "VİDEO BİLGİSİ",
                    "-" * 60,
                ])
                video = self.report.video_info
                lines.extend([
                    f"Codec: {video.get('codec', 'N/A')}",
                    f"Çözünürlük: {video.get('width', 0)}x{video.get('height', 0)}",
                    f"FPS: {video.get('fps', 'N/A')}",
                    f"Süre: {self._format_duration(video.get('duration', 0))}",
                    f"Pixel Format: {video.get('pix_fmt', 'N/A')}",
                    "",
                ])

            # Audio info
            if self.report.audio_info:
                lines.extend([
                    "-" * 60,
                    "SES BİLGİSİ",
                    "-" * 60,
                ])
                audio = self.report.audio_info
                lines.extend([
                    f"Codec: {audio.get('codec', 'N/A')}",
                    f"Bitrate: {audio.get('bitrate', 0)} kbps",
                    f"Kanallar: {audio.get('channels', 'N/A')}",
                    f"Sample Rate: {audio.get('sample_rate', 0)} Hz",
                    f"Süre: {self._format_duration(audio.get('duration', 0))}",
                    "",
                ])

            # Results
            lines.extend([
                "-" * 60,
                "DOĞRULAMA SONUÇLARI",
                "-" * 60,
            ])

            for result in self.report.results:
                status_symbol = {"pass": "✅", "fail": "❌", "warning": "⚠️"}[result.status]
                lines.append(f"\n{status_symbol} [{result.category}] {result.item_name}")
                lines.append(f"   {result.message}")
                if result.details:
                    for key, value in result.details.items():
                        lines.append(f"   - {key}: {value}")

            lines.append("\n" + "=" * 60)

            output_path.write_text("\n".join(lines), encoding="utf-8")

            self.app.notify(
                f"Rapor kaydedildi: {output_path.name}",
                title="Text Export",
                severity="success",
            )

        except Exception as e:
            self.app.notify(
                f"Export hatası: {str(e)}",
                severity="error",
            )

    def action_show_ffprobe(self) -> None:
        """Toggle ffprobe output visibility."""
        self._ffprobe_visible = not self._ffprobe_visible
        self._update_ffprobe_display()

    def action_go_back(self) -> None:
        """Go back to previous screen."""
        self.app.pop_screen()

    def action_quit(self) -> None:
        """Exit the application."""
        self.app.exit()

#!/usr/bin/env python3
"""
Validation Screen - Displays validation results with color-coded issues.

Shows:
- Overall validation status (pass/fail)
- Categorized issues (error, warning, info)
- Detailed error messages
- Suggestions for fixing issues
- Action buttons (retry, export report, continue)
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal
from textual.screen import Screen
from textual.widgets import Button, Footer, Static

from ..validator import ValidationIssue, ValidationResult, ValidationSeverity

# ═══════════════════════════════════════════════════════════════════════════════
# Validation Screen
# ═══════════════════════════════════════════════════════════════════════════════


class ValidationScreen(Screen):
    """
    Screen for displaying validation results.

    Features:
    - Color-coded severity levels
    - Categorized issue display
    - Export validation report
    - Retry/Continue actions
    """

    BINDINGS = [
        Binding("e", "export_report", "Rapor Dışa Aktar"),
        Binding("r", "retry", "Tekrar Dene"),
        Binding("c", "continue_anyway", "Yine de Devam"),
        Binding("escape", "go_back", "Geri"),
    ]

    def __init__(self, result: ValidationResult, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.result = result

    def compose(self) -> ComposeResult:
        # Determine status styling
        status_class = "status-success" if self.result.valid else "status-error"
        status_text = "✓ Başarılı" if self.result.valid else "✗ Başarısız"

        # Header
        yield Container(
            Static(
                f"{'Pre-Render' if self.result.stage == 'pre_render' else 'Post-Render'} Doğrulama",
                classes="title",
            ),
            Static(f"Durum: {status_text}", classes=f"status-text {status_class}"),
            classes="container",
        )

        # Summary stats
        with Container(classes="panel"):
            yield Static("📊 Özet", classes="panel-title")
            summary_text = self._get_summary_text()
            yield Static(summary_text, classes="info-text")

        # Issues table
        if self.result.issues:
            with Container(classes="panel"):
                yield Static("⚠️ Sorunlar", classes="panel-title")

                # Group issues by severity
                errors = self.result.errors
                warnings = self.result.warnings
                info = self.result.info

                if errors:
                    yield Static(f"❌ Hatalar ({len(errors)})", classes="error-text")
                    for issue in errors:
                        yield self._create_issue_widget(issue)

                if warnings:
                    yield Static(f"⚠️ Uyarılar ({len(warnings)})", classes="warning-text")
                    for issue in warnings:
                        yield self._create_issue_widget(issue)

                if info and not errors:
                    yield Static(f"ℹ️ Bilgi ({len(info)})", classes="info-text")
                    for issue in info[:5]:  # Show max 5 info items
                        yield self._create_issue_widget(issue)
        else:
            with Container(classes="panel"):
                yield Static("✓ Her şey yolunda!", classes="success-text")

        # Metadata (collapsible)
        if self.result.metadata:
            with Container(classes="panel"):
                yield Static("📋 Detaylar", classes="panel-title")
                metadata_text = self._format_metadata(self.result.metadata)
                yield Static(metadata_text, classes="info-text monospace")

        # Action buttons
        with Horizontal(classes="action-bar"):
            if not self.result.valid:
                yield Button("🔄 Tekrar Dene", id="retry", classes="-primary")
                yield Button("📄 Rapor Dışa Aktar", id="export", classes="-secondary")

                # Only show "continue anyway" for pre-render warnings
                if self.result.stage == "pre_render" and not self.result.errors:
                    yield Button("➡️ Yine de Devam", id="continue", classes="-warning")
            else:
                yield Button("✓ Tamam", id="ok", classes="-primary")
                yield Button("📄 Rapor Dışa Aktar", id="export", classes="-secondary")

            yield Button("🚪 Geri", id="back", classes="-secondary")

        yield Footer()

    def _create_issue_widget(self, issue: ValidationIssue) -> Static:
        """Create a widget for displaying a single issue."""
        severity_class = {
            ValidationSeverity.CRITICAL: "error-text",
            ValidationSeverity.ERROR: "error-text",
            ValidationSeverity.WARNING: "warning-text",
            ValidationSeverity.INFO: "info-text",
        }.get(issue.severity, "info-text")

        icon = {
            ValidationSeverity.CRITICAL: "🔴",
            ValidationSeverity.ERROR: "❌",
            ValidationSeverity.WARNING: "⚠️",
            ValidationSeverity.INFO: "ℹ️",
        }.get(issue.severity, "•")

        text = f"{icon} [{issue.category}] {issue.message}"
        if issue.details:
            text += f"\n   └─ {issue.details}"
        if issue.suggestion:
            text += f"\n   └─ 💡 {issue.suggestion}"

        return Static(text, classes=f"issue-item {severity_class}")

    def _get_summary_text(self) -> str:
        """Get summary statistics text."""
        total = len(self.result.issues)
        errors = len(self.result.errors)
        warnings = len(self.result.warnings)
        info = len(self.result.info)

        lines = [
            f"Toplam Sorun: {total}",
            f"  Hata: {errors}",
            f"  Uyarı: {warnings}",
            f"  Bilgi: {info}",
        ]

        # Add duration info if available
        if self.result.stage == "post_render":
            output_meta = self.result.metadata.get("output", {})
            if "duration" in output_meta:
                actual_dur = output_meta["duration"]
                target_dur = output_meta.get("target_duration", 0)
                lines.append(f"\nSüre: {actual_dur:.1f}s / {target_dur}s")

        return "\n".join(lines)

    def _format_metadata(self, metadata: dict[str, Any]) -> str:
        """Format metadata for display."""
        lines = []
        for key, value in metadata.items():
            if isinstance(value, dict):
                lines.append(f"{key}:")
                for sub_key, sub_value in value.items():
                    if isinstance(sub_value, float):
                        lines.append(f"  {sub_key}: {sub_value:.2f}")
                    else:
                        lines.append(f"  {sub_key}: {sub_value}")
            else:
                lines.append(f"{key}: {value}")
        return "\n".join(lines)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses."""
        if event.button.id == "retry":
            self.action_retry()
        elif event.button.id == "export":
            self.action_export_report()
        elif event.button.id == "continue":
            self.action_continue_anyway()
        elif event.button.id == "ok":
            self.app.pop_screen()
        elif event.button.id == "back":
            self.action_go_back()

    def action_export_report(self) -> None:
        """Export validation report to JSON file."""
        try:
            report_dir = Path.cwd() / "reports"
            report_dir.mkdir(parents=True, exist_ok=True)

            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            report_file = report_dir / f"validation_{self.result.stage}_{timestamp}.json"

            report_data = {
                "timestamp": datetime.now().isoformat(),
                "stage": self.result.stage,
                "valid": self.result.valid,
                "issues": [i.to_dict() for i in self.result.issues],
                "metadata": self.result.metadata,
            }

            with open(report_file, "w", encoding="utf-8") as f:
                json.dump(report_data, f, indent=2, ensure_ascii=False)

            self.app.notify(
                f"Rapor kaydedildi: {report_file.name}",
                title="Başarılı",
                severity="information",
            )
        except Exception as e:
            self.app.notify(
                f"Rapor kaydedilemedi: {e}",
                title="Hata",
                severity="error",
            )

    def action_retry(self) -> None:
        """Retry the render operation."""
        self.app.pop_screen()

    def action_continue_anyway(self) -> None:
        """Continue despite warnings (pre-render only)."""
        if self.result.stage == "pre_render" and not self.result.errors:
            # Set a flag to skip validation on next render
            self.app.skip_validation = True
            self.app.pop_screen()
        else:
            self.app.notify(
                "Hatalar varken devam edilemez",
                title="Uyarı",
                severity="error",
            )

    def action_go_back(self) -> None:
        """Go back to previous screen."""
        self.app.pop_screen()


# ═══════════════════════════════════════════════════════════════════════════════
# Validation Overlay (for in-app notifications)
# ═══════════════════════════════════════════════════════════════════════════════


class ValidationNotification(Static):
    """
    Floating notification widget for validation results.

    Can be shown as an overlay on any screen.
    """

    def __init__(self, result: ValidationResult, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.result = result

    def render(self) -> str:
        status_icon = "✓" if self.result.valid else "✗"
        status_color = "[green]" if self.result.valid else "[red]"

        text = f"{status_color}{status_icon} Doğrulama: "
        text += "Başarılı" if self.result.valid else f"Başarısız ({len(self.result.errors)} hata)"

        return text


# ═══════════════════════════════════════════════════════════════════════════════
# Convenience Functions
# ═══════════════════════════════════════════════════════════════════════════════


def show_validation_result(app, result: ValidationResult) -> None:
    """
    Show validation result screen or notification based on severity.

    - If valid: Show brief notification
    - If errors: Show full validation screen
    - If warnings only: Show screen with "continue" option
    """
    if result.valid:
        app.notify(
            "Doğrulama başarılı",
            title="✓ Tamam",
            severity="information",
            timeout=3,
        )
    elif result.errors:
        app.push_screen(ValidationScreen(result))
    else:  # Warnings only
        app.push_screen(ValidationScreen(result))

#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Complete Screen - Render completion summary with validation report export.
"""

from pathlib import Path
from datetime import datetime
import json

from textual.app import ComposeResult
from textual.screen import Screen
from textual.widgets import Static, Button, Footer
from textual.containers import Container, Vertical, Horizontal


class CompleteScreen(Screen):
    """Screen shown after successful render."""

    BINDINGS = [
        ("n", "new_render", "Yeni Render"),
        ("s", "show_summary", "Ozet"),
        ("d", "show_detail", "Detay"),
        ("e", "export_report", "Rapor Dışa Aktar"),
        ("q", "quit", "Cikis"),
    ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._review_mode = "summary"

    def compose(self) -> ComposeResult:
        result = getattr(self.app, "render_result", {})
        output_path = result.get("output", Path("output.mp4"))
        duration = result.get("duration", 0)
        validation = result.get("validation", {})
        post_result = validation.get("post_result")

        # Determine validation status
        validation_status = "✓ Başarılı"
        validation_class = "success-text"
        if post_result:
            if not post_result.valid:
                validation_status = "✗ Başarısız"
                validation_class = "error-text"
            elif post_result.warnings:
                validation_status = "⚠️ Uyarılarla"
                validation_class = "warning-text"

        yield Container(
            Static("🎉 Render Tamamlandi!", classes="title success-text"),
            classes="banner",
        )

        with Container(classes="panel"):
            yield Static("📋 Sonuc", classes="panel-title")
            yield Static(f"📁 Dosya: {output_path.name}", classes="info-text")
            yield Static(f"📂 Konum: {output_path.parent.as_posix()}", classes="subtitle")
            yield Static(f"⏱️ Sure: {self._format_duration(duration)}", classes="info-text")

            if output_path.exists():
                size_mb = output_path.stat().st_size / (1024 * 1024)
                yield Static(f"💾 Boyut: {size_mb:.1f} MB", classes="info-text")

            # Show validation status
            yield Static(f"🔍 Doğrulama: {validation_status}", classes=f"info-text {validation_class}")

            if post_result and post_result.issues:
                issues_count = len(post_result.issues)
                errors_count = len(post_result.errors)
                warnings_count = len(post_result.warnings)
                yield Static(
                    f"   - {errors_count} hata, {warnings_count} uyarı (toplam {issues_count})",
                    classes="subtitle"
                )

        with Container(classes="panel"):
            yield Static("🔎 Render Sonrasi Kontrol", classes="panel-title")
            yield Static("", id="review_text", classes="info-text")

        with Horizontal(classes="action-bar"):
            yield Button("📝 Ozet", id="summary", classes="-secondary")
            yield Button("📚 Detay", id="detail", classes="-secondary")
            yield Button("📄 Rapor Dışa Aktar", id="export", classes="-secondary")
            yield Button("🆕 Yeni Render", id="new", classes="-primary")
            yield Button("🚪 Cikis", id="quit", classes="-secondary")

        yield Footer()

    def on_mount(self) -> None:
        self._update_review_view()

    def _format_duration(self, seconds: float) -> str:
        """Format duration."""
        minutes, secs = divmod(int(seconds), 60)
        hours, minutes = divmod(minutes, 60)
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses."""
        if event.button.id == "summary":
            self.action_show_summary()
        elif event.button.id == "detail":
            self.action_show_detail()
        elif event.button.id == "export":
            self.action_export_report()
        elif event.button.id == "new":
            # Clear session and start fresh
            session_path = getattr(self.app, "session_file", Path.cwd() / "tmp" / "last_session.json")
            session_path.unlink(missing_ok=True)

            # Clear app state
            for attr in [
                "intro_path",
                "loop_path",
                "single_video_path",
                "single_video_info",
                "chosen_tracks",
                "chosen_bgs",
                "codec_family",
                "codec_config",
                "out_path",
                "session",
                "render_result",
                "render_mode",
            ]:
                if hasattr(self.app, attr):
                    delattr(self.app, attr)

            # Go to video select
            self.app.switch_screen("video_select")

        elif event.button.id == "quit":
            self.app.exit()

    def _update_review_view(self) -> None:
        """Render validation summary/detail text."""
        result = getattr(self.app, "render_result", {})
        validation = result.get("validation", {})
        post_result = validation.get("post_result")

        text_widget = self.query_one("#review_text", Static)

        if not post_result:
            text_widget.update("Doğrulama sonucu bulunamadı.")
            return

        if self._review_mode == "summary":
            output_meta = post_result.metadata.get("output", {}) if hasattr(post_result, "metadata") else {}
            youtube_meta = post_result.metadata.get("youtube", {}) if hasattr(post_result, "metadata") else {}

            summary_lines = [
                f"Durum: {'✅ Uygun' if post_result.valid else '❌ Sorunlu'}",
                f"Hata: {len(post_result.errors)} | Uyarı: {len(post_result.warnings)} | Bilgi: {len(post_result.info)}",
            ]

            if output_meta:
                summary_lines.append(
                    f"Cikti: {output_meta.get('codec', '-')} | {output_meta.get('width', '-') }x{output_meta.get('height', '-')} | {output_meta.get('fps', '-') }"
                )
                summary_lines.append(
                    f"Sure: hedef {output_meta.get('target_duration', '-')}s, gercek {float(output_meta.get('duration', 0)):.1f}s"
                )

            if youtube_meta:
                summary_lines.append(
                    f"YouTube: kapsayici={youtube_meta.get('format_name', '-')}, vcodec={youtube_meta.get('video_codec', '-')}, acodec={youtube_meta.get('audio_codec', '-')}"
                )

            text_widget.update("\n".join(summary_lines))
            return

        # Detail mode
        detail_lines = []
        if post_result.issues:
            for issue in post_result.issues:
                line = f"[{issue.severity.value.upper()}] ({issue.category}) {issue.message}"
                if issue.details:
                    line += f"\n  - {issue.details}"
                if issue.suggestion:
                    line += f"\n  - Oneri: {issue.suggestion}"
                detail_lines.append(line)
        else:
            detail_lines.append("Sorun bulunmadi.")

        text_widget.update("\n\n".join(detail_lines))

    def action_export_report(self) -> None:
        """Export validation report to JSON file."""
        try:
            result = getattr(self.app, "render_result", {})
            validation = result.get("validation", {})
            post_result = validation.get("post_result")

            if not post_result:
                self.app.notify(
                    "Dışa aktarılacak doğrulama verisi bulunamadı",
                    title="Hata",
                    severity="error"
                )
                return

            # Create reports directory
            reports_dir = Path.cwd() / "reports"
            reports_dir.mkdir(parents=True, exist_ok=True)

            # Generate filename with timestamp
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_path = result.get("output", Path("output.mp4"))
            filename = f"validation_{output_path.stem}_{timestamp}.json"
            report_file = reports_dir / filename

            # Export validation result
            report_data = {
                "timestamp": datetime.now().isoformat(),
                "render_result": {
                    "output": str(result.get("output", "")),
                    "duration": result.get("duration", 0),
                },
                "validation": {
                    "pre_render": validation.get("pre_render", False),
                    "post_render": validation.get("post_render", False),
                    "issues_count": validation.get("issues", 0),
                },
                "validation_result": post_result.to_dict() if hasattr(post_result, "to_dict") else {}
            }

            with open(report_file, "w", encoding="utf-8") as f:
                json.dump(report_data, f, indent=2, ensure_ascii=False)

            self.app.notify(
                f"Rapor kaydedildi: {report_file.name}",
                title="Başarılı",
                severity="information",
                timeout=5
            )

        except Exception as e:
            self.app.notify(
                f"Rapor dışa aktarılamadı: {str(e)}",
                title="Hata",
                severity="error"
            )

    def action_show_summary(self) -> None:
        self._review_mode = "summary"
        self._update_review_view()

    def action_show_detail(self) -> None:
        self._review_mode = "detail"
        self._update_review_view()

    def action_new_render(self) -> None:
        """Start new render."""
        self.on_button_pressed(Button.Pressed(self.query_one("#new", Button)))

    def action_quit(self) -> None:
        """Exit."""
        self.app.exit()

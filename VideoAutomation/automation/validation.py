#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Config validation modülü.

Pipeline configuration'ını validate eder ve üretim-ready kontrolü yapar.
"""

from pathlib import Path
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════════════
# Validation Result
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class ValidationResult:
    """Validation sonucu."""
    is_valid: bool
    errors: List[str]
    warnings: List[str]

    def __post_init__(self):
        """Validasyon sonucunu hesapla."""
        if self.is_valid is None:
            self.is_valid = len(self.errors) == 0

    def add_error(self, message: str):
        """Hata ekle."""
        self.errors.append(message)
        self.is_valid = False

    def add_warning(self, message: str):
        """Uyarı ekle."""
        self.warnings.append(message)

    def merge(self, other: 'ValidationResult'):
        """Başka bir sonucu birleştir."""
        self.errors.extend(other.errors)
        self.warnings.extend(other.warnings)
        self.is_valid = self.is_valid and other.is_valid


# ═══════════════════════════════════════════════════════════════════════════════
# Validators
# ═══════════════════════════════════════════════════════════════════════════════

class ConfigValidator:
    """Pipeline configuration validator."""

    def __init__(self):
        self.result = ValidationResult(is_valid=True, errors=[], warnings=[])

    def validate(self, config: Any) -> ValidationResult:
        """
        Config'i validate et.

        Args:
            config: PipelineConfig objesi

        Returns:
            ValidationResult
        """
        self.result = ValidationResult(is_valid=True, errors=[], warnings=[])

        # Directory validation
        self._validate_directories(config)

        # Video settings validation
        self._validate_video_settings(config)

        # YouTube config validation
        self._validate_youtube_config(config)

        # Pipeline settings validation
        self._validate_pipeline_settings(config)

        return self.result

    def _validate_directories(self, config):
        """Directory ayarlarını validate et."""
        # Work directory
        if config.work_dir is None:
            self.result.add_error("work_dir belirtilmemiş")
        else:
            work_dir = Path(config.work_dir)
            if not work_dir.exists():
                self.result.add_warning(f"work_dir mevcut değil: {work_dir}")

        # Music directory
        if config.music_dir is None:
            self.result.add_error("music_dir belirtilmemiş")
        else:
            music_dir = Path(config.music_dir)
            if not music_dir.exists():
                self.result.add_error(f"music_dir mevcut değil: {music_dir}")
            elif not list(music_dir.glob("*.mp3")):
                self.result.add_warning(f"music_dir'da MP3 dosyası yok: {music_dir}")

        # Output directory
        if config.output_dir is None:
            self.result.add_error("output_dir belirtilmemiş")
        else:
            output_dir = Path(config.output_dir)
            # Output directory create edilebilir, warning değil

    def _validate_video_settings(self, config):
        """Video ayarlarını validate et."""
        # Intro video
        if config.intro_video is not None:
            intro_path = Path(config.intro_video)
            if not intro_path.exists():
                self.result.add_error(f"intro_video mevcut değil: {intro_path}")
            elif intro_path.suffix.lower() not in {'.mp4', '.mkv', '.mov', '.avi'}:
                self.result.add_warning(f"intro_video formatı desteklenmeyebilir: {intro_path.suffix}")

        # Loop video
        if config.loop_video is not None:
            loop_path = Path(config.loop_video)
            if not loop_path.exists():
                self.result.add_error(f"loop_video mevcut değil: {loop_path}")
            elif loop_path.suffix.lower() not in {'.mp4', '.mkv', '.mov', '.avi'}:
                self.result.add_warning(f"loop_video formatı desteklenmeyebilir: {loop_path.suffix}")

        # Duration
        try:
            duration_parts = config.target_duration.split(":")
            if len(duration_parts) not in {2, 3}:
                self.result.add_error(f"Geçersiz duration formatı: {config.target_duration}")
            else:
                h, m, s = (0, 0, 0)
                if len(duration_parts) == 3:
                    h, m, s = map(int, duration_parts)
                else:
                    m, s = map(int, duration_parts)

                total_seconds = h * 3600 + m * 60 + s
                if total_seconds < 60:
                    self.result.add_warning(f"Duration çok kısa: {total_seconds}s")
                elif total_seconds > 24 * 3600:
                    self.result.add_warning(f"Duration çok uzun: {total_seconds}s")

        except (ValueError, AttributeError):
            self.result.add_error(f"Geçersiz duration formatı: {config.target_duration}")

        # Codec
        valid_codecs = {"av1", "h264", "h265", "vp9"}
        if config.codec.lower() not in valid_codecs:
            self.result.add_error(f"Geçersiz codec: {config.codec} (geçerli: {valid_codecs})")

    def _validate_youtube_config(self, config):
        """YouTube ayarlarını validate et."""
        yt_config = config.youtube

        if yt_config is None:
            self.result.add_warning("YouTube config belirtilmemiş")
            return

        # Client secrets
        if yt_config.client_secrets_file:
            secrets_path = Path(yt_config.client_secrets_file)
            if not secrets_path.exists():
                self.result.add_error(f"client_secrets.json mevcut değil: {secrets_path}")
            elif secrets_path.stat().st_size == 0:
                self.result.add_error(f"client_secrets.json boş: {secrets_path}")

        # Credentials
        if yt_config.credentials_file:
            creds_path = Path(yt_config.credentials_file)
            if not creds_path.exists():
                self.result.add_warning(f"credentials.json mevcut değil (ilk çalıştırmada normal): {creds_path}")

        # Privacy status
        valid_privacy = {"public", "private", "unlisted"}
        if yt_config.default_privacy.lower() not in valid_privacy:
            self.result.add_error(
                f"Geçersiz privacy status: {yt_config.default_privacy} "
                f"(geçerli: {valid_privacy})"
            )

        # Category
        try:
            category_id = int(yt_config.default_category)
            if not (1 <= category_id <= 999):
                self.result.add_warning(f"Şüpheli category ID: {category_id}")
        except (ValueError, TypeError):
            self.result.add_error(f"Geçersiz category ID: {yt_config.default_category}")

        # Title template
        if yt_config.title_template:
            required_vars = {"duration", "style", "genre"}
            template_vars = set()

            import re
            pattern = r"\{(\w+)\}"
            for match in re.finditer(pattern, yt_config.title_template):
                template_vars.add(match.group(1))

            missing = required_vars - template_vars
            if missing:
                self.result.add_warning(
                    f"Title template'de değişkenler eksik: {missing} "
                    f"(template: {yt_config.title_template})"
                )

            # Uzunluk kontrolü
            if len(yt_config.title_template) > 100:
                self.result.add_warning("Title template çok uzun (max 100 karakter)")

        # Description template
        if yt_config.description_template:
            if len(yt_config.description_template) > 5000:
                self.result.add_warning("Description template çok uzun (max 5000 karakter)")

        # Tags
        if yt_config.default_tags:
            if len(yt_config.default_tags) > 500:
                self.result.add_error(f"Çok fazla tag: {len(yt_config.default_tags)} (max 500)")

            for tag in yt_config.default_tags:
                if len(tag) > 500:
                    self.result.add_warning(f"Tag çok uzun: {tag[:30]}... (max 500 karakter)")

    def _validate_pipeline_settings(self, config):
        """Pipeline ayarlarını validate et."""
        # Delay between videos
        if config.delay_between_videos < 0:
            self.result.add_error("delay_between_videos negatif olamaz")
        elif config.delay_between_videos < 60:
            self.result.add_warning("delay_between_videos çok kısa (minimum 60s önerilir)")
        elif config.delay_between_videos > 86400:
            self.result.add_warning("delay_between_videos çok uzun (24 saat)")

        # Styles
        if not config.styles:
            self.result.add_warning("Styles listesi boş")
        elif len(config.styles) < 2:
            self.result.add_warning("Çok az style belirtilmiş")

        # Genres
        if not config.genres:
            self.result.add_warning("Genres listesi boş")
        elif len(config.genres) < 2:
            self.result.add_warning("Çok az genre belirtilmiş")


# ═══════════════════════════════════════════════════════════════════════════════
# Production Readiness Check
# ═══════════════════════════════════════════════════════════════════════════════

class ProductionReadinessChecker:
    """
    Production readiness kontrolü.

    Pipeline'ın prodüksiyon ortamında çalışmaya hazır olup olmadığını kontrol eder.
    """

    def __init__(self):
        self.result = ValidationResult(is_valid=True, errors=[], warnings=[])

    def check(self, config: Any) -> ValidationResult:
        """
        Prodüksiyon readiness kontrolü yap.

        Args:
            config: PipelineConfig objesi

        Returns:
            ValidationResult
        """
        self.result = ValidationResult(is_valid=True, errors=[], warnings=[])

        # Önce basic validation
        validator = ConfigValidator()
        basic_result = validator.validate(config)
        self.result.merge(basic_result)

        # Production-specific checks
        self._check_dependencies()
        self._check_disk_space(config)
        self._check_ffmpeg()
        self._check_credentials(config)

        return self.result

    def _check_dependencies(self):
        """Python dependencies'larını kontrol et."""
        required_packages = [
            ("googleapiclient", "google-api-python-client"),
            ("google_auth_oauthlib", "google-auth-oauthlib"),
            ("rich", "rich"),
        ]

        for package_name, pip_name in required_packages:
            try:
                __import__(package_name)
            except ImportError:
                self.result.add_error(f"Package kurulu değil: {pip_name}")

    def _check_disk_space(self, config):
        """Disk alanını kontrol et."""
        import shutil

        try:
            work_dir = Path(config.work_dir) if config.work_dir else Path.cwd()
            total, used, free = shutil.disk_usage(work_dir)

            # En az 10 GB boş alan
            required_gb = 10
            free_gb = free / (1024 ** 3)

            if free_gb < required_gb:
                self.result.add_warning(
                    f"Disk alanı düşük: {free_gb:.1f} GB (en az {required_gb} GB önerilir)"
                )

        except Exception as e:
            self.result.add_warning(f"Disk alanı kontrol edilemedi: {e}")

    def _check_ffmpeg(self):
        """FFmpeg kurulumunu kontrol et."""
        import subprocess

        try:
            result = subprocess.run(
                ["ffmpeg", "-version"],
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.returncode != 0:
                self.result.add_error("FFmpeg çalışmıyor")

        except FileNotFoundError:
            self.result.add_error("FFmpeg bulunamadı")
        except subprocess.TimeoutExpired:
            self.result.add_warning("FFmpeg zaman aşımı")
        except Exception:
            self.result.add_warning("FFmpeg kontrol edilemedi")

    def _check_credentials(self, config):
        """Credential dosyalarını kontrol et."""
        if config.youtube and config.youtube.client_secrets_file:
            secrets_path = Path(config.youtube.client_secrets_file)

            if secrets_path.exists():
                # JSON validate et
                import json
                try:
                    with open(secrets_path, 'r') as f:
                        data = json.load(f)

                    # Required fields
                    if "installed" not in data and "web" not in data:
                        self.result.add_error("client_secrets.json formatı geçersiz")

                except json.JSONDecodeError:
                    self.result.add_error("client_secrets.json geçersiz JSON")
                except Exception:
                    pass


def validate_config(config) -> ValidationResult:
    """
    Config validation快捷函数.

    Args:
        config: PipelineConfig objesi

    Returns:
        ValidationResult
    """
    validator = ConfigValidator()
    return validator.validate(config)


def check_production_readiness(config) -> ValidationResult:
    """
    Production readiness check快捷函数.

    Args:
        config: PipelineConfig objesi

    Returns:
        ValidationResult
    """
    checker = ProductionReadinessChecker()
    return checker.check(config)

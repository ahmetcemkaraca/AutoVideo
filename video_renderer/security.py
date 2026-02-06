#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Güvenlik modülü: Input validation, path security, ve sanitization.

Bu modül tüm kullanıcı girdilerini ve dosya yollarını güvenli bir şekilde
validate etmek için kullanılır.
"""

import os
import re
from pathlib import Path
from typing import Optional, List, Set
import logging

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════════════
# Constants
# ═══════════════════════════════════════════════════════════════════════════════

# İzin verilen video dosya formatları
ALLOWED_VIDEO_EXTENSIONS: Set[str] = {
    '.mp4', '.mkv', '.mov', '.avi', '.webm', '.flv', '.wmv'
}

# İzin verilen audio dosya formatları
ALLOWED_AUDIO_EXTENSIONS: Set[str] = {
    '.mp3', '.wav', '.flac', '.ogg', '.wma', '.aac', '.m4a', '.w64'
}

# İzin verilen resim formatları
ALLOWED_IMAGE_EXTENSIONS: Set[str] = {
    '.jpg', '.jpeg', '.png', '.webp', '.bmp'
}

# Tehlikeli karakterler (path traversal için)
DANGEROUS_CHARS = set('..\\\\')

# Max dosya boyutu (100 GB)
MAX_FILE_SIZE = 100 * 1024 * 1024 * 1024

# Min dosya boyutu (1 KB - boş/corrupted dosya kontrolü)
MIN_FILE_SIZE = 1024


# ═══════════════════════════════════════════════════════════════════════════════
# Path Security
# ═══════════════════════════════════════════════════════════════════════════════

class PathSecurityError(Exception):
    """Path güvenliği hatası."""
    pass


def validate_path(
    path: Path | str,
    allowed_extensions: Optional[Set[str]] = None,
    base_dir: Optional[Path] = None,
    check_exists: bool = False,
    max_size: Optional[int] = None
) -> Path:
    """
    Dosya yolunu güvenli bir şekilde validate eder.

    Args:
        path: Validate edilecek dosya yolu
        allowed_extensions: İzin verilen dosya uzantıları
        base_dir: Base directory (path traversal kontrolü için)
        check_exists: Dosya varlığını kontrol et
        max_size: Maksimum dosya boyutu

    Returns:
        Validate edilmiş Path objesi

    Raises:
        PathSecurityError: Güvenlik ihlali tespit edilirse
    """
    if isinstance(path, str):
        # String'deki tehlikeli karakterleri kontrol et
        if '..' in path or '\\\\' in path:
            raise PathSecurityError(f"Tehlikeli path tespit edildi: {path}")
        path = Path(path)

    # Path'i resolve et (symlink attack önlemi)
    try:
        resolved_path = path.resolve()
    except (OSError, RuntimeError) as e:
        raise PathSecurityError(f"Path resolve edilemedi: {path}") from e

    # Base directory kontrolü (path traversal)
    if base_dir is not None:
        try:
            resolved_base = base_dir.resolve()
            # Path'in base directory içinde olduğunu kontrol et
            try:
                resolved_path.relative_to(resolved_base)
            except ValueError:
                raise PathSecurityError(
                    f"Path base directory dışında: {resolved_path} "
                    f"(base: {resolved_base})"
                )
        except (OSError, RuntimeError) as e:
            raise PathSecurityError(f"Base directory resolve edilemedi: {base_dir}") from e

    # Dosya uzantısı kontrolü
    if allowed_extensions is not None:
        ext = resolved_path.suffix.lower()
        if ext not in allowed_extensions:
            raise PathSecurityError(
                f"İzin verilmeyen dosya uzantısı: {ext} "
                f"(izin verilen: {allowed_extensions})"
            )

    # Dosya varlığı kontrolü
    if check_exists and not resolved_path.exists():
        raise PathSecurityError(f"Dosya bulunamadı: {resolved_path}")

    # Dosya boyutu kontrolü
    if resolved_path.exists():
        try:
            file_size = resolved_path.stat().st_size
            if file_size < MIN_FILE_SIZE:
                raise PathSecurityError(
                    f"Dosya çok küçük (boş/corrupted olabilir): {resolved_path}"
                )
            if max_size is not None and file_size > max_size:
                raise PathSecurityError(
                    f"Dosya boyutu sınırı aşıldı: {file_size} > {max_size}"
                )
            if file_size > MAX_FILE_SIZE:
                raise PathSecurityError(
                    f"Dosya çok büyük: {file_size} > {MAX_FILE_SIZE}"
                )
        except OSError as e:
            raise PathSecurityError(f"Dosya bilgisi alınamadı: {resolved_path}") from e

    return resolved_path


def validate_video_path(path: Path | str, base_dir: Optional[Path] = None) -> Path:
    """Video dosyası path'ini validate eder."""
    return validate_path(
        path,
        allowed_extensions=ALLOWED_VIDEO_EXTENSIONS,
        base_dir=base_dir,
        check_exists=True,
        max_size=MAX_FILE_SIZE
    )


def validate_audio_path(path: Path | str, base_dir: Optional[Path] = None) -> Path:
    """Audio dosyası path'ini validate eder."""
    return validate_path(
        path,
        allowed_extensions=ALLOWED_AUDIO_EXTENSIONS,
        base_dir=base_dir,
        check_exists=True,
        max_size=MAX_FILE_SIZE
    )


def validate_image_path(path: Path | str, base_dir: Optional[Path] = None) -> Path:
    """Resim dosyası path'ini validate eder."""
    return validate_path(
        path,
        allowed_extensions=ALLOWED_IMAGE_EXTENSIONS,
        base_dir=base_dir,
        check_exists=True,
        max_size=50 * 1024 * 1024  # 50 MB max for images
    )


# ═══════════════════════════════════════════════════════════════════════════════
# Input Sanitization
# ═══════════════════════════════════════════════════════════════════════════════

def sanitize_filename(filename: str, max_length: int = 255) -> str:
    """
    Dosya ismini güvenli hale getirir.

    Args:
        filename: Temizlenecek dosya ismi
        max_length: Maksimum uzunluk

    Returns:
        Güvenli dosya ismi
    """
    # Tehlikeli karakterleri kaldır
    # Sadece alfanümerik, tire, alt çizgi, ve nokta bırak
    safe = re.sub(r'[^\w\-.]', '_', filename)

    # Sondaki noktaları ve boşlukları kaldır (Windows güvenliği)
    safe = safe.rstrip('. ')

    # Uzunluk kontrolü
    if len(safe) > max_length:
        # Uzantıyı koru
        name_part, ext = os.path.splitext(safe)
        safe = name_part[:max_length - len(ext)] + ext

    # Boş isim kontrolü
    if not safe or safe == '.':
        safe = 'unnamed'

    return safe


def sanitize_path_string(path_str: str) -> str:
    """
    Path string'ini güvenli hale getirir.

    Args:
        path_str: Temizlenecek path string'i

    Returns:
        Güvenli path string
    """
    # Path traversal karakterlerini kaldır
    safe = path_str.replace('..', '').replace('\\\\', '/')

    # Absolute path'i koru
    if os.path.isabs(path_str):
        return '/' + safe.lstrip('/')
    return safe


def safe_join(base: Path, *paths: str) -> Path:
    """
    Güvenli path birleştirme (os.path.join güvenli versiyonu).

    Args:
        base: Base directory
        *paths: Birleştirilecek path parçaları

    Returns:
        Güvenli birleştirilmiş path

    Raises:
        PathSecurityError: Sonuç base directory dışına çıkarsa
    """
    result = base
    for p in paths:
        # Her parçayı sanitize et
        safe_part = sanitize_path_string(p)
        result = result / safe_part

    # Sonucu resolve et ve base içinde olduğunu kontrol et
    try:
        resolved = result.resolve()
        resolved_base = base.resolve()
        resolved.relative_to(resolved_base)
    except ValueError:
        raise PathSecurityError(
            f"Path birleştirme sonucu base dışında: {result}"
        )

    return result


# ═══════════════════════════════════════════════════════════════════════════════
# Command Injection Prevention
# ═══════════════════════════════════════════════════════════════════════════════

def validate_command_arg(arg: str) -> bool:
    """
    Komut argümanını validate eder (command injection önlemi).

    Args:
        arg: Validate edilecek argüman

    Returns:
        True güvenliyse, False değilse
    """
    # Tehlikeli karakterleri kontrol et
    dangerous_patterns = [
        r';',          # Command separator
        r'&&', r'\|\|',  # Command chaining
        r'\|',         # Pipe
        r'\$',         # Variable expansion
        r'\`',         # Command substitution
        r'\$',         # Variable expansion
        r'\(', r'\)',  # Subshell
        r'<', r'>',    # Redirection
        r'&',          # Background execution
    ]

    arg_lower = arg.lower()
    for pattern in dangerous_patterns:
        if re.search(pattern, arg):
            logger.warning(f"Tehlikeli komut argümanı tespit edildi: {arg}")
            return False

    return True


def validate_ffmpeg_args(args: List[str]) -> bool:
    """
    FFmpeg argümanlarını validate eder.

    Args:
        args: FFmpeg komut argüman listesi

    Returns:
        True güvenliyse, False değilse
    """
    for arg in args:
        # Her argümanı validate et
        if not isinstance(arg, str):
            logger.error(f"Argüman string değil: {type(arg)}")
            return False

        if not validate_command_arg(arg):
            return False

    return True


# ═══════════════════════════════════════════════════════════════════════════════
# File Content Validation
# ═══════════════════════════════════════════════════════════════════════════════

def validate_media_file(path: Path) -> bool:
    """
    Medya dosyasının gerçekten medya dosyası olduğunu kontrol eder.

    Bu fonksiyon dosya uzantısının içerikle uyumlu olup olmadığını kontrol eder.
    FFmpeg ile doğrulama yapar.

    Args:
        path: Kontrol edilecek dosya yolu

    Returns:
        True dosya geçerliyse, False değilse
    """
    import subprocess

    try:
        # ffprobe ile dosyayı kontrol et
        result = subprocess.run(
            [
                'ffprobe',
                '-v', 'error',
                '-select_streams', 'v:0',
                '-show_entries', 'stream=codec_name',
                '-of', 'default=noprint_wrappers=1:nokey=1',
                str(path)
            ],
            capture_output=True,
            text=True,
            timeout=10  # 10 saniye timeout
        )

        # Video stream'i bulduysa geçerli
        if result.returncode == 0 and result.stdout.strip():
            return True

        # Video yoksa audio kontrol et
        result = subprocess.run(
            [
                'ffprobe',
                '-v', 'error',
                '-select_streams', 'a:0',
                '-show_entries', 'stream=codec_name',
                '-of', 'default=noprint_wrappers=1:nokey=1',
                str(path)
            ],
            capture_output=True,
            text=True,
            timeout=10
        )

        return result.returncode == 0 and bool(result.stdout.strip())

    except (subprocess.TimeoutExpired, FileNotFoundError, subprocess.SubprocessError):
        logger.warning(f"Medya doğrulama hatası: {path}")
        return False

#!/usr/bin/env python3
"""
Güvenlik modülü: Input validation, path security, ve sanitization.

Bu modül tüm kullanıcı girdilerini ve dosya yollarını güvenli bir şekilde
validate etmek için kullanılır.
"""

import hashlib
import json
import logging
import os
import re
import secrets
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════════════
# Constants
# ═══════════════════════════════════════════════════════════════════════════════

# İzin verilen video dosya formatları
ALLOWED_VIDEO_EXTENSIONS: set[str] = {".mp4", ".mkv", ".mov", ".avi", ".webm", ".flv", ".wmv"}

# İzin verilen audio dosya formatları
ALLOWED_AUDIO_EXTENSIONS: set[str] = {
    ".mp3",
    ".wav",
    ".flac",
    ".ogg",
    ".wma",
    ".aac",
    ".m4a",
    ".w64",
}

# İzin verilen resim formatları
ALLOWED_IMAGE_EXTENSIONS: set[str] = {".jpg", ".jpeg", ".png", ".webp", ".bmp"}

# Tehlikeli karakterler (path traversal için)
DANGEROUS_CHARS = set("..\\\\")

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
    allowed_extensions: set[str] | None = None,
    base_dir: Path | None = None,
    check_exists: bool = False,
    max_size: int | None = None,
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
        if ".." in path or "\\\\" in path:
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
                    f"Path base directory dışında: {resolved_path} " f"(base: {resolved_base})"
                )
        except (OSError, RuntimeError) as e:
            raise PathSecurityError(f"Base directory resolve edilemedi: {base_dir}") from e

    # Dosya uzantısı kontrolü
    if allowed_extensions is not None:
        ext = resolved_path.suffix.lower()
        if ext not in allowed_extensions:
            raise PathSecurityError(
                f"İzin verilmeyen dosya uzantısı: {ext} " f"(izin verilen: {allowed_extensions})"
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
                raise PathSecurityError(f"Dosya boyutu sınırı aşıldı: {file_size} > {max_size}")
            if file_size > MAX_FILE_SIZE:
                raise PathSecurityError(f"Dosya çok büyük: {file_size} > {MAX_FILE_SIZE}")
        except OSError as e:
            raise PathSecurityError(f"Dosya bilgisi alınamadı: {resolved_path}") from e

    return resolved_path


def validate_video_path(path: Path | str, base_dir: Path | None = None) -> Path:
    """Video dosyası path'ini validate eder."""
    return validate_path(
        path,
        allowed_extensions=ALLOWED_VIDEO_EXTENSIONS,
        base_dir=base_dir,
        check_exists=True,
        max_size=MAX_FILE_SIZE,
    )


def validate_audio_path(path: Path | str, base_dir: Path | None = None) -> Path:
    """Audio dosyası path'ini validate eder."""
    return validate_path(
        path,
        allowed_extensions=ALLOWED_AUDIO_EXTENSIONS,
        base_dir=base_dir,
        check_exists=True,
        max_size=MAX_FILE_SIZE,
    )


def validate_image_path(path: Path | str, base_dir: Path | None = None) -> Path:
    """Resim dosyası path'ini validate eder."""
    return validate_path(
        path,
        allowed_extensions=ALLOWED_IMAGE_EXTENSIONS,
        base_dir=base_dir,
        check_exists=True,
        max_size=50 * 1024 * 1024,  # 50 MB max for images
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
    safe = re.sub(r"[^\w\-.]", "_", filename)

    # Sondaki noktaları ve boşlukları kaldır (Windows güvenliği)
    safe = safe.rstrip(". ")

    # Uzunluk kontrolü
    if len(safe) > max_length:
        # Uzantıyı koru
        name_part, ext = os.path.splitext(safe)
        safe = name_part[: max_length - len(ext)] + ext

    # Boş isim kontrolü
    if not safe or safe == ".":
        safe = "unnamed"

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
    safe = path_str.replace("..", "").replace("\\\\", "/")

    # Absolute path'i koru
    if os.path.isabs(path_str):
        return "/" + safe.lstrip("/")
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
        raise PathSecurityError(f"Path birleştirme sonucu base dışında: {result}")

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
        r";",  # Command separator
        r"&&",
        r"\|\|",  # Command chaining
        r"\|",  # Pipe
        r"\$",  # Variable expansion
        r"\`",  # Command substitution
        r"\$",  # Variable expansion
        r"\(",
        r"\)",  # Subshell
        r"<",
        r">",  # Redirection
        r"&",  # Background execution
    ]

    arg_lower = arg.lower()
    for pattern in dangerous_patterns:
        if re.search(pattern, arg):
            logger.warning(f"Tehlikeli komut argümanı tespit edildi: {arg}")
            return False

    return True


def validate_ffmpeg_args(args: list[str]) -> bool:
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
                "ffprobe",
                "-v",
                "error",
                "-select_streams",
                "v:0",
                "-show_entries",
                "stream=codec_name",
                "-of",
                "default=noprint_wrappers=1:nokey=1",
                str(path),
            ],
            capture_output=True,
            text=True,
            timeout=10,  # 10 saniye timeout
        )

        # Video stream'i bulduysa geçerli
        if result.returncode == 0 and result.stdout.strip():
            return True

        # Video yoksa audio kontrol et
        result = subprocess.run(
            [
                "ffprobe",
                "-v",
                "error",
                "-select_streams",
                "a:0",
                "-show_entries",
                "stream=codec_name",
                "-of",
                "default=noprint_wrappers=1:nokey=1",
                str(path),
            ],
            capture_output=True,
            text=True,
            timeout=10,
        )

        return result.returncode == 0 and bool(result.stdout.strip())

    except (subprocess.TimeoutExpired, FileNotFoundError, subprocess.SubprocessError):
        logger.warning(f"Medya doğrulama hatası: {path}")
        return False


# ═══════════════════════════════════════════════════════════════════════════════
# Credential Security
# ═══════════════════════════════════════════════════════════════════════════════


def check_file_permissions(path: Path, expected_mode: int | None = None) -> bool:
    """
    Check if credential file has secure permissions.

    Args:
        path: Path to the credential file
        expected_mode: Expected permission mode (octal).
                      Defaults to 0600 on POSIX, None on Windows.

    Returns:
        True if permissions are secure, False otherwise
    """
    if not path.exists():
        return True  # Non-existent files are OK

    try:
        stat_info = path.stat()
        file_mode = stat_info.st_mode

        if os.name == "posix":
            # POSIX systems - check permission bits
            if expected_mode is None:
                expected_mode = 0o600

            mode = file_mode & 0o777
            if mode != expected_mode:
                logger.warning(
                    f"Insecure file permissions on {path}: {oct(mode)} "
                    f"(expected {oct(expected_mode)})"
                )
                return False

            # Check that file is owned by current user
            if stat_info.st_uid != os.getuid():
                logger.warning(f"File not owned by current user: {path}")
                return False

        elif os.name == "nt":
            # Windows systems - check for Everyone/Anonymous access
            try:
                import win32api
                import win32con
                import win32security

                # Get security descriptor
                sd = win32security.GetFileSecurity(
                    str(path), win32security.DACL_SECURITY_INFORMATION
                )
                dacl = sd.GetSecurityDescriptorDacl()

                if dacl:
                    for ace_index in range(dacl.GetAceCount()):
                        ace = dacl.GetAce(ace_index)
                        sid = ace[2]

                        # Check for Everyone or Anonymous Logon
                        account_name = win32security.LookupAccountSid(None, sid)[0]

                        if account_name in ["Everyone", "ANONYMOUS LOGON"]:
                            logger.warning(f"File accessible to everyone: {path}")
                            return False

            except ImportError:
                # win32security not available - skip detailed check
                logger.debug("win32security not available for permission check")

        # Additional check: ensure parent directory is secure
        parent = path.parent
        if parent.exists():
            parent_stat = parent.stat()
            if os.name == "posix":
                parent_mode = parent_stat.st_mode & 0o777
                # Parent should not be world-writable
                if parent_mode & 0o002:
                    logger.warning(f"Parent directory is world-writable: {parent}")
                    return False

        return True

    except OSError as e:
        logger.error(f"Failed to check file permissions for {path}: {e}")
        return False


def set_secure_permissions(path: Path) -> bool:
    """
    Set secure permissions on a file.

    Args:
        path: Path to the file

    Returns:
        True if successful, False otherwise
    """
    if not path.exists():
        return True

    try:
        if os.name == "posix":
            # Set 0600 (read/write for owner only)
            os.chmod(path, 0o600)
        elif os.name == "nt":
            # Windows - remove inherited permissions
            try:
                import win32api
                import win32con
                import win32security

                # Get current user
                user_sid = win32security.GetTokenInformation(
                    win32security.OpenProcessToken(
                        win32api.GetCurrentProcess(), win32con.TOKEN_QUERY
                    ),
                    win32security.TokenUser,
                )[0]

                # Create new security descriptor
                sd = win32security.SECURITY_DESCRIPTOR()
                sd.SetSecurityDescriptorOwner(user_sid, False)

                # Create DACL granting full control to owner only
                dacl = win32security.ACL()
                dacl.AddAccessAllowedAce(
                    win32security.ACL_REVISION_DS, win32con.FILE_ALL_ACCESS, user_sid
                )
                sd.SetSecurityDescriptorDacl(1, dacl, 0)

                # Apply security descriptor
                win32security.SetFileSecurity(
                    str(path), win32security.DACL_SECURITY_INFORMATION, sd
                )

            except ImportError:
                # win32security not available - skip Windows-specific setup
                logger.debug("win32security not available for setting permissions")

        return True

    except OSError as e:
        logger.error(f"Failed to set secure permissions for {path}: {e}")
        return False


def validate_client_secrets(path: Path) -> bool:
    """
    Validate client_secrets.json format and structure.

    Args:
        path: Path to the client_secrets.json file

    Returns:
        True if valid, False otherwise
    """
    if not path.exists():
        logger.error(f"Client secrets file not found: {path}")
        return False

    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)

        # Check for valid client type
        if "installed" not in data and "web" not in data:
            logger.error("Invalid client_secrets.json format: " "missing 'installed' or 'web' key")
            return False

        # Get client config
        client_config = data.get("installed") or data.get("web")

        # Validate required fields
        required_fields = ["client_id", "client_secret"]
        for field in required_fields:
            if field not in client_config:
                logger.error(f"Invalid client_secrets.json: missing required field '{field}'")
                return False

        # Check for redirect URIs
        if "redirect_uris" not in client_config:
            logger.warning("client_secrets.json missing 'redirect_uris' field")

        # Check for insecure configurations
        if "redirect_uris" in client_config:
            redirect_uris = client_config["redirect_uris"]
            if any(uri.startswith("http://") for uri in redirect_uris if uri):
                logger.warning("client_secrets.json contains insecure HTTP redirect URIs")

        return True

    except json.JSONDecodeError as e:
        logger.error(f"Invalid JSON in client_secrets.json: {e}")
        return False
    except Exception as e:
        logger.error(f"Client secrets validation failed: {e}")
        return False


def generate_oauth_state() -> str:
    """
    Generate a cryptographically secure OAuth state parameter.

    Returns:
        URL-safe random state string
    """
    return secrets.token_urlsafe(16)


def hash_file(path: Path, algorithm: str = "sha256") -> str:
    """
    Calculate hash of a file.

    Args:
        path: Path to the file
        algorithm: Hash algorithm (sha256, sha512, md5)

    Returns:
        Hexadecimal hash string
    """
    hash_func = hashlib.new(algorithm)

    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            hash_func.update(chunk)

    return hash_func.hexdigest()


def validate_integrity(path: Path, expected_hash: str, algorithm: str = "sha256") -> bool:
    """
    Validate file integrity using hash comparison.

    Args:
        path: Path to the file
        expected_hash: Expected hash value
        algorithm: Hash algorithm (sha256, sha512, md5)

    Returns:
        True if hash matches, False otherwise
    """
    try:
        actual_hash = hash_file(path, algorithm)
        return actual_hash.lower() == expected_hash.lower()
    except Exception as e:
        logger.error(f"Integrity validation failed for {path}: {e}")
        return False


def sanitize_log_data(
    data: dict[str, Any], sensitive_keys: list[str] | None = None
) -> dict[str, Any]:
    """
    Sanitize dictionary data for logging by redacting sensitive fields.

    Args:
        data: Dictionary to sanitize
        sensitive_keys: List of keys to redact (default: auto-detected)

    Returns:
        Sanitized dictionary
    """
    if sensitive_keys is None:
        sensitive_keys = [
            "password",
            "passwd",
            "pwd",
            "token",
            "access_token",
            "refresh_token",
            "secret",
            "client_secret",
            "api_key",
            "authorization",
            "auth",
        ]

    sanitized = {}
    for key, value in data.items():
        key_lower = key.lower()
        if any(sensitive in key_lower for sensitive in sensitive_keys):
            if isinstance(value, str) and len(value) > 4:
                # Show last 4 characters for debugging
                sanitized[key] = f"[REDACTED: ...{value[-4:]}]"
            else:
                sanitized[key] = "[REDACTED]"
        else:
            sanitized[key] = value

    return sanitized

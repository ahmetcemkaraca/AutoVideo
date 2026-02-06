#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Audit ve logging modülü.

Bu modül güvenlik olaylarını loglamak ve audit trail oluşturmak için kullanılır.
"""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional
from dataclasses import dataclass, asdict
from enum import Enum
import threading

logger = logging.getLogger(__name__)

# Import sensitive data filter
try:
    from video_renderer.log_filters import SensitiveDataFilter
except ImportError:
    # Fallback if log_filters is not available
    class SensitiveDataFilter(logging.Filter):
        """Fallback filter implementation."""
        def filter(self, record):
            return True


# ═══════════════════════════════════════════════════════════════════════════════
# Audit Event Types
# ═══════════════════════════════════════════════════════════════════════════════

class AuditEventType(Enum):
    """Audit olay tipleri."""

    # Authentication olayları
    AUTH_SUCCESS = "auth_success"
    AUTH_FAILURE = "auth_failure"
    AUTH_REFRESH = "auth_refresh"
    AUTH_LOGOUT = "auth_logout"

    # File operation olayları
    FILE_READ = "file_read"
    FILE_WRITE = "file_write"
    FILE_DELETE = "file_delete"
    FILE_DOWNLOAD = "file_download"
    FILE_UPLOAD = "file_upload"

    # Video processing olayları
    VIDEO_ENCODE_START = "video_encode_start"
    VIDEO_ENCODE_COMPLETE = "video_encode_complete"
    VIDEO_ENCODE_FAILURE = "video_encode_failure"

    # Configuration olayları
    CONFIG_READ = "config_read"
    CONFIG_WRITE = "config_write"
    CONFIG_CHANGE = "config_change"

    # Security olayları
    SECURITY_VIOLATION = "security_violation"
    SECURITY_WARNING = "security_warning"
    PATH_TRAVERSAL_ATTEMPT = "path_traversal_attempt"
    COMMAND_INJECTION_ATTEMPT = "command_injection_attempt"

    # API olayları
    API_CALL = "api_call"
    API_SUCCESS = "api_success"
    API_FAILURE = "api_failure"


# ═══════════════════════════════════════════════════════════════════════════════
# Audit Event
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class AuditEvent:
    """Audit olayı."""

    event_type: AuditEventType
    timestamp: str
    source: str
    details: Dict[str, Any]
    severity: str = "INFO"  # INFO, WARNING, ERROR, CRITICAL
    user_id: Optional[str] = None
    ip_address: Optional[str] = None
    session_id: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Dict olarak döndürür."""
        return {
            "event_type": self.event_type.value,
            "timestamp": self.timestamp,
            "source": self.source,
            "severity": self.severity,
            "user_id": self.user_id,
            "ip_address": self.ip_address,
            "session_id": self.session_id,
            "details": self.details,
        }


# ═══════════════════════════════════════════════════════════════════════════════
# Audit Logger
# ═══════════════════════════════════════════════════════════════════════════════

class AuditLogger:
    """
    Audit logger sınıfı.

    Bu sınıf:
    - Güvenlik olaylarını loglar
    - Audit trail oluşturur
    - Log dosyalarını yönetir
    """

    def __init__(
        self,
        log_dir: Optional[Path] = None,
        app_name: str = "video_renderer",
        enable_console: bool = True,
        enable_sensitive_filter: bool = True
    ):
        """
        Args:
            log_dir: Log dizini
            app_name: Uygulama adı
            enable_console: Konsol loglaması açık mı
            enable_sensitive_filter: Hassas veri filtresi açık mı
        """
        self.log_dir = Path(log_dir) if log_dir else Path.cwd() / "logs"
        self.app_name = app_name
        self.enable_console = enable_console
        self.enable_sensitive_filter = enable_sensitive_filter
        self._lock = threading.Lock()

        # Log dizinini oluştur
        self.log_dir.mkdir(parents=True, exist_ok=True)

        # Log dosyaları
        self.audit_log_file = self.log_dir / f"{app_name}_audit.log"
        self.security_log_file = self.log_dir / f"{app_name}_security.log"

        # Setup sensitive data filter
        self._sensitive_filter = None
        if enable_sensitive_filter:
            try:
                self._sensitive_filter = SensitiveDataFilter()
            except Exception:
                self._sensitive_filter = None

    def log_event(
        self,
        event_type: AuditEventType,
        source: str,
        details: Dict[str, Any],
        severity: str = "INFO",
        user_id: Optional[str] = None,
        ip_address: Optional[str] = None,
        session_id: Optional[str] = None
    ) -> None:
        """
        Audit olayını loglar.

        Args:
            event_type: Olay tipi
            source: Olay kaynağı (modül/ad)
            details: Olay detayları
            severity: Severite seviyesi
            user_id: Kullanıcı ID
            ip_address: IP adresi
            session_id: Oturum ID
        """
        event = AuditEvent(
            event_type=event_type,
            timestamp=datetime.utcnow().isoformat(),
            source=source,
            details=details,
            severity=severity,
            user_id=user_id,
            ip_address=ip_address,
            session_id=session_id
        )

        with self._lock:
            # Sanitize details if sensitive data filter is enabled
            sanitized_details = details
            if self._sensitive_filter:
                # Convert details to string for filtering
                details_str = json.dumps(details, ensure_ascii=False)
                # Apply filter
                sanitized_details_str = self._sensitive_filter._redact(details_str)
                try:
                    sanitized_details = json.loads(sanitized_details_str)
                except json.JSONDecodeError:
                    sanitized_details = details

            # Update event with sanitized details
            event.details = sanitized_details

            # JSON formatında logla
            log_line = json.dumps(event.to_dict(), ensure_ascii=False)

            # Audit log dosyasına yaz
            try:
                with open(self.audit_log_file, 'a', encoding='utf-8') as f:
                    f.write(log_line + '\n')
            except OSError as e:
                logger.error(f"Cannot write to audit log: {e}")

            # Security olaylarını ayrı dosyaya yaz
            if event_type in [
                AuditEventType.SECURITY_VIOLATION,
                AuditEventType.PATH_TRAVERSAL_ATTEMPT,
                AuditEventType.COMMAND_INJECTION_ATTEMPT,
            ]:
                try:
                    with open(self.security_log_file, 'a', encoding='utf-8') as f:
                        f.write(log_line + '\n')
                except OSError as e:
                    logger.error(f"Cannot write to security log: {e}")

            # Konsola yaz (isteğe bağlı)
            if self.enable_console:
                log_msg = f"[{event.event_type.value}] {source}: {details}"
                if severity == "CRITICAL":
                    logger.critical(log_msg)
                elif severity == "ERROR":
                    logger.error(log_msg)
                elif severity == "WARNING":
                    logger.warning(log_msg)
                else:
                    logger.info(log_msg)

    def log_file_access(
        self,
        action: str,
        filepath: Path,
        source: str,
        user_id: Optional[str] = None
    ) -> None:
        """
        Dosya erişimini loglar.

        Args:
            action: Action (read/write/delete)
            filepath: Dosya yolu
            source: Kaynak modül
            user_id: Kullanıcı ID
        """
        event_type = {
            "read": AuditEventType.FILE_READ,
            "write": AuditEventType.FILE_WRITE,
            "delete": AuditEventType.FILE_DELETE,
            "upload": AuditEventType.FILE_UPLOAD,
            "download": AuditEventType.FILE_DOWNLOAD,
        }.get(action, AuditEventType.FILE_READ)

        self.log_event(
            event_type=event_type,
            source=source,
            details={
                "filepath": str(filepath),
                "action": action,
                "size": filepath.stat().st_size if filepath.exists() else None,
            },
            user_id=user_id
        )

    def log_auth_event(
        self,
        success: bool,
        service: str,
        source: str,
        error: Optional[str] = None
    ) -> None:
        """
        Authentication olayını loglar.

        Args:
            success: Başarılı mı
            service: Service adı (youtube, gdrive, vb.)
            source: Kaynak modül
            error: Hata mesajı (başarısızsa)
        """
        event_type = AuditEventType.AUTH_SUCCESS if success else AuditEventType.AUTH_FAILURE
        severity = "INFO" if success else "WARNING"

        details = {
            "service": service,
        }

        if error:
            details["error"] = error

        self.log_event(
            event_type=event_type,
            source=source,
            details=details,
            severity=severity
        )

    def log_security_violation(
        self,
        violation_type: str,
        details: Dict[str, Any],
        source: str,
        severity: str = "WARNING"
    ) -> None:
        """
        Güvenlik ihlalini loglar.

        Args:
            violation_type: İhlal tipi
            details: İhlal detayları
            source: Kaynak modül
            severity: Severite
        """
        event_type = {
            "path_traversal": AuditEventType.PATH_TRAVERSAL_ATTEMPT,
            "command_injection": AuditEventType.COMMAND_INJECTION_ATTEMPT,
        }.get(violation_type, AuditEventType.SECURITY_VIOLATION)

        self.log_event(
            event_type=event_type,
            source=source,
            details=details,
            severity=severity
        )

    def log_video_encode(
        self,
        video_path: Path,
        success: bool,
        duration: Optional[float] = None,
        error: Optional[str] = None,
        source: str = "video_encoder"
    ) -> None:
        """
        Video encoding olayını loglar.

        Args:
            video_path: Video dosya yolu
            success: Başarılı mı
            duration: İşlem süresi (saniye)
            error: Hata mesajı
            source: Kaynak modül
        """
        if success:
            event_type = AuditEventType.VIDEO_ENCODE_COMPLETE
            severity = "INFO"
        else:
            event_type = AuditEventType.VIDEO_ENCODE_FAILURE
            severity = "ERROR"

        details = {
            "video_path": str(video_path),
        }

        if duration is not None:
            details["duration_seconds"] = duration

        if error:
            details["error"] = error

        self.log_event(
            event_type=event_type,
            source=source,
            details=details,
            severity=severity
        )

    def get_recent_events(
        self,
        event_type: Optional[AuditEventType] = None,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """
        Son olayları okur.

        Args:
            event_type: Filtrelenecek olay tipi
            limit: Maksimum olay sayısı

        Returns:
            Olay listesi
        """
        events = []

        try:
            with open(self.audit_log_file, 'r', encoding='utf-8') as f:
                lines = f.readlines()

            # Son N satırı al
            for line in reversed(lines[-limit:]):
                try:
                    event = json.loads(line.strip())
                    if event_type is None or event["event_type"] == event_type.value:
                        events.append(event)
                except (json.JSONDecodeError, KeyError):
                    continue

        except FileNotFoundError:
            pass

        return events

    def get_security_events(self, limit: int = 100) -> List[Dict[str, Any]]:
        """
        Güvenlik olaylarını okur.

        Args:
            limit: Maksimum olay sayısı

        Returns:
            Güvenlik olayları listesi
        """
        events = []

        try:
            with open(self.security_log_file, 'r', encoding='utf-8') as f:
                lines = f.readlines()

            for line in reversed(lines[-limit:]):
                try:
                    event = json.loads(line.strip())
                    events.append(event)
                except (json.JSONDecodeError, KeyError):
                    continue

        except FileNotFoundError:
            pass

        return events


# ═══════════════════════════════════════════════════════════════════════════════
# Global Audit Logger Instance
# ═══════════════════════════════════════════════════════════════════════════════

_global_audit_logger: Optional[AuditLogger] = None


def get_audit_logger() -> AuditLogger:
    """
    Global audit logger örneğini döndürür.

    Returns:
        AuditLogger örneği
    """
    global _global_audit_logger

    if _global_audit_logger is None:
        _global_audit_logger = AuditLogger()

    return _global_audit_logger


def init_audit_logger(
    log_dir: Optional[Path] = None,
    app_name: str = "video_renderer",
    enable_console: bool = True
) -> AuditLogger:
    """
    Global audit logger'ı başlatır.

    Args:
        log_dir: Log dizini
        app_name: Uygulama adı
        enable_console: Konsol loglaması

    Returns:
        AuditLogger örneği
    """
    global _global_audit_logger

    _global_audit_logger = AuditLogger(
        log_dir=log_dir,
        app_name=app_name,
        enable_console=enable_console
    )

    return _global_audit_logger

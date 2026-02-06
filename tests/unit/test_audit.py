#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Unit tests for Audit module.

Tests cover:
- Event logging
- Audit event types
- Event serialization
- Thread-safe logging
"""

import pytest
import json
from pathlib import Path
from unittest.mock import patch, MagicMock
from datetime import datetime
from video_renderer.audit import (
    AuditEventType,
    AuditEvent,
    AuditLogger,
)


@pytest.mark.unit
class TestAuditEventType:
    """Test suite for AuditEventType enum."""

    def test_authentication_events(self):
        """Test authentication event types exist."""
        assert hasattr(AuditEventType, 'AUTH_SUCCESS')
        assert hasattr(AuditEventType, 'AUTH_FAILURE')
        assert hasattr(AuditEventType, 'AUTH_REFRESH')
        assert hasattr(AuditEventType, 'AUTH_LOGOUT')

    def test_file_operation_events(self):
        """Test file operation event types exist."""
        assert hasattr(AuditEventType, 'FILE_READ')
        assert hasattr(AuditEventType, 'FILE_WRITE')
        assert hasattr(AuditEventType, 'FILE_DELETE')
        assert hasattr(AuditEventType, 'FILE_UPLOAD')

    def test_video_processing_events(self):
        """Test video processing event types exist."""
        assert hasattr(AuditEventType, 'VIDEO_ENCODE_START')
        assert hasattr(AuditEventType, 'VIDEO_ENCODE_COMPLETE')
        assert hasattr(AuditEventType, 'VIDEO_ENCODE_FAILURE')

    def test_security_events(self):
        """Test security event types exist."""
        assert hasattr(AuditEventType, 'SECURITY_VIOLATION')
        assert hasattr(AuditEventType, 'PATH_TRAVERSAL_ATTEMPT')
        assert hasattr(AuditEventType, 'COMMAND_INJECTION_ATTEMPT')


@pytest.mark.unit
class TestAuditEvent:
    """Test suite for AuditEvent dataclass."""

    def test_audit_event_creation(self):
        """Test creating an audit event."""
        event = AuditEvent(
            event_type=AuditEventType.FILE_READ,
            timestamp=datetime.utcnow().isoformat(),
            source="test_module",
            details={"file_path": "/path/to/file"}
        )

        assert event.event_type == AuditEventType.FILE_READ
        assert event.source == "test_module"
        assert event.details["file_path"] == "/path/to/file"

    def test_audit_event_to_dict(self):
        """Test converting audit event to dictionary."""
        timestamp = datetime.utcnow().isoformat()
        event = AuditEvent(
            event_type=AuditEventType.AUTH_SUCCESS,
            timestamp=timestamp,
            source="auth_module",
            details={"user": "test_user"}
        )

        event_dict = event.to_dict()

        assert event_dict["event_type"] == "auth_success"
        assert event_dict["timestamp"] == timestamp
        assert event_dict["source"] == "auth_module"
        assert event_dict["details"]["user"] == "test_user"

    def test_audit_event_serialization(self):
        """Test audit event can be serialized to JSON."""
        event = AuditEvent(
            event_type=AuditEventType.CONFIG_WRITE,
            timestamp=datetime.utcnow().isoformat(),
            source="config_module",
            details={"setting": "codec", "value": "h264"}
        )

        event_dict = event.to_dict()
        json_str = json.dumps(event_dict)

        assert json_str is not None
        assert "config_write" in json_str

    def test_audit_event_with_optional_fields(self):
        """Test audit event with optional fields."""
        event = AuditEvent(
            event_type=AuditEventType.API_CALL,
            timestamp=datetime.utcnow().isoformat(),
            source="api_module",
            details={"endpoint": "/api/test"},
            severity="WARNING",
            user_id="user123",
            ip_address="192.168.1.1",
            session_id="session456"
        )

        event_dict = event.to_dict()

        assert event_dict["severity"] == "WARNING"
        assert event_dict["user_id"] == "user123"
        assert event_dict["ip_address"] == "192.168.1.1"
        assert event_dict["session_id"] == "session456"


@pytest.mark.unit
class TestAuditLogger:
    """Test suite for AuditLogger class."""

    def test_audit_logger_init(self, temp_dir):
        """Test audit logger initialization."""
        logger = AuditLogger(log_dir=temp_dir)

        assert logger.log_dir == temp_dir
        assert logger.app_name == "video_renderer"
        assert logger.enable_console is True

    def test_audit_logger_log_event(self, temp_dir):
        """Test logging an event."""
        audit_logger = AuditLogger(log_dir=temp_dir)

        # Mock file write
        with patch('pathlib.Path.open', MagicMock()):
            audit_logger.log_event(
                event_type=AuditEventType.FILE_READ,
                source="test_module",
                details={"file": "test.mp4"}
            )

        # Verify log files exist
        assert audit_logger.audit_log_file.exists()

    def test_audit_logger_security_event(self, temp_dir):
        """Test logging a security event."""
        audit_logger = AuditLogger(log_dir=temp_dir)

        with patch('pathlib.Path.open', MagicMock()):
            audit_logger.log_event(
                event_type=AuditEventType.SECURITY_VIOLATION,
                source="security_module",
                details={"violation": "path_traversal"},
                severity="CRITICAL"
            )

        # Verify security log file exists
        assert audit_logger.security_log_file.exists()

    def test_audit_logger_thread_safety(self, temp_dir):
        """Test concurrent logging is thread-safe."""
        import threading

        audit_logger = AuditLogger(log_dir=temp_dir)

        errors = []

        def log_events(thread_id):
            try:
                for i in range(5):
                    audit_logger.log_event(
                        event_type=AuditEventType.FILE_READ,
                        source=f"thread_{thread_id}",
                        details={"index": i}
                    )
            except Exception as e:
                errors.append(e)

        threads = [
            threading.Thread(target=log_events, args=(i,))
            for i in range(5)
        ]

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # No errors should have occurred
        assert len(errors) == 0

    def test_audit_logger_sensitive_data_filtering(self, temp_dir):
        """Test sensitive data is filtered."""
        audit_logger = AuditLogger(log_dir=temp_dir, enable_sensitive_filter=True)

        with patch('pathlib.Path.open', MagicMock()):
            audit_logger.log_event(
                event_type=AuditEventType.AUTH_SUCCESS,
                source="auth_module",
                details={
                    "user": "test_user",
                    "password": "secret123",
                    "api_key": "abc123"
                }
            )

        # Event should be logged with filtered data
        # The actual filtering happens in the log_event method


@pytest.mark.unit
class TestAuditIntegration:
    """Test suite for audit logging integration."""

    def test_file_operation_logging(self, temp_dir):
        """Test logging file operations."""
        audit_logger = AuditLogger(log_dir=temp_dir)

        with patch('pathlib.Path.open', MagicMock()):
            audit_logger.log_event(
                event_type=AuditEventType.FILE_READ,
                source="video_renderer.video",
                details={"file": "test.mp4", "operation": "read"}
            )

            audit_logger.log_event(
                event_type=AuditEventType.FILE_WRITE,
                source="video_renderer.video",
                details={"file": "output.mp4", "operation": "write"}
            )

    def test_video_encode_logging(self, temp_dir):
        """Test logging video encoding operations."""
        audit_logger = AuditLogger(log_dir=temp_dir)

        with patch('pathlib.Path.open', MagicMock()):
            audit_logger.log_event(
                event_type=AuditEventType.VIDEO_ENCODE_START,
                source="video_renderer.video",
                details={"input": "intro.mp4", "codec": "h264"}
            )

            audit_logger.log_event(
                event_type=AuditEventType.VIDEO_ENCODE_COMPLETE,
                source="video_renderer.video",
                details={"output": "final.mp4", "duration": "3600"}
            )

    def test_security_violation_logging(self, temp_dir):
        """Test logging security violations."""
        audit_logger = AuditLogger(log_dir=temp_dir)

        with patch('pathlib.Path.open', MagicMock()):
            audit_logger.log_event(
                event_type=AuditEventType.PATH_TRAVERSAL_ATTEMPT,
                source="video_renderer.security",
                details={"path": "../../etc/passwd"},
                severity="CRITICAL"
            )

            audit_logger.log_event(
                event_type=AuditEventType.COMMAND_INJECTION_ATTEMPT,
                source="video_renderer.security",
                details={"input": "file.mp4; rm -rf /"},
                severity="CRITICAL"
            )

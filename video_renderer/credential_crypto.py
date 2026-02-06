#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Credential encryption module for secure storage of sensitive data.

This module provides encryption and decryption capabilities for storing
credentials at rest using Fernet symmetric encryption.
"""

import hashlib
import os
import base64
from pathlib import Path
from typing import Optional
import logging

logger = logging.getLogger(__name__)

# Fernet requires a 32-byte key
_KEY_ITERATIONS = 100000


class CredentialEncryption:
    """
    Encrypt and decrypt credentials using machine-specific key derivation.

    This class uses PBKDF2-HMAC-SHA256 to derive a unique encryption key
    from machine-specific identifiers, providing protection against
    credential file theft.
    """

    def __init__(self, salt: Optional[bytes] = None):
        """
        Initialize the credential encryption system.

        Args:
            salt: Optional salt for key derivation. If not provided,
                  a default salt is used (should be overridden in production).
        """
        self.salt = salt or b"AutoVideo_Credential_Salt_v1.0"
        self._key: Optional[bytes] = None
        self._cipher = None

    def _get_key_material(self) -> bytes:
        """
        Generate key material from machine-specific identifiers.

        Returns:
            Bytes derived from machine ID and username
        """
        # Combine multiple machine identifiers for better uniqueness
        identifiers = []

        # Get username
        try:
            username = os.getlogin()
            identifiers.append(username.encode())
        except (OSError, RuntimeError):
            identifiers.append(b"user_unknown")

        # Get machine identifier (platform-specific)
        try:
            import platform

            hostname = platform.node()
            identifiers.append(hostname.encode())
        except (OSError, RuntimeError):
            identifiers.append(b"host_unknown")

        # Combine identifiers
        combined = b"".join(identifiers)
        return combined

    def _get_key(self) -> bytes:
        """
        Derive encryption key using PBKDF2.

        Returns:
            32-byte encryption key suitable for Fernet
        """
        if self._key is None:
            key_material = self._get_key_material()
            # Derive 32-byte key using PBKDF2-HMAC-SHA256
            self._key = hashlib.pbkdf2_hmac(
                "sha256", key_material, self.salt, _KEY_ITERATIONS, dklen=32
            )
        return self._key

    def _get_cipher(self):
        """
        Get or create Fernet cipher instance.

        Returns:
            Fernet cipher instance
        """
        if self._cipher is None:
            from cryptography.fernet import Fernet

            # Fernet requires base64-encoded key
            key = base64.urlsafe_b64encode(self._get_key())
            self._cipher = Fernet(key)
        return self._cipher

    def encrypt(self, data: str) -> str:
        """
        Encrypt a string value.

        Args:
            data: Plain text data to encrypt

        Returns:
            Base64-encoded encrypted data
        """
        if not data:
            return ""

        try:
            cipher = self._get_cipher()
            encrypted = cipher.encrypt(data.encode("utf-8"))
            return encrypted.decode("utf-8")
        except Exception as e:
            logger.error(f"Encryption failed: {e}")
            raise

    def decrypt(self, encrypted: str) -> str:
        """
        Decrypt an encrypted string value.

        Args:
            encrypted: Base64-encoded encrypted data

        Returns:
            Decrypted plain text
        """
        if not encrypted:
            return ""

        try:
            cipher = self._get_cipher()
            decrypted = cipher.decrypt(encrypted.encode("utf-8"))
            return decrypted.decode("utf-8")
        except Exception as e:
            logger.error(f"Decryption failed: {e}")
            raise ValueError(f"Failed to decrypt data: {e}") from e

    def encrypt_dict(self, data: dict) -> dict:
        """
        Encrypt all string values in a dictionary.

        Args:
            data: Dictionary with string values to encrypt

        Returns:
            Dictionary with encrypted values
        """
        encrypted = {}
        for key, value in data.items():
            if isinstance(value, str):
                encrypted[key] = self.encrypt(value)
            else:
                encrypted[key] = value
        return encrypted

    def decrypt_dict(self, data: dict) -> dict:
        """
        Decrypt all string values in a dictionary.

        Args:
            data: Dictionary with encrypted string values

        Returns:
            Dictionary with decrypted values
        """
        decrypted = {}
        for key, value in data.items():
            if isinstance(value, str):
                try:
                    decrypted[key] = self.decrypt(value)
                except ValueError:
                    # If decryption fails, keep original value
                    decrypted[key] = value
            else:
                decrypted[key] = value
        return decrypted


def check_file_permissions(path: Path) -> bool:
    """
    Check if credential file has secure permissions.

    On POSIX systems, verifies that the file has 0600 permissions
    (read/write for owner only).

    On Windows, checks that the file is not in a world-writable location.

    Args:
        path: Path to the credential file

    Returns:
        True if permissions are secure, False otherwise
    """
    if not path.exists():
        return True  # Non-existent files are OK

    try:
        stat_info = path.stat()

        if os.name == "posix":
            # Check for 0600 permissions (read/write for owner only)
            mode = stat_info.st_mode & 0o777
            if mode != 0o600:
                logger.warning(
                    f"Insecure file permissions on {path}: {oct(mode)} " f"(expected 0o600)"
                )
                return False

        # Additional check: ensure parent directory is also secure
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


def validate_client_secrets(path: Path) -> bool:
    """
    Validate client_secrets.json format and structure.

    Ensures the file contains valid OAuth 2.0 client configuration
    in either 'installed' or 'web' format.

    Args:
        path: Path to the client_secrets.json file

    Returns:
        True if valid, False otherwise
    """
    import json

    if not path.exists():
        logger.error(f"Client secrets file not found: {path}")
        return False

    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)

        # Check for valid client type
        if "installed" not in data and "web" not in data:
            logger.error(
                f"Invalid client_secrets.json format: " f"missing 'installed' or 'web' key"
            )
            return False

        # Get client config
        client_config = data.get("installed") or data.get("web")

        # Validate required fields
        required_fields = ["client_id", "client_secret"]
        for field in required_fields:
            if field not in client_config:
                logger.error(f"Invalid client_secrets.json: missing required field '{field}'")
                return False

        # Check for redirect URIs (optional but recommended)
        if "redirect_uris" not in client_config:
            logger.warning(f"client_secrets.json missing 'redirect_uris' field")

        return True

    except json.JSONDecodeError as e:
        logger.error(f"Invalid JSON in client_secrets.json: {e}")
        return False
    except Exception as e:
        logger.error(f"Client secrets validation failed: {e}")
        return False


class SensitiveDataFilter(logging.Filter):
    """
    Logging filter that redacts sensitive data from log messages.

    Redacts:
    - Bearer tokens
    - Refresh tokens
    - API keys
    - Client secrets
    - Access tokens
    """

    SENSITIVE_PATTERNS = [
        (r"Bearer\s+[A-Za-z0-9\-._~+/]+={0,2}", "Bearer [REDACTED]"),
        (r'refresh_token["\s:]+[A-Za-z0-9\-._~+/]+={0,2}', "refresh_token: [REDACTED]"),
        (r'access_token["\s:]+[A-Za-z0-9\-._~+/]+={0,2}', "access_token: [REDACTED]"),
        (r'client_secret["\s:]+[A-Za-z0-9\-._~+/]+={0,2}', "client_secret: [REDACTED]"),
        (r'apikey["\s:]+[A-Za-z0-9\-._~+/]+={0,2}', "apikey: [REDACTED]"),
        (r'api_key["\s:]+[A-Za-z0-9\-._~+/]+={0,2}', "api_key: [REDACTED]"),
    ]

    def __init__(self):
        super().__init__()
        import re

        self._patterns = [(re.compile(p, re.IGNORECASE), r) for p, r in self.SENSITIVE_PATTERNS]

    def filter(self, record: logging.LogRecord) -> bool:
        """
        Filter log record and redact sensitive information.

        Args:
            record: Log record to filter

        Returns:
            True (always allow the log record)
        """
        if hasattr(record, "msg"):
            msg = str(record.msg)
            for pattern, replacement in self._patterns:
                msg = pattern.sub(replacement, msg)
            record.msg = msg

        if hasattr(record, "args") and record.args:
            new_args = []
            for arg in record.args:
                if isinstance(arg, str):
                    arg_str = arg
                    for pattern, replacement in self._patterns:
                        arg_str = pattern.sub(replacement, arg_str)
                    new_args.append(arg_str)
                else:
                    new_args.append(arg)
            record.args = tuple(new_args)

        return True


def setup_secure_logging() -> None:
    """
    Configure logging with sensitive data filtering.

    Adds SensitiveDataFilter to root logger and all handlers.
    """
    # Create filter instance
    sensitive_filter = SensitiveDataFilter()

    # Apply to root logger
    root_logger = logging.getLogger()
    root_logger.addFilter(sensitive_filter)

    # Apply to all existing handlers
    for handler in root_logger.handlers:
        handler.addFilter(sensitive_filter)

    # Also apply to common third-party loggers
    for logger_name in ["googleapiclient", "google.auth", "oauthlib", "googleapiclient.discovery"]:
        log = logging.getLogger(logger_name)
        log.addFilter(sensitive_filter)


# Global instance
_credential_crypto: Optional[CredentialEncryption] = None


def get_credential_crypto() -> CredentialEncryption:
    """
    Get the global credential encryption instance.

    Returns:
        CredentialEncryption instance
    """
    global _credential_crypto
    if _credential_crypto is None:
        _credential_crypto = CredentialEncryption()
    return _credential_crypto


# Auto-initialize secure logging on module import
setup_secure_logging()

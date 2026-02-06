#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Google Drive integration for uploading rendered videos.

Production-ready v1.0.0:
- Authentication with retry logic and exponential backoff
- Upload error recovery with chunking
- Thread-safe authentication with locking
- Progress tracking for uploads
- Proper exception handling
"""

import pickle
import os.path
import time
import threading
import secrets
from pathlib import Path
from typing import Optional, List, Dict, Tuple, Callable
import logging

from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

# Import security modules
from video_renderer.credential_crypto import (
    check_file_permissions,
    validate_client_secrets,
)

logger = logging.getLogger(__name__)

# Scopes required for uploading
SCOPES = ["https://www.googleapis.com/auth/drive.file"]


class DriveUploadError(Exception):
    """Exception raised when Drive upload fails."""

    pass


class DriveUploader:
    """
    Google Drive uploader with improved error handling.

    Features:
    - Authentication with retry logic and exponential backoff
    - Thread-safe authentication with locking
    - Upload error recovery with chunking
    - Progress tracking for uploads
    """

    def __init__(
        self,
        credentials_path: Optional[Path] = None,
        token_path: Optional[Path] = None,
        max_retries: int = 3,
    ):
        self.credentials_path = credentials_path or self._find_credentials()
        self.token_path = token_path or Path("token.pickle")
        self.creds = None
        self.service = None
        self._max_retries = max_retries
        self._auth_lock = threading.Lock()

    def _find_credentials(self) -> Path:
        """Find credentials file in common locations."""
        for name in ["credentials.json", "client_secrets.json"]:
            for path in [Path.cwd(), Path.home(), Path(__file__).parent]:
                p = path / name
                if p.exists():
                    return p
        return Path("credentials.json")

    def _authenticate_with_retry(self, max_retries: Optional[int] = None) -> bool:
        """
        Authenticate with retry logic.

        Args:
            max_retries: Maximum retry attempts (defaults to instance value)

        Returns:
            True if authentication successful

        Raises:
            DriveUploadError: If authentication fails after all retries
        """
        max_attempts = max_retries or self._max_retries

        for attempt in range(max_attempts):
            try:
                # Fast path: already authenticated
                if self.service:
                    return True

                # Double-check pattern with lock
                with self._auth_lock:
                    if self.service:
                        return True

                    # Load credentials
                    self.creds = None

                    # Load existing token (with security check)
                    if self.token_path.exists():
                        # Check file permissions before loading
                        if not check_file_permissions(self.token_path):
                            logger.warning(f"Insecure permissions on {self.token_path}")

                        with open(self.token_path, "rb") as token:
                            try:
                                self.creds = pickle.load(token)
                            except Exception:
                                self.creds = None

                    # Refresh or login if needed
                    if not self.creds or not self.creds.valid:
                        if self.creds and self.creds.expired and self.creds.refresh_token:
                            try:
                                self.creds.refresh(Request())
                            except Exception as e:
                                print(f"Token refresh failed: {e}")
                                self.creds = None

                        if not self.creds:
                            if not self.credentials_path.exists():
                                raise DriveUploadError(
                                    f"Credentials file not found: '{self.credentials_path}'\n"
                                    "Download from Google Cloud Console and save as credentials.json"
                                )

                            # Validate client secrets format
                            if not validate_client_secrets(self.credentials_path):
                                raise DriveUploadError(
                                    f"Invalid credentials.json format: '{self.credentials_path}'"
                                )

                            # Check credentials file permissions
                            if not check_file_permissions(self.credentials_path):
                                logger.warning(f"Insecure permissions on {self.credentials_path}")

                            try:
                                # Generate cryptographically secure state parameter
                                state = secrets.token_urlsafe(16)

                                print("Google Drive yetkilendirmesi baslatiliyor...")
                                print("Lutfen asagidaki linke tiklayin ve onay kodunu yapistirin:")
                                flow = InstalledAppFlow.from_client_secrets_file(
                                    str(self.credentials_path), SCOPES, state=state
                                )
                                # Use run_console to handle VPS scenario cleanly
                                self.creds = flow.run_console()
                            except Exception as e:
                                raise DriveUploadError(f"Authentication failed: {e}")

                        # Save the token (with secure permissions check)
                        with open(self.token_path, "wb") as token:
                            pickle.dump(self.creds, token)

                        # Verify/set secure permissions on token file
                        check_file_permissions(self.token_path)

                    # Build service
                    self.service = build("drive", "v3", credentials=self.creds)
                    return True

            except DriveUploadError:
                # Re-raise DriveUploadError immediately
                raise
            except Exception as e:
                if attempt == max_attempts - 1:
                    raise DriveUploadError(
                        f"Authentication failed after {max_attempts} attempts: {e}"
                    )
                # Exponential backoff
                wait_time = 2**attempt
                print(f"Authentication attempt {attempt + 1} failed, retrying in {wait_time}s...")
                time.sleep(wait_time)

        return False

    def authenticate(self) -> bool:
        """
        Authenticate with Google Drive API (legacy method).

        Returns:
            True if successful, False otherwise
        """
        try:
            return self._authenticate_with_retry()
        except DriveUploadError as e:
            print(f"Authentication error: {e}")
            return False

    def list_folders(self, page_size: int = 10) -> List[Dict[str, str]]:
        """
        List folders in root or last accessed.

        Returns:
            List of folder dictionaries with 'id' and 'name' keys
        """
        try:
            self._authenticate_with_retry()
        except DriveUploadError:
            return []

        try:
            results = (
                self.service.files()
                .list(
                    pageSize=page_size,
                    q="mimeType='application/vnd.google-apps.folder' and trashed=false",
                    fields="nextPageToken, files(id, name)",
                    orderBy="folder,name",
                )
                .execute()
            )
            items = results.get("files", [])
            return items
        except Exception as e:
            print(f"List folders failed: {e}")
            return []

    def upload_file(
        self,
        file_path: Path,
        folder_id: Optional[str] = None,
        progress_callback: Optional[Callable[[float], None]] = None,
        max_retries: Optional[int] = None,
    ) -> Tuple[bool, str]:
        """
        Upload a file to Google Drive with progress tracking and retry logic.

        Args:
            file_path: Path to the file to upload
            folder_id: ID of the folder to upload to (optional)
            progress_callback: Optional callback(progress: float) for progress updates (0.0-1.0)
            max_retries: Maximum retry attempts (defaults to instance value)

        Returns:
            Tuple of (success: bool, message_or_file_id: str)

        Raises:
            DriveUploadError: If upload fails after all retries
        """
        if not file_path.exists():
            return False, f"File not found: {file_path}"

        # Authenticate first
        try:
            self._authenticate_with_retry()
        except DriveUploadError as e:
            return False, str(e)

        # File metadata
        file_metadata = {"name": file_path.name, "parents": [folder_id] if folder_id else []}

        # Media upload with chunking for large files
        media = MediaFileUpload(
            str(file_path),
            mimetype="video/mp4",
            chunksize=1024 * 1024 * 5,  # 5MB chunks for better reliability
            resumable=True,
        )

        # Upload with retry
        max_attempts = max_retries or self._max_retries
        last_error = None

        for attempt in range(max_attempts):
            try:
                request = self.service.files().create(
                    body=file_metadata, media_body=media, fields="id"
                )

                response = None
                while response is None:
                    status, response = request.next_chunk()
                    if status and progress_callback:
                        progress_callback(status.progress())

                file_id = response.get("id")
                return True, file_id

            except Exception as e:
                last_error = e
                if attempt == max_attempts - 1:
                    break
                # Exponential backoff before retry
                wait_time = 5 * (2**attempt)
                print(f"Upload attempt {attempt + 1} failed, retrying in {wait_time}s...")
                time.sleep(wait_time)

        return False, f"Upload failed after {max_attempts} attempts: {last_error}"


if __name__ == "__main__":
    # Test
    uploader = DriveUploader()
    if uploader.authenticate():
        print("Authenticated!")
        folders = uploader.list_folders()
        for f in folders:
            print(f"{f['name']} ({f['id']})")
    else:
        print("Auth failed or no credentials.")

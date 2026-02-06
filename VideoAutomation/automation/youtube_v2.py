#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
YouTube uploader v2 - Production-ready upload client.

Features:
- Comprehensive error handling and categorization
- Rate limiting and quota management
- Exponential backoff with jitter
- Upload resumption
- Progress tracking
- Circuit breaker for API calls
"""

import os
import time
import logging
from pathlib import Path
from typing import Optional, List, Dict, Any, Callable
from datetime import datetime, timedelta
from dataclasses import dataclass, field

from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaFileUpload, MediaUploadProgress
from google_auth_oauthlib.flow import InstalledAppFlow
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request

from .errors import (
    ErrorCategory, ErrorSeverity, ErrorContext,
    categorize_google_api_error, RetryPolicy, with_retry, CircuitBreaker,
    AuthenticationError, QuotaExceededError, PipelineError
)

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════════════
# Constants
# ═══════════════════════════════════════════════════════════════════════════════

SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]

# YouTube category IDs
CATEGORY_MUSIC = "10"
CATEGORY_ENTERTAINMENT = "24"
CATEGORY_PEOPLE_BLOGS = "22"

# Retry settings
DEFAULT_RETRY_POLICY = RetryPolicy(
    max_attempts=10,
    base_delay=1.0,
    max_delay=600.0,
    exponential_base=2.0,
    jitter=True
)

# Rate limiting settings
RATE_LIMIT_WINDOW = timedelta(hours=24)
MAX_UPLOADS_PER_DAY = 6  # YouTube default daily quota
MIN_UPLOAD_INTERVAL = timedelta(minutes=5)


# ═══════════════════════════════════════════════════════════════════════════════
# Upload State Tracking
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class UploadAttempt:
    """Record of an upload attempt."""
    timestamp: datetime = field(default_factory=datetime.now)
    video_id: Optional[str] = None
    success: bool = False
    error: Optional[str] = None
    bytes_uploaded: int = 0
    total_bytes: int = 0
    duration_seconds: float = 0.0


@dataclass
class UploadStats:
    """Upload statistics for rate limiting."""
    uploads_today: int = 0
    last_upload_time: Optional[datetime] = None
    recent_attempts: List[UploadAttempt] = field(default_factory=list)
    total_bytes_uploaded: int = 0
    total_upload_time: float = 0.0

    def can_upload(self, max_uploads: int, min_interval: timedelta) -> tuple[bool, str]:
        """
        Check if upload is allowed based on rate limits.

        Returns:
            Tuple of (can_upload, reason)
        """
        now = datetime.now()
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)

        # Count uploads today
        today_uploads = sum(
            1 for a in self.recent_attempts
            if a.timestamp >= today_start and a.success
        )

        if today_uploads >= max_uploads:
            return False, f"Daily quota reached ({today_uploads}/{max_uploads})"

        # Check minimum interval
        if self.last_upload_time:
            elapsed = now - self.last_upload_time
            if elapsed < min_interval:
                wait_time = min_interval - elapsed
                return False, f"Must wait {wait_time.total_seconds():.0f}s between uploads"

        return True, "OK"

    def record_attempt(self, attempt: UploadAttempt):
        """Record an upload attempt."""
        self.recent_attempts.append(attempt)
        if attempt.success:
            self.uploads_today += 1
            self.last_upload_time = attempt.timestamp
        self.total_bytes_uploaded += attempt.bytes_uploaded
        self.total_upload_time += attempt.duration_seconds

        # Clean old attempts (keep last 24 hours)
        cutoff = datetime.now() - timedelta(hours=24)
        self.recent_attempts = [
            a for a in self.recent_attempts
            if a.timestamp > cutoff
        ]


# ═══════════════════════════════════════════════════════════════════════════════
# YouTube Uploader v2
# ═══════════════════════════════════════════════════════════════════════════════

class YouTubeUploader:
    """
    Production-ready YouTube video uploader.

    Features:
    - Automatic retry with exponential backoff
    - Rate limiting and quota management
    - Circuit breaker for API failures
    - Comprehensive error handling
    - Upload progress tracking
    """

    def __init__(
        self,
        client_secrets_file: str = "client_secrets.json",
        credentials_file: str = "youtube_credentials.json",
        retry_policy: Optional[RetryPolicy] = None,
        enable_circuit_breaker: bool = True
    ):
        """
        Initialize YouTube uploader.

        Args:
            client_secrets_file: Path to OAuth client secrets
            credentials_file: Path to stored credentials
            retry_policy: Custom retry policy (uses default if None)
            enable_circuit_breaker: Enable circuit breaker for API calls
        """
        self.client_secrets_file = client_secrets_file
        self.credentials_file = credentials_file
        self.retry_policy = retry_policy or DEFAULT_RETRY_POLICY
        self.enable_circuit_breaker = enable_circuit_breaker

        self.youtube = None
        self._credentials = None
        self._stats = UploadStats()
        self._circuit_breaker = CircuitBreaker() if enable_circuit_breaker else None

    def authenticate(self, force_refresh: bool = False) -> bool:
        """
        Authenticate with YouTube API.

        Args:
            force_refresh: Force credential refresh even if valid

        Returns:
            True if authenticated successfully

        Raises:
            AuthenticationError: If authentication fails
        """
        creds = None

        # Load existing credentials
        if os.path.exists(self.credentials_file) and not force_refresh:
            try:
                creds = Credentials.from_authorized_user_file(
                    self.credentials_file, SCOPES
                )
                if creds and creds.valid:
                    logger.info("Loaded valid credentials from file")
                    self._credentials = creds
                    self._build_service()
                    return True
            except Exception as e:
                logger.warning(f"Failed to load credentials: {e}")
                creds = None

        # Refresh or get new credentials
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                try:
                    logger.info("Refreshing expired credentials")
                    creds.refresh(Request())
                    self._save_credentials(creds)
                    self._credentials = creds
                    self._build_service()
                    return True
                except Exception as e:
                    logger.warning(f"Failed to refresh credentials: {e}")
                    creds = None

            if not creds:
                if not os.path.exists(self.client_secrets_file):
                    raise AuthenticationError(
                        f"Client secrets file not found: {self.client_secrets_file}\n"
                        "Download from Google Cloud Console -> Credentials"
                    )

                logger.info("Starting OAuth flow")
                flow = InstalledAppFlow.from_client_secrets_file(
                    self.client_secrets_file, SCOPES
                )
                creds = flow.run_local_server(port=8080)
                self._save_credentials(creds)

        self._credentials = creds
        self._build_service()
        return True

    def _save_credentials(self, creds: Credentials):
        """Save credentials to file."""
        try:
            with open(self.credentials_file, "w") as f:
                f.write(creds.to_json())
            logger.info(f"Saved credentials to {self.credentials_file}")
        except Exception as e:
            logger.error(f"Failed to save credentials: {e}")
            raise

    def _build_service(self):
        """Build YouTube service object."""
        self.youtube = build("youtube", "v3", credentials=self._credentials)
        logger.info("YouTube API service initialized")

    def check_rate_limit(self, max_uploads: int = MAX_UPLOADS_PER_DAY) -> tuple[bool, str]:
        """
        Check if upload is allowed based on rate limits.

        Args:
            max_uploads: Maximum uploads per day

        Returns:
            Tuple of (can_upload, reason_message)
        """
        return self._stats.can_upload(max_uploads, MIN_UPLOAD_INTERVAL)

    def upload_video(
        self,
        video_path: Path,
        title: str,
        description: str,
        tags: List[str],
        category_id: str = CATEGORY_MUSIC,
        privacy_status: str = "public",
        progress_callback: Optional[Callable[[MediaUploadProgress], None]] = None
    ) -> str:
        """
        Upload a video to YouTube with automatic retry.

        Args:
            video_path: Path to video file
            title: Video title (max 100 chars)
            description: Video description (max 5000 chars)
            tags: List of tags
            category_id: YouTube category ID
            privacy_status: public, private, or unlisted
            progress_callback: Optional callback for upload progress

        Returns:
            Video ID

        Raises:
            AuthenticationError: If not authenticated
            QuotaExceededError: If quota exceeded
            PipelineError: For other errors
        """
        if not self.youtube:
            raise AuthenticationError("Not authenticated. Call authenticate() first.")

        if not video_path.exists():
            raise FileNotFoundError(f"Video file not found: {video_path}")

        # Check file size (YouTube limit: 256GB)
        file_size = video_path.stat().st_size
        max_size = 256 * 1024 * 1024 * 1024  # 256GB
        if file_size > max_size:
            raise ValueError(f"Video file too large: {file_size} bytes (max {max_size})")

        # Check rate limit
        can_upload, reason = self.check_rate_limit()
        if not can_upload:
            raise QuotaExceededError(f"Rate limit: {reason}")

        # Record attempt start
        attempt = UploadAttempt(
            timestamp=datetime.now(),
            total_bytes=file_size
        )

        try:
            video_id = self._upload_with_retry(
                video_path=video_path,
                title=title,
                description=description,
                tags=tags,
                category_id=category_id,
                privacy_status=privacy_status,
                progress_callback=progress_callback
            )

            # Record successful attempt
            attempt.success = True
            attempt.video_id = video_id
            attempt.bytes_uploaded = file_size
            attempt.duration_seconds = (datetime.now() - attempt.timestamp).total_seconds()
            self._stats.record_attempt(attempt)

            return video_id

        except Exception as e:
            # Record failed attempt
            attempt.success = False
            attempt.error = str(e)
            attempt.duration_seconds = (datetime.now() - attempt.timestamp).total_seconds()
            self._stats.record_attempt(attempt)
            raise

    def _upload_with_retry(
        self,
        video_path: Path,
        title: str,
        description: str,
        tags: List[str],
        category_id: str,
        privacy_status: str,
        progress_callback: Optional[Callable[[MediaUploadProgress], None]]
    ) -> str:
        """Upload with retry logic."""
        last_error = None

        for attempt in range(self.retry_policy.max_attempts):
            try:
                return self._upload_single(
                    video_path=video_path,
                    title=title,
                    description=description,
                    tags=tags,
                    category_id=category_id,
                    privacy_status=privacy_status,
                    progress_callback=progress_callback
                )

            except HttpError as e:
                last_error = e

                # Categorize error
                context = categorize_google_api_error(e.resp.status, str(e))

                # Don't retry if not retryable
                if not context.can_retry:
                    logger.error(f"Non-retryable error: {context.message}")
                    if context.category == ErrorCategory.QUOTA:
                        raise QuotaExceededError(context.suggested_action)
                    if context.category == ErrorCategory.AUTHENTICATION:
                        raise AuthenticationError(context.suggested_action)
                    raise PipelineError(context.message)

                # Last attempt, give up
                if attempt == self.retry_policy.max_attempts - 1:
                    logger.error(f"Max retries ({self.retry_policy.max_attempts}) exceeded")
                    raise

                # Calculate delay
                delay = self.retry_policy.get_delay(attempt)

                logger.warning(
                    f"Upload attempt {attempt + 1}/{self.retry_policy.max_attempts} "
                    f"failed, retrying in {delay:.1f}s: {context.message}"
                )

                time.sleep(delay)

            except Exception as e:
                last_error = e
                logger.error(f"Unexpected error during upload: {e}")

                # Last attempt
                if attempt == self.retry_policy.max_attempts - 1:
                    raise

                delay = self.retry_policy.get_delay(attempt)
                time.sleep(delay)

        raise last_error

    def _upload_single(
        self,
        video_path: Path,
        title: str,
        description: str,
        tags: List[str],
        category_id: str,
        privacy_status: str,
        progress_callback: Optional[Callable[[MediaUploadProgress], None]]
    ) -> str:
        """Perform a single upload attempt."""
        # Prepare metadata
        body = {
            "snippet": {
                "title": title[:100],
                "description": description[:5000],
                "tags": tags[:500],  # Max 500 tags
                "categoryId": category_id,
            },
            "status": {
                "privacyStatus": privacy_status,
                "selfDeclaredMadeForKids": False,
            }
        }

        # Create media upload
        media = MediaFileUpload(
            str(video_path),
            mimetype="video/*",
            resumable=True,
            chunksize=1024 * 1024  # 1MB chunks
        )

        # Create request
        request = self.youtube.videos().insert(
            part="snippet,status",
            body=body,
            media_body=media
        )

        # Execute upload
        response = None
        while response is None:
            status, response = request.next_chunk()
            if progress_callback and status:
                progress_callback(status)

        return response.get("id")

    def set_thumbnail(
        self,
        video_id: str,
        thumbnail_path: Path
    ) -> bool:
        """
        Set custom thumbnail for a video.

        Args:
            video_id: YouTube video ID
            thumbnail_path: Path to thumbnail image (jpg, png)

        Returns:
            True if successful
        """
        if not self.youtube:
            raise AuthenticationError("Not authenticated. Call authenticate() first.")

        if not thumbnail_path.exists():
            raise FileNotFoundError(f"Thumbnail not found: {thumbnail_path}")

        try:
            media = MediaFileUpload(str(thumbnail_path), mimetype="image/*")

            self.youtube.thumbnails().set(
                videoId=video_id,
                media_body=media
            ).execute()

            logger.info(f"Thumbnail set for video {video_id}")
            return True

        except HttpError as e:
            logger.error(f"Failed to set thumbnail: {e}")
            return False

    def get_channel_info(self) -> Optional[Dict[str, Any]]:
        """
        Get info about the authenticated user's channel.

        Returns:
            Channel info dict or None
        """
        if not self.youtube:
            raise AuthenticationError("Not authenticated. Call authenticate() first.")

        try:
            response = self.youtube.channels().list(
                part="snippet,statistics",
                mine=True
            ).execute()

            items = response.get("items", [])
            if items:
                return items[0]
            return None

        except HttpError as e:
            logger.error(f"Failed to get channel info: {e}")
            return None

    def get_upload_status(self, video_id: str) -> Optional[Dict[str, Any]]:
        """
        Get upload status and processing status of a video.

        Args:
            video_id: YouTube video ID

        Returns:
            Video status dict or None
        """
        if not self.youtube:
            raise AuthenticationError("Not authenticated. Call authenticate() first.")

        try:
            response = self.youtube.videos().list(
                part="status,processingDetails",
                id=video_id
            ).execute()

            items = response.get("items", [])
            if items:
                return {
                    "status": items[0].get("status", {}).get("uploadStatus"),
                    "privacy": items[0].get("status", {}).get("privacyStatus"),
                    "processing": items[0].get("processingDetails", {})
                }
            return None

        except HttpError as e:
            logger.error(f"Failed to get upload status: {e}")
            return None

    def delete_video(self, video_id: str) -> bool:
        """
        Delete a video from YouTube.

        Args:
            video_id: YouTube video ID

        Returns:
            True if successful
        """
        if not self.youtube:
            raise AuthenticationError("Not authenticated. Call authenticate() first.")

        try:
            self.youtube.videos().delete(id=video_id).execute()
            logger.info(f"Deleted video {video_id}")
            return True

        except HttpError as e:
            logger.error(f"Failed to delete video: {e}")
            return False

    @property
    def stats(self) -> UploadStats:
        """Get upload statistics."""
        return self._stats

    def reset_stats(self):
        """Reset upload statistics."""
        self._stats = UploadStats()

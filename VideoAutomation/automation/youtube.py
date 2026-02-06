#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
YouTube Data API v3 client for video uploads.

Production-ready v1.0.0:
- Metadata validation (title, description length)
- Improved upload progress tracking
- Better error handling with retry logic
- Enhanced chunking for large files (5MB chunks)
"""

import os
import time
import json
import httplib2
from pathlib import Path
from typing import Optional, List, Dict, Any, Callable

from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaFileUpload
from google_auth_oauthlib.flow import InstalledAppFlow
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request


# ═══════════════════════════════════════════════════════════════════════════════
# Constants
# ═══════════════════════════════════════════════════════════════════════════════

SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]

# YouTube category IDs
CATEGORY_MUSIC = "10"
CATEGORY_ENTERTAINMENT = "24"
CATEGORY_PEOPLE_BLOGS = "22"

# Retry settings
MAX_RETRIES = 10
RETRIABLE_STATUS_CODES = [500, 502, 503, 504]

# Validation limits
MAX_TITLE_LENGTH = 100
MAX_DESCRIPTION_LENGTH = 5000
MAX_TAGS_COUNT = 500


class YouTubeUploadError(Exception):
    """Exception raised when YouTube upload fails."""
    pass


class ValidationError(YouTubeUploadError):
    """Exception raised for validation errors."""
    pass


# ═══════════════════════════════════════════════════════════════════════════════
# Constants
# ═══════════════════════════════════════════════════════════════════════════════

SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]

# YouTube category IDs
CATEGORY_MUSIC = "10"
CATEGORY_ENTERTAINMENT = "24"
CATEGORY_PEOPLE_BLOGS = "22"

# Retry settings
MAX_RETRIES = 10
RETRIABLE_STATUS_CODES = [500, 502, 503, 504]


# ═══════════════════════════════════════════════════════════════════════════════
# YouTube Uploader
# ═══════════════════════════════════════════════════════════════════════════════

class YouTubeUploader:
    """
    YouTube video uploader using Data API v3.
    """
    
    def __init__(
        self,
        client_secrets_file: str = "client_secrets.json",
        credentials_file: str = "youtube_credentials.json"
    ):
        self.client_secrets_file = client_secrets_file
        self.credentials_file = credentials_file
        self.youtube = None
        self._credentials = None
    
    def authenticate(self) -> bool:
        """
        Authenticate with YouTube API.
        
        First run will open browser for OAuth consent.
        Subsequent runs use stored credentials.
        
        Returns:
            True if authenticated successfully
        """
        creds = None
        
        # Load existing credentials
        if os.path.exists(self.credentials_file):
            try:
                creds = Credentials.from_authorized_user_file(self.credentials_file, SCOPES)
            except Exception:
                creds = None
        
        # Refresh or get new credentials
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                try:
                    creds.refresh(Request())
                except Exception:
                    creds = None
            
            if not creds:
                if not os.path.exists(self.client_secrets_file):
                    raise FileNotFoundError(
                        f"Client secrets file not found: {self.client_secrets_file}\n"
                        "Download from Google Cloud Console -> Credentials"
                    )
                
                flow = InstalledAppFlow.from_client_secrets_file(
                    self.client_secrets_file, SCOPES
                )
                creds = flow.run_local_server(port=8080)
            
            # Save credentials for next run
            with open(self.credentials_file, "w") as f:
                f.write(creds.to_json())
        
        self._credentials = creds
        self.youtube = build("youtube", "v3", credentials=creds)
        return True
    
    def _validate_metadata(self, title: str, description: str, tags: List[str]) -> None:
        """
        Validate video metadata before upload.

        Args:
            title: Video title
            description: Video description
            tags: List of tags

        Raises:
            ValidationError: If validation fails
        """
        if len(title) > MAX_TITLE_LENGTH:
            raise ValidationError(
                f"Title too long: {len(title)} characters (max: {MAX_TITLE_LENGTH})"
            )

        if len(description) > MAX_DESCRIPTION_LENGTH:
            raise ValidationError(
                f"Description too long: {len(description)} characters (max: {MAX_DESCRIPTION_LENGTH})"
            )

        if len(tags) > MAX_TAGS_COUNT:
            raise ValidationError(
                f"Too many tags: {len(tags)} tags (max: {MAX_TAGS_COUNT})"
            )

        # Check for empty required fields
        if not title or not title.strip():
            raise ValidationError("Title cannot be empty")

    def upload_video(
        self,
        video_path: Path,
        title: str,
        description: str,
        tags: List[str],
        category_id: str = CATEGORY_MUSIC,
        privacy_status: str = "public",
        progress_callback: Optional[Callable[[int, int], None]] = None
    ) -> Optional[str]:
        """
        Upload a video to YouTube with improved validation and progress tracking.

        Args:
            video_path: Path to video file
            title: Video title (max 100 chars)
            description: Video description (max 5000 chars)
            tags: List of tags (max 500)
            category_id: YouTube category ID
            privacy_status: public, private, or unlisted
            progress_callback: Optional callback(bytes_uploaded, total_bytes)

        Returns:
            Video ID if successful, None otherwise

        Raises:
            RuntimeError: If not authenticated
            FileNotFoundError: If video file not found
            ValidationError: If metadata validation fails
            YouTubeUploadError: If upload fails
        """
        if not self.youtube:
            raise RuntimeError("Not authenticated. Call authenticate() first.")

        if not video_path.exists():
            raise FileNotFoundError(f"Video file not found: {video_path}")

        # Validate metadata
        try:
            self._validate_metadata(title, description, tags)
        except ValidationError as e:
            raise YouTubeUploadError(f"Metadata validation failed: {e}") from e

        # Prepare metadata (truncate to limits)
        body = {
            "snippet": {
                "title": title[:MAX_TITLE_LENGTH].strip(),
                "description": description[:MAX_DESCRIPTION_LENGTH],
                "tags": tags[:MAX_TAGS_COUNT],
                "categoryId": category_id,
            },
            "status": {
                "privacyStatus": privacy_status,
                "selfDeclaredMadeForKids": False,
            }
        }

        # Create media upload with 5MB chunks for better reliability
        media = MediaFileUpload(
            str(video_path),
            mimetype="video/*",
            resumable=True,
            chunksize=1024 * 1024 * 5  # 5MB chunks (increased from 1MB)
        )

        # Create request
        request = self.youtube.videos().insert(
            part="snippet,status",
            body=body,
            media_body=media
        )

        # Execute with retry
        video_id = None
        response = None

        try:
            status, response = None, None
            while response is None:
                status, response = request.next_chunk()
                if progress_callback and status:
                    progress_callback(status.resumable_progress, status.total_size)
        except HttpError as e:
            if e.resp.status in RETRIABLE_STATUS_CODES:
                # Let the caller (upload_with_exponential_backoff) handle retries
                raise
            raise YouTubeUploadError(f"YouTube API error: {e}") from e
        except Exception as e:
            raise YouTubeUploadError(f"Upload failed: {e}") from e

        if response:
            video_id = response.get("id")

        return video_id
    
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
            raise RuntimeError("Not authenticated. Call authenticate() first.")
        
        media = MediaFileUpload(str(thumbnail_path), mimetype="image/*")
        
        self.youtube.thumbnails().set(
            videoId=video_id,
            media_body=media
        ).execute()
        
        return True
    
    def get_channel_info(self) -> Optional[Dict[str, Any]]:
        """Get info about the authenticated user's channel."""
        if not self.youtube:
            raise RuntimeError("Not authenticated. Call authenticate() first.")
        
        response = self.youtube.channels().list(
            part="snippet,statistics",
            mine=True
        ).execute()
        
        items = response.get("items", [])
        if items:
            return items[0]
        return None


# ═══════════════════════════════════════════════════════════════════════════════
# Upload with Retry
# ═══════════════════════════════════════════════════════════════════════════════

def upload_with_exponential_backoff(
    uploader: YouTubeUploader,
    video_path: Path,
    title: str,
    description: str,
    tags: List[str],
    category_id: str = CATEGORY_MUSIC,
    privacy_status: str = "public",
    max_retries: int = MAX_RETRIES,
    progress_callback: Optional[Callable[[int, int], None]] = None
) -> Optional[str]:
    """
    Upload video with exponential backoff retry.
    
    Returns:
        Video ID if successful, None otherwise
    """
    retry = 0
    
    while retry < max_retries:
        try:
            video_id = uploader.upload_video(
                video_path=video_path,
                title=title,
                description=description,
                tags=tags,
                category_id=category_id,
                privacy_status=privacy_status,
                progress_callback=progress_callback
            )
            return video_id
            
        except HttpError as e:
            if e.resp.status in RETRIABLE_STATUS_CODES:
                retry += 1
                sleep_time = 2 ** retry
                time.sleep(sleep_time)
                continue
            raise
            
        except Exception as e:
            # Network errors, etc.
            retry += 1
            sleep_time = 2 ** retry
            time.sleep(sleep_time)
    
    return None

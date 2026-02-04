#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Google Drive Uploader Helper.

Handles authentication and background uploads.
"""

import os
import pickle
import threading
from pathlib import Path
from typing import Optional, List, Dict, Any, Callable

# Google APIs
try:
    from google_auth_oauthlib.flow import InstalledAppFlow
    from google.auth.transport.requests import Request
    from googleapiclient.discovery import build
    from googleapiclient.http import MediaFileUpload
    HAS_DRIVE = True
except ImportError:
    HAS_DRIVE = False

# Scopes
SCOPES = ['https://www.googleapis.com/auth/drive.file']


class DriveUploader:
    """Handles Google Drive authentication and uploads."""

    def __init__(self, secrets_file: str = "client_secrets.json", token_file: str = "token.pickle"):
        self.secrets_file = Path(secrets_file)
        self.token_file = Path(token_file)
        self.service = None
        self.creds = None
        self._auth_lock = threading.Lock()

    def authenticate(self) -> bool:
        """
        Authenticate with Google Drive.
        Returns True if successful, False otherwise.
        """
        if not HAS_DRIVE:
            print("Google Drive kütüphaneleri eksik. 'pip install google-api-python-client google-auth-oauthlib'")
            return False

        with self._auth_lock:
            try:
                # Load existing tokens
                if self.token_file.exists():
                    with open(self.token_file, 'rb') as token:
                        self.creds = pickle.load(token)

                # Refresh if expired
                if not self.creds or not self.creds.valid:
                    if self.creds and self.creds.expired and self.creds.refresh_token:
                        self.creds.refresh(Request())
                    else:
                        if not self.secrets_file.exists():
                            print(f"Hata: {self.secrets_file} bulunamadı!")
                            return False
                        
                        flow = InstalledAppFlow.from_client_secrets_file(
                            str(self.secrets_file), SCOPES
                        )
                        self.creds = flow.run_local_server(port=0)

                    # Save creds
                    with open(self.token_file, 'wb') as token:
                        pickle.dump(self.creds, token)

                self.service = build('drive', 'v3', credentials=self.creds)
                return True

            except Exception as e:
                print(f"Drive Auth Hatası: {e}")
                return False

    def list_folders(self, page_size: int = 20) -> List[Dict[str, str]]:
        """List folders in the root directory."""
        if not self.service:
            return []

        try:
            results = self.service.files().list(
                pageSize=page_size,
                q="mimeType='application/vnd.google-apps.folder' and trashed=false",
                fields="nextPageToken, files(id, name)"
            ).execute()
            return results.get('files', [])
        except Exception as e:
            print(f"Klasör listeleme hatası: {e}")
            return []

    def upload_file(
        self, 
        file_path: Path, 
        folder_id: Optional[str] = None,
        callback: Optional[Callable[[float], None]] = None
    ) -> Optional[str]:
        """
        Uploads a file to Google Drive.
        
        Args:
            file_path: Path to the file.
            folder_id: Destination folder ID.
            callback: Progress callback (not fully supported by simple MediaFileUpload but kept for interface).
            
        Returns:
            File ID if successful, None otherwise.
        """
        if not self.service:
            if not self.authenticate():
                return None

        file_path = Path(file_path)
        if not file_path.exists():
            print(f"Dosya bulunamadı: {file_path}")
            return None

        try:
            file_metadata = {'name': file_path.name}
            if folder_id:
                file_metadata['parents'] = [folder_id]

            media = MediaFileUpload(
                str(file_path),
                mimetype='video/mp4', # Adjust if willing to support other types generically
                resumable=True
            )

            # Basic upload (synchronous in this function, but this function will be called in a thread)
            # For progress updates, we'd need a more complex loop with media.next_chunk()
            # For now, we'll do a simple execute() which blocks until done.
            
            # NOTE: To support "real" progress in TUI, we might want manual chunking.
            # But "background upload" usually implies fire-and-forget for the user flow.
            # I will implement a basic chunked upload to support basic logging/status if needed later.
            
            request = self.service.files().create(
                body=file_metadata,
                media_body=media,
                fields='id'
            )
            
            response = None
            while response is None:
                status, response = request.next_chunk()
                if status:
                    # int(status.progress() * 100)
                    if callback:
                        callback(status.progress())
            
            # 100%
            if callback:
                callback(1.0)
                
            return response.get('id')

        except Exception as e:
            print(f"Upload hatası ({file_path.name}): {e}")
            return None

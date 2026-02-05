#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Google Drive integration for uploading rendered videos.
"""

import pickle
import os.path
from pathlib import Path
from typing import Optional, List, Dict, Tuple

from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

# Scopes required for uploading
SCOPES = ['https://www.googleapis.com/auth/drive.file']

class DriveUploader:
    def __init__(self, credentials_path: Path = Path("credentials.json"), token_path: Path = Path("token.pickle")):
        self.credentials_path = credentials_path
        self.token_path = token_path
        self.creds = None
        self.service = None

    def authenticate(self) -> bool:
        """
        Authenticate with Google Drive API.
        Returns True if successful, False otherwise.
        """
        self.creds = None
        
        # Load existing token
        if self.token_path.exists():
            with open(self.token_path, 'rb') as token:
                try:
                    self.creds = pickle.load(token)
                except Exception:
                    pass
        
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
                    print(f"HATA: '{self.credentials_path}' dosyasi bulunamadi!")
                    print("Google Cloud Console'dan indirdiginiz OAuth client secret dosyasini bu isimle kaydedin.")
                    return False
                
                try:
                    print("Google Drive yetkilendirmesi baslatiliyor...")
                    print("Lutfen asagidaki linke tiklayin ve onay kodunu yapistirin:")
                    flow = InstalledAppFlow.from_client_secrets_file(
                        str(self.credentials_path), SCOPES)
                    # Use run_console to handle VPS scenario cleanly
                    self.creds = flow.run_console()
                except Exception as e:
                    print(f"Authentication failed: {e}")
                    return False
            
            # Save the token
            with open(self.token_path, 'wb') as token:
                pickle.dump(self.creds, token)
        
        try:
            self.service = build('drive', 'v3', credentials=self.creds)
            return True
        except Exception as e:
            print(f"Service build failed: {e}")
            return False

    def list_folders(self, page_size: int = 10) -> List[Dict[str, str]]:
        """List folders in root or last accessed."""
        if not self.service:
            return []
        
        try:
            results = self.service.files().list(
                pageSize=page_size,
                q="mimeType='application/vnd.google-apps.folder' and trashed=false",
                fields="nextPageToken, files(id, name)",
                orderBy="folder,name").execute()
            items = results.get('files', [])
            return items
        except Exception as e:
            print(f"List folders failed: {e}")
            return []

    def upload_file(self, file_path: Path, folder_id: Optional[str] = None) -> Tuple[bool, str]:
        """
        Upload a file to Google Drive.
        
        Args:
            file_path: Path to the file to upload.
            folder_id: ID of the folder to upload to (optional).
            
        Returns:
            (Success, Message/FileID)
        """
        if not self.service:
            if not self.authenticate():
                 return False, "Not authenticated"

        file_metadata = {'name': file_path.name}
        if folder_id:
            file_metadata['parents'] = [folder_id]
            
        media = MediaFileUpload(str(file_path), resumable=True)
        
        try:
            file = self.service.files().create(
                body=file_metadata,
                media_body=media,
                fields='id'
            ).execute()
            return True, file.get('id')
        except Exception as e:
            return False, str(e)

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

#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Jamendo API client for royalty-free music search and download.
"""

import re
import time
import requests
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Dict, Any
from urllib.parse import urljoin


# ═══════════════════════════════════════════════════════════════════════════════
# Data Types
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class JamendoTrack:
    """Represents a Jamendo music track."""
    id: str
    name: str
    artist_name: str
    album_name: str
    duration: int  # seconds
    genre: str
    audio_url: str
    audio_download_url: str
    license_ccurl: str
    
    @property
    def filename(self) -> str:
        """Generate safe filename for the track."""
        safe_name = re.sub(r'[^\w\s-]', '', self.name)
        safe_name = re.sub(r'\s+', '_', safe_name)
        safe_artist = re.sub(r'[^\w\s-]', '', self.artist_name)
        safe_artist = re.sub(r'\s+', '_', safe_artist)
        return f"{safe_artist}_{safe_name}_{self.id}.mp3"
    
    @classmethod
    def from_api_response(cls, data: Dict[str, Any]) -> "JamendoTrack":
        """Create from Jamendo API response."""
        return cls(
            id=str(data.get("id", "")),
            name=data.get("name", "Unknown"),
            artist_name=data.get("artist_name", "Unknown Artist"),
            album_name=data.get("album_name", "Unknown Album"),
            duration=int(data.get("duration", 0)),
            genre=data.get("musicinfo", {}).get("tags", {}).get("genres", ["unknown"])[0] if data.get("musicinfo") else "unknown",
            audio_url=data.get("audio", ""),
            audio_download_url=data.get("audiodownload", ""),
            license_ccurl=data.get("license_ccurl", ""),
        )


# ═══════════════════════════════════════════════════════════════════════════════
# Jamendo Client
# ═══════════════════════════════════════════════════════════════════════════════

class JamendoClient:
    """
    Client for Jamendo API.
    
    Docs: https://developer.jamendo.com/v3.0
    """
    
    BASE_URL = "https://api.jamendo.com/v3.0"
    
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "VideoAutomation/1.0"
        })
    
    def _request(self, endpoint: str, params: Dict[str, Any] = None) -> Dict[str, Any]:
        """Make API request."""
        if params is None:
            params = {}
        
        params["client_id"] = self.api_key
        params["format"] = "json"
        
        url = urljoin(self.BASE_URL + "/", endpoint)
        
        response = self.session.get(url, params=params)
        response.raise_for_status()
        
        data = response.json()
        
        if data.get("headers", {}).get("status") == "failed":
            error_msg = data.get("headers", {}).get("error_message", "Unknown error")
            raise ValueError(f"Jamendo API error: {error_msg}")
        
        return data
    
    def search_tracks(
        self,
        tags: Optional[List[str]] = None,
        fuzzytags: Optional[str] = None,
        limit: int = 15,
        offset: int = 0,
        duration_min: Optional[int] = None,
        duration_max: Optional[int] = None,
        order: str = "popularity_total",
        audioformat: str = "mp32",
        include: str = "musicinfo",
    ) -> List[JamendoTrack]:
        """
        Search for tracks.
        
        Args:
            tags: Exact genre tags to search for
            fuzzytags: Fuzzy search for mood/genre
            limit: Max results (1-200)
            offset: Pagination offset
            duration_min: Minimum duration in seconds
            duration_max: Maximum duration in seconds
            order: Sort order (popularity_total, popularity_week, etc.)
            audioformat: mp31 (96kbps), mp32 (VBR ~192kbps)
            include: Additional info (musicinfo for genres)
            
        Returns:
            List of JamendoTrack objects
        """
        params = {
            "limit": min(limit, 200),
            "offset": offset,
            "order": order,
            "audioformat": audioformat,
            "include": include,
        }
        
        if tags:
            params["tags"] = "+".join(tags)
        
        if fuzzytags:
            params["fuzzytags"] = fuzzytags
        
        if duration_min:
            params["durationbetween"] = f"{duration_min}_{duration_max or 9999}"
        
        response = self._request("tracks", params)
        
        tracks = []
        for item in response.get("results", []):
            try:
                track = JamendoTrack.from_api_response(item)
                if track.audio_download_url:  # Only include downloadable tracks
                    tracks.append(track)
            except Exception:
                continue
        
        return tracks
    
    def get_track(self, track_id: str) -> Optional[JamendoTrack]:
        """Get a specific track by ID."""
        params = {
            "id": track_id,
            "include": "musicinfo",
            "audioformat": "mp32",
        }
        
        response = self._request("tracks", params)
        results = response.get("results", [])
        
        if results:
            return JamendoTrack.from_api_response(results[0])
        return None
    
    def download_track(
        self,
        track: JamendoTrack,
        output_dir: Path,
        filename: Optional[str] = None,
        progress_callback=None
    ) -> Path:
        """
        Download a track to local file.
        
        Args:
            track: Track to download
            output_dir: Directory to save file
            filename: Optional custom filename
            progress_callback: Optional callback(bytes_downloaded, total_bytes)
            
        Returns:
            Path to downloaded file
        """
        output_dir.mkdir(parents=True, exist_ok=True)
        
        if filename is None:
            filename = track.filename
        
        output_path = output_dir / filename
        
        # Use audiodownload URL which allows direct download
        url = track.audio_download_url
        if not url:
            url = track.audio_url
        
        response = self.session.get(url, stream=True)
        response.raise_for_status()
        
        total_size = int(response.headers.get("content-length", 0))
        downloaded = 0
        
        with open(output_path, "wb") as f:
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)
                    downloaded += len(chunk)
                    if progress_callback:
                        progress_callback(downloaded, total_size)
        
        return output_path
    
    def search_by_mood_genre(
        self,
        mood: str,
        genre: Optional[str] = None,
        limit: int = 15,
        min_duration: int = 120,  # At least 2 minutes
    ) -> List[JamendoTrack]:
        """
        Search tracks by mood and optionally genre.
        
        This is a convenience method combining fuzzytags search.
        """
        fuzzytags = mood
        if genre:
            fuzzytags = f"{mood} {genre}"
        
        return self.search_tracks(
            fuzzytags=fuzzytags,
            limit=limit,
            duration_min=min_duration,
            order="popularity_total",
        )


# ═══════════════════════════════════════════════════════════════════════════════
# Batch Download
# ═══════════════════════════════════════════════════════════════════════════════

def download_tracks_batch(
    client: JamendoClient,
    tracks: List[JamendoTrack],
    output_dir: Path,
    delay_between: float = 0.5,
    on_progress=None,
    on_complete=None,
) -> List[Path]:
    """
    Download multiple tracks with rate limiting.
    
    Args:
        client: Jamendo client
        tracks: List of tracks to download
        output_dir: Output directory
        delay_between: Delay between downloads (seconds)
        on_progress: Callback(track_index, track, bytes, total)
        on_complete: Callback(track_index, track, path)
        
    Returns:
        List of downloaded file paths
    """
    paths = []
    
    for i, track in enumerate(tracks):
        def progress_cb(downloaded, total):
            if on_progress:
                on_progress(i, track, downloaded, total)
        
        path = client.download_track(track, output_dir, progress_callback=progress_cb)
        paths.append(path)
        
        if on_complete:
            on_complete(i, track, path)
        
        # Rate limiting
        if i < len(tracks) - 1:
            time.sleep(delay_between)
    
    return paths

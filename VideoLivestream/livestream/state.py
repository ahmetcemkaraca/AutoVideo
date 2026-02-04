#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
State management for livestream rotation.
"""

import json
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Dict, Optional
from datetime import datetime


@dataclass
class ChannelState:
    """State for a single channel."""
    current_playlist_index: int = 0
    times_played: int = 0
    last_played: Optional[str] = None


@dataclass
class LivestreamState:
    """Complete livestream state."""
    current_channel_index: int = 0
    channels: Dict[str, ChannelState] = None
    total_segments: int = 0
    started_at: Optional[str] = None
    last_rotation: Optional[str] = None
    
    def __post_init__(self):
        if self.channels is None:
            self.channels = {}


class StateManager:
    """
    Manages persistent state for livestream rotation.
    """
    
    def __init__(self, state_file: Path):
        self.state_file = state_file
        self._state = LivestreamState()
        self._load()
    
    def _load(self):
        """Load state from file."""
        if not self.state_file.exists():
            return
        
        try:
            with open(self.state_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            
            channels = {}
            for name, ch_data in data.get("channels", {}).items():
                channels[name] = ChannelState(**ch_data)
            
            self._state = LivestreamState(
                current_channel_index=data.get("current_channel_index", 0),
                channels=channels,
                total_segments=data.get("total_segments", 0),
                started_at=data.get("started_at"),
                last_rotation=data.get("last_rotation"),
            )
            
        except Exception as e:
            print(f"Warning: Could not load state: {e}")
    
    def save(self):
        """Save state to file."""
        self.state_file.parent.mkdir(parents=True, exist_ok=True)
        
        data = {
            "current_channel_index": self._state.current_channel_index,
            "channels": {
                name: asdict(ch) for name, ch in self._state.channels.items()
            },
            "total_segments": self._state.total_segments,
            "started_at": self._state.started_at,
            "last_rotation": self._state.last_rotation,
        }
        
        with open(self.state_file, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
    
    def get_current_channel_index(self) -> int:
        """Get current channel index."""
        return self._state.current_channel_index
    
    def set_current_channel_index(self, index: int):
        """Set current channel index."""
        self._state.current_channel_index = index
        self.save()
    
    def get_channel_state(self, channel_name: str) -> ChannelState:
        """Get state for a specific channel."""
        if channel_name not in self._state.channels:
            self._state.channels[channel_name] = ChannelState()
        return self._state.channels[channel_name]
    
    def advance_playlist(self, channel_name: str, playlist_count: int):
        """Advance to next playlist for a channel."""
        state = self.get_channel_state(channel_name)
        state.current_playlist_index = (state.current_playlist_index + 1) % playlist_count
        state.times_played += 1
        state.last_played = datetime.now().isoformat()
        self.save()
    
    def record_rotation(self):
        """Record that a rotation happened."""
        self._state.total_segments += 1
        self._state.last_rotation = datetime.now().isoformat()
        
        if self._state.started_at is None:
            self._state.started_at = datetime.now().isoformat()
        
        self.save()
    
    @property
    def stats(self) -> dict:
        """Get statistics."""
        return {
            "total_segments": self._state.total_segments,
            "started_at": self._state.started_at,
            "last_rotation": self._state.last_rotation,
        }

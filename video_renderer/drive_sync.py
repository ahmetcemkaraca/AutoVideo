#!/usr/bin/env python3
"""
Google Drive sync support for shared asset folders.

This module pulls new music and source videos from the shared Drive folder into
local `music/` and `upload/` directories while tracking sync state to avoid
duplicate downloads.
"""

import logging
from dataclasses import dataclass, field
from pathlib import Path

from .config import AUDIO_EXTENSIONS, VIDEO_EXTENSIONS
from .drive import DriveUploader
from .state_manager import StateManager

logger = logging.getLogger(__name__)


@dataclass
class DriveSyncResult:
    downloaded: list[Path] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


class DriveSyncService:
    STATE_KEY = "drive_sync"

    def __init__(
        self,
        root_folder_id: str,
        base_dir: Path | None = None,
        state_file: Path | None = None,
    ):
        self.root_folder_id = root_folder_id
        self.base_dir = base_dir or Path.cwd()
        self.uploader = DriveUploader()
        self.state = StateManager(
            state_file=state_file or (self.base_dir / "tmp" / "drive_sync_state.json"),
            auto_save=True,
        )

    def _folder_id(self, folder_name: str) -> str | None:
        folders = self.uploader.list_folders(page_size=100, parent_folder_id=self.root_folder_id)
        for folder in folders:
            if folder.get("name") == folder_name:
                return folder.get("id")
        return None

    def _sync_dir(self, folder_name: str) -> Path:
        path = self.base_dir / folder_name
        path.mkdir(parents=True, exist_ok=True)
        return path

    def _state_for(self, folder_name: str) -> dict[str, dict]:
        state = self.state.get(self.STATE_KEY, {})
        folder_state = state.get(folder_name, {})
        if not isinstance(folder_state, dict):
            return {}
        return folder_state

    def _save_folder_state(self, folder_name: str, folder_state: dict[str, dict]) -> None:
        state = self.state.get(self.STATE_KEY, {})
        if not isinstance(state, dict):
            state = {}
        state[folder_name] = folder_state
        self.state.set(self.STATE_KEY, state)

    def sync(self) -> DriveSyncResult:
        result = DriveSyncResult()
        targets = {
            "music": AUDIO_EXTENSIONS,
            "upload": VIDEO_EXTENSIONS,
        }

        for folder_name, allowed_extensions in targets.items():
            folder_id = self._folder_id(folder_name)
            if not folder_id:
                result.errors.append(f"Drive folder not found: {folder_name}")
                continue

            remote_files = self.uploader.list_files(folder_id)
            local_dir = self._sync_dir(folder_name)
            folder_state = self._state_for(folder_name)

            for file_meta in remote_files:
                name = file_meta.get("name") or ""
                ext = Path(name).suffix.lower()
                if ext not in allowed_extensions:
                    result.skipped.append(name)
                    continue

                file_id = file_meta.get("id")
                md5 = file_meta.get("md5Checksum") or ""
                state_entry = folder_state.get(file_id)
                if state_entry and state_entry.get("md5Checksum") == md5:
                    result.skipped.append(name)
                    continue

                destination = local_dir / name
                success, message = self.uploader.download_file(file_id, destination)
                if not success:
                    result.errors.append(f"{name}: {message}")
                    continue

                folder_state[file_id] = {
                    "name": name,
                    "md5Checksum": md5,
                    "path": str(destination),
                }
                result.downloaded.append(destination)

            self._save_folder_state(folder_name, folder_state)

        return result


def sync_drive_assets(root_folder_id: str, base_dir: Path | None = None) -> DriveSyncResult:
    service = DriveSyncService(root_folder_id=root_folder_id, base_dir=base_dir)
    return service.sync()

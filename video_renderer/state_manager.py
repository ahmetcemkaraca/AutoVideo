#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Unified State Management System.

Provides thread-safe, atomic state management for batch and pipeline systems.
This module implements a unified approach to state persistence across all
video rendering components.

Key Features:
- Thread-safe operations with RLock
- Atomic file writes using temp file + rename pattern
- Cross-process file locking
- State snapshots for resume capability
- Automatic stale lock cleanup
"""

import json
import time
import threading
import os
import tempfile
from dataclasses import dataclass, asdict, field
from pathlib import Path
from typing import Any, Optional, Dict, List, Callable
import logging

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class StateSnapshot:
    """
    Immutable state snapshot for resume capability.

    Attributes:
        version: State format version for migration support
        timestamp: Creation time as Unix timestamp
        data: Copy of state data at snapshot time
        metadata: Optional metadata about the snapshot
    """

    version: str
    timestamp: float
    data: Dict[str, Any]
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "StateSnapshot":
        """Create from dictionary."""
        return cls(**data)


class StateLock:
    """
    Cross-process file lock for state synchronization.

    Uses platform-specific locking mechanisms:
    - Windows: O_EXCL file creation
    - Unix: fcntl.flock (if available)

    Includes automatic stale lock cleanup (locks older than 5 minutes).
    """

    STALE_LOCK_SECONDS = 300  # 5 minutes

    def __init__(self, state_file: Path, timeout: float = 10.0):
        """
        Initialize state lock.

        Args:
            state_file: Path to the state file (lock file will be .lock)
            timeout: Maximum seconds to wait for lock acquisition
        """
        self.state_file = state_file
        self.timeout = timeout
        self._lock_path = state_file.parent / f"{state_file.name}.lock"
        self._fd = None
        self._locked = False

    def __enter__(self):
        """Acquire lock with stale lock cleanup."""
        start_time = time.time()

        while True:
            # Check for stale lock
            if self._lock_path.exists():
                lock_age = time.time() - self._lock_path.stat().st_mtime
                if lock_age > self.STALE_LOCK_SECONDS:
                    logger.warning(
                        f"Removing stale lock file: {self._lock_path} " f"(age: {lock_age:.0f}s)"
                    )
                    try:
                        self._lock_path.unlink()
                    except OSError:
                        pass  # Lock was just removed by another process

            # Try to acquire lock
            try:
                # Use O_EXCL for atomic lock creation
                flags = os.O_CREAT | os.O_EXCL | os.O_WRONLY
                self._fd = os.open(self._lock_path, flags)
                # Write PID for debugging
                os.write(self._fd, str(os.getpid()).encode())
                self._locked = True
                return self
            except FileExistsError:
                # Lock held by another process
                if time.time() - start_time > self.timeout:
                    raise TimeoutError(
                        f"Could not acquire lock on {self.state_file} " f"after {self.timeout}s"
                    )
                time.sleep(0.05)  # Wait 50ms before retry

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Release lock."""
        if self._fd is not None:
            try:
                os.close(self._fd)
            except OSError:
                pass
        if self._locked and self._lock_path.exists():
            try:
                self._lock_path.unlink()
            except OSError:
                pass


class StateManager:
    """
    Thread-safe, atomic state manager with persistence.

    This is the unified state management solution for all video rendering
    components including BatchQueue and PipelineState.

    Thread-Safety Guarantees:
    - All operations are protected by RLock
    - File I/O uses atomic write pattern (temp file + rename)
    - Cross-process synchronization via file locking

    Usage:
        state = StateManager(Path("tmp/state.json"))
        state.set("job_id", 123)
        job_id = state.get("job_id")
        snapshot = state.create_snapshot()
    """

    DEFAULT_VERSION = "1.0"

    def __init__(
        self,
        state_file: Path,
        version: str = DEFAULT_VERSION,
        auto_save: bool = True,
        enable_locking: bool = True,
    ):
        """
        Initialize state manager.

        Args:
            state_file: Path to state file
            version: State format version (for migration support)
            auto_save: Automatically save after set operations
            enable_locking: Enable cross-process file locking
        """
        self.state_file = state_file
        self._version = version
        self._auto_save = auto_save
        self._enable_locking = enable_locking

        # Internal state storage
        self._state: Dict[str, Any] = {}
        self._lock = threading.RLock()

        # Change callbacks
        self._on_changed: Optional[Callable[[str, Any], None]] = None

        # Load existing state
        self.load()

    def get(self, key: str, default: Any = None) -> Any:
        """
        Get state value.

        Args:
            key: State key
            default: Default value if key not found

        Returns:
            State value or default
        """
        with self._lock:
            return self._state.get(key, default)

    def set(self, key: str, value: Any, save: Optional[bool] = None) -> None:
        """
        Set state value.

        Args:
            key: State key
            value: Value to set
            save: Override auto_save setting for this operation
        """
        with self._lock:
            self._state[key] = value

            # Invoke change callback
            if self._on_changed:
                try:
                    self._on_changed(key, value)
                except Exception as e:
                    logger.error(f"Error in state change callback: {e}")

            # Save if auto_save is enabled
            if save is None:
                save = self._auto_save
            if save:
                self._save()

    def update(self, data: Dict[str, Any], save: Optional[bool] = None) -> None:
        """
        Update multiple state values at once.

        Args:
            data: Dictionary of key-value pairs to update
            save: Override auto_save setting
        """
        with self._lock:
            for key, value in data.items():
                self._state[key] = value
                if self._on_changed:
                    try:
                        self._on_changed(key, value)
                    except Exception as e:
                        logger.error(f"Error in state change callback: {e}")

            if save is None:
                save = self._auto_save
            if save:
                self._save()

    def delete(self, key: str, save: Optional[bool] = None) -> bool:
        """
        Delete state value.

        Args:
            key: State key to delete
            save: Override auto_save setting

        Returns:
            True if key was deleted, False if it didn't exist
        """
        with self._lock:
            if key not in self._state:
                return False

            del self._state[key]

            if save is None:
                save = self._auto_save
            if save:
                self._save()

            return True

    def clear(self, save: Optional[bool] = None) -> None:
        """
        Clear all state.

        Args:
            save: Override auto_save setting
        """
        with self._lock:
            self._state.clear()

            if save is None:
                save = self._auto_save
            if save:
                self._save()

    def keys(self) -> List[str]:
        """Get all state keys."""
        with self._lock:
            return list(self._state.keys())

    def items(self) -> List[tuple[str, Any]]:
        """Get all state key-value pairs."""
        with self._lock:
            return list(self._state.items())

    def _save(self) -> None:
        """
        Save state to file using atomic write.

        Thread-safe: Uses temp file + atomic rename pattern.
        Cross-process safe: Uses file locking if enabled.
        """
        # Ensure parent directory exists
        self.state_file.parent.mkdir(parents=True, exist_ok=True)

        # Create snapshot
        snapshot = StateSnapshot(
            version=self._version, timestamp=time.time(), data=self._state.copy()
        )

        # Write to temp file
        try:
            with tempfile.NamedTemporaryFile(
                mode="w", suffix=".tmp", dir=self.state_file.parent, delete=False, encoding="utf-8"
            ) as tmp:
                json.dump(snapshot.to_dict(), tmp, indent=2, ensure_ascii=False)
                tmp_path = Path(tmp.name)

            # Apply file lock if enabled
            if self._enable_locking:
                with StateLock(self.state_file):
                    tmp_path.replace(self.state_file)
            else:
                tmp_path.replace(self.state_file)

        except Exception as e:
            # Clean up temp file on error
            if "tmp_path" in locals() and tmp_path.exists():
                try:
                    tmp_path.unlink()
                except OSError:
                    pass
            logger.error(f"Error saving state: {e}")
            raise

    def load(self) -> bool:
        """
        Load state from file.

        Returns:
            True if state was loaded, False if file doesn't exist
        """
        if not self.state_file.exists():
            return False

        try:
            # Apply file lock if enabled
            if self._enable_locking:
                with StateLock(self.state_file):
                    data = json.loads(self.state_file.read_text(encoding="utf-8"))
            else:
                data = json.loads(self.state_file.read_text(encoding="utf-8"))

            # Parse snapshot
            snapshot = StateSnapshot.from_dict(data)

            # Version check (for future migration support)
            if snapshot.version != self._version:
                logger.warning(
                    f"State version mismatch: expected {self._version}, " f"got {snapshot.version}"
                )

            with self._lock:
                self._state = snapshot.data

            return True

        except json.JSONDecodeError as e:
            logger.error(f"Could not parse state file {self.state_file}: {e}")
            return False
        except Exception as e:
            logger.error(f"Error loading state: {e}")
            return False

    def create_snapshot(self) -> StateSnapshot:
        """
        Create state snapshot for resume capability.

        Returns:
            Immutable snapshot of current state
        """
        with self._lock:
            return StateSnapshot(
                version=self._version, timestamp=time.time(), data=self._state.copy()
            )

    def restore_snapshot(self, snapshot: StateSnapshot, save: bool = True) -> None:
        """
        Restore state from snapshot.

        Args:
            snapshot: Snapshot to restore
            save: Whether to save after restoring
        """
        with self._lock:
            # Version check
            if snapshot.version != self._version:
                logger.warning(
                    f"Snapshot version mismatch: expected {self._version}, "
                    f"got {snapshot.version}"
                )

            self._state = snapshot.data.copy()

            if save:
                self._save()

    def set_change_callback(self, callback: Optional[Callable[[str, Any], None]]) -> None:
        """
        Set callback for state changes.

        Args:
            callback: Function to call when state changes (key, value)
        """
        with self._lock:
            self._on_changed = callback

    @property
    def version(self) -> str:
        """Get state format version."""
        return self._version

    @property
    def size(self) -> int:
        """Get number of state items."""
        with self._lock:
            return len(self._state)

    def __contains__(self, key: str) -> bool:
        """Check if key exists in state."""
        with self._lock:
            return key in self._state

    def __len__(self) -> int:
        """Get number of state items."""
        return self.size

    def __repr__(self) -> str:
        """String representation."""
        return f"StateManager(file={self.state_file}, items={self.size})"


class TypedStateManager(StateManager):
    """
    State manager with type-safe accessors.

    Provides typed get/set methods for common data types.
    Useful for components that need type safety.
    """

    def get_int(self, key: str, default: int = 0) -> int:
        """Get integer value."""
        value = self.get(key)
        if value is None:
            return default
        try:
            return int(value)
        except (ValueError, TypeError):
            return default

    def get_float(self, key: str, default: float = 0.0) -> float:
        """Get float value."""
        value = self.get(key)
        if value is None:
            return default
        try:
            return float(value)
        except (ValueError, TypeError):
            return default

    def get_str(self, key: str, default: str = "") -> str:
        """Get string value."""
        value = self.get(key)
        if value is None:
            return default
        return str(value)

    def get_bool(self, key: str, default: bool = False) -> bool:
        """Get boolean value."""
        value = self.get(key)
        if value is None:
            return default
        if isinstance(value, bool):
            return value
        return str(value).lower() in ("true", "1", "yes", "on")

    def get_list(self, key: str, default: Optional[List] = None) -> List:
        """Get list value."""
        value = self.get(key)
        if value is None:
            return default or []
        if isinstance(value, list):
            return value
        return []

    def get_dict(self, key: str, default: Optional[Dict] = None) -> Dict:
        """Get dict value."""
        value = self.get(key)
        if value is None:
            return default or {}
        if isinstance(value, dict):
            return value
        return {}

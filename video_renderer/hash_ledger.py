#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Source Hash Ledger for Duplicate Video Prevention.

Tracks intro/loop source videos by SHA256 hash to prevent duplicate renders.
Uses thread-safe, atomic file operations for persistence.

Key Features:
- SHA256 hash calculation for source video files
- Persistent JSON ledger with thread-safe operations
- Check-before-render workflow integration
- CLI force override support
- Cross-process file locking

Usage:
    ledger = HashLedger(ledger_file=Path("tmp/hash_ledger.json"))
    
    if ledger.check_and_register(intro_path, loop_path, output_path):
        # Proceed with render
    else:
        # Skip - already rendered
"""

import hashlib
import json
import threading
import time
import tempfile
import os
from dataclasses import dataclass, asdict, field
from pathlib import Path
from typing import Optional, List, Dict, Any
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


@dataclass
class HashEntry:
    """
    Represents a single hash ledger entry.
    
    Attributes:
        file_hash: SHA256 hash of the source file
        file_path: Original file path
        timestamp: ISO format timestamp when entry was created
        output_path: Path to the rendered output video
    """
    
    file_hash: str
    file_path: str
    timestamp: str
    output_path: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "HashEntry":
        return cls(**data)


@dataclass 
class SourcePair:
    """
    Represents a matched intro/loop pair with their hashes.
    
    Attributes:
        intro_hash: SHA256 hash of intro video
        loop_hash: SHA256 hash of loop video
        intro_path: Path to intro video
        loop_path: Path to loop video
        timestamp: When this pair was registered
        output_path: Path to rendered output
    """
    
    intro_hash: str
    loop_hash: str
    intro_path: str
    loop_path: str
    timestamp: str
    output_path: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SourcePair":
        return cls(**data)
    
    @property
    def combined_hash(self) -> str:
        """Generate a combined hash for the pair."""
        combined = f"{self.intro_hash}:{self.loop_hash}"
        return hashlib.sha256(combined.encode()).hexdigest()[:16]


class HashLedgerLock:
    """
    Cross-process file lock for hash ledger.
    
    Uses O_EXCL for atomic lock creation on all platforms.
    Includes automatic stale lock cleanup.
    """
    
    STALE_LOCK_SECONDS = 300
    
    def __init__(self, ledger_file: Path, timeout: float = 10.0):
        self.ledger_file = ledger_file
        self.timeout = timeout
        self._lock_path = ledger_file.parent / f"{ledger_file.name}.lock"
        self._fd = None
        self._locked = False
    
    def __enter__(self):
        start_time = time.time()
        
        while True:
            if self._lock_path.exists():
                lock_age = time.time() - self._lock_path.stat().st_mtime
                if lock_age > self.STALE_LOCK_SECONDS:
                    logger.warning(f"Removing stale lock: {self._lock_path}")
                    try:
                        self._lock_path.unlink()
                    except OSError:
                        pass
            
            try:
                flags = os.O_CREAT | os.O_EXCL | os.O_WRONLY
                self._fd = os.open(self._lock_path, flags)
                os.write(self._fd, str(os.getpid()).encode())
                self._locked = True
                return self
            except FileExistsError:
                if time.time() - start_time > self.timeout:
                    raise TimeoutError(
                        f"Could not acquire lock on {self.ledger_file}"
                    )
                time.sleep(0.05)
    
    def __exit__(self, exc_type, exc_val, exc_tb):
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


class HashLedger:
    """
    Thread-safe hash ledger for duplicate video prevention.
    
    Tracks source video files by SHA256 hash and prevents
    re-rendering of identical source combinations.
    
    Thread-Safety Guarantees:
    - All operations protected by RLock
    - Atomic file writes (temp file + rename)
    - Cross-process file locking
    
    Usage:
        ledger = HashLedger()
        
        # Check before render
        if ledger.is_registered(intro_path, loop_path):
            print("Already rendered, skipping...")
        else:
            render_video()
            ledger.register(intro_path, loop_path, output_path)
    """
    
    LEDGER_VERSION = "1.0"
    CHUNK_SIZE = 65536
    
    def __init__(
        self,
        ledger_file: Optional[Path] = None,
        enable_locking: bool = True
    ):
        """
        Initialize hash ledger.
        
        Args:
            ledger_file: Path to ledger JSON file
            enable_locking: Enable cross-process file locking
        """
        # Keep the default ledger in config/ so renders share one human-readable registry.
        self._ledger_file = ledger_file or Path.cwd() / "config" / "ledger.json"
        self._enable_locking = enable_locking
        self._lock = threading.RLock()
        
        self._entries: Dict[str, HashEntry] = {}
        self._pairs: Dict[str, SourcePair] = {}
        
        self._load()
    
    def calculate_hash(self, file_path: Path) -> str:
        """
        Calculate SHA256 hash of a file.
        
        Args:
            file_path: Path to file
            
        Returns:
            SHA256 hash as hex string
            
        Raises:
            FileNotFoundError: If file doesn't exist
            IOError: If file can't be read
        """
        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")
        
        sha256 = hashlib.sha256()
        
        with open(file_path, 'rb') as f:
            while True:
                chunk = f.read(self.CHUNK_SIZE)
                if not chunk:
                    break
                sha256.update(chunk)
        
        return sha256.hexdigest()
    
    def _load(self) -> None:
        """Load ledger from file."""
        if not self._ledger_file.exists():
            return
        
        try:
            if self._enable_locking:
                with HashLedgerLock(self._ledger_file):
                    data = json.loads(self._ledger_file.read_text(encoding="utf-8"))
            else:
                data = json.loads(self._ledger_file.read_text(encoding="utf-8"))
            
            if data.get("version") != self.LEDGER_VERSION:
                logger.warning(
                    f"Ledger version mismatch: expected {self.LEDGER_VERSION}, "
                    f"got {data.get('version')}"
                )
            
            with self._lock:
                for entry_data in data.get("entries", []):
                    entry = HashEntry.from_dict(entry_data)
                    self._entries[entry.file_hash] = entry
                
                for pair_data in data.get("pairs", []):
                    pair = SourcePair.from_dict(pair_data)
                    self._pairs[pair.combined_hash] = pair
            
            logger.debug(f"Loaded {len(self._entries)} entries, {len(self._pairs)} pairs")
            
        except json.JSONDecodeError as e:
            logger.error(f"Could not parse ledger file: {e}")
        except Exception as e:
            logger.error(f"Error loading ledger: {e}")
    
    def _save(self) -> None:
        """Save ledger to file with atomic write."""
        self._ledger_file.parent.mkdir(parents=True, exist_ok=True)
        
        with self._lock:
            data = {
                "version": self.LEDGER_VERSION,
                "entries": [e.to_dict() for e in self._entries.values()],
                "pairs": [p.to_dict() for p in self._pairs.values()]
            }
        
        tmp_path = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w",
                suffix=".tmp",
                dir=self._ledger_file.parent,
                delete=False,
                encoding="utf-8"
            ) as tmp:
                json.dump(data, tmp, indent=2, ensure_ascii=False)
                tmp_path = Path(tmp.name)
            
            if self._enable_locking:
                with HashLedgerLock(self._ledger_file):
                    tmp_path.replace(self._ledger_file)
            else:
                tmp_path.replace(self._ledger_file)
            
        except Exception as e:
            if tmp_path and tmp_path.exists():
                try:
                    tmp_path.unlink()
                except OSError:
                    pass
            logger.error(f"Error saving ledger: {e}")
            raise
    
    def is_registered(
        self,
        intro_path: Optional[Path] = None,
        loop_path: Optional[Path] = None,
        single_path: Optional[Path] = None
    ) -> bool:
        """
        Check if a source combination is already registered.
        
        Args:
            intro_path: Path to intro video (optional)
            loop_path: Path to loop video (optional)
            single_path: Path to single video (optional)
            
        Returns:
            True if already registered, False otherwise
        """
        with self._lock:
            if single_path:
                try:
                    file_hash = self.calculate_hash(single_path)
                    return file_hash in self._entries
                except FileNotFoundError:
                    return False
            
            if intro_path and loop_path:
                try:
                    intro_hash = self.calculate_hash(intro_path)
                    loop_hash = self.calculate_hash(loop_path)
                    combined = self._get_combined_hash(intro_hash, loop_hash)
                    return combined in self._pairs
                except FileNotFoundError:
                    return False
            
            return False
    
    def _get_combined_hash(self, intro_hash: str, loop_hash: str) -> str:
        """Generate combined hash for intro/loop pair."""
        combined = f"{intro_hash}:{loop_hash}"
        return hashlib.sha256(combined.encode()).hexdigest()[:16]
    
    def register(
        self,
        intro_path: Optional[Path] = None,
        loop_path: Optional[Path] = None,
        single_path: Optional[Path] = None,
        output_path: Optional[Path] = None
    ) -> bool:
        """
        Register a source combination after successful render.
        
        Args:
            intro_path: Path to intro video (optional)
            loop_path: Path to loop video (optional)
            single_path: Path to single video (optional)
            output_path: Path to rendered output
            
        Returns:
            True if registered successfully
        """
        timestamp = datetime.now().isoformat()
        
        with self._lock:
            if single_path:
                try:
                    file_hash = self.calculate_hash(single_path)
                    entry = HashEntry(
                        file_hash=file_hash,
                        file_path=str(single_path),
                        timestamp=timestamp,
                        output_path=str(output_path) if output_path else None
                    )
                    self._entries[file_hash] = entry
                    self._save()
                    logger.info(f"Registered single video: {single_path.name}")
                    return True
                except FileNotFoundError as e:
                    logger.error(f"File not found: {e}")
                    return False
            
            if intro_path and loop_path:
                try:
                    intro_hash = self.calculate_hash(intro_path)
                    loop_hash = self.calculate_hash(loop_path)
                    
                    pair = SourcePair(
                        intro_hash=intro_hash,
                        loop_hash=loop_hash,
                        intro_path=str(intro_path),
                        loop_path=str(loop_path),
                        timestamp=timestamp,
                        output_path=str(output_path) if output_path else None
                    )
                    
                    combined = self._get_combined_hash(intro_hash, loop_hash)
                    self._pairs[combined] = pair
                    self._save()
                    logger.info(f"Registered pair: {intro_path.name} + {loop_path.name}")
                    return True
                except FileNotFoundError as e:
                    logger.error(f"File not found: {e}")
                    return False
            
            return False
    
    def check_and_register(
        self,
        intro_path: Optional[Path] = None,
        loop_path: Optional[Path] = None,
        single_path: Optional[Path] = None,
        output_path: Optional[Path] = None,
        force: bool = False
    ) -> bool:
        """
        Check if source is registered, and register if not.
        
        Combined check + register operation for convenience.
        
        Args:
            intro_path: Path to intro video (optional)
            loop_path: Path to loop video (optional)
            single_path: Path to single video (optional)
            output_path: Path to rendered output
            force: Skip duplicate check and register anyway
            
        Returns:
            True if should proceed with render (not registered or forced)
        """
        if force:
            logger.info("Force flag set, bypassing duplicate check")
            return True
        
        if self.is_registered(intro_path, loop_path, single_path):
            logger.info("Source already registered, skipping render")
            return False
        
        return True
    
    def get_entry(
        self,
        intro_path: Optional[Path] = None,
        loop_path: Optional[Path] = None,
        single_path: Optional[Path] = None
    ) -> Optional[HashEntry]:
        """
        Get existing entry for a source combination.
        
        Returns:
            HashEntry if found, None otherwise
        """
        with self._lock:
            if single_path:
                try:
                    file_hash = self.calculate_hash(single_path)
                    return self._entries.get(file_hash)
                except FileNotFoundError:
                    return None
            
            if intro_path and loop_path:
                try:
                    intro_hash = self.calculate_hash(intro_path)
                    loop_hash = self.calculate_hash(loop_path)
                    combined = self._get_combined_hash(intro_hash, loop_hash)
                    pair = self._pairs.get(combined)
                    if pair:
                        return HashEntry(
                            file_hash=pair.intro_hash,
                            file_path=pair.intro_path,
                            timestamp=pair.timestamp,
                            output_path=pair.output_path
                        )
                except FileNotFoundError:
                    return None
            
            return None
    
    def get_pair(
        self,
        intro_path: Path,
        loop_path: Path
    ) -> Optional[SourcePair]:
        """
        Get existing pair entry.
        
        Returns:
            SourcePair if found, None otherwise
        """
        with self._lock:
            try:
                intro_hash = self.calculate_hash(intro_path)
                loop_hash = self.calculate_hash(loop_path)
                combined = self._get_combined_hash(intro_hash, loop_hash)
                return self._pairs.get(combined)
            except FileNotFoundError:
                return None
    
    def remove(
        self,
        intro_path: Optional[Path] = None,
        loop_path: Optional[Path] = None,
        single_path: Optional[Path] = None
    ) -> bool:
        """
        Remove an entry from the ledger.
        
        Returns:
            True if removed, False if not found
        """
        with self._lock:
            if single_path:
                try:
                    file_hash = self.calculate_hash(single_path)
                    if file_hash in self._entries:
                        del self._entries[file_hash]
                        self._save()
                        return True
                except FileNotFoundError:
                    return False
            
            if intro_path and loop_path:
                try:
                    intro_hash = self.calculate_hash(intro_path)
                    loop_hash = self.calculate_hash(loop_path)
                    combined = self._get_combined_hash(intro_hash, loop_hash)
                    if combined in self._pairs:
                        del self._pairs[combined]
                        self._save()
                        return True
                except FileNotFoundError:
                    return False
            
            return False
    
    def clear(self) -> None:
        """Clear all entries from the ledger."""
        with self._lock:
            self._entries.clear()
            self._pairs.clear()
            self._save()
    
    @property
    def entry_count(self) -> int:
        """Get number of single entries."""
        with self._lock:
            return len(self._entries)
    
    @property
    def pair_count(self) -> int:
        """Get number of registered pairs."""
        with self._lock:
            return len(self._pairs)
    
    @property
    def ledger_file(self) -> Path:
        """Get ledger file path."""
        return self._ledger_file
    
    def __len__(self) -> int:
        """Get total number of entries (singles + pairs)."""
        with self._lock:
            return len(self._entries) + len(self._pairs)
    
    def __repr__(self) -> str:
        return f"HashLedger(file={self._ledger_file}, entries={self.entry_count}, pairs={self.pair_count})"


def should_render(
    ledger: HashLedger,
    intro_path: Optional[Path] = None,
    loop_path: Optional[Path] = None,
    single_path: Optional[Path] = None,
    output_path: Optional[Path] = None,
    force: bool = False
) -> bool:
    """
    Convenience function to check if render should proceed.
    
    Args:
        ledger: HashLedger instance
        intro_path: Path to intro video
        loop_path: Path to loop video
        single_path: Path to single video
        output_path: Path to output video
        force: Force render even if duplicate
        
    Returns:
        True if should render, False if should skip
    """
    return ledger.check_and_register(
        intro_path=intro_path,
        loop_path=loop_path,
        single_path=single_path,
        output_path=output_path,
        force=force
    )

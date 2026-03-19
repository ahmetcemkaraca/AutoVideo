#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Unit tests for HashLedger module.

Tests cover:
- Hash calculation
- Entry registration and lookup
- Pair registration and lookup
- Check-before-render workflow
- Force override
- Thread safety
- Persistence
"""

import pytest
import json
import hashlib
from pathlib import Path
from unittest.mock import patch, MagicMock
from video_renderer.hash_ledger import (
    HashLedger,
    HashEntry,
    SourcePair,
    should_render
)


@pytest.mark.unit
class TestHashEntry:
    """Test suite for HashEntry dataclass."""

    def test_hash_entry_creation(self):
        """Test creating a HashEntry."""
        entry = HashEntry(
            file_hash="abc123",
            file_path="/path/to/video.mp4",
            timestamp="2024-01-01T00:00:00",
            output_path="/path/to/output.mp4"
        )

        assert entry.file_hash == "abc123"
        assert entry.file_path == "/path/to/video.mp4"
        assert entry.timestamp == "2024-01-01T00:00:00"
        assert entry.output_path == "/path/to/output.mp4"

    def test_hash_entry_to_dict(self):
        """Test converting HashEntry to dictionary."""
        entry = HashEntry(
            file_hash="abc123",
            file_path="/path/to/video.mp4",
            timestamp="2024-01-01T00:00:00",
            output_path="/path/to/output.mp4"
        )

        data = entry.to_dict()

        assert data["file_hash"] == "abc123"
        assert data["file_path"] == "/path/to/video.mp4"
        assert data["timestamp"] == "2024-01-01T00:00:00"
        assert data["output_path"] == "/path/to/output.mp4"

    def test_hash_entry_from_dict(self):
        """Test creating HashEntry from dictionary."""
        data = {
            "file_hash": "abc123",
            "file_path": "/path/to/video.mp4",
            "timestamp": "2024-01-01T00:00:00",
            "output_path": "/path/to/output.mp4"
        }

        entry = HashEntry.from_dict(data)

        assert entry.file_hash == "abc123"
        assert entry.file_path == "/path/to/video.mp4"
        assert entry.timestamp == "2024-01-01T00:00:00"
        assert entry.output_path == "/path/to/output.mp4"

    def test_hash_entry_optional_output(self):
        """Test HashEntry with no output path."""
        entry = HashEntry(
            file_hash="abc123",
            file_path="/path/to/video.mp4",
            timestamp="2024-01-01T00:00:00"
        )

        assert entry.output_path is None


@pytest.mark.unit
class TestSourcePair:
    """Test suite for SourcePair dataclass."""

    def test_source_pair_creation(self):
        """Test creating a SourcePair."""
        pair = SourcePair(
            intro_hash="intro123",
            loop_hash="loop456",
            intro_path="/path/to/intro.mp4",
            loop_path="/path/to/loop.mp4",
            timestamp="2024-01-01T00:00:00",
            output_path="/path/to/output.mp4"
        )

        assert pair.intro_hash == "intro123"
        assert pair.loop_hash == "loop456"
        assert pair.intro_path == "/path/to/intro.mp4"
        assert pair.loop_path == "/path/to/loop.mp4"
        assert pair.timestamp == "2024-01-01T00:00:00"
        assert pair.output_path == "/path/to/output.mp4"

    def test_source_pair_combined_hash(self):
        """Test combined hash generation."""
        pair = SourcePair(
            intro_hash="intro123",
            loop_hash="loop456",
            intro_path="/path/to/intro.mp4",
            loop_path="/path/to/loop.mp4",
            timestamp="2024-01-01T00:00:00"
        )

        combined = pair.combined_hash

        expected_input = "intro123:loop456"
        expected_hash = hashlib.sha256(expected_input.encode()).hexdigest()[:16]

        assert combined == expected_hash
        assert len(combined) == 16

    def test_source_pair_to_dict(self):
        """Test converting SourcePair to dictionary."""
        pair = SourcePair(
            intro_hash="intro123",
            loop_hash="loop456",
            intro_path="/path/to/intro.mp4",
            loop_path="/path/to/loop.mp4",
            timestamp="2024-01-01T00:00:00"
        )

        data = pair.to_dict()

        assert data["intro_hash"] == "intro123"
        assert data["loop_hash"] == "loop456"
        assert data["intro_path"] == "/path/to/intro.mp4"
        assert data["loop_path"] == "/path/to/loop.mp4"

    def test_source_pair_from_dict(self):
        """Test creating SourcePair from dictionary."""
        data = {
            "intro_hash": "intro123",
            "loop_hash": "loop456",
            "intro_path": "/path/to/intro.mp4",
            "loop_path": "/path/to/loop.mp4",
            "timestamp": "2024-01-01T00:00:00",
            "output_path": None
        }

        pair = SourcePair.from_dict(data)

        assert pair.intro_hash == "intro123"
        assert pair.loop_hash == "loop456"


@pytest.mark.unit
class TestHashLedger:
    """Test suite for HashLedger class."""

    def test_hash_ledger_default_location(self, temp_dir, monkeypatch):
        """Test default ledger location resolves to config/ledger.json."""
        monkeypatch.chdir(temp_dir)

        ledger = HashLedger()

        assert ledger.ledger_file == temp_dir / "config" / "ledger.json"

    def test_hash_ledger_init(self, temp_dir):
        """Test HashLedger initialization."""
        ledger_file = temp_dir / "hash_ledger.json"
        ledger = HashLedger(ledger_file=ledger_file)

        assert ledger.ledger_file == ledger_file
        assert ledger.entry_count == 0
        assert ledger.pair_count == 0

    def test_hash_ledger_calculate_hash(self, temp_dir):
        """Test SHA256 hash calculation."""
        test_file = temp_dir / "test.mp4"
        test_file.write_bytes(b"test content for hashing")

        ledger = HashLedger(ledger_file=temp_dir / "ledger.json")
        file_hash = ledger.calculate_hash(test_file)

        expected_hash = hashlib.sha256(b"test content for hashing").hexdigest()

        assert file_hash == expected_hash
        assert len(file_hash) == 64

    def test_hash_ledger_calculate_hash_file_not_found(self, temp_dir):
        """Test hash calculation with missing file."""
        ledger = HashLedger(ledger_file=temp_dir / "ledger.json")

        with pytest.raises(FileNotFoundError):
            ledger.calculate_hash(temp_dir / "nonexistent.mp4")

    def test_hash_ledger_register_single(self, temp_dir):
        """Test registering a single video."""
        test_file = temp_dir / "video.mp4"
        test_file.write_bytes(b"test video content")

        output_file = temp_dir / "output.mp4"

        ledger = HashLedger(ledger_file=temp_dir / "ledger.json")
        result = ledger.register(
            single_path=test_file,
            output_path=output_file
        )

        assert result is True
        assert ledger.entry_count == 1

    def test_hash_ledger_register_pair(self, temp_dir):
        """Test registering an intro/loop pair."""
        intro_file = temp_dir / "intro.mp4"
        loop_file = temp_dir / "loop.mp4"
        intro_file.write_bytes(b"intro content")
        loop_file.write_bytes(b"loop content")

        output_file = temp_dir / "output.mp4"

        ledger = HashLedger(ledger_file=temp_dir / "ledger.json")
        result = ledger.register(
            intro_path=intro_file,
            loop_path=loop_file,
            output_path=output_file
        )

        assert result is True
        assert ledger.pair_count == 1

    def test_hash_ledger_is_registered_single(self, temp_dir):
        """Test checking if single video is registered."""
        test_file = temp_dir / "video.mp4"
        test_file.write_bytes(b"test video content")

        ledger = HashLedger(ledger_file=temp_dir / "ledger.json")

        assert not ledger.is_registered(single_path=test_file)

        ledger.register(single_path=test_file)

        assert ledger.is_registered(single_path=test_file)

    def test_hash_ledger_is_registered_pair(self, temp_dir):
        """Test checking if pair is registered."""
        intro_file = temp_dir / "intro.mp4"
        loop_file = temp_dir / "loop.mp4"
        intro_file.write_bytes(b"intro content")
        loop_file.write_bytes(b"loop content")

        ledger = HashLedger(ledger_file=temp_dir / "ledger.json")

        assert not ledger.is_registered(intro_path=intro_file, loop_path=loop_file)

        ledger.register(intro_path=intro_file, loop_path=loop_file)

        assert ledger.is_registered(intro_path=intro_file, loop_path=loop_file)

    def test_hash_ledger_check_and_register_new(self, temp_dir):
        """Test check_and_register for new content."""
        intro_file = temp_dir / "intro.mp4"
        loop_file = temp_dir / "loop.mp4"
        intro_file.write_bytes(b"intro content")
        loop_file.write_bytes(b"loop content")

        output_file = temp_dir / "output.mp4"

        ledger = HashLedger(ledger_file=temp_dir / "ledger.json")
        result = ledger.check_and_register(
            intro_path=intro_file,
            loop_path=loop_file,
            output_path=output_file
        )

        assert result is True

    def test_hash_ledger_check_and_register_duplicate(self, temp_dir):
        """Test check_and_register for duplicate content."""
        intro_file = temp_dir / "intro.mp4"
        loop_file = temp_dir / "loop.mp4"
        intro_file.write_bytes(b"intro content")
        loop_file.write_bytes(b"loop content")

        output_file = temp_dir / "output.mp4"

        ledger = HashLedger(ledger_file=temp_dir / "ledger.json")
        
        ledger.register(
            intro_path=intro_file,
            loop_path=loop_file,
            output_path=output_file
        )

        result = ledger.check_and_register(
            intro_path=intro_file,
            loop_path=loop_file,
            output_path=output_file
        )

        assert result is False

    def test_hash_ledger_check_and_register_force(self, temp_dir):
        """Test check_and_register with force flag."""
        intro_file = temp_dir / "intro.mp4"
        loop_file = temp_dir / "loop.mp4"
        intro_file.write_bytes(b"intro content")
        loop_file.write_bytes(b"loop content")

        output_file = temp_dir / "output.mp4"

        ledger = HashLedger(ledger_file=temp_dir / "ledger.json")
        
        ledger.register(
            intro_path=intro_file,
            loop_path=loop_file,
            output_path=output_file
        )

        result = ledger.check_and_register(
            intro_path=intro_file,
            loop_path=loop_file,
            output_path=output_file,
            force=True
        )

        assert result is True

    def test_hash_ledger_get_entry(self, temp_dir):
        """Test getting an entry."""
        test_file = temp_dir / "video.mp4"
        test_file.write_bytes(b"test video content")

        ledger = HashLedger(ledger_file=temp_dir / "ledger.json")
        ledger.register(single_path=test_file)

        entry = ledger.get_entry(single_path=test_file)

        assert entry is not None
        assert entry.file_path == str(test_file)

    def test_hash_ledger_get_pair(self, temp_dir):
        """Test getting a pair."""
        intro_file = temp_dir / "intro.mp4"
        loop_file = temp_dir / "loop.mp4"
        intro_file.write_bytes(b"intro content")
        loop_file.write_bytes(b"loop content")

        ledger = HashLedger(ledger_file=temp_dir / "ledger.json")
        ledger.register(intro_path=intro_file, loop_path=loop_file)

        pair = ledger.get_pair(intro_file, loop_file)

        assert pair is not None
        assert pair.intro_path == str(intro_file)
        assert pair.loop_path == str(loop_file)

    def test_hash_ledger_remove_single(self, temp_dir):
        """Test removing a single entry."""
        test_file = temp_dir / "video.mp4"
        test_file.write_bytes(b"test video content")

        ledger = HashLedger(ledger_file=temp_dir / "ledger.json")
        ledger.register(single_path=test_file)

        assert ledger.entry_count == 1

        result = ledger.remove(single_path=test_file)

        assert result is True
        assert ledger.entry_count == 0

    def test_hash_ledger_remove_pair(self, temp_dir):
        """Test removing a pair."""
        intro_file = temp_dir / "intro.mp4"
        loop_file = temp_dir / "loop.mp4"
        intro_file.write_bytes(b"intro content")
        loop_file.write_bytes(b"loop content")

        ledger = HashLedger(ledger_file=temp_dir / "ledger.json")
        ledger.register(intro_path=intro_file, loop_path=loop_file)

        assert ledger.pair_count == 1

        result = ledger.remove(intro_path=intro_file, loop_path=loop_file)

        assert result is True
        assert ledger.pair_count == 0

    def test_hash_ledger_clear(self, temp_dir):
        """Test clearing the ledger."""
        test_file = temp_dir / "video.mp4"
        test_file.write_bytes(b"test video content")

        ledger = HashLedger(ledger_file=temp_dir / "ledger.json")
        ledger.register(single_path=test_file)

        assert ledger.entry_count == 1

        ledger.clear()

        assert ledger.entry_count == 0
        assert ledger.pair_count == 0

    def test_hash_ledger_persistence(self, temp_dir):
        """Test ledger persistence across instances."""
        ledger_file = temp_dir / "ledger.json"
        
        intro_file = temp_dir / "intro.mp4"
        loop_file = temp_dir / "loop.mp4"
        intro_file.write_bytes(b"intro content")
        loop_file.write_bytes(b"loop content")

        ledger1 = HashLedger(ledger_file=ledger_file)
        ledger1.register(intro_path=intro_file, loop_path=loop_file)

        ledger2 = HashLedger(ledger_file=ledger_file)

        assert ledger2.pair_count == 1
        assert ledger2.is_registered(intro_path=intro_file, loop_path=loop_file)


@pytest.mark.unit
class TestShouldRender:
    """Test suite for should_render convenience function."""

    def test_should_render_new_content(self, temp_dir):
        """Test should_render returns True for new content."""
        intro_file = temp_dir / "intro.mp4"
        loop_file = temp_dir / "loop.mp4"
        intro_file.write_bytes(b"intro content")
        loop_file.write_bytes(b"loop content")

        ledger = HashLedger(ledger_file=temp_dir / "ledger.json")

        result = should_render(
            ledger=ledger,
            intro_path=intro_file,
            loop_path=loop_file
        )

        assert result is True

    def test_should_render_duplicate_content(self, temp_dir):
        """Test should_render returns False for duplicate content."""
        intro_file = temp_dir / "intro.mp4"
        loop_file = temp_dir / "loop.mp4"
        intro_file.write_bytes(b"intro content")
        loop_file.write_bytes(b"loop content")

        ledger = HashLedger(ledger_file=temp_dir / "ledger.json")
        ledger.register(intro_path=intro_file, loop_path=loop_file)

        result = should_render(
            ledger=ledger,
            intro_path=intro_file,
            loop_path=loop_file
        )

        assert result is False

    def test_should_render_force(self, temp_dir):
        """Test should_render with force flag."""
        intro_file = temp_dir / "intro.mp4"
        loop_file = temp_dir / "loop.mp4"
        intro_file.write_bytes(b"intro content")
        loop_file.write_bytes(b"loop content")

        ledger = HashLedger(ledger_file=temp_dir / "ledger.json")
        ledger.register(intro_path=intro_file, loop_path=loop_file)

        result = should_render(
            ledger=ledger,
            intro_path=intro_file,
            loop_path=loop_file,
            force=True
        )

        assert result is True


@pytest.mark.unit
class TestHashLedgerThreadSafety:
    """Test suite for HashLedger thread safety."""

    def test_concurrent_registration(self, temp_dir):
        """Test concurrent registration doesn't cause conflicts."""
        import threading

        ledger = HashLedger(ledger_file=temp_dir / "ledger.json")
        results = []
        errors = []

        def register_video(index):
            try:
                video_file = temp_dir / f"video_{index}.mp4"
                video_file.write_bytes(f"content {index}".encode())
                result = ledger.register(single_path=video_file)
                results.append(result)
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=register_video, args=(i,)) for i in range(10)]

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0
        assert len(results) == 10
        assert ledger.entry_count == 10


@pytest.fixture
def temp_dir(tmp_path):
    """Create a temporary directory for tests."""
    return tmp_path

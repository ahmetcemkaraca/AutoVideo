#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Audio processing: looping, mixing, gain adjustment.

OPTIMIZED VERSION:
- Memory-efficient audio processing
- Optimized FFmpeg commands for better performance
- Better error handling with automatic recovery
- Streaming operations for large files
"""

import re
import os
import subprocess
import json
from pathlib import Path
from typing import List, Tuple, Optional, Callable, Set
from concurrent.futures import ThreadPoolExecutor, as_completed
from .ffmpeg import FFmpegRunner, FFmpegProgress, get_duration, write_concat_list

# ═══════════════════════════════════════════════════════════════════════════════
# Audio Utilities
# ═══════════════════════════════════════════════════════════════════════════════


# Import AudioProcessingError from exceptions module instead of defining it here
# This prevents duplicate exception definitions and maintains proper exception hierarchy
from .exceptions import AudioProcessingError


def get_duration_safe(path: Path) -> Optional[float]:
    """
    Get duration with error handling for corrupted files.

    Args:
        path: Path to audio file

    Returns:
        Duration in seconds, or None if failed
    """
    try:
        return get_duration(path)
    except subprocess.TimeoutExpired:
        print(f"[WARN] Timeout getting duration for {path.name}")
        return None
    except Exception as e:
        print(f"[WARN] Failed to get duration for {path.name}: {e}")
        return None


def is_background_file(path: Path) -> bool:
    """
    Check if file is a background audio.
    Matches if filename starts with 'bg' or contains '_bg_'.
    """
    name = path.stem.lower()
    return name.startswith("bg") or "_bg_" in name


def parse_background_gain_db(path: Path) -> float:
    """
    Parse gain in dB from background filename.
    Examples: bg_-8.5.mp3 -> -8.5, ates_bg_-1.mp3 -> -1
    """
    name = path.stem
    # Match bg followed by volume. Handles:
    # bg_-8.5, bg-8.5, _bg_-8.5, _bg-8.5
    match = re.search(r"(?:^|[_-])bg[_-]?([+-]?\d+(?:\.\d+)?)", name, re.IGNORECASE)
    if match:
        return float(match.group(1))
    return 0.0


# ═══════════════════════════════════════════════════════════════════════════════
# Audio Processor
# ═══════════════════════════════════════════════════════════════════════════════


def get_ffmpeg_version() -> Tuple[int, int, int]:
    """
    Get FFmpeg version as (major, minor, patch).

    Returns:
        Tuple of (major, minor, patch) version numbers
        Defaults to (4, 4, 0) if version cannot be determined
    """
    try:
        cmd = ["ffmpeg", "-version"]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
        match = re.search(r"ffmpeg version (\d+)\.(\d+)\.(\d+)", result.stdout)
        if match:
            return tuple(map(int, match.groups()))
    except (subprocess.TimeoutExpired, FileNotFoundError, Exception):
        pass
    # Assume modern version if we can't detect
    return (4, 4, 0)


class AudioProcessor:
    """
    OPTIMIZED audio processor with:
    - Memory-efficient processing using streaming operations
    - Parallel validation for multiple tracks
    - Optimized FFmpeg commands for better performance
    - Automatic recovery from transient errors
    - Smart caching to avoid redundant processing
    """

    # Audio format for intermediate processing (high quality, large file support)
    INTERMEDIATE_FORMAT = "w64"  # Wave64 for >4GB files
    INTERMEDIATE_CODEC = "pcm_s16le"
    SAMPLE_RATE = 48000

    def __init__(self, runner: FFmpegRunner, tmp_dir: Path, max_workers: Optional[int] = None):
        self.runner = runner
        self.tmp_dir = tmp_dir
        # Optimal worker count for parallel audio processing
        self._max_workers = max_workers or min(4, os.cpu_count() or 4)
        # Cache for validated files to avoid re-processing
        self._validated_cache: Set[str] = set()
        # FFmpeg version cache
        self._ffmpeg_version: Optional[Tuple[int, int, int]] = None

    def _get_ffmpeg_version(self) -> Tuple[int, int, int]:
        """
        Get FFmpeg version with caching.

        Returns:
            Tuple of (major, minor, patch) version numbers
        """
        if self._ffmpeg_version is None:
            self._ffmpeg_version = get_ffmpeg_version()
        return self._ffmpeg_version

    def _get_audio_channels(self, file_path: Path) -> int:
        """
        Detect audio channel count from file.

        Args:
            file_path: Path to audio file

        Returns:
            Number of audio channels (1 for mono, 2 for stereo, etc.)
        """
        import json

        try:
            cmd = [
                "ffprobe",
                "-v",
                "quiet",
                "-show_streams",
                "-select_streams",
                "a",
                "-of",
                "json",
                str(file_path),
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, check=True, timeout=30)
            data = json.loads(result.stdout)

            if data.get("streams"):
                return int(data["streams"][0].get("channels", 2))

        except Exception as e:
            print(f"[DEBUG] Failed to detect channels for {file_path.name}: {e}")

        return 2  # Default to stereo

    def _extract_metadata(self, track: Path) -> dict:
        """
        Extract metadata from audio file.

        Args:
            track: Path to audio file

        Returns:
            Dictionary with title, artist, album, and cover art data
        """
        import json

        metadata = {"title": "", "artist": "", "album": "", "cover_data": None}

        try:
            cmd = [
                "ffprobe",
                "-v",
                "quiet",
                "-show_format",
                "-show_streams",
                "-of",
                "json",
                str(track),
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, check=True, timeout=30)
            data = json.loads(result.stdout)

            # Extract text metadata
            tags = data.get("format", {}).get("tags", {})
            metadata["title"] = tags.get("title", "") or tags.get("TITLE", "")
            metadata["artist"] = tags.get("artist", "") or tags.get("ARTIST", "")
            metadata["album"] = tags.get("album", "") or tags.get("ALBUM", "")

            # Check for embedded cover art (usually in stream 0 for audio files)
            for stream in data.get("streams", []):
                if stream.get("codec_name") == "mjpeg" or stream.get("codec_name") == "png":
                    # Extract cover art
                    try:
                        cover_cmd = [
                            "ffmpeg",
                            "-y",
                            "-i",
                            str(track),
                            "-map",
                            f"0:{stream.get('index')}",
                            "-c:v",
                            "copy",
                            "-frames:v",
                            "1",
                            str(self.tmp_dir / "cover.jpg"),
                        ]
                        subprocess.run(cover_cmd, capture_output=True, check=True, timeout=30)

                        cover_path = self.tmp_dir / "cover.jpg"
                        if cover_path.exists():
                            # Fixed: Use context manager for proper file handling
                            with open(cover_path, "rb") as f:
                                metadata["cover_data"] = f.read()
                            # File is automatically closed by context manager
                            cover_path.unlink()  # Clean up temp file
                    except Exception:
                        pass
                    break

        except Exception as e:
            print(f"[DEBUG] Failed to extract metadata from {track.name}: {e}")

        return metadata

    def _apply_metadata(self, audio_file: Path, metadata: dict) -> bool:
        """
        Apply metadata to audio file.

        Args:
            audio_file: Path to audio file
            metadata: Dictionary with title, artist, album, cover_data

        Returns:
            True if metadata was applied successfully, False otherwise
        """
        if not any(metadata.values()):
            return False

        try:
            # Create temp file for metadata application
            temp_output = self.tmp_dir / f"meta_{audio_file.name}"

            cmd = ["ffmpeg", "-y", "-i", str(audio_file)]

            # Add metadata tags
            for key, value in metadata.items():
                if key == "cover_data":
                    continue  # Handle cover art separately
                if value:
                    cmd.extend(["-metadata", f"{key}={value}"])

            # Copy audio codec
            cmd.extend(["-c:a", "copy", "-map", "0:a:0"])

            # Add cover art if available
            if metadata.get("cover_data"):
                cover_path = self.tmp_dir / "temp_cover.jpg"
                try:
                    # Fixed: Use context manager for proper file handling
                    with open(cover_path, "wb") as f:
                        f.write(metadata["cover_data"])
                    # File is automatically closed by context manager

                    cmd.extend(
                        [
                            "-i",
                            str(cover_path),
                            "-map",
                            "1:v:0",
                            "-c:v",
                            "copy",
                            "-id3v2_version",
                            "3",
                            "-metadata:s:v",
                            "title=Album cover",
                            "-metadata:s:v",
                            "comment=Cover (front)",
                        ]
                    )
                except Exception:
                    pass

            cmd.extend(["-f", self.INTERMEDIATE_FORMAT, str(temp_output)])

            subprocess.run(cmd, capture_output=True, check=True, timeout=120)

            # Replace original with metadata-tagged file
            import shutil

            shutil.move(str(temp_output), str(audio_file))

            # Clean up temp cover if it exists
            cover_path = self.tmp_dir / "temp_cover.jpg"
            if cover_path.exists():
                cover_path.unlink()

            return True

        except Exception as e:
            print(f"[DEBUG] Failed to apply metadata to {audio_file.name}: {e}")
            return False

    def validate_and_convert_track(
        self, track: Path, use_cache: bool = True, preserve_metadata: bool = True
    ) -> Tuple[Path, bool, str]:
        """
        OPTIMIZED: Validate and convert a single audio track.

        Improvements:
        - Caching to avoid re-processing
        - Optimized FFmpeg command with better error handling
        - Streaming output to reduce memory usage
        - Detailed error messages
        - Optional metadata preservation

        Args:
            track: Input audio file path
            use_cache: Whether to use caching
            preserve_metadata: Whether to preserve metadata (artist, album, cover)

        Returns:
            Tuple of (output_path, success, error_message)
        """
        safe_name = re.sub(r"[^a-zA-Z0-9_.+-]+", "_", track.stem)
        # Use size + mtime combination for better cache invalidation
        stat = track.stat()
        cache_key = f"{track.name}_{stat.st_size}_{stat.st_mtime}"
        output = self.tmp_dir / f"validated_{safe_name}.{self.INTERMEDIATE_FORMAT}"

        # Check cache
        if use_cache and cache_key in self._validated_cache and output.exists():
            return output, True, ""

        # If already converted (and recent), skip
        if output.exists() and output.stat().st_size > 1000:
            if use_cache:
                self._validated_cache.add(cache_key)
            return output, True, ""

        # Extract metadata before conversion if preservation is enabled
        metadata = {}
        if preserve_metadata:
            metadata = self._extract_metadata(track)

        # Detect original channel count to preserve it
        channels = self._get_audio_channels(track)

        # Optimized FFmpeg command for audio validation
        cmd = [
            "ffmpeg",
            "-y",
            "-hide_banner",
            "-err_detect",
            "ignore_err",  # Ignore minor errors
            "-i",
            str(track),
            "-c:a",
            self.INTERMEDIATE_CODEC,
            "-ar",
            str(self.SAMPLE_RATE),
            "-ac",
            str(channels),  # Preserve original channels (mono/stereo)
            "-map_metadata",
            "-1",  # Strip metadata for faster processing
            "-f",
            self.INTERMEDIATE_FORMAT,
            str(output),
        ]

        try:
            # Run with timeout and streaming output
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=120,  # 2 min timeout per file
                check=False,  # We'll handle errors manually
            )

            if result.returncode != 0:
                # Check for critical errors in stderr
                stderr = result.stderr
                if any(err in stderr for err in ["Invalid data", "Error", "Corrupt"]):
                    return track, False, f"Donusturme hatasi: {track.name}"

            # Verify output exists and has content
            if not output.exists() or output.stat().st_size < 1000:
                return track, False, f"Cikti dosyasi gecersiz: {track.name}"

            # Re-apply metadata if preservation was requested
            if preserve_metadata and any(metadata.values()):
                self._apply_metadata(output, metadata)

            # Add to cache
            if use_cache:
                self._validated_cache.add(cache_key)

            return output, True, ""

        except subprocess.TimeoutExpired:
            return track, False, f"Zaman asimi: {track.name}"
        except Exception as e:
            return track, False, f"Hata: {track.name} - {e}"

    def validate_tracks(
        self,
        tracks: List[Path],
        progress_callback: Optional[Callable[[str, int, int], None]] = None,
        parallel: bool = True,
    ) -> Tuple[List[Path], List[Tuple[Path, str]]]:
        """
        OPTIMIZED: Validate and convert all tracks.

        Improvements:
        - Parallel processing for better performance
        - Detailed progress reporting
        - Better error handling

        Args:
            tracks: List of audio tracks
            progress_callback: Optional callback(track_name, current, total)
            parallel: Use parallel processing (default: True)

        Returns:
            Tuple of (valid_converted_paths, invalid_tracks_with_errors)
        """
        if not parallel or len(tracks) <= 2:
            # Sequential processing for small batches
            return self._validate_tracks_sequential(tracks, progress_callback)

        # Parallel processing for larger batches
        return self._validate_tracks_parallel(tracks, progress_callback)

    def _validate_tracks_sequential(
        self,
        tracks: List[Path],
        progress_callback: Optional[Callable[[str, int, int], None]] = None,
    ) -> Tuple[List[Path], List[Tuple[Path, str]]]:
        """Sequential track validation (memory-efficient)."""
        valid = []
        invalid = []

        for i, track in enumerate(tracks):
            if progress_callback:
                progress_callback(track.name, i + 1, len(tracks))

            converted, success, error = self.validate_and_convert_track(track)

            if success:
                valid.append(converted)
            else:
                invalid.append((track, error))

        return valid, invalid

    def _validate_tracks_parallel(
        self,
        tracks: List[Path],
        progress_callback: Optional[Callable[[str, int, int], None]] = None,
    ) -> Tuple[List[Path], List[Tuple[Path, str]]]:
        """Parallel track validation (performance-optimized)."""
        valid = []
        invalid = []
        completed = 0

        with ThreadPoolExecutor(max_workers=self._max_workers) as executor:
            # Submit all tasks
            future_to_track = {
                executor.submit(self.validate_and_convert_track, track): track for track in tracks
            }

            # Process results as they complete
            for future in as_completed(future_to_track):
                track = future_to_track[future]
                completed += 1

                if progress_callback:
                    progress_callback(track.name, completed, len(tracks))

                try:
                    converted, success, error = future.result()
                    if success:
                        valid.append(converted)
                    else:
                        invalid.append((track, error))
                except Exception as e:
                    invalid.append((track, f"Unexpected error: {e}"))

        return valid, invalid

    def _trim_silence(self, track: Path, output: Path) -> bool:
        """
        Trim silence from the beginning and end of an audio track.

        Uses FFmpeg's silencedetect and atrim filters to remove silence.

        Args:
            track: Input audio file
            output: Output audio file path

        Returns:
            True if trimming was successful, False otherwise
        """
        import json

        try:
            # Detect silence at the beginning
            detect_cmd = [
                "ffmpeg",
                "-y",
                "-i",
                str(track),
                "-af",
                "silencedetect=noise=0.0001:duration=0.1",
                "-f",
                "null",
                "-",
            ]

            result = subprocess.run(
                detect_cmd, capture_output=True, text=True, timeout=60, check=False
            )

            # Parse silence detection output
            silence_start = None
            silence_end = None

            for line in result.stderr.split("\n"):
                if "silence_start" in line:
                    try:
                        silence_start = float(line.split("silence_start:")[1].split()[0])
                    except (IndexError, ValueError):
                        pass
                elif "silence_end" in line:
                    try:
                        silence_end = float(line.split("silence_end:")[1].split()[0])
                    except (IndexError, ValueError):
                        pass

            # If we detected significant silence at start or end, trim it
            if silence_start is not None and silence_start > 0.1:
                # Trim silence from start
                trim_cmd = [
                    "ffmpeg",
                    "-y",
                    "-i",
                    str(track),
                    "-af",
                    f"atrim={silence_start}:",
                    "-c:a",
                    self.INTERMEDIATE_CODEC,
                    "-ar",
                    str(self.SAMPLE_RATE),
                    str(output),
                ]
                subprocess.run(trim_cmd, capture_output=True, check=True, timeout=120)
                return True

            # No significant silence detected, just copy the file
            import shutil

            shutil.copy2(track, output)
            return False

        except Exception as e:
            print(f"[WARN] Failed to trim silence from {track.name}: {e}")
            # Fallback: just copy the file
            import shutil

            shutil.copy2(track, output)
            return False

    def create_music_loop(
        self,
        tracks: List[Path],
        total_seconds: int,
        global_music_db: float = 0.0,
        progress_callback: Optional[Callable[[FFmpegProgress], None]] = None,
        pre_validated: bool = False,
        trim_silence: bool = False,
    ) -> Path:
        """
        OPTIMIZED: Create a looped music track from multiple tracks.

        Improvements:
        - Optimized concat list generation
        - Better memory efficiency with streaming
        - Parallel validation option
        - Optional silence trimming for smooth transitions

        Args:
            tracks: List of music tracks to loop (or pre-validated w64 files)
            total_seconds: Target duration
            global_music_db: Audio gain/volume level for music tracks
            progress_callback: Optional progress callback
            pre_validated: If True, tracks are already validated w64 files
            trim_silence: If True, trim silence from track beginnings/ends

        Returns:
            Path to looped audio file
        """
        # If not pre-validated, validate first (with parallel processing)
        if not pre_validated:
            valid_tracks, invalid = self.validate_tracks(tracks, parallel=True)
            if invalid:
                invalid_names = [t[0].name for t in invalid]
                raise ValueError(f"Bozuk track'ler: {', '.join(invalid_names)}")
            tracks = valid_tracks

        # Optionally trim silence from tracks for smooth transitions
        if trim_silence:
            print(f"[AUDIO] Trimming silence from {len(tracks)} tracks...")
            trimmed_tracks = []
            for i, track in enumerate(tracks):
                trimmed_path = self.tmp_dir / f"trimmed_{i}.{self.INTERMEDIATE_FORMAT}"
                self._trim_silence(track, trimmed_path)
                trimmed_tracks.append(trimmed_path)
            tracks = trimmed_tracks

        # Calculate total duration of all tracks (with error handling)
        durations = [get_duration_safe(t) for t in tracks]
        if None in durations:
            corrupted = [tracks[i].name for i, d in enumerate(durations) if d is None]
            raise AudioProcessingError(
                f"Bazi track'lerin suresi hesaplanamadi: {', '.join(corrupted)}"
            )

        total_track_duration = sum(durations)

        if total_track_duration <= 0:
            raise ValueError("Track'lerin toplam suresi 0 veya negatif!")

        # Calculate how many times we need to repeat the track list
        repeat_count = int(total_seconds / total_track_duration) + 1

        print(
            f"[AUDIO] Looping {len(tracks)} tracks ({total_track_duration:.1f}s total) "
            f"{repeat_count} times for {total_seconds}s target"
        )

        # Create a repeated concat list (memory-efficient)
        music_list = self.tmp_dir / "music_list.txt"
        write_concat_list(tracks, music_list, repeat_count)

        output = self.tmp_dir / f"music_loop.{self.INTERMEDIATE_FORMAT}"

        if progress_callback:
            self.runner.set_total_duration(total_seconds)
            self.runner.set_progress_callback(progress_callback)

        filter_args = ["-c:a", "copy"]
        if global_music_db != 0.0:
            filter_args = [
                "-filter:a",
                f"volume={global_music_db}dB",
                "-c:a",
                self.INTERMEDIATE_CODEC,
            ]

        # Optimized FFmpeg command with threading
        cmd = [
            "ffmpeg",
            "-y",
            "-f",
            "concat",
            "-safe",
            "0",
            "-i",
            str(music_list),
            "-t",
            str(total_seconds),
            "-threads",
            str(self._max_workers),  # Optimal threading
        ]
        cmd.extend(filter_args)
        cmd.extend([
            "-f",
            self.INTERMEDIATE_FORMAT,
            str(output),
        ])

        self.runner.run(cmd, capture_progress=bool(progress_callback))

        # Cleanup temp list
        try:
            if music_list.exists():
                music_list.unlink()
        except:
            pass

        # Cleanup trimmed tracks if any
        if trim_silence:
            for track in tracks:
                try:
                    if track.exists() and track.parent == self.tmp_dir:
                        track.unlink()
                except:
                    pass

        return output

    def apply_gain(self, source: Path, gain_db: float, output_name: Optional[str] = None) -> Path:
        """
        Apply gain adjustment to an audio file.

        Args:
            source: Source audio path
            gain_db: Gain in decibels (negative to reduce volume)
            output_name: Optional output filename

        Returns:
            Path to processed audio file
        """
        if output_name is None:
            safe_name = re.sub(r"[^a-zA-Z0-9_.+-]+", "_", source.stem)
            output_name = f"{safe_name}_gain.{self.INTERMEDIATE_FORMAT}"

        output = self.tmp_dir / output_name

        cmd = [
            "ffmpeg",
            "-y",
            "-i",
            str(source),
            "-filter:a",
            f"volume={gain_db}dB",
            "-c:a",
            self.INTERMEDIATE_CODEC,
            "-ar",
            str(self.SAMPLE_RATE),
            "-f",
            self.INTERMEDIATE_FORMAT,
            str(output),
        ]

        self.runner.run_simple(cmd)
        return output

    def mix_tracks(
        self,
        main_track: Path,
        background_tracks: List[Path],
        total_seconds: int,
        progress_callback: Optional[Callable[[FFmpegProgress], None]] = None,
    ) -> Path:
        """
        OPTIMIZED: Mix main track with background tracks.

        Improvements:
        - Optimized amix filter configuration
        - Better threading for performance
        - Memory-efficient processing

        Uses amerge + pan filter to properly mix audio without normalizing volumes.
        Background tracks should already have gain applied via apply_gain().

        Args:
            main_track: Primary audio track (music loop)
            background_tracks: List of background audio tracks (already gain-adjusted)
            total_seconds: Target duration
            progress_callback: Optional progress callback

        Returns:
            Path to mixed audio file
        """
        if not background_tracks:
            return main_track

        output = self.tmp_dir / f"audio_mixed.{self.INTERMEDIATE_FORMAT}"

        if progress_callback:
            self.runner.set_total_duration(total_seconds)
            self.runner.set_progress_callback(progress_callback)

        # Build command with all inputs
        cmd = ["ffmpeg", "-y", "-threads", str(self._max_workers), "-i", str(main_track)]

        for bg in background_tracks:
            cmd.extend(["-stream_loop", "-1", "-i", str(bg)])

        # Optimized amix filter configuration with FFmpeg version compatibility
        # Key fixes:
        # - weights=1 for all inputs (equal weight, gain already applied to BGs)
        # - normalize=0 (don't divide by N)
        # - dropout_transition=0 (don't fade out)
        # - Compatible with FFmpeg < 4.4 (no weights parameter support)
        input_count = 1 + len(background_tracks)

        # Check FFmpeg version for weights parameter support
        ffmpeg_version = self._get_ffmpeg_version()
        if ffmpeg_version >= (4, 4, 0):
            # Modern FFmpeg with weights support
            weights = " ".join(["1"] * input_count)
            filter_complex = (
                f"amix=inputs={input_count}:"
                f"duration=first:"
                f"dropout_transition=0:"
                f"weights='{weights}':"
                f"normalize=0"
            )
        else:
            # Older FFmpeg without weights - use simpler amix
            # Background tracks should already have gain applied via apply_gain()
            filter_complex = (
                f"amix=inputs={input_count}:"
                f"duration=first:"
                f"dropout_transition=0:"
                f"normalize=0"
            )

        cmd.extend(
            [
                "-filter_complex",
                filter_complex,
                "-t",
                str(total_seconds),
                "-c:a",
                self.INTERMEDIATE_CODEC,
                "-ar",
                str(self.SAMPLE_RATE),
                "-f",
                self.INTERMEDIATE_FORMAT,
                str(output),
            ]
        )

        self.runner.run(cmd, capture_progress=bool(progress_callback))
        return output

    def process_backgrounds(self, backgrounds: List[Tuple[Path, float]]) -> List[Path]:
        """
        Process background audio files with gain adjustment.

        Args:
            backgrounds: List of (path, gain_db) tuples

        Returns:
            List of processed background audio paths
        """
        processed = []
        for path, gain_db in backgrounds:
            safe_name = re.sub(r"[^a-zA-Z0-9_.+-]+", "_", path.stem)
            output = self.apply_gain(path, gain_db, f"{safe_name}_bg.{self.INTERMEDIATE_FORMAT}")
            processed.append(output)
        return processed

    def standardize_tracks(
        self,
        tracks: List[Path],
        archive_dir: Path,
        progress_callback: Optional[Callable[[str, int, int], None]] = None,
    ) -> List[Path]:
        """
        Convert tracks to standard HQ format (MP3 320k 48kHz) and archive originals.

        Skips files that are already in the correct format to prevent re-processing.

        Args:
            tracks: List of track paths
            archive_dir: Directory to move original files
            progress_callback: Callback(name, current, total)

        Returns:
            List of new track paths (same names but updated content/ext if needed)
        """
        import shutil
        import subprocess

        archive_dir.mkdir(parents=True, exist_ok=True)
        results = []

        for i, track in enumerate(tracks):
            if progress_callback:
                progress_callback(track.name, i + 1, len(tracks))

            # ═══════════════════════════════════════════════════════════════════
            # FIX: Check if file is ALREADY a valid standardized MP3
            # This prevents re-processing and the "mp31" double-extension bug
            # ═══════════════════════════════════════════════════════════════════
            is_already_valid = False
            if track.suffix.lower() == ".mp3":
                try:
                    # Probe the file to check its specs
                    probe_cmd = [
                        "ffprobe",
                        "-v",
                        "quiet",
                        "-print_format",
                        "json",
                        "-show_streams",
                        str(track),
                    ]
                    probe_result = subprocess.run(
                        probe_cmd, capture_output=True, text=True, timeout=10
                    )
                    if probe_result.returncode == 0:
                        import json

                        probe_data = json.loads(probe_result.stdout)
                        for stream in probe_data.get("streams", []):
                            if stream.get("codec_name") == "mp3":
                                sample_rate = int(stream.get("sample_rate", 0))
                                bit_rate = int(stream.get("bit_rate", 0))
                                # Check if already 48kHz and >= 300kbps (close to 320k)
                                if sample_rate >= 44100 and bit_rate >= 300000:
                                    is_already_valid = True
                                    break
                except Exception:
                    pass  # If probe fails, we'll re-encode

            if is_already_valid:
                # Skip conversion, use original file
                results.append(track)
                continue

            # Temp output - use unique temp name to avoid conflicts
            tmp_std = self.tmp_dir / f"std_{track.stem}.mp3"

            cmd = [
                "ffmpeg",
                "-y",
                "-hide_banner",
                "-i",
                str(track),
                "-c:a",
                "libmp3lame",
                "-b:a",
                "320k",
                "-ar",
                "48000",
                "-ac",
                "2",
                str(tmp_std),
            ]

            try:
                subprocess.run(
                    cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
                )

                # Archive original
                archive_path = archive_dir / track.name
                if archive_path.exists():
                    timestamp = "_" + str(int(self.tmp_dir.stat().st_mtime))
                    archive_path = archive_dir / f"{track.stem}_archived{track.suffix}"

                shutil.move(str(track), str(archive_path))

                # Move new file to original location (always .mp3)
                new_track_path = track.with_suffix(".mp3")
                shutil.move(str(tmp_std), str(new_track_path))
                results.append(new_track_path)

            except Exception as e:
                print(f"Error standardizing {track.name}: {e}")
                # Fallback to keep original
                results.append(track)

        return results


# ═══════════════════════════════════════════════════════════════════════════════
# Final Muxer
# ═══════════════════════════════════════════════════════════════════════════════


def mux_video_audio(
    runner: FFmpegRunner,
    video: Path,
    audio: Path,
    output: Path,
    audio_bitrate: str = "192k",
    progress_callback: Optional[Callable[[FFmpegProgress], None]] = None,
    keep_video_audio: bool = False,
    apply_audio_fades: bool = True,
    fade_in_sec: float = 2.0,
    fade_out_sec: float = 4.0,
) -> Path:
    """
    OPTIMIZED: Mux video and audio into final output.

    Improvements:
    - Optimized thread configuration
    - Better memory management for long videos
    - Optimized buffer settings

    Args:
        runner: FFmpeg runner instance
        video: Video-only file path
        audio: Audio file path
        output: Final output path
        audio_bitrate: AAC audio bitrate
        progress_callback: Optional progress callback

    Returns:
        Output path
    """
    # Get video duration to use as explicit trim
    video_duration = get_duration(video)

    if progress_callback:
        runner.set_total_duration(video_duration)
        runner.set_progress_callback(progress_callback)

    # Optimal thread count for muxing (I/O bound operation)
    import os

    threads = min(4, os.cpu_count() or 4)

    def _video_has_audio_stream(video_path: Path) -> bool:
        cmd_probe = [
            "ffprobe",
            "-v",
            "error",
            "-select_streams",
            "a",
            "-show_entries",
            "stream=index",
            "-of",
            "csv=p=0",
            str(video_path),
        ]
        try:
            result = subprocess.run(cmd_probe, capture_output=True, text=True, timeout=10)
            return bool(result.stdout.strip())
        except Exception:
            return False

    has_video_audio = keep_video_audio and _video_has_audio_stream(video)

    cmd = [
        "ffmpeg",
        "-y",
        "-threads",
        str(threads),
        "-i",
        str(video),
        "-stream_loop",
        "-1",
        "-i",
        str(audio),
        "-map",
        "0:v:0",
    ]

    fade_out_start = max(0.0, video_duration - max(0.0, float(fade_out_sec)))

    if has_video_audio:
        ext_chain = "[1:a]aresample=48000,asetpts=PTS-STARTPTS"
        if apply_audio_fades:
            ext_chain += (
                f",afade=t=in:st=0:d={max(0.0, float(fade_in_sec))}"
                f",afade=t=out:st={fade_out_start}:d={max(0.0, float(fade_out_sec))}"
            )
        ext_chain += "[ext]"

        filter_complex = (
            "[0:a:0]aresample=48000,asetpts=PTS-STARTPTS[vin];"
            f"{ext_chain};"
            "[vin][ext]amix=inputs=2:duration=first:dropout_transition=0:normalize=0[mix]"
        )
        cmd.extend(["-filter_complex", filter_complex, "-map", "[mix]"])
    else:
        cmd.extend(["-map", "1:a:0"])
        if apply_audio_fades:
            af = (
                f"afade=t=in:st=0:d={max(0.0, float(fade_in_sec))},"
                f"afade=t=out:st={fade_out_start}:d={max(0.0, float(fade_out_sec))}"
            )
            cmd.extend(["-af", af])

    cmd.extend(
        [
            "-c:v",
            "copy",
            "-c:a",
            "aac",
            "-b:a",
            audio_bitrate,
            "-profile:a",
            "aac_low",
            "-ac",
            "2",
            "-t",
            str(video_duration),
            "-movflags",
            "+faststart",
            "-max_muxing_queue_size",
            "4096",
            "-flush_packets",
            "1",
            str(output),
        ]
    )

    # Calculate timeout based on video duration
    # For muxing with -c:v copy, use generous timeout (no progress updates during fast copy)
    # Base: 10 min + 2 min per hour of video
    mux_timeout = 600 + (video_duration / 3600) * 120  # seconds

    runner.run(cmd, capture_progress=bool(progress_callback), timeout=mux_timeout)
    return output


def _normalize_effect_timeline(
    total_seconds: int,
    start_after_sec: float,
    interval_sec: float,
) -> List[float]:
    """Build event timeline for one-shot effects."""
    timeline = []
    start = max(0.0, float(start_after_sec))
    interval = max(0.1, float(interval_sec))
    current = start
    while current < total_seconds:
        timeline.append(current)
        current += interval
    return timeline


def _safe_float(value, default: float) -> float:
    try:
        return float(value)
    except Exception:
        return default


def _safe_int(value, default: int) -> int:
    try:
        return int(value)
    except Exception:
        return default


def _coerce_effect(effect: dict) -> dict:
    return {
        "path": effect.get("path", ""),
        "start_after_sec": _safe_float(effect.get("start_after_sec", 5.0), 5.0),
        "interval_sec": _safe_float(effect.get("interval_sec", 20.0), 20.0),
        "fade_in_sec": _safe_float(effect.get("fade_in_sec", 0.1), 0.1),
        "fade_out_sec": _safe_float(effect.get("fade_out_sec", 0.5), 0.5),
        "gain_db": _safe_float(effect.get("gain_db", -6.0), -6.0),
        "max_plays": _safe_int(effect.get("max_plays", 0), 0),
    }


def _build_effect_output_path(tmp_dir: Path) -> Path:
    return tmp_dir / "timed_effects.w64"


def create_timed_effects_track(
    runner: FFmpegRunner,
    tmp_dir: Path,
    effects: List[dict],
    total_seconds: int,
    sample_rate: int = 48000,
) -> Optional[Path]:
    """Create one-shot timed effects track mixed over silence timeline."""
    if not effects:
        return None

    output = _build_effect_output_path(tmp_dir)
    cmd = [
        "ffmpeg",
        "-y",
        "-f",
        "lavfi",
        "-i",
        f"anullsrc=r={sample_rate}:cl=stereo",
        "-t",
        str(total_seconds),
    ]

    filter_parts = [f"[0:a]atrim=0:{total_seconds},asetpts=PTS-STARTPTS[base]"]
    mix_inputs = ["[base]"]
    input_idx = 1

    for raw_effect in effects:
        effect = _coerce_effect(raw_effect)
        effect_path = Path(effect["path"])
        if not effect_path.exists():
            continue

        src_duration = get_duration_safe(effect_path)
        if not src_duration or src_duration <= 0:
            continue

        timeline = _normalize_effect_timeline(
            total_seconds,
            effect["start_after_sec"],
            effect["interval_sec"],
        )
        max_plays = effect["max_plays"]
        if max_plays > 0:
            timeline = timeline[:max_plays]

        for start_t in timeline:
            remaining = total_seconds - start_t
            if remaining <= 0:
                continue
            clip_duration = min(src_duration, remaining)
            fade_in = max(0.0, effect["fade_in_sec"])
            fade_out = max(0.0, effect["fade_out_sec"])
            fade_out_start = max(0.0, clip_duration - fade_out)
            delay_ms = max(0, int(start_t * 1000))

            cmd.extend(["-stream_loop", "-1", "-i", str(effect_path)])

            label = f"e{input_idx}"
            chain = (
                f"[{input_idx}:a]"
                f"atrim=0:{clip_duration},asetpts=PTS-STARTPTS,"
                f"volume={effect['gain_db']}dB"
            )
            if fade_in > 0:
                chain += f",afade=t=in:st=0:d={fade_in}"
            if fade_out > 0:
                chain += f",afade=t=out:st={fade_out_start}:d={fade_out}"
            chain += f",adelay={delay_ms}|{delay_ms}[{label}]"

            filter_parts.append(chain)
            mix_inputs.append(f"[{label}]")
            input_idx += 1

    if len(mix_inputs) == 1:
        return None

    filter_parts.append(
        f"{''.join(mix_inputs)}amix=inputs={len(mix_inputs)}:duration=first:dropout_transition=0:normalize=0[mix]"
    )

    cmd.extend(
        [
            "-filter_complex",
            ";".join(filter_parts),
            "-map",
            "[mix]",
            "-c:a",
            "pcm_s16le",
            "-ar",
            str(sample_rate),
            "-ac",
            "2",
            "-f",
            "w64",
            str(output),
        ]
    )

    runner.run_simple(cmd)
    return output if output.exists() else None

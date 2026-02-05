#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Audio processing: looping, mixing, gain adjustment.
"""

import re
from pathlib import Path
from typing import List, Tuple, Optional, Callable

from .ffmpeg import FFmpegRunner, FFmpegProgress, get_duration, write_concat_list


# ═══════════════════════════════════════════════════════════════════════════════
# Audio Utilities
# ═══════════════════════════════════════════════════════════════════════════════

def is_background_file(path: Path) -> bool:
    """Check if file is a background audio (starts with 'bg')."""
    return path.stem.lower().startswith("bg")


def parse_background_gain_db(path: Path) -> float:
    """
    Parse gain in dB from background filename.
    Examples: bg_-8.5.mp3 -> -8.5, bg_+2.wav -> +2, bg-1.flac -> -1
    """
    name = path.stem
    match = re.search(r"bg[_-]([+-]?\d+(?:\.\d+)?)", name, re.IGNORECASE)
    if match:
        return float(match.group(1))
    return 0.0


# ═══════════════════════════════════════════════════════════════════════════════
# Audio Processor
# ═══════════════════════════════════════════════════════════════════════════════

class AudioProcessor:
    """
    Handles audio processing operations.
    """
    
    # Audio format for intermediate processing (high quality, large file support)
    INTERMEDIATE_FORMAT = "w64"  # Wave64 for >4GB files
    INTERMEDIATE_CODEC = "pcm_s16le"
    SAMPLE_RATE = 48000
    
    def __init__(self, runner: FFmpegRunner, tmp_dir: Path):
        self.runner = runner
        self.tmp_dir = tmp_dir
    
    def validate_and_convert_track(self, track: Path) -> tuple[Path, bool, str]:
        """
        Validate and convert a single audio track to intermediate format.
        
        Returns:
            Tuple of (output_path, success, error_message)
        """
        import subprocess
        import re
        
        safe_name = re.sub(r"[^a-zA-Z0-9_.+-]+", "_", track.stem)
        output = self.tmp_dir / f"validated_{safe_name}.{self.INTERMEDIATE_FORMAT}"
        
        # If already converted, skip
        if output.exists():
            return output, True, ""
        
        cmd = [
            "ffmpeg", "-y", "-hide_banner",
            "-err_detect", "ignore_err",  # Ignore minor errors
            "-i", str(track),
            "-c:a", self.INTERMEDIATE_CODEC,
            "-ar", str(self.SAMPLE_RATE),
            "-ac", "2",  # Stereo
            "-f", self.INTERMEDIATE_FORMAT,
            str(output)
        ]
        
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=120  # 2 min timeout per file
            )
            
            if result.returncode != 0:
                # Check for critical errors in stderr
                stderr = result.stderr
                if "Invalid data" in stderr or "Error" in stderr:
                    return track, False, f"Donusturme hatasi: {track.name}"
            
            # Verify output exists and has content
            if not output.exists() or output.stat().st_size < 1000:
                return track, False, f"Cikti dosyasi gecersiz: {track.name}"
            
            return output, True, ""
            
        except subprocess.TimeoutExpired:
            return track, False, f"Zaman asimi: {track.name}"
        except Exception as e:
            return track, False, f"Hata: {track.name} - {e}"
    
    def validate_tracks(
        self,
        tracks: List[Path],
        progress_callback: Optional[Callable[[str, int, int], None]] = None
    ) -> tuple[List[Path], List[tuple[Path, str]]]:
        """
        Validate and convert all tracks to intermediate format.
        
        Args:
            tracks: List of audio tracks
            progress_callback: Optional callback(track_name, current, total)
            
        Returns:
            Tuple of (valid_converted_paths, invalid_tracks_with_errors)
        """
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
    
    def create_music_loop(
        self,
        tracks: List[Path],
        total_seconds: int,
        progress_callback: Optional[Callable[[FFmpegProgress], None]] = None,
        pre_validated: bool = False
    ) -> Path:
        """
        Create a looped music track from multiple tracks.
        
        Args:
            tracks: List of music tracks to loop (or pre-validated w64 files)
            total_seconds: Target duration
            progress_callback: Optional progress callback
            pre_validated: If True, tracks are already validated w64 files
            
        Returns:
            Path to looped audio file
        """
        # If not pre-validated, validate first
        if not pre_validated:
            valid_tracks, invalid = self.validate_tracks(tracks)
            if invalid:
                invalid_names = [t[0].name for t in invalid]
                raise ValueError(f"Bozuk track'ler: {', '.join(invalid_names)}")
            tracks = valid_tracks
        
        # Calculate total duration of all tracks
        total_track_duration = sum(get_duration(t) for t in tracks)
        
        if total_track_duration <= 0:
            raise ValueError("Track'lerin toplam suresi 0 veya negatif!")
        
        # Calculate how many times we need to repeat the track list
        # Add 1 to ensure we have enough audio to cover the target duration
        repeat_count = int(total_seconds / total_track_duration) + 1
        
        # Create a repeated concat list (instead of using buggy -stream_loop)
        music_list = self.tmp_dir / "music_list.txt"
        repeated_tracks = tracks * repeat_count
        write_concat_list(repeated_tracks, music_list)
        
        output = self.tmp_dir / f"music_loop.{self.INTERMEDIATE_FORMAT}"
        
        if progress_callback:
            self.runner.set_total_duration(total_seconds)
            self.runner.set_progress_callback(progress_callback)
        
        # No stream_loop needed - we've already repeated the list
        cmd = [
            "ffmpeg", "-y",
            "-f", "concat", "-safe", "0",
            "-i", str(music_list),
            "-t", str(total_seconds),
            "-c:a", "copy",  # Copy since already in correct format
            "-f", self.INTERMEDIATE_FORMAT,
            str(output)
        ]
        
        self.runner.run(cmd, capture_progress=bool(progress_callback))
        return output
    
    def apply_gain(
        self,
        source: Path,
        gain_db: float,
        output_name: Optional[str] = None
    ) -> Path:
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
            "ffmpeg", "-y",
            "-i", str(source),
            "-filter:a", f"volume={gain_db}dB",
            "-c:a", self.INTERMEDIATE_CODEC,
            "-ar", str(self.SAMPLE_RATE),
            "-f", self.INTERMEDIATE_FORMAT,
            str(output)
        ]
        
        self.runner.run_simple(cmd)
        return output
    
    def mix_tracks(
        self,
        main_track: Path,
        background_tracks: List[Path],
        total_seconds: int,
        progress_callback: Optional[Callable[[FFmpegProgress], None]] = None
    ) -> Path:
        """
        Mix main track with background tracks.
        
        Args:
            main_track: Primary audio track
            background_tracks: List of background audio tracks
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
        cmd = ["ffmpeg", "-y", "-i", str(main_track)]
        
        for bg in background_tracks:
            cmd.extend(["-stream_loop", "-1", "-i", str(bg)])
        
        # Mix all inputs
        input_count = 1 + len(background_tracks)
        filter_complex = f"amix=inputs={input_count}:duration=shortest:normalize=0"
        
        cmd.extend([
            "-filter_complex", filter_complex,
            "-t", str(total_seconds),
            "-c:a", self.INTERMEDIATE_CODEC,
            "-ar", str(self.SAMPLE_RATE),
            "-f", self.INTERMEDIATE_FORMAT,
            str(output)
        ])
        
        self.runner.run(cmd, capture_progress=bool(progress_callback))
        return output
    
    def process_backgrounds(
        self,
        backgrounds: List[Tuple[Path, float]]
    ) -> List[Path]:
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
            output = self.apply_gain(
                path,
                gain_db,
                f"{safe_name}_bg.{self.INTERMEDIATE_FORMAT}"
            )
            processed.append(output)
        return processed

    def standardize_tracks(
        self,
        tracks: List[Path],
        archive_dir: Path,
        progress_callback: Optional[Callable[[str, int, int], None]] = None
    ) -> List[Path]:
        """
        Convert tracks to standard HQ format (MP3 320k 48kHz) and archive originals.
        
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
            
            # Check if likely already standard (mp3, >10MB check rough, but better to force re-encode to ensure specs)
            # We will force re-encode to 320k MP3 48kHz Stereo for uniformity
            
            # Temp input
            tmp_std = self.tmp_dir / f"std_{track.stem}.mp3"
            
            cmd = [
                "ffmpeg", "-y", "-hide_banner",
                "-i", str(track),
                "-c:a", "libmp3lame",
                "-b:a", "320k",
                "-ar", "48000",
                "-ac", "2",
                str(tmp_std)
            ]
            
            try:
                subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                
                # Archive original
                # If original is in music dir, move it. If it's elsewhere, copy/delete?
                # Assumption: tracks are in music/ directory
                
                # Construct archive path
                # Handle name collisions in archive
                archive_path = archive_dir / track.name
                if archive_path.exists():
                     timestamp = "_" + str(int(self.tmp_dir.stat().st_mtime)) # simple hack or just random
                     archive_path = archive_dir / f"{track.stem}_archived{track.suffix}"
                
                shutil.move(str(track), str(archive_path))
                
                # Move new file to original location
                # Ensure extension is .mp3
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
    progress_callback: Optional[Callable[[FFmpegProgress], None]] = None
) -> Path:
    """
    Mux video and audio into final output.
    
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
    if progress_callback:
        duration = get_duration(video)
        runner.set_total_duration(duration)
        runner.set_progress_callback(progress_callback)
    
    cmd = [
        "ffmpeg", "-y",
        "-threads", "0",  # Auto-detect optimal thread count
        "-i", str(video),
        "-i", str(audio),
        "-c:v", "copy",
        "-c:a", "aac",
        "-b:a", audio_bitrate,
        "-profile:a", "aac_low",  # AAC-LC for compatibility
        "-ac", "2",  # Stereo
        "-shortest",
        "-movflags", "+faststart",
        "-max_muxing_queue_size", "4096",  # Large queue for 48hr+ videos
        str(output)
    ]
    
    runner.run(cmd, capture_progress=bool(progress_callback))
    return output

# AudioProcessor Module

The AudioProcessor module (`video_renderer/audio.py`) handles audio processing, validation, looping, and mixing operations.

## Overview

AudioProcessor is responsible for:
- Audio track validation and conversion
- Background audio detection and processing
- Audio looping to target duration
- Gain application from filename patterns
- Track mixing and standardization
- Metadata extraction and preservation

## Class Reference

### AudioProcessor

```python
class AudioProcessor:
    """Handles audio processing and manipulation operations."""

    def __init__(
        self,
        runner: FFmpegRunner,
        tmp_dir: Path
    ):
        """
        Initialize AudioProcessor.

        Args:
            runner: FFmpegRunner instance for executing FFmpeg commands
            tmp_dir: Temporary directory for intermediate files
        """
```

## Key Methods

### validate_and_convert_track

```python
def validate_and_convert_track(
    self,
    track: Path,
    use_cache: bool = True
) -> Path:
    """
    Validate and convert audio track to standard format.

    Args:
        track: Path to audio file
        use_cache: Use validation cache for performance

    Returns:
        Path to validated/converted audio file

    Raises:
        AudioProcessingError: If validation or conversion fails
    """
```

Supported formats: MP3, WAV, FLAC, M4A, AAC, OGG, WMA

### validate_tracks

```python
def validate_tracks(
    self,
    tracks: List[Path],
    parallel: bool = True
) -> Tuple[List[Path], List[Tuple[Path, str]]]:
    """
    Validate multiple audio tracks in parallel.

    Args:
        tracks: List of paths to audio files
        parallel: Enable parallel validation

    Returns:
        Tuple of (valid_tracks, invalid_tracks)
        - valid_tracks: List of valid track paths
        - invalid_tracks: List of (path, error) tuples
    """
```

### is_background_file

```python
def is_background_file(self, track: Path) -> bool:
    """
    Check if file is a background audio file.

    Background files are detected by:
    - Filename starting with 'bg'
    - Filename containing '_bg_'

    Args:
        track: Path to audio file

    Returns:
        True if file is background audio
    """
```

### parse_gain_from_filename

```python
def parse_gain_from_filename(self, filename: str) -> Optional[float]:
    """
    Parse gain value from filename.

    Patterns:
    - 'bg_-8.5.mp3' → -8.5 dB
    - 'background_-10.mp3' → -10.0 dB

    Args:
        filename: Audio filename

    Returns:
        Gain value in dB, or None if not found
    """
```

### create_music_loop

```python
def create_music_loop(
    self,
    tracks: List[Path],
    output: Path,
    duration: float,
    backgrounds: Optional[List[Tuple[Path, float]]] = None,
    progress_callback: Optional[Callable[[str, float], None]] = None
) -> Path:
    """
    Create looped music track to target duration.

    Args:
        tracks: List of music track paths
        output: Output path for looped audio
        duration: Target duration in seconds
        backgrounds: Optional list of (bg_path, gain_db) tuples
        progress_callback: Optional callback for progress

    Returns:
        Path to created audio file
    """
```

### apply_gain

```python
def apply_gain(
    self,
    track: Path,
    output: Path,
    gain_db: float
) -> Path:
    """
    Apply gain adjustment to audio track.

    Args:
        track: Path to input audio
        output: Path for output audio
        gain_db: Gain in decibels (negative to reduce)

    Returns:
        Path to output audio file
    """
```

### mix_tracks

```python
def mix_tracks(
    self,
    main: Path,
    backgrounds: List[Tuple[Path, float]],
    output: Path
) -> Path:
    """
    Mix main track with background tracks.

    Args:
        main: Path to main audio track
        backgrounds: List of (path, gain_db) tuples
        output: Output path

    Returns:
        Path to mixed audio file
    """
```

### standardize_tracks

```python
def standardize_tracks(
    self,
    tracks: List[Path],
    output_dir: Path
) -> List[Path]:
    """
    Standardize all tracks to consistent format.

    Converts all tracks to:
    - Sample rate: 44100 Hz
    - Channels: Stereo
    - Format: W64 (for >4GB support)

    Args:
        tracks: List of track paths
        output_dir: Directory for standardized tracks

    Returns:
        List of standardized track paths
    """
```

## Audio Format Support

| Format | Extension | Validation | Conversion |
|--------|-----------|------------|------------|
| MP3 | .mp3 | ✓ | ✓ |
| WAV | .wav | ✓ | ✓ |
| FLAC | .flac | ✓ | ✓ |
| M4A | .m4a | ✓ | ✓ |
| AAC | .aac | ✓ | ✓ |
| OGG | .ogg | ✓ | ✓ |
| WMA | .wma | ✓ | ✓ |

## Background Audio Patterns

Background audio files are automatically detected:

```python
# Detected as background:
"bg_ambient_-8.5.mp3"      # Starts with 'bg'
"music_bg_rain_-10.mp3"    # Contains '_bg_'
"background_nature.mp3"    # Starts with 'background'

# Not detected as background:
"ambient_track.mp3"
"music_track_01.mp3"
```

## Gain Format

Gain values in dB are parsed from filenames:

| Filename | Gain |
|----------|------|
| bg_-8.5.mp3 | -8.5 dB |
| background_-10.mp3 | -10.0 dB |
| bg_ambient_-5.mp3 | -5.0 dB |

## Usage Examples

### Basic Usage

```python
from video_renderer.ffmpeg import FFmpegRunner
from video_renderer.audio import AudioProcessor
from pathlib import Path

runner = FFmpegRunner()
processor = AudioProcessor(runner, Path("tmp"))

# Validate single track
validated = processor.validate_and_convert_track(Path("music.mp3"))

# Validate multiple tracks
valid, invalid = processor.validate_tracks([
    Path("track1.mp3"),
    Path("track2.flac")
])

print(f"Valid: {len(valid)}, Invalid: {len(invalid)}")
```

### Create Music Loop

```python
# Create 10-hour music loop
output = processor.create_music_loop(
    tracks=[Path("song1.mp3"), Path("song2.mp3")],
    output=Path("looped.w64"),
    duration=36000,  # 10 hours
    backgrounds=[
        (Path("bg_rain_-8.mp3"), -8.0),
        (Path("bg_wind_-10.mp3"), -10.0)
    ]
)
```

### Check Background Files

```python
# Check if file is background
if processor.is_background_file(Path("bg_ambient_-8.mp3")):
    gain = processor.parse_gain_from_filename("bg_ambient_-8.mp3")
    print(f"Background with gain: {gain} dB")
```

### Apply Gain

```python
# Reduce volume by 10 dB
processor.apply_gain(
    Path("loud.mp3"),
    Path("quiet.mp3"),
    gain_db=-10.0
)
```

## Error Handling

```python
from video_renderer.exceptions import AudioProcessingError

try:
    validated = processor.validate_and_convert_track(track)
except AudioProcessingError as e:
    print(f"Audio processing failed: {e}")
```

## Caching

AudioProcessor caches validation results for performance:

```python
# First call validates file
processor.validate_and_convert_track(Path("track.mp3"))

# Second call uses cache (faster)
processor.validate_and_convert_track(Path("track.mp3"))

# Skip cache
processor.validate_and_convert_track(Path("track.mp3"), use_cache=False)
```

## See Also

- [VideoEncoder](video_encoder.md) - Video processing
- [FFmpegRunner](ffmpeg_runner.md) - FFmpeg execution
- [Batch System](batch_system.md) - Batch processing

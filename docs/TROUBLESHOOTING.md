# API Reference

Complete API documentation for AutoVideo v1.0.0 modules.

---

## Table of Contents

- [video_renderer.video](#video_renderer-video)
- [video_renderer.audio](#video_renderer-audio)
- [video_renderer.batch](#video_renderer-batch)
- [video_renderer.ffmpeg](#video_renderer-ffmpeg)
- [video_renderer.config](#video_renderer-config)
- [video_renderer.drive](#video_renderer-drive)
- [video_renderer.app](#video_renderer-app)
- [video_renderer.security](#video_renderer-security)
- [video_renderer.audit](#video_renderer-audit)
- [video_renderer.logging](#video_renderer-logging)

---

## video_renderer.video

Video encoding, normalization, and concatenation.

### VideoEncoder

Main video encoding class.

```python
from video_renderer.video import VideoEncoder
from video_renderer.config import get_best_encoder

codec_config = get_best_encoder("h264")
encoder = VideoEncoder(codec_config=codec_config)
```

#### Methods

##### `check_compatibility(file_path: str | Path) -> tuple[bool, str]`

Check if a video file is compatible with target settings.

**Parameters:**
- `file_path`: Path to video file

**Returns:**
- `tuple[compatible: bool, reason: str]`

**Example:**
```python
compatible, reason = encoder.check_compatibility("video.mp4")
if not compatible:
    print(f"Incompatible: {reason}")
```

**Compatibility checks:**
- Resolution matches target
- FPS is in allowed set (60, 59.94)
- Pixel format is supported
- Codec matches target

##### `normalize_video(source: Path, output: Path) -> Path`

Normalize video to target format and settings.

**Parameters:**
- `source`: Source video path
- `output`: Output video path

**Returns:**
- `Path`: Path to normalized video

**Example:**
```python
normalized = encoder.normalize_video(
    source=Path("input.mp4"),
    output=Path("tmp/normalized.mp4")
)
```

**Normalization includes:**
- Codec conversion
- Resolution scaling
- FPS adjustment
- Pixel format conversion

##### `concat_videos(sources: list[Path], output: Path, duration: float) -> Path`

Concatenate multiple videos to target duration.

**Parameters:**
- `sources`: List of video paths to concatenate
- `output`: Output video path
- `duration`: Target duration in seconds

**Returns:**
- `Path`: Path to concatenated video

**Example:**
```python
result = encoder.concat_videos(
    sources=[Path("intro.mp4"), Path("loop.mp4")],
    output=Path("output.mp4"),
    duration=36000  # 10 hours
)
```

**Process:**
1. Generates concat list
2. Uses FFmpeg concat demuxer
3. Loops videos as needed
4. Outputs to specified duration

---

## video_renderer.audio

Audio processing, looping, and mixing.

### AudioProcessor

Main audio processing class.

```python
from video_renderer.audio import AudioProcessor

processor = AudioProcessor()
```

#### Methods

##### `validate_tracks(tracks: list[Path]) -> list[Path]`

Validate audio tracks for processing.

**Parameters:**
- `tracks`: List of audio file paths

**Returns:**
- `list[Path]`: List of valid tracks

**Raises:**
- `AudioValidationError`: If track is invalid

**Example:**
```python
valid_tracks = processor.validate_tracks([
    Path("track1.mp3"),
    Path("track2.wav")
])
```

**Validation checks:**
- File exists
- File format supported
- File not corrupted
- Duration > 0

##### `create_music_loop(tracks: list[Path], target_duration: float, output: Path) -> float`

Create a looped music track from multiple sources.

**Parameters:**
- `tracks`: List of audio track paths
- `target_duration`: Target duration in seconds
- `output`: Output file path (W64 format)

**Returns:**
- `float`: Actual duration of loop

**Example:**
```python
duration = processor.create_music_loop(
    tracks=[Path("track1.mp3"), Path("track2.mp3")],
    target_duration=36000,
    output=Path("tmp/music_loop.w64")
)
print(f"Created loop: {duration}s")
```

**Process:**
1. Concatenates all tracks
2. Loops to target duration
3. Handles silence detection
4. Preserves metadata

##### `mix_tracks(main: Path, backgrounds: list[tuple[Path, float]], output: Path) -> None`

Mix main audio with background tracks.

**Parameters:**
- `main`: Main audio path
- `backgrounds`: List of (audio_path, gain_db) tuples
- `output`: Output file path

**Example:**
```python
processor.mix_tracks(
    main=Path("music_loop.w64"),
    backgrounds=[
        (Path("rain.mp3"), -12.0),
        (Path("thunder.mp3"), -8.5)
    ],
    output=Path("tmp/final_audio.w64")
)
```

**Mixing process:**
1. Normalizes all tracks
2. Applies gain to backgrounds
3. Uses amix filter
4. Outputs to specified format

---

## video_renderer.batch

Batch processing queue management.

### BatchQueue

Thread-safe batch queue for render jobs.

```python
from video_renderer.batch import BatchQueue
from video_renderer.config import get_render_config

queue = BatchQueue(render_config=get_render_config("standard"))
```

#### Methods

##### `add_job(job: RenderJob) -> str`

Add a render job to the queue.

**Parameters:**
- `job`: RenderJob instance

**Returns:**
- `str`: Job ID

**Example:**
```python
from video_renderer.batch import RenderJob

job = RenderJob(
    mode="intro_loop",
    intro_path=Path("intro.mp4"),
    loop_path=Path("loop.mp4"),
    target_duration=36000
)
job_id = queue.add_job(job)
```

##### `start() -> None`

Start processing the queue.

**Example:**
```python
queue.start()
```

##### `pause() -> None`

Pause queue processing.

**Example:**
```python
queue.pause()
```

##### `resume() -> None`

Resume paused queue.

**Example:**
```python
queue.resume()
```

##### `clear() -> None`

Clear all jobs from queue.

**Example:**
```python
queue.clear()
```

### RenderJob

Render job configuration.

```python
from video_renderer.batch import RenderJob
from pathlib import Path

job = RenderJob(
    mode="intro_loop",
    intro_path=Path("intro.mp4"),
    loop_path=Path("loop.mp4"),
    target_duration=36000,
    codec="h264",
    output_path=Path("output.mp4")
)
```

#### Attributes

| Attribute | Type | Description |
|-----------|------|-------------|
| `mode` | str | Render mode (intro_loop, single) |
| `intro_path` | Path | Intro video path |
| `loop_path` | Path | Loop video path |
| `single_path` | Path | Single video path |
| `target_duration` | float | Target duration in seconds |
| `codec` | str | Codec family |
| `output_path` | Path | Output file path |
| `status` | JobStatus | Job status |

---

## video_renderer.ffmpeg

FFmpeg command execution and progress parsing.

### FFmpegRunner

Execute FFmpeg commands with progress tracking.

```python
from video_renderer.ffmpeg import FFmpegRunner

runner = FFmpegRunner()
```

#### Methods

##### `run(cmd: list[str], progress_callback: Callable | None = None) -> bool`

Run FFmpeg command with optional progress callback.

**Parameters:**
- `cmd`: FFmpeg command as list
- `progress_callback`: Optional callback for progress updates

**Returns:**
- `bool`: True if successful

**Example:**
```python
def on_progress(progress):
    print(f"Progress: {progress['percent']}%")

success = runner.run(
    cmd=["ffmpeg", "-i", "input.mp4", "output.mp4"],
    progress_callback=on_progress
)
```

**Progress callback data:**
```python
{
    "frame": int,
    "fps": float,
    "time": float,
    "bitrate": str,
    "speed": float,
    "percent": float
}
```

### probe_video

Get video file information.

```python
from video_renderer.ffmpeg import probe_video

info = probe_video("video.mp4")
```

**Returns:**
```python
{
    "duration": float,
    "width": int,
    "height": int,
    "fps": float,
    "codec": str,
    "pixel_format": str,
    "has_audio": bool
}
```

---

## video_renderer.config

Configuration and codec management.

### get_best_encoder

Get the best available encoder for a codec family.

```python
from video_renderer.config import get_best_encoder

codec_config = get_best_encoder("h264")
# Returns hardware encoder if available, else software
```

**Parameters:**
- `codec_family`: "av1", "h264", or "h265"

**Returns:**
- `CodecConfig`: Best available encoder config

### detect_available_encoders

Detect which hardware encoders are available.

```python
from video_renderer.config import detect_available_encoders

available = detect_available_encoders()
# Returns: {"h264_nvenc": True, "hevc_nvenc": False, ...}
```

**Parameters:**
- `use_cache`: Use cached results (default: True)
- `force_refresh`: Force re-detection (default: False)

**Returns:**
- `dict[str, bool]`: Encoder availability mapping

### get_render_config

Get configuration for a render mode.

```python
from video_renderer.config import get_render_config

config = get_render_config("ramtest")
```

**Parameters:**
- `mode`: "standard", "ramtest", "ramdisk", or "high_vram"

**Returns:**
- `RenderModeConfig`: Mode-specific configuration

### CodecConfig

Codec configuration dataclass.

```python
@dataclass
class CodecConfig:
    name: str              # Display name
    encoder: str           # FFmpeg encoder name
    preset: str            # Encoder preset
    crf: int               # CRF value
    profile: str | None    # Codec profile
    level: str | None      # Codec level
    extra_args: list[str]  # Extra FFmpeg args

    def to_ffmpeg_args(self) -> list[str]:
        # Convert to FFmpeg argument list
```

---

## video_renderer.drive

Google Drive upload integration.

### DriveUploader

Upload files to Google Drive.

```python
from video_renderer.drive import DriveUploader

uploader = DriveUploader()
```

#### Methods

##### `upload_file(file_path: Path, folder_id: str | None = None) -> str`

Upload a file to Google Drive.

**Parameters:**
- `file_path`: Path to file to upload
- `folder_id`: Optional Google Drive folder ID

**Returns:**
- `str`: Google Drive file ID

**Example:**
```python
file_id = uploader.upload_file(
    file_path=Path("final_video.mp4"),
    folder_id="1a2b3c4d5e6f7g8h9i0j"
)
print(f"Uploaded: {file_id}")
```

##### `authenticate() -> None`

Authenticate with Google Drive.

**Example:**
```python
uploader.authenticate()
# Opens browser for OAuth flow
```

---

## video_renderer.app

Main TUI application.

### VideoRendererApp

Textual TUI application.

```python
from video_renderer.app import VideoRendererApp

app = VideoRendererApp()
app.run()
```

#### Screens

- **HomeScreen**: Main menu
- **VideoSelectScreen**: Video file selection
- **AudioSelectScreen**: Audio track selection
- **SettingsScreen**: Configuration management
- **RenderScreen**: Render progress display
- **BatchScreen**: Batch queue management
- **CompleteScreen**: Completion summary

#### Usage

```bash
python -m video_renderer --tui
```

**Keyboard shortcuts:**
- `q`: Quit
- `Space`: Select/deselect
- `Enter`: Confirm
- `Esc`: Back/cancel

---

## video_renderer.security

Security and input validation.

### validate_path

Validate and sanitize file paths.

```python
from video_renderer.security import validate_path

safe_path = validate_path("../video.mp4", base_dir=Path.cwd())
# Raises SecurityError if path is unsafe
```

**Parameters:**
- `path`: Path to validate
- `base_dir`: Base directory for resolution
- `allow_absolute`: Allow absolute paths (default: False)

**Returns:**
- `Path`: Validated absolute path

**Security checks:**
- Path traversal protection
- Symbolic link validation
- Permission verification

### sanitize_filename

Sanitize filename for safe use.

```python
from video_renderer.security import sanitize_filename

safe_name = sanitize_filename("video:*.mp4")
# Returns: "video___mp4"
```

**Parameters:**
- `filename`: Filename to sanitize

**Returns:**
- `str`: Sanitized filename

---

## video_renderer.audit

Audit logging for security events.

### log_security_event

Log a security-related event.

```python
from video_renderer.audit import log_security_event

log_security_event(
    event_type="FILE_ACCESS",
    details={"file": "video.mp4", "user": "ahmet"}
)
```

**Parameters:**
- `event_type`: Type of security event
- `details`: Event details dictionary

**Event types:**
- `FILE_ACCESS`: File accessed
- `AUTH_SUCCESS`: Authentication succeeded
- `AUTH_FAILURE`: Authentication failed
- `PERMISSION_DENIED`: Permission denied
- `PATH_TRAVERSAL`: Path traversal attempt

### get_audit_log

Retrieve audit log entries.

```python
from video_renderer.audit import get_audit_log

entries = get_audit_log(limit=100)
```

**Parameters:**
- `limit`: Maximum entries to return
- `event_type`: Filter by event type
- `start_time`: Filter by start time
- `end_time`: Filter by end time

**Returns:**
- `list[dict]`: Audit log entries

---

## video_renderer.logging

Logging configuration and utilities.

### setup_logging

Configure application logging.

```python
from video_renderer.logging import setup_logging

setup_logging(
    log_level="INFO",
    log_file="autovideo.log"
)
```

**Parameters:**
- `log_level`: Logging level (DEBUG, INFO, WARNING, ERROR)
- `log_file`: Optional log file path
- `console`: Enable console logging (default: True)

### get_logger

Get a logger instance.

```python
from video_renderer.logging import get_logger

logger = get_logger(__name__)
logger.info("Video processing started")
```

**Parameters:**
- `name`: Logger name (usually `__name__`)

**Returns:**
- `logging.Logger`: Logger instance

---

## Type Definitions

### JobStatus

Render job status enum.

```python
class JobStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
```

### RenderMode

Render mode enum.

```python
class RenderMode(Enum):
    STANDARD = "standard"
    RAMTEST = "ramtest"
    RAMDISK = "ramdisk"
    HIGH_VRAM = "high_vram"
```

### ProgressInfo

Progress information dictionary.

```python
type ProgressInfo = dict[str, Any]
{
    "frame": int,
    "fps": float,
    "time": float,
    "bitrate": str,
    "speed": float,
    "percent": float
}
```

---

## Error Handling

### Exceptions

```python
# Video processing errors
class VideoError(Exception):
    """Base video processing error"""

class CompatibilityError(VideoError):
    """Video compatibility check failed"""

class EncodingError(VideoError):
    """Video encoding failed"""

# Audio processing errors
class AudioError(Exception):
    """Base audio processing error"""

class AudioValidationError(AudioError):
    """Audio validation failed"""

# Security errors
class SecurityError(Exception):
    """Security-related error"""

class PathTraversalError(SecurityError):
    """Path traversal attempt detected"""

# Batch processing errors
class BatchError(Exception):
    """Base batch processing error"""

class JobError(BatchError):
    """Job processing failed"""
```

---

## Examples

### Complete Render Pipeline

```python
from pathlib import Path
from video_renderer.video import VideoEncoder
from video_renderer.audio import AudioProcessor
from video_renderer.config import get_best_encoder
from video_renderer.ffmpeg import probe_video

# Setup
codec_config = get_best_encoder("h264")
video_encoder = VideoEncoder(codec_config=codec_config)
audio_processor = AudioProcessor()

# Check compatibility
compatible, reason = video_encoder.check_compatibility("loop.mp4")
if not compatible:
    print(f"Loop incompatible: {reason}")

# Process video
normalized = video_encoder.normalize_video(
    source=Path("loop.mp4"),
    output=Path("tmp/normalized.mp4")
)

# Process audio
audio_duration = audio_processor.create_music_loop(
    tracks=[Path("music/track1.mp3")],
    target_duration=36000,
    output=Path("tmp/music_loop.w64")
)

# Mix audio
audio_processor.mix_tracks(
    main=Path("tmp/music_loop.w64"),
    backgrounds=[(Path("bg/rain.mp3"), -12.0)],
    output=Path("tmp/final_audio.w64")
)

print("Render complete!")
```

### Batch Processing

```python
from pathlib import Path
from video_renderer.batch import BatchQueue, RenderJob
from video_renderer.config import get_render_config

# Setup queue
queue = BatchQueue(render_config=get_render_config("standard"))

# Add jobs
for i in range(5):
    job = RenderJob(
        mode="intro_loop",
        intro_path=Path(f"intros/intro_{i}.mp4"),
        loop_path=Path(f"loops/loop_{i}.mp4"),
        target_duration=36000
    )
    queue.add_job(job)

# Start processing
queue.start()
queue.wait_until_complete()
```

---

**Last Updated:** 2025-02-06
**Version:** 1.0.0

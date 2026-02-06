# Video Renderer API Reference

## Core Classes

### VideoEncoder

**Purpose**: Handles video encoding, normalization, and concatenation.

**Location**: `video_renderer/video.py`

#### Methods

##### `__init__(config: RenderConfig)`

Initialize the video encoder with configuration.

**Parameters**:
- `config` (RenderConfig): Rendering configuration including codec, resolution, duration

**Example**:
```python
from video_renderer.video import VideoEncoder
from video_renderer.config import RenderConfig

config = RenderConfig(
    codec="av1",
    width=1920,
    height=1080,
    duration_seconds=32400
)
encoder = VideoEncoder(config)
```

##### `check_compatibility(video_path: Path) -> bool`

Check if a video file is compatible with target settings.

**Parameters**:
- `video_path` (Path): Path to video file

**Returns**:
- `bool`: True if compatible, False if re-encoding needed

**Example**:
```python
if encoder.check_compatibility(Path("intro.mp4")):
    print("Video is compatible, no re-encoding needed")
else:
    print("Video needs re-encoding")
```

##### `normalize(video_path: Path, output_path: Path) -> None`

Normalize video to standard format (resolution, FPS, codec).

**Parameters**:
- `video_path` (Path): Input video file
- `output_path` (Path): Output video file

**Raises**:
- `VideoEncodingError`: If encoding fails

**Example**:
```python
encoder.normalize(
    Path("intro.mp4"),
    Path("tmp/intro_normalized.mp4")
)
```

##### `concat_videos(video_paths: List[Path], output_path: Path, target_duration: int) -> None`

Concatenate videos to target duration.

**Parameters**:
- `video_paths` (List[Path]): List of video files to concatenate
- `output_path` (Path): Output video file
- `target_duration` (int): Target duration in seconds

**Example**:
```python
encoder.concat_videos(
    [Path("tmp/intro.mp4"), Path("tmp/loop.mp4")],
    Path("tmp/concat.mp4"),
    32400  # 9 hours
)
```

---

### AudioProcessor

**Purpose**: Processes audio tracks, handles looping and mixing.

**Location**: `video_renderer/audio.py`

#### Methods

##### `__init__(config: RenderConfig)`

Initialize the audio processor.

**Parameters**:
- `config` (RenderConfig): Rendering configuration

##### `validate_track(track_path: Path) -> bool`

Validate audio track format and integrity.

**Parameters**:
- `track_path` (Path): Path to audio file

**Returns**:
- `bool`: True if valid, False otherwise

**Example**:
```python
processor = AudioProcessor(config)
if processor.validate_track(Path("music/track.mp3")):
    print("Track is valid")
```

##### `loop_track(track_path: Path, target_duration: int, output_path: Path) -> None`

Loop audio track to target duration.

**Parameters**:
- `track_path` (Path): Input audio file
- `target_duration` (int): Target duration in seconds
- `output_path` (Path): Output audio file

**Example**:
```python
processor.loop_track(
    Path("music/track.mp3"),
    32400,
    Path("tmp/looped_audio.w64")
)
```

##### `mix_audio(primary_path: Path, backgrounds: List[Tuple[Path, float]], output_path: Path) -> None`

Mix primary audio with background tracks at specified gain levels.

**Parameters**:
- `primary_path` (Path): Primary audio track
- `backgrounds` (List[Tuple[Path, float]]): List of (background_path, gain_db) tuples
- `output_path` (Path): Output mixed audio file

**Example**:
```python
processor.mix_audio(
    Path("tmp/looped_audio.w64"),
    [(Path("bg/rain.mp3"), -8.5)],
    Path("tmp/mixed_audio.w64")
)
```

---

### FFmpegRunner

**Purpose**: Executes FFmpeg commands with progress tracking.

**Location**: `video_renderer/ffmpeg.py`

#### Methods

##### `__init__(command: List[str])`

Initialize FFmpeg runner with command.

**Parameters**:
- `command` (List[str]): FFmpeg command as list of strings

##### `run(timeout: Optional[int] = None) -> str`

Run FFmpeg command and return output.

**Parameters**:
- `timeout` (Optional[int]): Timeout in seconds

**Returns**:
- `str`: FFmpeg stderr output

**Raises**:
- `FFmpegError`: If command fails

**Example**:
```python
from video_renderer.ffmpeg import FFmpegRunner

cmd = [
    "ffmpeg", "-i", "input.mp4",
    "-c:v", "libx264", "output.mp4"
]
runner = FFmpegRunner(cmd)
output = runner.run(timeout=3600)
```

##### `run_with_progress(callback: Callable[[float], None]) -> str`

Run FFmpeg command with progress callbacks.

**Parameters**:
- `callback` (Callable[[float], None]): Progress callback function (0-100)

**Returns**:
- `str`: FFmpeg stderr output

**Example**:
```python
def progress_handler(percent: float):
    print(f"Progress: {percent}%")

runner = FFmpegRunner(cmd)
output = runner.run_with_progress(progress_handler)
```

---

### BatchQueue

**Purpose**: Thread-safe queue for managing render jobs.

**Location**: `video_renderer/batch.py`

#### Methods

##### `__init__(queue_file: Optional[Path] = None)`

Initialize batch queue with optional persistence.

**Parameters**:
- `queue_file` (Optional[Path]): Path to queue file for persistence

##### `create_job() -> RenderJob`

Create a new pending render job.

**Returns**:
- `RenderJob`: New job object

**Example**:
```python
queue = BatchQueue()
job = queue.create_job()
job.codec_family = "av1"
job.duration_str = "9:00:00"
```

##### `queue_job(job_id: int) -> Optional[RenderJob]`

Mark a job as ready to run.

**Parameters**:
- `job_id` (int): Job ID

**Returns**:
- `Optional[RenderJob]`: The queued job or None

##### `set_callbacks(on_complete: Callable, on_error: Callable, on_progress: Callable) -> None`

Set event callbacks for job updates.

**Parameters**:
- `on_complete` (Callable): Called when job completes
- `on_error` (Callable): Called when job fails
- `on_progress` (Callable): Called during progress updates

**Example**:
```python
def on_complete(job):
    print(f"Job {job.id} complete!")

def on_error(job, error):
    print(f"Job {job.id} failed: {error}")

queue.set_callbacks(on_complete, on_error)
```

---

### SmartBatchDetector

**Purpose**: Auto-detects intro/loop video pairs.

**Location**: `video_renderer/batch.py`

#### Methods

##### `__init__(directory: Optional[Path] = None)`

Initialize detector with target directory.

**Parameters**:
- `directory` (Optional[Path]): Directory to scan (default: current directory)

##### `scan() -> List[BatchPair]`

Scan directory for matching intro/loop pairs.

**Returns**:
- `List[BatchPair]`: List of detected pairs

**Example**:
```python
detector = SmartBatchDetector()
pairs = detector.scan()
for pair in pairs:
    print(f"{pair.name}: {pair.intro} + {pair.loop}")
```

---

## Data Classes

### RenderConfig

**Purpose**: Complete configuration for a render session.

**Location**: `video_renderer/config.py`

#### Fields

```python
@dataclass
class RenderConfig:
    work_dir: Path = field(default_factory=Path.cwd)
    music_dir: Optional[Path] = None
    tmp_dir: Optional[Path] = None
    output_path: Optional[Path] = None

    width: int = 1920
    height: int = 1080
    fps: int = 60
    codec: str = "av1"

    duration_seconds: int = 0

    intro_path: Optional[Path] = None
    loop_path: Optional[Path] = None

    tracks: List[Path] = field(default_factory=list)
    backgrounds: List[tuple] = field(default_factory=list)

    post_action: str = "keep"
    use_hw_accel: bool = True
    parallel_encode: bool = True
```

**Example**:
```python
config = RenderConfig(
    width=1920,
    height=1080,
    codec="av1",
    duration_seconds=32400,
    use_hw_accel=True
)
```

---

### RenderJob

**Purpose**: Represents a single render job in the batch queue.

**Location**: `video_renderer/batch.py`

#### Fields

```python
@dataclass
class RenderJob:
    id: int
    intro_path: Optional[Path] = None
    loop_path: Optional[Path] = None
    single_video_path: Optional[Path] = None
    mode: str = "intro_loop"
    codec_family: str = "av1"
    duration_str: str = "9:00:00"
    total_seconds: int = 32400
    tracks: List[Path] = field(default_factory=list)
    backgrounds: List[tuple] = field(default_factory=list)
    output_path: Optional[Path] = None
    status: JobStatus = JobStatus.PENDING
    progress: float = 0.0
    error_message: Optional[str] = None
```

#### Methods

##### `to_dict() -> Dict[str, Any]`

Convert job to serializable dictionary.

##### `from_dict(data: Dict[str, Any]) -> RenderJob`

Create job from dictionary (class method).

---

### CodecConfig

**Purpose**: Configuration for a video codec.

**Location**: `video_renderer/config.py`

#### Fields

```python
@dataclass
class CodecConfig:
    name: str
    encoder: str
    preset: str
    crf: int
    profile: Optional[str] = None
    level: Optional[str] = None
    extra_args: List[str] = field(default_factory=list)
```

#### Methods

##### `to_ffmpeg_args() -> List[str]`

Convert config to FFmpeg command arguments.

**Example**:
```python
config = CODEC_AV1
args = config.to_ffmpeg_args()
# ['-c:v', 'libsvtav1', '-preset', '6', '-crf', '28', '-g', '240']
```

---

## Utility Functions

### probe_video(video_path: Path) -> Dict[str, Any]

Probe video file with ffprobe and return metadata.

**Parameters**:
- `video_path` (Path): Path to video file

**Returns**:
- `Dict[str, Any]`: Video metadata including streams, format, duration

**Example**:
```python
from video_renderer.ffmpeg import probe_video

metadata = probe_video(Path("video.mp4"))
print(f"Duration: {metadata['format']['duration']}")
print(f"Streams: {len(metadata['streams'])}")
```

---

### detect_available_encoders() -> Dict[str, bool]

Detect available hardware encoders.

**Returns**:
- `Dict[str, bool]`: Dictionary mapping encoder names to availability

**Example**:
```python
from video_renderer.config import detect_available_encoders

encoders = detect_available_encoders()
if encoders.get("h264_nvenc"):
    print("NVENC H.264 available")
```

---

### get_best_encoder(codec_family: str) -> CodecConfig

Get the best available encoder for a codec family.

**Parameters**:
- `codec_family` (str): Codec family ("av1", "h264", "h265")

**Returns**:
- `CodecConfig`: Best available encoder configuration

**Example**:
```python
from video_renderer.config import get_best_encoder

config = get_best_encoder("h264")
print(f"Using encoder: {config.encoder}")
```

---

## Exception Classes

### VideoEncodingError

Raised when video encoding fails.

### AudioProcessingError

Raised when audio processing fails.

### FFmpegError

Raised when FFmpeg command fails.

### ConfigError

Raised when configuration is invalid.

---

**Document Version**: 1.0
**Last Updated**: 2024-01-XX
**Author**: AutoVideo Development Team

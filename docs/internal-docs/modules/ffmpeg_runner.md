# FFmpegRunner Module

The FFmpegRunner module (`video_renderer/ffmpeg.py`) handles FFmpeg command execution, progress parsing, and video probing.

## Overview

FFmpegRunner is responsible for:
- FFmpeg command execution with progress tracking
- FFmpeg stderr parsing for progress information
- Video file probing (codec, resolution, FPS, duration)
- Concatenation list file generation
- Error handling and timeout management

## Class Reference

### FFmpegProgress

```python
@dataclass
class FFmpegProgress:
    """Progress information from FFmpeg."""
    frame: int = 0
    fps: float = 0.0
    time: str = "0:00:00"
    bitrate: str = "0kb/s"
    speed: str = "0x"
    percent: float = 0.0
```

### FFmpegRunner

```python
class FFmpegRunner:
    """Handles FFmpeg command execution and progress tracking."""

    def __init__(
        self,
        ffmpeg_path: str = "ffmpeg",
        ffprobe_path: str = "ffprobe",
        timeout: int = 36000  # 10 hours default
    ):
        """
        Initialize FFmpegRunner.

        Args:
            ffmpeg_path: Path to ffmpeg executable
            ffprobe_path: Path to ffprobe executable
            timeout: Default timeout in seconds
        """
```

## Key Methods

### run

```python
def run(
    self,
    cmd: List[str],
    capture_progress: bool = False,
    progress_callback: Optional[Callable[[FFmpegProgress], None]] = None,
    timeout: Optional[int] = None
) -> Tuple[bool, str]:
    """
    Execute FFmpeg command.

    Args:
        cmd: FFmpeg command as list of strings
        capture_progress: Parse progress from stderr
        progress_callback: Optional callback for progress updates
        timeout: Optional timeout override

    Returns:
        Tuple of (success, output)
        - success: True if command completed successfully
        - output: Stderr output from FFmpeg

    Raises:
        subprocess.TimeoutExpired: If command times out
        subprocess.CalledProcessError: If command fails
    """
```

### probe_video

```python
def probe_video(self, video_path: Path) -> VideoInfo:
    """
    Probe video file for metadata.

    Args:
        video_path: Path to video file

    Returns:
        VideoInfo with:
        - codec: Video codec name
        - width: Width in pixels
        - height: Height in pixels
        - fps: Frames per second (string, e.g., "60/1")
        - duration: Duration in seconds
        - pix_fmt: Pixel format
        - color_space: Color space

    Raises:
        VideoProcessingError: If probing fails
    """
```

### get_duration

```python
def get_duration(self, video_path: Path) -> float:
    """
    Get video duration in seconds.

    Args:
        video_path: Path to video file

    Returns:
        Duration in seconds

    Raises:
        VideoProcessingError: If probing fails
    """
```

### write_concat_list

```python
def write_concat_list(
    self,
    output: Path,
    files: List[Path],
    repeat_count: int = 1
) -> None:
    """
    Write FFmpeg concatenation list file.

    Args:
        output: Path for concat list file
        files: List of video file paths
        repeat_count: Number of times to repeat the list

    The concat list format:
    ```
    file '/path/to/video1.mp4'
    file '/path/to/video2.mp4'
    ```
    """
```

## Progress Parsing

FFmpegRunner parses FFmpeg stderr output for progress:

```
frame=  120 fps= 60 q=28.0 size=   15360kB time=00:00:02.00 bitrate=62914.5kbits/s speed=1.00x
```

Parsed into FFmpegProgress:
- `frame`: Current frame number
- `fps`: Encoding speed in frames/second
- `time`: Current timestamp
- `bitrate`: Current bitrate
- `speed`: Encoding speed multiplier
- `percent`: Calculated from time vs duration

## Usage Examples

### Basic Command Execution

```python
from video_renderer.ffmpeg import FFmpegRunner

runner = FFmpegRunner()

# Simple command
success, output = runner.run([
    "ffmpeg", "-i", "input.mp4", "-c:v", "libx264", "output.mp4"
])

if success:
    print("Encoding completed")
else:
    print(f"Encoding failed: {output}")
```

### With Progress Tracking

```python
def on_progress(progress: FFmpegProgress):
    print(f"Frame: {progress.frame}, FPS: {progress.fps:.1f}")
    print(f"Time: {progress.time}, Speed: {progress.speed}")
    print(f"Progress: {progress.percent:.1f}%")

runner.run(
    ["ffmpeg", "-i", "input.mp4", "output.mp4"],
    capture_progress=True,
    progress_callback=on_progress
)
```

### Probe Video

```python
info = runner.probe_video(Path("video.mp4"))

print(f"Codec: {info.codec}")
print(f"Resolution: {info.width}x{info.height}")
print(f"FPS: {info.fps}")
print(f"Duration: {info.duration} seconds")
print(f"Pixel Format: {info.pix_fmt}")
```

### Get Duration Only

```python
duration = runner.get_duration(Path("video.mp4"))
print(f"Duration: {duration} seconds")
```

### Write Concat List

```python
# Create concat list for intro + 100 loops
runner.write_concat_list(
    Path("concat.txt"),
    [Path("intro.mp4"), Path("loop.mp4")],
    repeat_count=100
)
```

## Error Handling

```python
from video_renderer.exceptions import VideoProcessingError
import subprocess

try:
    success, output = runner.run(cmd, timeout=300)
except subprocess.TimeoutExpired:
    print("FFmpeg timed out")
except subprocess.CalledProcessError as e:
    print(f"FFmpeg failed: {e}")
except VideoProcessingError as e:
    print(f"Video processing error: {e}")
```

## Timeout Handling

FFmpegRunner has built-in timeout protection:

```python
# Default timeout: 10 hours
runner = FFmpegRunner(timeout=36000)

# Per-command timeout override
runner.run(cmd, timeout=300)  # 5 minutes
```

The stderr reading loop includes timeout detection to prevent indefinite hangs.

## Stderr Buffer

FFmpegRunner maintains a circular buffer of recent stderr lines:

```python
# Access recent stderr lines
recent_lines = runner._stderr_buffer
```

This is useful for debugging failed encodings.

## FFmpeg Version Detection

```python
from video_renderer.audio import get_ffmpeg_version

version = get_ffmpeg_version()
print(f"FFmpeg version: {version}")  # (4, 4, 0)
```

## See Also

- [VideoEncoder](video_encoder.md) - Video encoding
- [AudioProcessor](audio_processor.md) - Audio processing
- [FFmpeg Documentation](https://ffmpeg.org/documentation.html)

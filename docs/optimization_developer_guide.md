# Optimization Developer Guide

## Quick Reference

### FFmpeg Command Execution

**Basic Usage:**
```python
from video_renderer.ffmpeg import FFmpegRunner

runner = FFmpegRunner(log_path=Path("logs/ffmpeg.log"), max_retries=3)
runner.set_total_duration(duration=3600)  # For percent calculation

# Run with progress tracking
runner.set_progress_callback(lambda p: print(f"{p.percent:.1f}%"))
runner.run(cmd, capture_progress=True)
```

**Key Features:**
- Automatic retry with exponential backoff
- Hardware → software fallback on GPU errors
- Streaming output handling (memory efficient)
- Thread-safe progress callbacks

### Video Encoding

**Optimized Usage:**
```python
from video_renderer.video import VideoEncoder
from video_renderer.config import CODEC_H264_NVENC

# Create encoder with hardware acceleration
encoder = VideoEncoder(
    runner=runner,
    codec_config=CODEC_H264_NVENC,
    width=1920,
    height=1080,
    fps=60
)

# Check compatibility (cached)
is_compatible, reason = encoder.check_compatibility(source_video)

# Normalize with automatic GPU acceleration
encoder.normalize_video(
    source=source_video,
    output=output_video,
    progress_callback=callback,
    scale_algo="lanczos"
)
```

**Acceleration Types Detected:**
- `nvenc`: NVIDIA NVENC (CUDA)
- `qsv`: Intel Quick Sync Video
- `vaapi`: VAAPI (Linux AMD/Intel)
- `videotoolbox`: Apple VideoToolbox
- `none`: Software encoding

### Audio Processing

**Optimized Usage:**
```python
from video_renderer.audio import AudioProcessor

# Create processor with parallel processing
processor = AudioProcessor(
    runner=runner,
    tmp_dir=Path("tmp"),
    max_workers=4  # Configurable worker count
)

# Parallel validation (faster for multiple files)
valid_tracks, invalid = processor.validate_tracks(
    tracks=audio_files,
    progress_callback=callback,
    parallel=True
)

# Create music loop with optimization
loop = processor.create_music_loop(
    tracks=valid_tracks,
    total_seconds=3600,
    progress_callback=callback,
    pre_validated=True  # Skip validation if already validated
)
```

### Hardware Encoder Detection

**Usage:**
```python
from video_renderer.config import detect_available_encoders, get_best_encoder

# Detect with caching (default 5-minute TTL)
encoders = detect_available_encoders(use_cache=True)

# Get best encoder for codec family
best_h264 = get_best_encoder("h264")
best_av1 = get_best_encoder("av1")

# Force re-detection
encoders = detect_available_encoders(force_refresh=True)

# Clear cache
from video_renderer.config import clear_encoder_cache
clear_encoder_cache()
```

**Priority Order:**
1. NVIDIA NVENC (best performance)
2. Intel QSV (good performance)
3. VAAPI (Linux AMD/Intel)
4. Software encoders (universal)

## Performance Tips

### 1. Enable Hardware Acceleration
```python
# Automatic detection is enabled by default
config.use_hw_accel = True  # Default
encoder = VideoEncoder(runner, config.get_codec_config())
```

### 2. Use Parallel Processing for Audio
```python
# For 5+ audio files, parallel processing is faster
valid, invalid = processor.validate_tracks(tracks, parallel=True)
```

### 3. Cache-Friendly Operations
```python
# Check compatibility (cached)
if encoder.check_compatibility(video)[0]:
    # Fast path: direct copy
    pass
```

### 4. Optimal Thread Configuration
```python
# Automatically calculated based on:
# - GPU encoding: 4 threads
# - CPU encoding: 75% of available CPUs
threads = encoder._get_optimal_threads()
```

## Error Handling

### Automatic Retry
```python
# FFmpegRunner automatically retries up to 3 times
runner = FFmpegRunner(max_retries=3)  # Default
```

### Hardware Fallback
```python
# Automatic fallback on GPU errors
# Try: NVENC → Fallback: libx264
# No manual intervention needed
```

### Custom Error Detection
```python
# Check if error was hardware-related
is_hw_error, reason = runner._detect_hardware_failure(stderr_lines)
if is_hw_error:
    print(f"Hardware failed: {reason}")
```

## Memory Optimization

### Circular Buffer
```python
# Stderr buffer limited to 100 lines
# Reduces memory usage for long renders
runner._stderr_buffer  # deque(maxlen=100)
```

### Streaming I/O
```python
# FFmpeg processes use line-buffered I/O
# Reduces memory footprint for large files
```

### Caching
```python
# Avoid redundant ffprobe calls
encoder._compatibility_cache  # Video compatibility cache
processor._validated_cache    # Audio validation cache
```

## Monitoring Progress

### Progress Callback Format
```python
from video_renderer.ffmpeg import FFmpegProgress

@dataclass
class FFmpegProgress:
    frame: int           # Current frame number
    fps: float          # Current FPS
    time_seconds: float # Current time in seconds
    speed: float        # Encoding speed multiplier
    size_kb: int        # Output size in KB
    bitrate_kbps: float # Current bitrate
    percent: float      # Percentage (if duration set)

def on_progress(p: FFmpegProgress):
    print(f"{p.percent:.1f}% - {p.speed:.2f}x - {p.fps:.1f} fps")
```

### Thread-Safe Callbacks
```python
# Callbacks are thread-safe by default
# No additional locking needed
runner.set_progress_callback(lambda p: update_ui(p))
```

## Common Patterns

### Batch Video Processing
```python
# Parallel encoding for multiple videos
from video_renderer.video import encode_parallel

sources = [(src1, out1), (src2, out2), (src3, out3)]
results = encode_parallel(
    encoder=encoder,
    sources=sources,
    progress_callback=lambda label, p: print(f"{label}: {p.percent}%")
)
```

### Audio Loop Creation
```python
# Optimal workflow
tracks = [audio1, audio2, audio3]

# Step 1: Validate in parallel
valid, invalid = processor.validate_tracks(tracks, parallel=True)

# Step 2: Create loop with pre-validated tracks
loop = processor.create_music_loop(
    tracks=valid,
    total_seconds=3600,
    pre_validated=True  # Skip re-validation
)

# Step 3: Mix with backgrounds
mixed = processor.mix_tracks(
    main_track=loop,
    background_tracks=processed_bg,
    total_seconds=3600
)
```

## Troubleshooting

### GPU Not Detected
```python
# Check encoder availability
from video_renderer.config import detect_available_encoders
encoders = detect_available_encoders()
print(encoders)  # Check which are True

# Force refresh if hardware was just installed
encoders = detect_available_encoders(force_refresh=True)
```

### Memory Issues
```python
# Reduce workers for memory-constrained systems
processor = AudioProcessor(runner, tmp_dir, max_workers=2)

# Use RAM disk if available (Linux)
from video_renderer.config import setup_temp_directory
tmp_dir = setup_temp_directory(base_dir, use_ramdisk=True)
```

### Slow Encoding
```python
# Check if hardware acceleration is being used
encoder = VideoEncoder(runner, codec_config)
print(f"Acceleration: {encoder._accel_type}")
print(f"Using GPU: {encoder._use_gpu}")

# Verify thread count
print(f"Threads: {encoder._get_optimal_threads()}")
```

## Best Practices

1. **Always use hardware acceleration** when available
2. **Enable parallel processing** for 5+ audio files
3. **Use caching** for repeated compatibility checks
4. **Monitor progress** for long-running operations
5. **Handle errors gracefully** with retry mechanism
6. **Clear caches** if hardware configuration changes

## Performance Expectations

| Operation | Before | After | Improvement |
|-----------|--------|-------|-------------|
| Progress parsing | ~0.1ms | 0.003ms | 33x faster |
| Cached encoder detect | ~1s | <0.001s | 1000x faster |
| Memory for stderr | Unbounded | 100 lines | Fixed |
| Audio validation (10 files) | Sequential | Parallel | ~4x faster |

## Version History

- **v1.0** (2024): Initial implementation
- **v2.0** (2025): Optimized version with caching, parallel processing, GPU acceleration

For more details, see `performance_optimization_summary.md`.

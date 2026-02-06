# RAM-Optimized Rendering Mode (Ramtest)

## Overview

The video renderer now supports a **RAM-optimized (ramtest)** mode that provides enhanced performance for high-memory systems. This mode was developed by merging the `video_renderer_ramtest` module into the main `video_renderer` package.

## Key Features

### 1. RAM Disk Support (Linux)
- Uses Linux tmpfs (`/dev/shm`) for temporary files when available
- Requires at least 10GB free space on RAM disk
- Automatic fallback to disk-based tmp directory if RAM disk unavailable
- Significantly faster I/O for encoding operations

### 2. High-VRAM Optimization
- Enhanced GPU buffer configuration for systems with 20GB+ VRAM
- Increased NVENC surfaces (128 vs 64)
- Larger lookahead frames (48 vs 32)
- Extra hardware frames in pipeline (16 vs 8)
- Optimized decode surfaces (32)

### 3. Memory Tracking
- Real-time RAM usage monitoring
- GPU memory tracking via nvidia-smi
- Memory usage displayed in TUI during render

## Usage

### Command Line

```bash
# Enable RAM-optimized mode
python -m video_renderer --rm --tui

# Or use long form
python -m video_renderer --ramtest --tui

# Standard mode (default)
python -m video_renderer --tui
```

### Python API

```python
from video_renderer.app import run_tui

# Run with ramtest mode
run_tui(ramtest_mode=True)

# Standard mode
run_tui(ramtest_mode=False)
```

## Configuration

### RamTestConfig Class

```python
from video_renderer.config import RamTestConfig

# Create configuration
config = RamTestConfig(
    enabled=True,           # Enable ramtest mode
    use_ramdisk=True,       # Use RAM disk if available
    high_vram=True,         # Enable high-VRAM optimizations
    chunk_long_videos=False # Enable chunking for very long videos
)
```

## Implementation Details

### RAM Disk Detection

The ramtest mode automatically detects and uses Linux tmpfs:

```python
from video_renderer.config import get_ramdisk_path

ramdisk = get_ramdisk_path()
if ramdisk:
    print(f"Using RAM disk: {ramdisk}")
else:
    print("Falling back to disk tmp")
```

### GPU Optimization

High-VRAM mode provides enhanced NVENC parameters:

```python
from video_renderer.config import get_nvenc_extra_args

# Standard NVENC args
args = get_nvenc_extra_args("av1", high_vram=False)

# High-VRAM NVENC args (20GB+ VRAM)
args = get_nvenc_extra_args("av1", high_vram=True)
```

### Video Encoder Integration

The VideoEncoder class supports ramtest mode:

```python
from video_renderer.video import VideoEncoder

# Create encoder with ramtest optimizations
encoder = VideoEncoder(
    runner=runner,
    codec_config=codec_config,
    ramtest_mode=True,
    high_vram=True
)
```

## Memory Tracking

Memory usage is tracked using `psutil` and displayed in the TUI:

- **RAM Usage**: Current process memory in MB and percentage
- **VRAM Usage**: GPU memory usage via nvidia-smi (if available)

### Example Output

```
💾 Memory Usage
RAM: 2048MB (12.5%) | VRAM: 8192MB
```

## Performance Benefits

### RAM Disk Mode
- **Faster I/O**: RAM disk provides much faster read/write speeds
- **Reduced Wear**: Less disk I/O extends SSD lifespan
- **Better Performance**: Especially beneficial for multiple concurrent operations

### High-VRAM Mode
- **Better Quality**: Larger lookahead allows better encoding decisions
- **Higher Throughput**: More GPU surfaces enable better pipelining
- **Stable Encoding**: Extra buffers reduce frame drops

## System Requirements

### Minimum Requirements
- Python 3.10+
- 16GB RAM (32GB+ recommended for ramtest mode)
- GPU with 8GB+ VRAM (20GB+ for high_vram mode)
- Linux with tmpfs support (for RAM disk)

### Recommended Configuration
- 64GB+ RAM
- NVIDIA GPU with 20GB+ VRAM (RTX 3080/3090/4080/4090, A5000+, etc.)
- NVMe SSD for disk tmp fallback
- Linux OS (for tmpfs RAM disk)

## Troubleshooting

### RAM Disk Not Available

If you see `[DISK] Temp files kullanilacak`, RAM disk is not available:

1. Check if `/dev/shm` exists: `ls -la /dev/shm`
2. Check available space: `df -h /dev/shm`
3. Ensure at least 10GB free space

### High VRAM Mode Issues

If encoding fails with high VRAM mode:

1. Check GPU memory: `nvidia-smi`
2. Try standard NVENC mode: set `high_vram=False`
3. Reduce resolution or bitrate

### Memory Tracking Not Working

If memory info shows `---`:

1. Ensure `psutil` is installed: `pip install psutil`
2. Check `nvidia-smi` is available for VRAM tracking
3. Verify permissions for system monitoring

## Migration from video_renderer_ramtest

The `video_renderer_ramtest` module has been merged into `video_renderer`. All functionality is preserved:

### Old Usage
```bash
cd video_renderer_ramtest
python -m app --tui
```

### New Usage
```bash
python -m video_renderer --rm --tui
```

### Code Changes

Replace:
```python
from video_renderer_ramtest.config import get_ramdisk_path
```

With:
```python
from video_renderer.config import get_ramdisk_path
```

## Future Enhancements

Planned improvements for ramtest mode:

1. Automatic chunking for very long videos (>12 hours)
2. Multi-GPU support
3. Memory pressure monitoring and automatic adjustment
4. Windows support for RAM disk (ImDisk, etc.)
5. Benchmarking and performance comparison tools

## Contributing

When adding new ramtest features:

1. Update `RamTestConfig` class
2. Add feature flag to command line args
3. Update TUI to show new status
4. Document in this file
5. Test on both high-memory and standard systems

## License

Same as the main video_renderer project.

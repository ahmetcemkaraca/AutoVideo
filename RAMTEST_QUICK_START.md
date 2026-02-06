# RAM-Optimized Mode - Quick Start Guide

## What is Ramtest Mode?

Ramtest mode is a special performance-optimized rendering mode that uses:
- **RAM Disk** (Linux) for faster I/O
- **High-VRAM** optimizations for better GPU utilization
- **Memory Tracking** to monitor resource usage

## Quick Start

### Enable Ramtest Mode

Simply add `--rm` or `--ramtest` to any command:

```bash
# TUI with ramtest
python -m video_renderer --rm --tui

# CLI wizard with ramtest
python -m video_renderer --rm

# Batch mode with ramtest
python -m video_renderer --rm --batch
```

## Requirements

### Minimum
- Python 3.10+
- 16GB RAM
- GPU with 8GB+ VRAM

### Recommended
- 64GB+ RAM
- NVIDIA GPU with 20GB+ VRAM
- Linux OS (for RAM disk)

## What Changes?

### In Ramtest Mode:
- ✅ Uses `/dev/shm` for temp files (Linux)
- ✅ Higher GPU buffer settings
- ✅ Real-time memory usage display
- ✅ Enhanced NVENC parameters

### In Standard Mode:
- ✅ Regular disk temp files
- ✅ Standard GPU settings
- ✅ No memory tracking

## When to Use Ramtest Mode?

### Use Ramtest Mode When:
- Rendering on high-memory system (32GB+ RAM)
- Using NVIDIA GPU with 20GB+ VRAM
- Need maximum performance
- Running on Linux with tmpfs

### Use Standard Mode When:
- Rendering on standard system (16GB RAM)
- Using GPU with 8GB VRAM or less
- Running on Windows (no RAM disk support)
- Don't need memory tracking

## Performance Comparison

| Feature | Standard Mode | Ramtest Mode |
|---------|--------------|--------------|
| NVENC Surfaces | 64 | 128 |
| Lookahead Frames | 32 | 48 |
| Extra HW Frames | 8 | 16 |
| Temp Location | Disk (/tmp) | RAM (/dev/shm) |
| Memory Tracking | No | Yes |

## Troubleshooting

### RAM Disk Not Available

If you see `[DISK] Temp files kullanilacak`:
- RAM disk not available (Windows or insufficient space)
- System falls back to disk automatically
- No performance benefit, but no errors

### High VRAM Mode Issues

If encoding fails:
1. Try standard mode: `python -m video_renderer --tui`
2. Check GPU memory: `nvidia-smi`
3. Reduce resolution or bitrate

### Memory Tracking Shows `---`

This means:
- `psutil` not installed (run: `pip install psutil`)
- nvidia-smi not available for VRAM tracking
- System permissions issue

## Examples

### Render a Single Video with Ramtest

```bash
# Start TUI in ramtest mode
python -m video_renderer --rm --tui

# Follow the prompts:
# 1. Select intro and loop videos
# 2. Choose codec (AV1 recommended)
# 3. Set duration (e.g., 9:00:00)
# 4. Select music tracks
# 5. Start render
```

### Batch Render with Ramtest

```bash
# Run smart batch in ramtest mode
python -m video_renderer --rm --batch

# This will:
# 1. Auto-detect intro/loop pairs
# 2. Use RAM disk for temp files
# 3. Apply high-VRAM optimizations
# 4. Show memory usage during render
```

## Getting Help

### Documentation
- Full guide: `video_renderer/RAMTEST_MODE.md`
- Merge details: `video_renderer/MERGE_SUMMARY.md`
- Completion report: `MERGE_COMPLETION_REPORT.md`

### Testing
Run verification test:
```bash
python test_ramtest_core.py
```

## Tips

1. **First Time**: Try standard mode first, then ramtest
2. **Linux Users**: Ramtest mode provides biggest benefit on Linux
3. **GPU Users**: High VRAM mode needs 20GB+ VRAM for best results
4. **Memory**: Monitor memory usage in TUI to avoid OOM

## FAQ

**Q: Is ramtest mode safe?**
A: Yes, it's just optimized settings. Same output quality.

**Q: Can I switch modes?**
A: Yes, just add/remove `--rm` flag. No config changes needed.

**Q: Does it work on Windows?**
A: Yes, but without RAM disk benefit (falls back to disk).

**Q: Will it use all my RAM?**
A: No, it uses RAM for temp files only (~10-20GB typically).

**Q: How do I know if it's working?**
A: You'll see `[RAM] Temp files kullanilacak` on startup (Linux only).

## Command Reference

```bash
# Show help
python -m video_renderer --help

# List hardware encoders
python -m video_renderer --list-hw

# Standard TUI
python -m video_renderer --tui

# Ramtest TUI
python -m video_renderer --rm --tui

# Batch mode
python -m video_renderer --batch

# Batch with ramtest
python -m video_renderer --rm --batch

# Resume
python -m video_renderer --resume

# Resume with ramtest
python -m video_renderer --rm --resume
```

---

**Version**: 2.0
**Date**: 2025-02-06
**Status**: Production Ready

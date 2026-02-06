# Migration Guide

## From 0.x to 1.0.0

AutoVideo v1.0.0 introduces several improvements and changes. This guide helps you migrate from earlier versions.

---

## Breaking Changes

### 1. Ramtest Module Deprecation

The `video_renderer_ramtest` module is now deprecated and merged into the main `video_renderer` package. Use the mode flag instead.

**Old approach (0.x):**
```bash
cd video_renderer_ramtest
python -m app
```

**New approach (1.0.0):**
```bash
# Use ramtest mode
python -m video_renderer --tui --mode ramtest

# Or use CLI flag
python -m video_renderer --ramtest
```

**Migration steps:**
1. Update any scripts that import from `video_renderer_ramtest`
2. Replace module references with mode flags
3. Update configuration files to use new render mode settings

### 2. Configuration Import Paths

Config files are now organized in a unified structure.

**Old imports (0.x):**
```python
from video_renderer.config import get_best_encoder
from video_renderer_ramtest.config import RamTestConfig
```

**New imports (1.0.0):**
```python
from video_renderer.config import get_best_encoder, RenderModeConfig
```

**Configuration changes:**

**Old format:**
```python
config = {
    "codec": "libx264",
    "preset": "medium",
    "use_ramdisk": True
}
```

**New format:**
```python
from video_renderer.config import get_render_config

config = get_render_config("ramdisk")
# or explicitly
config = RenderModeConfig(
    mode="ramdisk",
    use_ramdisk=True
)
```

### 3. State File Format

State files have been updated with new fields. The system auto-migrates old state files on first run.

**Old state file (0.x):**
```json
{
    "jobs": [],
    "current_job": null,
    "completed_count": 0
}
```

**New state file (1.0.0):**
```json
{
    "version": "1.0.0",
    "jobs": [],
    "current_job": null,
    "completed_count": 0,
    "failed_count": 0,
    "start_time": null,
    "render_mode": "standard"
}
```

**Note:** Auto-migration happens automatically. No manual action needed.

### 4. CLI Flag Changes

Some command-line flags have been renamed for clarity.

| Old Flag (0.x) | New Flag (1.0.0) | Notes |
|----------------|------------------|-------|
| `--gpu` | `--hw-accel` | More explicit |
| `--youtube-upload` | `--youtube` | Shorter name |
| N/A | `--mode <mode>` | New unified mode flag |
| N/A | `--ramtest` | Shorthand for `--mode ramtest` |

---

## New Features in v1.0.0

### Unified Render Modes

v1.0.0 introduces unified render modes that replace the separate ramtest module:

```bash
# Standard mode (default)
python -m video_renderer --tui

# Memory-constrained systems
python -m video_renderer --tui --mode ramtest

# High-performance with RAM disk
python -m video_renderer --tui --mode ramdisk

# High-VRAM systems
python -m video_renderer --tui --mode high_vram
```

### Enhanced Security

New security features are enabled by default:
- Credential encryption at rest
- File permission validation
- Sensitive data filtering in logs
- OAuth state parameter

**Migration:** No action required. Features are automatic.

### Improved Batch Processing

Batch queue now includes:
- Better thread-safety guarantees
- Automatic stale lock cleanup
- Enhanced error recovery
- Memory management for large batches

**Migration:** Existing batch configs work unchanged. New features are automatic.

---

## Configuration Migration

### Old Config File Migration

If you have an old config file, migrate it as follows:

**Old `config.json` (0.x):**
```json
{
    "codec": "libx264",
    "preset": "medium",
    "crf": 20,
    "use_ramdisk": false
}
```

**New `config.json` (1.0.0):**
```json
{
    "encoder": {
        "default_codec": "h264",
        "preset": "fast",
        "crf": 20
    },
    "render_mode": "standard"
}
```

**Auto-migration command:**
```bash
python -m video_renderer --migrate-config
```

### Environment Variables

New environment variables available in v1.0.0:

```bash
# Render mode
export AUTORENDER_MODE=ramtest

# Hardware acceleration
export AUTORENDER_HW_ACCEL=true

# RAM disk
export AUTORENDER_RAM_DISK=true

# High VRAM mode
export AUTORENDER_HIGH_VRAM=true
```

---

## Code Migration Examples

### Batch Queue Usage

**Old (0.x):**
```python
from video_renderer.batch import BatchQueue, RenderJob

queue = BatchQueue()
job = RenderJob(
    intro_path="intro.mp4",
    loop_path="loop.mp4",
    duration=36000
)
queue.add_job(job)
```

**New (1.0.0):**
```python
from video_renderer.batch import BatchQueue, RenderJob
from video_renderer.config import get_render_config

queue = BatchQueue(render_config=get_render_config("standard"))
job = RenderJob(
    mode="intro_loop",
    intro_path=Path("intro.mp4"),
    loop_path=Path("loop.mp4"),
    target_duration=36000
)
queue.add_job(job)
```

### Video Encoder Usage

**Old (0.x):**
```python
from video_renderer.video import VideoEncoder

encoder = VideoEncoder(codec="h264")
result = encoder.encode(video_path)
```

**New (1.0.0):**
```python
from video_renderer.video import VideoEncoder
from video_renderer.config import get_best_encoder

codec_config = get_best_encoder("h264")
encoder = VideoEncoder(codec_config=codec_config)
result = encoder.encode(video_path)
```

### Audio Processor Usage

**Old (0.x):**
```python
from video_renderer.audio import AudioProcessor

processor = AudioProcessor()
audio = processor.create_loop(tracks, duration)
```

**New (1.0.0):**
```python
from video_renderer.audio import AudioProcessor

processor = AudioProcessor()
audio = processor.create_music_loop(
    tracks=tracks,
    target_duration=duration,
    output=Path("output.w64")
)
```

---

## Testing Your Migration

After migrating, verify your setup:

### 1. Health Check
```bash
python -m video_renderer --health-check
```

### 2. Hardware Detection
```bash
python -m video_renderer --list-hw
```

### 3. Test Render
```bash
python -m video_renderer --test-render
```

### 4. Config Validation
```bash
python -m video_renderer --validate-config
```

---

## Rollback Procedure

If you encounter issues after migration:

### 1. Backup New State
```bash
cp tmp/batch_queue.json tmp/batch_queue.json.bak
cp tmp/last_session.json tmp/last_session.json.bak
```

### 2. Restore Old Version
```bash
git checkout <previous-version-tag>
```

### 3. Restore Old State
```bash
cp tmp/batch_queue.json.bak tmp/batch_queue.json
cp tmp/last_session.json.bak tmp/last_session.json
```

### 4. Report Issues
Include:
- Old version number
- New version number
- Error messages
- Configuration files (sanitized)

---

## Common Migration Issues

### Issue: "Module not found: video_renderer_ramtest"

**Solution:** Update imports and use mode flags instead.

```python
# Old
from video_renderer_ramtest.config import RamTestConfig

# New
from video_renderer.config import get_render_config
config = get_render_config("ramtest")
```

### Issue: "Invalid config file format"

**Solution:** Run the config migration tool.

```bash
python -m video_renderer --migrate-config
```

### Issue: "State file version mismatch"

**Solution:** Delete state files and let them regenerate.

```bash
rm tmp/batch_queue.json
rm tmp/last_session.json
```

**Warning:** This clears your batch queue. Export it first if needed.

### Issue: "Hardware encoder not detected"

**Solution:** Run detection with cache refresh.

```bash
python -m video_renderer --list-hw --refresh-cache
```

---

## Next Steps

After migration:

1. **Review new features** in [CHANGELOG.md](CHANGELOG.md)
2. **Update configuration** for your use case
3. **Test with sample videos** before production use
4. **Monitor performance** with new metrics
5. **Update automation scripts** with new CLI flags

---

## Need Help?

- **Documentation:** See [docs/](INDEX.md)
- **Issues:** [GitHub Issues](https://github.com/ahmetcemkaraca/AutoVideo/issues)
- **Discussions:** [GitHub Discussions](https://github.com/ahmetcemkaraca/AutoVideo/discussions)

---

**Last Updated:** 2025-02-06
**Version:** 1.0.0

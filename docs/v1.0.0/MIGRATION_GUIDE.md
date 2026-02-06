# AutoVideo v1.0.0 - Migration Guide
**Version**: 1.0.0
**Last Updated**: 2025-02-06

---

## Table of Contents

1. [Overview](#overview)
2. [Pre-Migration Checklist](#pre-migration-checklist)
3. [Configuration Migration](#configuration-migration)
4. [Code Migration](#code-migration)
5. [Module Migration](#module-migration)
6. [Data Migration](#data-migration)
7. [Post-Migration Verification](#post-migration-verification)
8. [Rollback Plan](#rollback-plan)

---

## Overview

This guide helps you migrate from pre-1.0.0 versions to AutoVideo v1.0.0.

### Supported Migration Paths

- **0.9.x → 1.0.0**: Supported
- **0.8.x → 1.0.0**: Supported (via 0.9.x)
- **0.7.x and below**: Not supported (upgrade to 0.9.x first)

### Breaking Changes Summary

| Area | Change | Impact |
|------|--------|--------|
| Config | Nested structure | Medium |
| CLI | New flag names | Low |
| Module | Ramtest merged | Low |
| API | Some deprecated | Medium |

---

## Pre-Migration Checklist

### 1. Backup Your Data

```bash
# Backup entire project
cp -r AutoVideo AutoVideo_backup_$(date +%Y%m%d)

# Backup configuration
cp config.json config.json.backup

# Backup state files
cp tmp/last_session.json tmp/last_session.json.backup
cp tmp/batch_queue.json tmp/batch_queue.json.backup
```

### 2. Note Your Current Settings

Document your current configuration:

```bash
# Export current settings
python -m video_renderer --show-config > current_config.txt

# List installed packages
pip freeze > requirements_backup.txt
```

### 3. Check Dependencies

```bash
# Verify Python version (requires 3.10+)
python --version

# Check FFmpeg
ffmpeg -version
```

### 4. Stop Running Processes

```bash
# Stop any running renders
pkill -f video_renderer

# Stop automation if running
pkill -f run_automation
```

---

## Configuration Migration

### Old Config Format (Pre-1.0.0)

```json
{
  "codec": "libx264",
  "preset": "medium",
  "crf": 23,
  "output_dir": "output",
  "temp_dir": "tmp",
  "hardware_acceleration": true,
  "audio_bitrate": "192k",
  "youtube_upload": true
}
```

### New Config Format (v1.0.0+)

```json
{
  "version": "1.0.0",
  "core": {
    "output_dir": "output",
    "temp_dir": "tmp",
    "log_level": "INFO"
  },
  "encoder": {
    "default_codec": "libx264",
    "preset": "medium",
    "crf": 23,
    "hardware_acceleration": true
  },
  "audio": {
    "bitrate": "192k"
  },
  "youtube": {
    "enabled": true
  }
}
```

### Automatic Migration

Run the migration tool:

```bash
python -m video_renderer --migrate-config
```

This will:
1. Backup your current config
2. Convert to new format
3. Validate new config
4. Report any issues

### Manual Migration

If automatic migration fails, migrate manually:

```json
{
  "version": "1.0.0",

  "core": {
    "output_dir": "<your_output_dir>",
    "temp_dir": "<your_temp_dir>",
    "archive_dir": "archive",
    "log_dir": "logs",
    "log_level": "INFO"
  },

  "encoder": {
    "default_codec": "<your_codec>",
    "preset": "<your_preset>",
    "crf": <your_crf>,
    "hardware_acceleration": <your_hw_setting>
  },

  "audio": {
    "codec": "aac",
    "bitrate": "<your_bitrate>",
    "sample_rate": 48000,
    "channels": 2
  },

  "duration": {
    "mode": "fixed",
    "target_hours": 8
  },

  "batch": {
    "max_concurrent": 1,
    "cleanup_temp": true
  }
}
```

---

## Code Migration

### Deprecated Imports

**Old** (pre-1.0.0):
```python
from video_renderer_ramtest import VideoEncoder
from video_renderer.config import get_best_encoder
```

**New** (v1.0.0+):
```python
from video_renderer import VideoEncoder
from video_renderer.config import get_best_encoder

# For ramtest mode, use flag instead:
# python -m video_renderer --ramtest
```

### API Changes

#### VideoEncoder

**Old**:
```python
encoder = VideoEncoder(codec="libx264", preset="medium")
result = encoder.encode_video("input.mp4", "output.mp4")
```

**New** (same interface, but ramtest via config):
```python
from video_renderer.config import RamTestConfig, RenderConfig

# Standard mode
config = RenderConfig(codec="libx264", preset="medium")
encoder = VideoEncoder(config)

# Ramtest mode
ramtest_config = RamTestConfig(enabled=True)
config = RenderConfig(codec="libx264", ramtest_config=ramtest_config)
encoder = VideoEncoder(config)
```

#### BatchQueue

**Old**:
```python
queue = BatchQueue()
queue.add_job(job)
```

**New** (same interface):
```python
queue = BatchQueue()
queue.add_job(job)  # No changes needed
```

### CLI Flag Changes

| Old Flag | New Flag | Equivalent |
|----------|----------|-------------|
| `--gpu` | `--hw-accel` | Enable hardware acceleration |
| `--youtube-upload` | `--youtube` | Enable YouTube upload |
| N/A | `--ramtest` / `--rm` | Enable ramtest mode |
| N/A | `--migrate-config` | Migrate config file |

---

## Module Migration

### video_renderer_ramtest → video_renderer

The `video_renderer_ramtest` module has been merged into `video_renderer`.

#### Old Usage

```bash
# Using separate ramtest module
python -m video_renderer_ramtest --tui
```

#### New Usage

```bash
# Using integrated ramtest mode
python -m video_renderer --ramtest --tui
# Or short form
python -m video_renderer --rm --tui
```

#### Code Changes

**Old**:
```python
from video_renderer_ramtest import VideoEncoder
from video_renderer_ramtest.config import RamTestConfig
```

**New**:
```python
from video_renderer import VideoEncoder
from video_renderer.config import RamTestConfig
```

### VideoAutomation

No major changes. Update imports if needed:

```python
# Old
from VideoAutomation.automation import pipeline

# New (same, but verify paths)
from VideoAutomation.automation.pipeline import AutomationPipeline
```

---

## Data Migration

### Session State Migration

If you have active sessions:

```bash
# Backup session state
cp tmp/last_session.json tmp/last_session.json.pre1.0
cp tmp/batch_queue.json tmp/batch_queue.json.pre1.0

# Migrate state (automatic on first run)
python -m video_renderer --resume
```

### Credential Migration

Google Drive and YouTube credentials remain compatible:

```bash
# Credentials are automatically reused
# No migration needed

# To re-authenticate (optional):
python -m video_renderer --auth-drive
python -m video_renderer --auth-youtube
```

### Archive Directory Migration

If using archive feature:

```bash
# Archive structure remains the same
# No migration needed

# Verify archive directory exists
ls -la archive/
```

---

## Post-Migration Verification

### 1. Configuration Validation

```bash
# Validate new config
python -m video_renderer --validate-config

# Show current config
python -m video_renderer --show-config
```

### 2. Health Check

```bash
# Run comprehensive health check
python -m video_renderer --health-check
```

Expected output:
```
✓ Python 3.10+ installed
✓ FFmpeg found in PATH
✓ All dependencies installed
✓ Configuration valid
✓ Hardware encoders detected
✓ Output directory writable
✓ Temp directory writable
```

### 3. Test Render

Run a test render to verify functionality:

```bash
# Use test videos
python -m video_renderer --tui
# Select a short video to test

# Or test with command line
python -m video_renderer \
  --intro test_intro.mp4 \
  --loop test_loop.mp4 \
  --duration 10m \
  --output test_output.mp4
```

### 4. Verify Batch Queue

```bash
# Test batch functionality
python -m video_renderer --batch

# Check queue persists
cat tmp/batch_queue.json
```

### 5. Test Cloud Integration (if used)

```bash
# Test Google Drive
python -m video_renderer --test-drive

# Test YouTube
python -m video_renderer --test-youtube
```

---

## Rollback Plan

If migration fails:

### 1. Restore Backup

```bash
# Restore entire project
rm -rf AutoVideo
mv AutoVideo_backup_$(date +%Y%m%d) AutoVideo

# Or restore specific files
cp config.json.backup config.json
cp tmp/last_session.json.backup tmp/last_session.json
```

### 2. Reinstall Old Version

```bash
# Checkout previous version
git checkout tags/v0.9.0

# Reinstall dependencies
pip install -r requirements.txt
pip install -e .
```

### 3. Verify Rollback

```bash
# Test old version
python -m video_renderer --version

# Verify functionality
python -m video_renderer --tui
```

---

## Common Migration Issues

### Issue: Config validation fails

**Symptoms**:
```
ValidationError: Configuration validation failed
```

**Solution**:
1. Check JSON syntax: `python -m json.tool config.json`
2. Compare with new config format
3. Use `--migrate-config` again
4. Contact support with config file

### Issue: Imports fail

**Symptoms**:
```
ModuleNotFoundError: No module named 'video_renderer_ramtest'
```

**Solution**:
1. Update imports to use `video_renderer`
2. Use `--ramtest` flag instead
3. Check [API Documentation](../internal-docs/api/video-renderer-api.md)

### Issue: Credentials not working

**Symptoms**:
```
AuthenticationError: Invalid credentials
```

**Solution**:
1. Credentials should work (no migration needed)
2. Re-authenticate if needed:
   ```bash
   rm youtube_credentials.json
   python -m video_renderer --auth-youtube
   ```

### Issue: Batch queue corrupted

**Symptoms**:
```
JSONDecodeError: Expecting value: line 1 column 1
```

**Solution**:
1. Restore backup:
   ```bash
   cp tmp/batch_queue.json.pre1.0 tmp/batch_queue.json
   ```
2. Or start fresh:
   ```bash
   rm tmp/batch_queue.json
   python -m video_renderer --batch
   ```

---

## Migration Checklist

Use this checklist to track your migration progress:

### Pre-Migration
- [ ] Backup entire project
- [ ] Backup configuration files
- [ ] Document current settings
- [ ] Verify Python version
- [ ] Verify FFmpeg installation
- [ ] Stop running processes

### Migration
- [ ] Update repository (`git pull`)
- [ ] Update dependencies (`pip install -r requirements.txt`)
- [ ] Migrate configuration (`--migrate-config`)
- [ ] Update code imports
- [ ] Update CLI flags

### Post-Migration
- [ ] Validate configuration
- [ ] Run health check
- [ ] Test render
- [ ] Test batch queue
- [ ] Test cloud integration
- [ ] Verify all features work

---

## Need Help?

### Resources

- [Installation Guide](INSTALLATION_GUIDE.md)
- [Configuration Reference](CONFIGURATION_REFERENCE.md)
- [Troubleshooting Guide](TROUBLESHOOTING_GUIDE.md)
- [API Documentation](../internal-docs/api/video-renderer-api.md)

### Support

- [GitHub Issues](https://github.com/ahmetcemkaraca/AutoVideo/issues)
- [GitHub Discussions](https://github.com/ahmetcemkaraca/AutoVideo/discussions)

### Getting Help

When requesting help, please include:
1. Pre-migration configuration
2. Migration command output
3. Error messages
4. System information (`--system-info`)

---

**Last Updated**: 2025-02-06
**Version**: 1.0.0

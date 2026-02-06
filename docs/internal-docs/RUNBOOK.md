# Operations Runbook

This runbook provides operational procedures for deploying, monitoring, and troubleshooting AutoVideo in production environments.

---

## Table of Contents

- [Deployment](#deployment)
- [Configuration](#configuration)
- [Monitoring](#monitoring)
- [Maintenance](#maintenance)
- [Troubleshooting](#troubleshooting)
- [Disaster Recovery](#disaster-recovery)

---

## Deployment

### Prerequisites

**System Requirements:**

- **OS:** Linux (Ubuntu 20.04+, Debian 11+, RHEL 8+), macOS 12+, Windows 10+
- **Python:** 3.10 or later
- **RAM:** 4GB minimum, 8GB+ recommended
- **Disk:** 10GB minimum, 50GB+ recommended
- **GPU:** NVIDIA GTX 10-series+, Intel 4th Gen+, or AMD GPU (optional)

**Software Requirements:**

```bash
# Check Python version
python --version  # Must be 3.10+

# Check FFmpeg
ffmpeg -version
ffprobe -version

# Check GPU drivers (if using hardware acceleration)
nvidia-smi  # NVIDIA
vainfo      # Intel/AMD Linux
```

### Installation

#### 1. System Preparation

**Linux (Ubuntu/Debian):**
```bash
# Update system
sudo apt update && sudo apt upgrade -y

# Install dependencies
sudo apt install -y python3.10 python3.10-venv ffmpeg
sudo apt install -y nvidia-driver-535  # For NVIDIA GPUs

# Install Intel media drivers (optional)
sudo apt install -y intel-media-va-driver-non-free
```

**macOS:**
```bash
# Install Homebrew if not installed
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

# Install dependencies
brew install python@3.10 ffmpeg
```

**Windows:**
1. Install Python 3.10+ from https://www.python.org/downloads/
2. Install FFmpeg from https://ffmpeg.org/download.html
3. Add Python and FFmpeg to PATH

#### 2. Application Installation

```bash
# Clone repository
git clone https://github.com/ahmetcemkaraca/AutoVideo.git
cd AutoVideo

# Create virtual environment
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Install dependencies
pip install --upgrade pip
pip install -r requirements.txt

# Install in development mode
pip install -e .

# Verify installation
python -m video_renderer --health-check
```

#### 3. Configuration

```bash
# Copy default config
mkdir -p ~/.config/autovideo
cp config.example.json ~/.config/autovideo/config.json

# Edit configuration
nano ~/.config/autovideo/config.json
```

**Production config example:**
```json
{
    "version": "1.0.0",
    "encoder": {
        "default_codec": "h264",
        "preset": "fast",
        "crf": 20
    },
    "render_mode": "standard",
    "batch": {
        "max_concurrent": 1,
        "auto_detect": true
    },
    "upload": {
        "enable_drive": false,
        "enable_youtube": false
    },
    "security": {
        "encrypt_credentials": true,
        "validate_permissions": true,
        "audit_log": true
    },
    "paths": {
        "tmp_dir": "/var/cache/autovideo/tmp",
        "music_dir": "/var/lib/autovideo/music",
        "output_dir": "/var/lib/autovideo/output"
    }
}
```

#### 4. Directory Setup

```bash
# Create directories
sudo mkdir -p /var/cache/autovideo/tmp
sudo mkdir -p /var/lib/autovideo/{music,output,archive}
sudo mkdir -p /var/log/autovideo

# Set permissions
sudo chown -R $USER:$USER /var/cache/autovideo
sudo chown -R $USER:$USER /var/lib/autovideo
sudo chown -R $USER:$USER /var/log/autovideo

# Set permissions for security
chmod 750 /var/lib/autovideo
chmod 700 ~/.config/autovideo
```

#### 5. Service Setup (Linux)

**Create systemd service:**

```bash
sudo nano /etc/systemd/system/autovideo.service
```

**Service file:**
```ini
[Unit]
Description=AutoVideo Rendering Service
After=network.target

[Service]
Type=simple
User=autovideo
Group=autovideo
WorkingDirectory=/opt/AutoVideo
Environment="PATH=/opt/AutoVideo/venv/bin:/usr/bin:/bin"
Environment="AUTORENDER_MODE=standard"
Environment="AUTORENDER_LOG_LEVEL=INFO"
ExecStart=/opt/AutoVideo/venv/bin/python -m video_renderer --tui
Restart=on-failure
RestartSec=10

[Install]
WantedBy=multi-user.target
```

**Enable and start service:**
```bash
# Reload systemd
sudo systemctl daemon-reload

# Enable service
sudo systemctl enable autovideo

# Start service
sudo systemctl start autovideo

# Check status
sudo systemctl status autovideo
```

---

## Configuration

### Environment Variables

**Production Environment Variables:**

```bash
# Render configuration
export AUTORENDER_MODE=standard
export AUTORENDER_HW_ACCEL=true
export AUTORENDER_LOG_LEVEL=INFO

# Paths
export AUTORENDER_TMP_DIR=/var/cache/autovideo/tmp
export AUTORENDER_MUSIC_DIR=/var/lib/autovideo/music
export AUTORENDER_OUTPUT_DIR=/var/lib/autovideo/output

# Security
export AUTORENDER_ENCRYPT_CREDS=true
export AUTORENDER_AUDIT_LOG=true
export AUTORENDER_CREDS_PATH=/etc/autovideo/credentials.json

# Upload
export AUTORENDER_ENABLE_DRIVE=false
export AUTORENDER_ENABLE_YOUTUBE=false
```

**Environment file (/etc/default/autovideo):**
```bash
# AutoVideo Configuration
AUTORENDER_MODE=standard
AUTORENDER_HW_ACCEL=true
AUTORENDER_LOG_LEVEL=INFO
AUTORENDER_TMP_DIR=/var/cache/autovideo/tmp
AUTORENDER_OUTPUT_DIR=/var/lib/autovideo/output
```

### Config Management

**Update configuration:**
```bash
# Edit config
nano ~/.config/autovideo/config.json

# Validate config
python -m video_renderer --validate-config

# Reload service (if running)
sudo systemctl reload autovideo
```

**Configuration backup:**
```bash
# Backup config
cp ~/.config/autovideo/config.json ~/.config/autovideo/config.json.bak

# Restore config
cp ~/.config/autovideo/config.json.bak ~/.config/autovideo/config.json
```

---

## Monitoring

### Logging

**Log Locations:**

- **Main log:** `/var/log/autovideo/app.log`
- **Audit log:** `/var/log/autovideo/audit.log`
- **Error log:** `/var/log/autovideo/error.log`
- **FFmpeg log:** `tmp/ffmpeg.log`

**Log rotation (/etc/logrotate.d/autovideo):**
```
/var/log/autovideo/*.log {
    daily
    rotate 14
    compress
    delaycompress
    missingok
    notifempty
    create 0640 autovideo autovideo
    sharedscripts
    postrotate
        systemctl reload autovideo > /dev/null 2>&1 || true
    endscript
}
```

**View logs:**
```bash
# Follow main log
tail -f /var/log/autovideo/app.log

# View error log
tail -f /var/log/autovideo/error.log

# Search logs
grep "ERROR" /var/log/autovideo/app.log

# View audit log
tail -f /var/log/autovideo/audit.log
```

### Metrics

**System Metrics:**

Monitor these metrics for health:

1. **CPU Usage:**
   ```bash
   top -b -n 1 | grep python
   ```

2. **Memory Usage:**
   ```bash
   ps aux | grep python | awk '{sum+=$4} END {print sum"%"}'
   ```

3. **Disk Usage:**
   ```bash
   df -h /var/cache/autovideo
   df -h /var/lib/autovideo
   ```

4. **GPU Usage:**
   ```bash
   nvidia-smi  # NVIDIA
   ```

5. **Process Status:**
   ```bash
   systemctl status autovideo
   ```

**Application Metrics:**

- Active render jobs
- Queue size
- Success/failure rate
- Average render time
- Hardware encoder utilization

**Collect metrics:**
```bash
python -m video_renderer --stats
```

### Health Checks

**Basic health check:**
```bash
python -m video_renderer --health-check
```

**Comprehensive health check script:**
```bash
#!/bin/bash
# health-check.sh

echo "AutoVideo Health Check"
echo "====================="

# Check service
if systemctl is-active --quiet autovideo; then
    echo "✓ Service is running"
else
    echo "✗ Service is not running"
    exit 1
fi

# Check Python
python_version=$(python --version 2>&1 | awk '{print $2}')
echo "Python version: $python_version"

# Check FFmpeg
if command -v ffmpeg &> /dev/null; then
    echo "✓ FFmpeg is installed"
else
    echo "✗ FFmpeg is not installed"
    exit 1
fi

# Check disk space
disk_usage=$(df /var/cache/autovideo | tail -1 | awk '{print $5}' | sed 's/%//')
if [ $disk_usage -lt 80 ]; then
    echo "✓ Disk usage: ${disk_usage}%"
else
    echo "✗ Disk usage high: ${disk_usage}%"
fi

# Check hardware encoders
python -m video_renderer --list-hw

echo "Health check complete"
```

**Schedule health checks (cron):**
```bash
# Add to crontab
crontab -e

# Run every hour
0 * * * * /opt/AutoVideo/scripts/health-check.sh >> /var/log/autovideo/health.log 2>&1
```

---

## Maintenance

### Regular Tasks

**Daily:**
- Check error logs
- Verify disk space
- Monitor render queue

**Weekly:**
- Review audit logs
- Check for updates
- Clean temporary files

**Monthly:**
- Review and rotate logs
- Update dependencies
- Performance analysis

### Cleanup

**Clean temporary files:**
```bash
# Clean tmp directory
rm -rf /var/cache/autovideo/tmp/*

# Clean old logs
find /var/log/autovideo -name "*.log.*" -mtime +30 -delete

# Clean archived sources
find /var/lib/autovideo/archive -type f -mtime +90 -delete
```

**Automated cleanup script:**
```bash
#!/bin/bash
# cleanup.sh

# Clean tmp files older than 1 day
find /var/cache/autovideo/tmp -type f -mtime +1 -delete

# Clean old logs
find /var/log/autovideo -name "*.log.*" -mtime +30 -delete

# Clean archives
find /var/lib/autovideo/archive -type f -mtime +90 -delete

echo "Cleanup complete"
```

### Updates

**Update AutoVideo:**
```bash
# Stop service
sudo systemctl stop autovideo

# Update repository
cd /opt/AutoVideo
git pull origin master

# Update dependencies
source venv/bin/activate
pip install --upgrade -r requirements.txt

# Restart service
sudo systemctl start autovideo

# Verify
python -m video_renderer --health-check
```

**Update dependencies:**
```bash
# Check for updates
pip list --outdated

# Update specific package
pip install --upgrade textual

# Update all dependencies
pip install --upgrade -r requirements.txt
```

---

## Troubleshooting

### Common Issues

#### Service Not Starting

**Check service status:**
```bash
sudo systemctl status autovideo
```

**Check logs:**
```bash
sudo journalctl -u autovideo -n 50
```

**Common solutions:**
```bash
# Fix permissions
sudo chown -R autovideo:autovideo /var/cache/autovideo
sudo chown -R autovideo:autovideo /var/lib/autovideo

# Fix configuration
python -m video_renderer --validate-config

# Reinstall dependencies
pip install --upgrade -r requirements.txt
```

#### High Memory Usage

**Identify process:**
```bash
ps aux | grep python
```

**Solutions:**
```bash
# Restart service
sudo systemctl restart autovideo

# Use memory-optimized mode
export AUTORENDER_MODE=ramtest

# Reduce concurrent jobs
export AUTORENDER_MAX_CONCURRENT=1
```

#### Slow Rendering

**Check hardware acceleration:**
```bash
python -m video_renderer --list-hw
```

**Solutions:**
```bash
# Ensure hardware acceleration is enabled
export AUTORENDER_HW_ACCEL=true

# Use faster preset
export AUTORENDER_PRESET=fast

# Check GPU usage
nvidia-smi
```

#### Upload Failures

**Check authentication:**
```bash
python -m video_renderer --auth-youtube
python -m video_renderer --auth-drive
```

**Check network:**
```bash
ping youtube.com
ping drive.google.com
```

### Debug Mode

**Enable debug logging:**
```bash
export AUTORENDER_LOG_LEVEL=DEBUG
sudo systemctl restart autovideo
```

**Run with verbose output:**
```bash
python -m video_renderer --tui --verbose --debug
```

**Generate debug report:**
```bash
python -m video_renderer --debug-report > debug_report.txt
```

---

## Disaster Recovery

### Backup Strategy

**Backup locations:**
- Configuration: `~/.config/autovideo/`
- Music files: `/var/lib/autovideo/music`
- Output videos: `/var/lib/autovideo/output`
- Credentials: `/etc/autovideo/credentials.json` (if using custom location)

**Backup script:**
```bash
#!/bin/bash
# backup.sh

BACKUP_DIR="/backup/autovideo/$(date +%Y%m%d)"
mkdir -p "$BACKUP_DIR"

# Backup configuration
cp -r ~/.config/autovideo "$BACKUP_DIR/config"

# Backup music files
cp -r /var/lib/autovideo/music "$BACKUP_DIR/music"

# Backup credentials (encrypted)
cp /etc/autovideo/credentials.json "$BACKUP_DIR/credentials.json.enc"

# Backup logs
cp -r /var/log/autovideo "$BACKUP_DIR/logs"

echo "Backup complete: $BACKUP_DIR"
```

**Automated backup (cron):**
```bash
# Daily backup at 2 AM
0 2 * * * /opt/AutoVideo/scripts/backup.sh
```

### Restore Procedure

**Restore from backup:**
```bash
# Stop service
sudo systemctl stop autovideo

# Restore configuration
cp -r /backup/autovideo/20250206/config/* ~/.config/autovideo/

# Restore music files
cp -r /backup/autovideo/20250206/music/* /var/lib/autovideo/music/

# Restore credentials
cp /backup/autovideo/20250206/credentials.json.enc /etc/autovideo/credentials.json

# Start service
sudo systemctl start autovideo
```

### Recovery Scenarios

#### Corrupted Configuration

```bash
# Restore from backup
cp ~/.config/autovideo/config.json.bak ~/.config/autovideo/config.json

# Or recreate from default
cp config.example.json ~/.config/autovideo/config.json
```

#### Lost Credentials

```bash
# Re-authenticate
python -m video_renderer --auth-youtube
python -m video_renderer --auth-drive
```

#### Data Loss

```bash
# Restore from backup
cp -r /backup/autovideo/20250206/music/* /var/lib/autovideo/music/
cp -r /backup/autovideo/20250206/output/* /var/lib/autovideo/output/
```

---

## Security

### Access Control

**File permissions:**
```bash
# Secure config directory
chmod 700 ~/.config/autovideo
chmod 600 ~/.config/autovideo/config.json

# Secure credentials
chmod 600 /etc/autovideo/credentials.json

# Secure logs
chmod 640 /var/log/autovideo/*.log
```

**Service permissions:**
```bash
# Run as non-root user
sudo useradd -r -s /bin/false autovideo

# Set ownership
sudo chown -R autovideo:autovideo /var/cache/autovideo
sudo chown -R autovideo:autovideo /var/lib/autovideo
```

### Audit Logging

**Review audit logs:**
```bash
# View recent security events
tail -f /var/log/autovideo/audit.log

# Search for specific events
grep "AUTH_FAILURE" /var/log/autovideo/audit.log
grep "PATH_TRAVERSAL" /var/log/autovideo/audit.log
```

### Updates

**Security updates:**
```bash
# Update system
sudo apt update && sudo apt upgrade -y

# Update Python packages
pip install --upgrade -r requirements.txt

# Check for vulnerabilities
pip-audit
```

---

## Performance Tuning

### GPU Optimization

**For high-VRAM systems:**
```bash
export AUTORENDER_MODE=high_vram
```

**For memory-constrained systems:**
```bash
export AUTORENDER_MODE=ramtest
```

### I/O Optimization

**Use RAM disk (Linux):**
```bash
export AUTORENDER_MODE=ramdisk
```

**Use fast storage:**
```bash
export AUTORENDER_TMP_DIR=/mnt/ssd/autovideo_tmp
```

### Concurrent Processing

**Adjust concurrent jobs:**
```bash
export AUTORENDER_MAX_CONCURRENT=2  # For high-VRAM systems
export AUTORENDER_MAX_CONCURRENT=1  # For standard systems
```

---

## Contact & Support

**Internal Support:**
- Lead Architect: [Contact]
- Development Team: [Contact]

**External Resources:**
- Documentation: [docs/](../INDEX.md)
- Issues: [GitHub Issues](https://github.com/ahmetcemkaraca/AutoVideo/issues)
- Discussions: [GitHub Discussions](https://github.com/ahmetcemkaraca/AutoVideo/discussions)

---

**Last Updated:** 2025-02-06
**Version:** 1.0.0

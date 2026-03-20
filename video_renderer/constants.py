#!/usr/bin/env python3
"""
Constants for video renderer application.

This module contains all magic numbers and configuration constants
used throughout the video_renderer package. Grouped by functionality
for easy maintenance and discovery.
"""

# ═══════════════════════════════════════════════════════════════════════════════
# Video Resolution Constants
# ═══════════════════════════════════════════════════════════════════════════════

# Standard resolutions (width, height) tuples
RESOLUTION_1080P = (1920, 1080)
RESOLUTION_1440P = (2560, 1440)
RESOLUTION_2160P = (3840, 2160)

# Resolution mapping by name
RESOLUTIONS = {
    "1080p": RESOLUTION_1080P,
    "1440p": RESOLUTION_1440P,
    "2160p": RESOLUTION_2160P,
    "4k": RESOLUTION_2160P,
}

# Default resolution
DEFAULT_RESOLUTION = RESOLUTION_1080P
DEFAULT_WIDTH = 1920
DEFAULT_HEIGHT = 1080

# Resolution ranges
MIN_WIDTH = 100
MAX_WIDTH = 7680
MIN_HEIGHT = 100
MAX_HEIGHT = 4320

# ═══════════════════════════════════════════════════════════════════════════════
# Frame Rate Constants
# ═══════════════════════════════════════════════════════════════════════════════

# Standard frame rates (fps)
FPS_24 = 24
FPS_30 = 30
FPS_60 = 60

# Default frame rate
DEFAULT_FPS = FPS_60

# Allowed frame rates
ALLOWED_FPS = [FPS_24, FPS_30, FPS_60]

# ═══════════════════════════════════════════════════════════════════════════════
# Duration Constants
# ═══════════════════════════════════════════════════════════════════════════════

# Duration thresholds (in seconds)
DURATION_8_HOURS = 8 * 3600  # 28800 seconds
DURATION_9_HOURS = 9 * 3600  # 32400 seconds
DURATION_10_HOURS = 10 * 3600  # 36000 seconds

# Default batch duration range (min, max) in seconds
DEFAULT_BATCH_DURATION_MIN = DURATION_8_HOURS
DEFAULT_BATCH_DURATION_MAX = DURATION_10_HOURS

# Default single hour value for duration selection
DEFAULT_DURATION_HOURS = 8

# ═══════════════════════════════════════════════════════════════════════════════
# Audio Bitrate Constants
# ═══════════════════════════════════════════════════════════════════════════════

# Standard audio bitrates
AUDIO_BITRATE_128K = "128k"
AUDIO_BITRATE_192K = "192k"
AUDIO_BITRATE_256K = "256k"
AUDIO_BITRATE_320K = "320k"

# Default audio bitrate
DEFAULT_AUDIO_BITRATE = AUDIO_BITRATE_192K

# Allowed audio bitrates
ALLOWED_AUDIO_BITRATES = [
    AUDIO_BITRATE_128K,
    AUDIO_BITRATE_192K,
    AUDIO_BITRATE_256K,
    AUDIO_BITRATE_320K,
]

# ═══════════════════════════════════════════════════════════════════════════════
# Performance & Threading Constants
# ═══════════════════════════════════════════════════════════════════════════════

# CPU usage percentage threshold
DEFAULT_CPU_PERCENT = 75

# GPU thread count for encoding
DEFAULT_GPU_THREADS = 4

# Thread pool sizes
VIDEO_AUDIO_THREAD_POOL_SIZE = 2  # For parallel video/audio processing
BATCH_THREAD_POOL_SIZE = 4  # For batch operations

# ═══════════════════════════════════════════════════════════════════════════════
# Buffer & Cache Constants
# ═══════════════════════════════════════════════════════════════════════════════

# FFmpeg stderr buffer size
STDERR_BUFFER_SIZE = 100

# Rate limiting interval (seconds)
RATE_LIMIT_INTERVAL = 0.1  # 100ms

# Cache TTL (seconds)
CACHE_TTL_SECONDS = 300  # 5 minutes

# ═══════════════════════════════════════════════════════════════════════════════
# Audio Processing Constants
# ═══════════════════════════════════════════════════════════════════════════════

# Standard audio sample rate (Hz)
STANDARD_SAMPLE_RATE = 48000

# Default background gain (dB)
DEFAULT_BACKGROUND_GAIN_DB = -8.0

# Default background gain when parsed from filename fails
PARSE_BACKGROUND_GAIN_FALLBACK_DB = -13.0

# Audio normalization settings
AUDIO_NORMALIZATION_TARGET_BITRATE = 320000  # 320k for MP3
AUDIO_NORMALIZATION_TARGET_SAMPLE_RATE = 48000  # 48kHz

# ═══════════════════════════════════════════════════════════════════════════════
# File & Directory Constants
# ═══════════════════════════════════════════════════════════════════════════════

# Standard directory names
MUSIC_DIR_NAME = "music"
MUSIC_DIR_CAPITALIZED = "Music"
TMP_DIR_NAME = "tmp"
ARCHIVE_DIR_NAME = "archive"
BACKGROUND_DIR_NAME = "background"
OUTPUT_DIR_NAME = "output"

# Music directory candidates (case-insensitive)
MUSIC_DIR_CANDIDATES = [MUSIC_DIR_NAME, MUSIC_DIR_CAPITALIZED]

# Session file name
SESSION_FILE_NAME = "last_session.json"
BATCH_QUEUE_FILE_NAME = "batch_queue.json"

# Log file names
RUN_LOG_NAME = "run_log.txt"
ERROR_LOG_NAME = "error_log.txt"

# ═══════════════════════════════════════════════════════════════════════════════
# Scale Algorithm Constants
# ═══════════════════════════════════════════════════════════════════════════════

# FFmpeg scale algorithms
SCALE_ALGO_LANCZOS = "lanczos"
SCALE_ALGO_BICUBIC = "bicubic"
SCALE_ALGO_BILINEAR = "bilinear"
SCALE_ALGO_SPLINE = "spline"

# Default scale algorithm
DEFAULT_SCALE_ALGO = SCALE_ALGO_LANCZOS

# Allowed scale algorithms
ALLOWED_SCALE_ALGOS = [
    SCALE_ALGO_LANCZOS,
    SCALE_ALGO_BICUBIC,
    SCALE_ALGO_BILINEAR,
    SCALE_ALGO_SPLINE,
]

# ═══════════════════════════════════════════════════════════════════════════════
# Codec Constants
# ═══════════════════════════════════════════════════════════════════════════════

# Default codec family
DEFAULT_CODEC_FAMILY = "av1"

# ═══════════════════════════════════════════════════════════════════════════════
# Render Mode Constants
# ═══════════════════════════════════════════════════════════════════════════════

# Render modes
MODE_INTRO_LOOP = "intro_loop"
MODE_SINGLE = "single"
MODE_BATCH = "batch"
MODE_SMART_BATCH = "smart_batch"

# ═══════════════════════════════════════════════════════════════════════════════
# Post-Action Constants
# ═══════════════════════════════════════════════════════════════════════════════

# Post-render actions for source files
POST_ACTION_KEEP = "keep"
POST_ACTION_ARCHIVE = "archive"
POST_ACTION_DELETE = "delete"

# ═══════════════════════════════════════════════════════════════════════════════
# Smart Batch Detection Constants
# ═══════════════════════════════════════════════════════════════════════════════

# Intro/loop file patterns
INTRO_PATTERN_SUFFIXES = ["_intro", "-intro", "-int", "_int"]
LOOP_PATTERN_SUFFIXES = ["_loop", "-loop", "-lp", "_lp"]

# ═══════════════════════════════════════════════════════════════════════════════
# File Extension Constants
# ═══════════════════════════════════════════════════════════════════════════════

# Temporary file extensions
TEMP_VIDEO_EXT = ".mp4"
TEMP_AUDIO_EXT = ".w64"
TEMP_CONCAT_EXT = ".txt"

# ═══════════════════════════════════════════════════════════════════════════════
# Exported Constants
# ═══════════════════════════════════════════════════════════════════════════════

__all__ = [
    # Video Resolution
    "RESOLUTION_1080P",
    "RESOLUTION_1440P",
    "RESOLUTION_2160P",
    "RESOLUTIONS",
    "DEFAULT_RESOLUTION",
    "DEFAULT_WIDTH",
    "DEFAULT_HEIGHT",
    "MIN_WIDTH",
    "MAX_WIDTH",
    "MIN_HEIGHT",
    "MAX_HEIGHT",
    # Frame Rate
    "FPS_24",
    "FPS_30",
    "FPS_60",
    "DEFAULT_FPS",
    "ALLOWED_FPS",
    # Duration
    "DURATION_8_HOURS",
    "DURATION_9_HOURS",
    "DURATION_10_HOURS",
    "DEFAULT_BATCH_DURATION_MIN",
    "DEFAULT_BATCH_DURATION_MAX",
    "DEFAULT_DURATION_HOURS",
    # Audio Bitrate
    "AUDIO_BITRATE_128K",
    "AUDIO_BITRATE_192K",
    "AUDIO_BITRATE_256K",
    "AUDIO_BITRATE_320K",
    "DEFAULT_AUDIO_BITRATE",
    "ALLOWED_AUDIO_BITRATES",
    # Performance
    "DEFAULT_CPU_PERCENT",
    "DEFAULT_GPU_THREADS",
    "VIDEO_AUDIO_THREAD_POOL_SIZE",
    "BATCH_THREAD_POOL_SIZE",
    # Buffer & Cache
    "STDERR_BUFFER_SIZE",
    "RATE_LIMIT_INTERVAL",
    "CACHE_TTL_SECONDS",
    # Audio Processing
    "STANDARD_SAMPLE_RATE",
    "DEFAULT_BACKGROUND_GAIN_DB",
    "PARSE_BACKGROUND_GAIN_FALLBACK_DB",
    "AUDIO_NORMALIZATION_TARGET_BITRATE",
    "AUDIO_NORMALIZATION_TARGET_SAMPLE_RATE",
    # File & Directory
    "MUSIC_DIR_NAME",
    "MUSIC_DIR_CAPITALIZED",
    "TMP_DIR_NAME",
    "ARCHIVE_DIR_NAME",
    "BACKGROUND_DIR_NAME",
    "OUTPUT_DIR_NAME",
    "MUSIC_DIR_CANDIDATES",
    "SESSION_FILE_NAME",
    "BATCH_QUEUE_FILE_NAME",
    "RUN_LOG_NAME",
    "ERROR_LOG_NAME",
    # Scale Algorithm
    "SCALE_ALGO_LANCZOS",
    "SCALE_ALGO_BICUBIC",
    "SCALE_ALGO_BILINEAR",
    "SCALE_ALGO_SPLINE",
    "DEFAULT_SCALE_ALGO",
    "ALLOWED_SCALE_ALGOS",
    # Codec
    "DEFAULT_CODEC_FAMILY",
    # Render Mode
    "MODE_INTRO_LOOP",
    "MODE_SINGLE",
    "MODE_BATCH",
    "MODE_SMART_BATCH",
    # Post-Action
    "POST_ACTION_KEEP",
    "POST_ACTION_ARCHIVE",
    "POST_ACTION_DELETE",
    # Smart Batch
    "INTRO_PATTERN_SUFFIXES",
    "LOOP_PATTERN_SUFFIXES",
]

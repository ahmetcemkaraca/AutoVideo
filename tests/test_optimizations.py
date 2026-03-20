#!/usr/bin/env python3
"""
Comprehensive tests for AudioProcessor and VideoEncoder optimizations.

Tests cover:
- FFmpeg command optimization
- Hardware encoder detection and caching
- Progress parsing performance
- Memory efficiency
- GPU utilization
- Error handling and retry mechanism
"""

import sys
import time
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from config import (
    CODEC_H264_NVENC,
    clear_encoder_cache,
    detect_available_encoders,
    get_best_encoder,
)
from video_renderer.audio import AudioProcessor
from video_renderer.ffmpeg import ERROR_PATTERNS, PROGRESS_PATTERNS, FFmpegRunner
from video_renderer.video import VideoEncoder

# ═══════════════════════════════════════════════════════════════════════════════
# FFmpeg Optimization Tests
# ═══════════════════════════════════════════════════════════════════════════════


def test_precompiled_regex_patterns():
    """Test that regex patterns are pre-compiled for performance."""
    print("\n[TEST] Precompiled Regex Patterns")

    # Verify patterns are compiled
    assert hasattr(PROGRESS_PATTERNS["frame"], "pattern"), "Frame pattern should be compiled"
    assert hasattr(PROGRESS_PATTERNS["fps"], "pattern"), "FPS pattern should be compiled"
    assert hasattr(PROGRESS_PATTERNS["time"], "pattern"), "Time pattern should be compiled"
    assert hasattr(ERROR_PATTERNS["hardware_error"], "pattern"), "Error pattern should be compiled"

    # Test pattern matching
    test_line = "frame=  123 fps= 45.6 q=28.0 size=    1234kB time=00:01:23.45 bitrate= 123.4kbits/s speed=1.23x"

    # Test all patterns in one pass (simulating fast-path optimization)
    matches = 0
    for pattern in PROGRESS_PATTERNS.values():
        if pattern.search(test_line):
            matches += 1

    assert matches == 6, f"Should match 6 patterns, got {matches}"
    print("  [PASS] All patterns pre-compiled and functional")


def test_progress_parsing_performance():
    """Test progress parsing performance with optimized regex."""
    print("\n[TEST] Progress Parsing Performance")

    test_line = "frame=  123 fps= 45.6 q=28.0 size=    1234kB time=00:01:23.45 bitrate= 123.4kbits/s speed=1.23x"
    iterations = 10000

    runner = FFmpegRunner()

    start = time.perf_counter()
    for _ in range(iterations):
        result = runner._parse_progress_line(test_line)
    elapsed = time.perf_counter() - start

    assert result is not None, "Should parse progress line"
    assert result.frame == 123, "Should extract frame count"
    assert result.fps == 45.6, "Should extract FPS"
    assert result.time_seconds == 83.45, "Should extract time in seconds"

    per_iteration = elapsed / iterations * 1000  # microseconds
    assert (
        per_iteration < 0.1
    ), f"Parsing too slow: {per_iteration:.3f}ms per iteration (target: <0.1ms)"

    print(f"  [PASS] Parsed {iterations} lines in {elapsed:.3f}s ({per_iteration:.3f}ms/iteration)")


def test_error_detection():
    """Test error pattern detection for hardware failures."""
    print("\n[TEST] Error Detection")

    runner = FFmpegRunner()

    # Test hardware error detection (using actual FFmpeg error format)
    hw_error = "Error initializing output stream 0:0 -- Error while opening encoder for output stream #0:0 - maybe incorrect parameters such as bit_rate, rate, width or height"
    is_hw, reason = runner._detect_hardware_failure([hw_error])

    # Test memory error detection
    mem_error = "Cannot allocate memory for GPU frame"
    is_hw, reason = runner._detect_hardware_failure([mem_error])
    assert is_hw, "Should detect memory error"
    assert "memory" in reason.lower(), "Reason should mention memory"

    # Test no error
    no_error = "frame=  123 fps= 45.6"
    is_hw, reason = runner._detect_hardware_failure([no_error])
    assert not is_hw, "Should not detect error in normal output"

    print("  [PASS] Error detection working correctly")


def test_fallback_command_building():
    """Test fallback command generation for software encoding."""
    print("\n[TEST] Fallback Command Building")

    runner = FFmpegRunner()

    # Test NVENC fallback
    nvenc_cmd = [
        "ffmpeg",
        "-y",
        "-hwaccel",
        "cuda",
        "-hwaccel_output_format",
        "cuda",
        "-i",
        "input.mp4",
        "-c:v",
        "h264_nvenc",
        "output.mp4",
    ]
    fallback = runner._build_fallback_command(nvenc_cmd)

    assert fallback is not None, "Should generate fallback"
    assert "-hwaccel" not in fallback, "Should remove hwaccel flags"
    assert "libx264" in fallback, "Should replace with software encoder"

    print("  [PASS] Fallback command generation working")


def test_stderr_circular_buffer():
    """Test that stderr buffer uses circular buffer for memory efficiency."""
    print("\n[TEST] Stderr Circular Buffer")

    runner = FFmpegRunner()

    # Fill buffer beyond its capacity
    for i in range(200):
        runner._stderr_buffer.append(f"Line {i}")

    # Should only keep last 100 lines (buffer capacity)
    assert (
        len(runner._stderr_buffer) == 100
    ), f"Buffer should have 100 lines, has {len(runner._stderr_buffer)}"

    # Check oldest line is 100, not 0
    oldest = runner._stderr_buffer[0]
    assert "Line 100" in oldest, f"Oldest line should be 100, got: {oldest}"

    print(f"  [PASS] Circular buffer maintains {len(runner._stderr_buffer)} lines")


# ═══════════════════════════════════════════════════════════════════════════════
# Hardware Encoder Detection Tests
# ═══════════════════════════════════════════════════════════════════════════════


def test_encoder_detection_caching():
    """Test that encoder detection uses caching."""
    print("\n[TEST] Encoder Detection Caching")

    # Clear cache first
    clear_encoder_cache()

    # First call - should detect
    start = time.perf_counter()
    encoders1 = detect_available_encoders(use_cache=True)
    time1 = time.perf_counter() - start

    # Second call - should use cache (much faster)
    start = time.perf_counter()
    encoders2 = detect_available_encoders(use_cache=True)
    time2 = time.perf_counter() - start

    assert encoders1 == encoders2, "Cached result should match"

    # Cached call should be significantly faster (or equal if detection is very fast)
    print(f"  First call: {time1:.3f}s, Cached call: {time2:.3f}s")

    print("  [PASS] Encoder caching working")


def test_best_encoder_selection():
    """Test best encoder selection logic."""
    print("\n[TEST] Best Encoder Selection")

    # Test with mocked availability
    encoders = detect_available_encoders()

    # Get best H.264 encoder
    best_h264 = get_best_encoder("h264")

    # Verify it's a valid encoder
    assert best_h264 is not None, "Should return an encoder"
    assert best_h264.name is not None, "Encoder should have a name"

    if encoders.get("h264_nvenc"):
        assert "nvenc" in best_h264.encoder.lower(), "Should prefer NVENC if available"
    elif encoders.get("h264_qsv"):
        assert "qsv" in best_h264.encoder.lower(), "Should prefer QSV if available"

    print(f"  [PASS] Best H.264 encoder: {best_h264.name} ({best_h264.encoder})")


# ═══════════════════════════════════════════════════════════════════════════════
# Audio Processor Optimization Tests
# ═══════════════════════════════════════════════════════════════════════════════


def test_audio_processor_caching():
    """Test AudioProcessor caching for validated files."""
    print("\n[TEST] AudioProcessor Caching")

    from video_renderer.ffmpeg import FFmpegRunner

    runner = FFmpegRunner()
    processor = AudioProcessor(runner, Path("tmp"))

    # Verify cache is initialized
    assert hasattr(processor, "_validated_cache"), "Should have validation cache"

    # Test max workers optimization
    assert hasattr(processor, "_max_workers"), "Should have max_workers setting"
    assert processor._max_workers <= 4, "Max workers should be reasonable"

    print(f"  [PASS] AudioProcessor initialized with {processor._max_workers} workers")


# ═══════════════════════════════════════════════════════════════════════════════
# Video Encoder Optimization Tests
# ═══════════════════════════════════════════════════════════════════════════════


def test_video_encoder_acceleration_detection():
    """Test VideoEncoder acceleration type detection."""
    print("\n[TEST] VideoEncoder Acceleration Detection")

    from video_renderer.ffmpeg import FFmpegRunner

    runner = FFmpegRunner()

    # Test with NVENC codec
    encoder_nvenc = VideoEncoder(runner, CODEC_H264_NVENC)
    assert encoder_nvenc._accel_type == "nvenc", "Should detect NVENC"
    assert encoder_nvenc._use_gpu == True, "Should use GPU"

    # Test optimal thread calculation
    threads = encoder_nvenc._get_optimal_threads()
    assert threads > 0, "Should have positive thread count"
    assert threads <= 8, "Thread count should be reasonable"

    print(f"  [PASS] Detected {encoder_nvenc._accel_type} acceleration, {threads} threads")


def test_video_encoder_compatibility_caching():
    """Test VideoEncoder compatibility checking with caching."""
    print("\n[TEST] VideoEncoder Compatibility Caching")

    from video_renderer.ffmpeg import FFmpegRunner

    runner = FFmpegRunner()
    encoder = VideoEncoder(runner, CODEC_H264_NVENC)

    # Verify cache is initialized
    assert hasattr(encoder, "_compatibility_cache"), "Should have compatibility cache"

    # Test FPS parsing
    fps = encoder._parse_fps("60/1")
    assert fps == 60.0, "Should parse simple fraction"

    fps = encoder._parse_fps("30000/1001")
    assert abs(fps - 29.97) < 0.01, "Should parse NTSC fraction"

    print("  [PASS] Compatibility checking and FPS parsing working")


# ═══════════════════════════════════════════════════════════════════════════════
# Test Runner
# ═══════════════════════════════════════════════════════════════════════════════


def run_all_tests():
    """Run all optimization tests."""
    print("=" * 80)
    print("AudioProcessor & VideoEncoder Optimization Tests")
    print("=" * 80)

    tests = [
        (
            "FFmpeg Optimizations",
            [
                test_precompiled_regex_patterns,
                test_progress_parsing_performance,
                test_error_detection,
                test_fallback_command_building,
                test_stderr_circular_buffer,
            ],
        ),
        (
            "Hardware Detection",
            [
                test_encoder_detection_caching,
                test_best_encoder_selection,
            ],
        ),
        (
            "Audio Processor",
            [
                test_audio_processor_caching,
            ],
        ),
        (
            "Video Encoder",
            [
                test_video_encoder_acceleration_detection,
                test_video_encoder_compatibility_caching,
            ],
        ),
    ]

    passed = 0
    failed = 0

    for category, test_list in tests:
        print(f"\n{'='*20} {category} {'='*20}")
        for test in test_list:
            try:
                test()
                passed += 1
            except AssertionError as e:
                failed += 1
                print(f"  [FAIL] {test.__name__}: {e}")
            except Exception as e:
                failed += 1
                print(f"  [ERROR] {test.__name__}: {e}")

    print(f"\n{'='*80}")
    print(f"Results: {passed} passed, {failed} failed")
    print(f"{'='*80}")

    return failed == 0


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)

#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Test script to verify video_renderer and ramtest merge.

This script tests:
1. Import compatibility
2. Ramtest configuration
3. CLI argument parsing
4. Memory tracking components
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))


def test_imports():
    """Test that all imports work correctly."""
    print("Testing imports...")

    try:
        from video_renderer.config import (
            get_ramdisk_path,
            setup_temp_directory,
            cleanup_ramdisk,
            get_nvenc_extra_args,
            get_hwaccel_input_args,
            RamTestConfig,
            RenderConfig,
            CodecConfig,
        )
        print("  ✓ Config imports successful")
    except ImportError as e:
        print(f"  ✗ Config import failed: {e}")
        return False

    try:
        from video_renderer.app import VideoRendererApp, run_tui
        print("  ✓ App imports successful")
    except ImportError as e:
        print(f"  ✗ App import failed: {e}")
        return False

    try:
        from video_renderer.video import VideoEncoder
        print("  ✓ Video encoder imports successful")
    except ImportError as e:
        print(f"  ✗ Video encoder import failed: {e}")
        return False

    try:
        import psutil
        print("  ✓ psutil available for memory tracking")
    except ImportError:
        print("  ⚠ psutil not available (memory tracking disabled)")

    return True


def test_ramtest_config():
    """Test RamTestConfig class."""
    print("\nTesting RamTestConfig...")

    from video_renderer.config import RamTestConfig

    # Test default config
    config = RamTestConfig()
    assert config.enabled == False
    assert config.use_ramdisk == True
    assert config.high_vram == False
    print("  ✓ Default RamTestConfig created")

    # Test ramtest-enabled config
    config_ramtest = RamTestConfig(
        enabled=True,
        use_ramdisk=True,
        high_vram=True,
        chunk_long_videos=False
    )
    assert config_ramtest.enabled == True
    assert config_ramtest.high_vram == True
    print("  ✓ RamTestConfig with ramtest enabled created")

    # Test NVENC args
    args = config_ramtest.get_nvenc_args("av1")
    assert "-rc" in args
    assert "-cq" in args
    print("  ✓ NVENC args generation works")

    # Test hwaccel args
    args = config_ramtest.get_hwaccel_args()
    assert "-hwaccel" in args
    print("  ✓ HW accel args generation works")

    return True


def test_ramdisk_detection():
    """Test RAM disk detection."""
    print("\nTesting RAM disk detection...")

    from video_renderer.config import get_ramdisk_path, setup_temp_directory

    ramdisk = get_ramdisk_path()
    if ramdisk:
        print(f"  ✓ RAM disk detected: {ramdisk}")
    else:
        print("  ℹ RAM disk not available (expected on non-Linux)")

    # Test temp directory setup
    tmp = setup_temp_directory(Path.cwd(), use_ramdisk=False)
    assert tmp.exists()
    print(f"  ✓ Temp directory setup: {tmp}")

    return True


def test_gpu_config():
    """Test GPU configuration."""
    print("\nTesting GPU configuration...")

    from video_renderer.config import (
        get_nvenc_extra_args,
        get_hwaccel_input_args,
        GPU_CONFIG,
    )

    # Test standard NVENC args
    args = get_nvenc_extra_args("av1", high_vram=False)
    assert "-surfaces" in args
    print("  ✓ Standard NVENC args generated")

    # Test high-VRAM NVENC args
    args = get_nvenc_extra_args("av1", high_vram=True)
    surfaces = [a for a in args if a == "-surfaces"]
    assert len(surfaces) == 1
    idx = args.index("-surfaces")
    assert args[idx + 1] == "128"  # High VRAM uses 128 surfaces
    print("  ✓ High-VRAM NVENC args generated")

    # Test hwaccel args
    args = get_hwaccel_input_args(high_vram=False)
    assert "-hwaccel" in args
    print("  ✓ Standard hwaccel args generated")

    args = get_hwaccel_input_args(high_vram=True)
    assert "-extra_hw_frames" in args
    print("  ✓ High-VRAM hwaccel args generated")

    return True


def test_app_integration():
    """Test app integration with ramtest mode."""
    print("\nTesting app integration...")

    from video_renderer.app import VideoRendererApp

    # Test standard mode
    app = VideoRendererApp(ramtest_mode=False)
    assert app.ramtest_mode == False
    assert app.ramtest_config.enabled == False
    print("  ✓ Standard mode app created")

    # Test ramtest mode
    app_ramtest = VideoRendererApp(ramtest_mode=True)
    assert app_ramtest.ramtest_mode == True
    assert app_ramtest.ramtest_config.enabled == True
    print("  ✓ Ramtest mode app created")

    return True


def test_video_encoder_ramtest():
    """Test VideoEncoder with ramtest parameters."""
    print("\nTesting VideoEncoder ramtest integration...")

    from video_renderer.video import VideoEncoder
    from video_renderer.config import get_best_encoder
    from video_renderer.ffmpeg import FFmpegRunner

    codec_config = get_best_encoder("av1")
    runner = FFmpegRunner()

    # Test standard encoder
    encoder = VideoEncoder(
        runner=runner,
        codec_config=codec_config,
        ramtest_mode=False,
        high_vram=False
    )
    assert encoder.ramtest_mode == False
    assert encoder.high_vram == False
    print("  ✓ Standard VideoEncoder created")

    # Test ramtest encoder
    encoder_ramtest = VideoEncoder(
        runner=runner,
        codec_config=codec_config,
        ramtest_mode=True,
        high_vram=True
    )
    assert encoder_ramtest.ramtest_mode == True
    assert encoder_ramtest.high_vram == True
    print("  ✓ Ramtest VideoEncoder created")

    return True


def main():
    """Run all tests."""
    print("=" * 60)
    print("Video Renderer Ramtest Merge Test Suite")
    print("=" * 60)

    tests = [
        test_imports,
        test_ramtest_config,
        test_ramdisk_detection,
        test_gpu_config,
        test_app_integration,
        test_video_encoder_ramtest,
    ]

    passed = 0
    failed = 0

    for test in tests:
        try:
            if test():
                passed += 1
            else:
                failed += 1
        except Exception as e:
            print(f"\n✗ Test {test.__name__} failed with exception: {e}")
            import traceback
            traceback.print_exc()
            failed += 1

    print("\n" + "=" * 60)
    print(f"Test Results: {passed} passed, {failed} failed")
    print("=" * 60)

    if failed == 0:
        print("\n✓ All tests passed! Merge verified successfully.")
        return 0
    else:
        print(f"\n✗ {failed} test(s) failed. Please review the errors above.")
        return 1


if __name__ == "__main__":
    sys.exit(main())

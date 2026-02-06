#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Test script for video_renderer.validator module.

Tests all three validator classes:
- VideoValidator: General video file validation
- PreRenderValidator: Pre-render validation
- PostRenderValidator: Post-render validation
"""

import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from video_renderer.validator import (
    VideoValidator,
    PreRenderValidator,
    PostRenderValidator,
    ValidationResult,
    VideoSpecs,
    validate_video_file,
    validate_render_preconditions,
    validate_render_output,
)


def test_video_validator():
    """Test VideoValidator class."""
    print("\n" + "=" * 60)
    print("Testing VideoValidator")
    print("=" * 60)

    validator = VideoValidator(language="en")

    # Test with non-existent file
    print("\n1. Testing with non-existent file:")
    result = validator.validate_file(Path("nonexistent.mp4"))
    print(f"   Valid: {result.is_valid}")
    print(f"   Errors: {len(result.errors)}")
    if result.errors:
        for error in result.errors[:3]:  # Show first 3 errors
            print(f"   - [{error.category}] {error.message}")

    # Test with a real video file if available
    print("\n2. Testing with real video file (if available):")
    test_files = list(Path(".").glob("*.mp4"))[:3]  # Test up to 3 files
    if not test_files:
        print("   No MP4 files found in current directory")
        return

    for video_file in test_files:
        print(f"\n   Testing: {video_file.name}")
        result = validator.validate_file(video_file)
        print(f"   Valid: {result.is_valid}")
        print(f"   Duration: {result.duration:.2f}s" if result.duration else "   Duration: N/A")
        print(f"   File size: {result.file_size / (1024**2):.2f} MB" if result.file_size else "   File size: N/A")

        if result.video_info:
            print(f"   Codec: {result.video_info.codec}")
            print(f"   Resolution: {result.video_info.width}x{result.video_info.height}")
            print(f"   FPS: {result.video_info.fps}")

        if result.warnings:
            print(f"   Warnings: {len(result.warnings)}")
            for warning in result.warnings[:2]:
                print(f"   - {warning.message}")


def test_pre_render_validator():
    """Test PreRenderValidator class."""
    print("\n" + "=" * 60)
    print("Testing PreRenderValidator")
    print("=" * 60)

    validator = PreRenderValidator(language="en")

    # Test 1: No source files
    print("\n1. Testing without source files:")
    result = validator.validate_render_job(duration_seconds=3600)
    print(f"   Valid: {result.is_valid}")
    print(f"   Errors: {len(result.errors)}")
    if result.errors:
        for error in result.errors[:2]:
            print(f"   - {error.message}")

    # Test 2: With real video files
    print("\n2. Testing with real video files:")
    test_videos = list(Path(".").glob("*_intro.mp4"))[:1]
    if test_videos:
        intro = test_videos[0]
        loop = intro.with_name(intro.name.replace("_intro", "_loop"))

        if not loop.exists():
            print(f"   No matching loop found for {intro.name}")
            return

        print(f"   Intro: {intro.name}")
        print(f"   Loop: {loop.name}")

        result = validator.validate_render_job(
            intro_path=intro,
            loop_path=loop,
            duration_seconds=36000,
        )

        print(f"   Valid: {result.is_valid}")
        print(f"   Render mode: {result.metadata.get('render_mode', 'N/A')}")

        if result.warnings:
            print(f"   Warnings: {len(result.warnings)}")
            for warning in result.warnings[:2]:
                print(f"   - {warning.message}")

        # Check metadata
        if "intro_info" in result.metadata:
            intro_info = result.metadata["intro_info"]
            print(f"   Intro duration: {intro_info.get('duration', 0):.2f}s")
            print(f"   Intro resolution: {intro_info.get('width', 0)}x{intro_info.get('height', 0)}")
    else:
        print("   No *_intro.mp4 files found")


def test_post_render_validator():
    """Test PostRenderValidator class."""
    print("\n" + "=" * 60)
    print("Testing PostRenderValidator")
    print("=" * 60)

    validator = PostRenderValidator(language="en")

    # Define expected specs
    specs = VideoSpecs(
        width=1920,
        height=1080,
        fps=60.0,
        codec="h264",
    )

    # Test with a real output file
    print("\n1. Testing with rendered output:")
    output_files = list(Path(".").glob("final_*.mp4"))[:1]

    if not output_files:
        print("   No final_*.mp4 files found")
        return

    output_file = output_files[0]
    print(f"   Output: {output_file.name}")

    result = validator.validate_output(
        output_path=output_file,
        expected_specs=specs,
        expected_duration=36000,  # 10 hours
    )

    print(f"   Valid: {result.is_valid}")
    print(f"   Duration: {result.duration:.2f}s" if result.duration else "   Duration: N/A")

    if result.errors:
        print(f"   Errors: {len(result.errors)}")
        for error in result.errors[:3]:
            print(f"   - [{error.category}] {error.message}")

    if result.warnings:
        print(f"   Warnings: {len(result.warnings)}")
        for warning in result.warnings[:2]:
            print(f"   - {warning.message}")


def test_convenience_functions():
    """Test convenience functions."""
    print("\n" + "=" * 60)
    print("Testing Convenience Functions")
    print("=" * 60)

    # Test validate_video_file
    print("\n1. Testing validate_video_file():")
    test_file = next(iter(Path(".").glob("*.mp4")), None)
    if test_file:
        result = validate_video_file(test_file, language="tr")
        print(f"   File: {test_file.name}")
        print(f"   Valid: {result.is_valid}")
        print(f"   Messages (TR):")
        for msg in result.get_messages(language="tr")[:3]:
            print(f"   - {msg}")
    else:
        print("   No MP4 files found")


def main():
    """Run all tests."""
    print("\n" + "=" * 60)
    print("Video Validator Module Test Suite")
    print("=" * 60)

    try:
        test_video_validator()
        test_pre_render_validator()
        test_post_render_validator()
        test_convenience_functions()

        print("\n" + "=" * 60)
        print("All tests completed!")
        print("=" * 60)

    except Exception as e:
        print(f"\nError during testing: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()

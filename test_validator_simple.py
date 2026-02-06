#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Simple test for video_renderer.validator module.

Tests the key functionality of the validator classes.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from video_renderer.validator import (
    VideoValidator,
    PreRenderValidator,
    PostRenderValidator,
    VideoMetadata,
    ValidationResult,
    ValidationSeverity,
    validate_ffmpeg_available,
    quick_validate,
)


def print_header(text):
    print("\n" + "=" * 70)
    print(f"  {text}")
    print("=" * 70)


def test_ffmpeg_availability():
    """Test FFmpeg availability check."""
    print_header("Testing FFmpeg Availability")

    result = validate_ffmpeg_available()

    print(f"\nFFmpeg/FFprobe Available: {result.valid}")
    print(f"Stage: {result.stage}")
    print(f"Issues: {len(result.issues)}")

    if result.issues:
        for issue in result.issues:
            print(f"  - [{issue.severity.value}] {issue.message}")


def test_video_validator():
    """Test VideoValidator class."""
    print_header("Testing VideoValidator")

    validator = VideoValidator()

    print(f"\nFFprobe Available: {validator.is_ffprobe_available()}")

    # Test with non-existent file
    print("\n1. Testing with non-existent file:")
    try:
        metadata = validator.get_video_info(Path("nonexistent.mp4"))
        print(f"   Unexpected: Got metadata")
    except FileNotFoundError:
        print("   Expected: FileNotFoundError raised")
    except Exception as e:
        print(f"   Error: {type(e).__name__}: {e}")

    # Test checking capabilities
    print("\n2. Testing check methods:")

    # These should work even with non-existent files (return False)
    print(f"   check_duration (nonexistent): {validator.check_duration(Path('test.mp4'), 10)}")
    print(f"   check_codec (nonexistent): {validator.check_codec(Path('test.mp4'), 'h264')}")
    print(f"   check_resolution (nonexistent): {validator.check_resolution(Path('test.mp4'), (1920, 1080))}")
    print(f"   check_fps (nonexistent): {validator.check_fps(Path('test.mp4'), 60)}")
    print(f"   check_audio (nonexistent): {validator.check_audio(Path('test.mp4'), True)}")
    print(f"   check_file_integrity (nonexistent): {validator.check_file_integrity(Path('test.mp4'))}")

    # Test validate_output with empty specs
    print("\n3. Testing validate_output with empty specs:")
    result = validator.validate_output(Path("test.mp4"), {})
    print(f"   Valid: {result.valid}")
    print(f"   Stage: {result.stage}")
    print(f"   Errors: {len(result.errors)}")
    if result.errors:
        for error in result.errors[:2]:
            print(f"   - [{error.category}] {error.message}")


def test_pre_render_validator():
    """Test PreRenderValidator class."""
    print_header("Testing PreRenderValidator")

    validator = PreRenderValidator(
        target_width=1920,
        target_height=1080,
        target_fps=60
    )

    # Test with no source files
    print("\n1. Testing without source files:")
    result = validator.validate_render_specs(
        intro_path=None,
        loop_path=None,
        single_path=None,
        tracks=[],
        target_duration=3600,
        output_dir=Path(".")
    )

    print(f"   Valid: {result.valid}")
    print(f"   Stage: {result.stage}")
    print(f"   Total issues: {len(result.issues)}")
    print(f"   Errors: {len(result.errors)}")
    print(f"   Warnings: {len(result.warnings)}")

    if result.issues:
        print("\n   First few issues:")
        for issue in result.issues[:3]:
            print(f"   - [{issue.severity.value}] {issue.message}")
            if issue.details:
                print(f"     Details: {issue.details}")
            if issue.suggestion:
                print(f"     Suggestion: {issue.suggestion}")


def test_post_render_validator():
    """Test PostRenderValidator class."""
    print_header("Testing PostRenderValidator")

    validator = PostRenderValidator()

    # Test with non-existent file
    print("\n1. Testing with non-existent output:")
    result = validator.validate_output(
        output_path=Path("nonexistent.mp4"),
        target_duration=3600
    )

    print(f"   Valid: {result.valid}")
    print(f"   Stage: {result.stage}")
    print(f"   Issues: {len(result.issues)}")

    if result.issues:
        for issue in result.issues[:3]:
            print(f"   - [{issue.severity.value}] {issue.message}")
            if issue.suggestion:
                print(f"     Suggestion: {issue.suggestion}")


def test_validation_result():
    """Test ValidationResult class."""
    print_header("Testing ValidationResult")

    result = ValidationResult(valid=True, stage="test")

    # Add various issues
    result.add_error("video", "Test error EN", "Test error TR")
    result.add_warning("audio", "Test warning EN", "Test warning TR")
    result.add_info("codec", "Test info EN", "Test info TR")

    print(f"\nValid: {result.valid}")
    print(f"Errors: {len(result.errors)}")
    print(f"Warnings: {len(result.warnings)}")
    print(f"Info: {len(result.info)}")

    print("\nAll issues:")
    for issue in result.issues:
        print(f"  - [{issue.severity.value}] {issue.get_bilingual_message()}")

    print("\nTo dict:")
    data = result.to_dict()
    print(f"  Keys: {list(data.keys())}")


def main():
    """Run all tests."""
    print_header("Video Validator Module Test Suite")

    try:
        test_ffmpeg_availability()
        test_video_validator()
        test_pre_render_validator()
        test_post_render_validator()
        test_validation_result()

        print_header("All Tests Completed Successfully!")

    except Exception as e:
        print(f"\nError: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Test script for existing video_renderer.validator module.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from video_renderer.validator import (
    VideoValidator,
    PreRenderValidator,
    PostRenderValidator,
    ValidationResult,
    VideoMetadata,
    ValidationSeverity,
    validate_before_render,
    validate_after_render,
    quick_validate,
    validate_ffmpeg_available,
)


def print_separator(title=""):
    print("\n" + "=" * 70)
    if title:
        print(f"  {title}")
        print("=" * 70)


def test_video_validator():
    """Test VideoValidator class."""
    print_separator("Testing VideoValidator")

    validator = VideoValidator()

    # Check ffprobe availability
    print(f"\nFFprobe available: {VideoValidator.is_ffprobe_available()}")

    # Test with non-existent file
    print("\n1. Testing with non-existent file:")
    try:
        metadata = validator.get_video_info(Path("nonexistent.mp4"))
        print(f"   Unexpected success: {metadata}")
    except FileNotFoundError as e:
        print(f"   Expected error: {e}")
    except Exception as e:
        print(f"   Error: {e}")

    # Test with real video files
    print("\n2. Testing with real video files:")
    test_files = list(Path(".").glob("*.mp4"))[:3]

    if not test_files:
        print("   No MP4 files found in current directory")
        return

    for video_file in test_files:
        print(f"\n   File: {video_file.name}")

        try:
            metadata = validator.get_video_info(video_file)
            print(f"   Duration: {metadata.duration:.2f}s")
            print(f"   Codec: {metadata.codec}")
            print(f"   Resolution: {metadata.width}x{metadata.height}")
            print(f"   FPS: {float(metadata.fps):.2f}")
            print(f"   Has audio: {metadata.has_audio}")
            if metadata.has_audio:
                print(f"   Audio codec: {metadata.audio_codec}")
                print(f"   Audio channels: {metadata.audio_channels}")

        except Exception as e:
            print(f"   Error: {e}")


def test_pre_render_validator():
    """Test PreRenderValidator class."""
    print_separator("Testing PreRenderValidator")

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
        print("\n   Issues:")
        for issue in result.issues[:3]:
            print(f"   - [{issue.severity.value}] {issue.message}")
            if issue.details:
                print(f"     Details: {issue.details}")
            if issue.suggestion:
                print(f"     Suggestion: {issue.suggestion}")

    # Test with real intro/loop pair
    print("\n2. Testing with intro/loop pair:")
    intros = list(Path(".").glob("*_intro.mp4"))[:1]

    if not intros:
        print("   No *_intro.mp4 files found")
        return

    intro = intros[0]
    loop_name = intro.name.replace("_intro", "_loop")
    loop = intro.with_name(loop_name)

    if not loop.exists():
        print(f"   No matching loop found ({loop_name})")
        return

    print(f"   Intro: {intro.name}")
    print(f"   Loop: {loop.name}")

    result = validator.validate_render_specs(
        intro_path=intro,
        loop_path=loop,
        single_path=None,
        tracks=[],
        target_duration=28800,  # 8 hours
        output_dir=Path(".")
    )

    print(f"   Valid: {result.valid}")
    print(f"   Metadata keys: {list(result.metadata.keys())}")

    if result.issues:
        print(f"\n   Issues ({len(result.issues)}):")
        for issue in result.issues:
            print(f"   - [{issue.severity.value}] {issue.message}")


def test_post_render_validator():
    """Test PostRenderValidator class."""
    print_separator("Testing PostRenderValidator")

    validator = PostRenderValidator()

    # Test with non-existent file
    print("\n1. Testing with non-existent output:")
    result = validator.validate_output(
        output_path=Path("nonexistent_output.mp4"),
        target_duration=3600,
        target_specs={"codec": "h264", "width": 1920, "height": 1080, "fps": 60}
    )

    print(f"   Valid: {result.valid}")
    print(f"   Issues: {len(result.issues)}")

    if result.issues:
        for issue in result.issues:
            print(f"   - [{issue.severity.value}] {issue.message}")

    # Test with real output file
    print("\n2. Testing with real output file:")
    outputs = list(Path(".").glob("final_*.mp4"))[:1]

    if not outputs:
        print("   No final_*.mp4 files found")
        return

    output = outputs[0]
    print(f"   Output: {output.name}")

    target_specs = {
        "codec": "h264",
        "width": 1920,
        "height": 1080,
        "fps": 60
    }

    result = validator.validate_output(
        output_path=output,
        target_duration=28800,  # 8 hours
        target_specs=target_specs
    )

    print(f"   Valid: {result.valid}")
    print(f"   Duration: {result.duration_seconds:.2f}s")

    if result.metadata.get("output"):
        output_meta = result.metadata["output"]
        print(f"   Resolution: {output_meta.get('width')}x{output_meta.get('height')}")
        print(f"   FPS: {output_meta.get('fps_float', 0):.2f}")
        print(f"   Codec: {output_meta.get('codec')}")

    if result.issues:
        print(f"\n   Issues ({len(result.issues)}):")
        for issue in result.issues[:5]:
            print(f"   - [{issue.severity.value}] {issue.message}")
            if issue.details:
                print(f"     {issue.details}")


def test_convenience_functions():
    """Test convenience functions."""
    print_separator("Testing Convenience Functions")

    # Test quick_validate
    print("\n1. Testing quick_validate():")
    test_file = next(iter(Path(".").glob("*.mp4")), None)

    if test_file:
        print(f"   File: {test_file.name}")
        is_valid, message = quick_validate(test_file)
        print(f"   Valid: {is_valid}")
        print(f"   Message: {message}")
    else:
        print("   No MP4 files found")

    # Test validate_ffmpeg_available
    print("\n2. Testing validate_ffmpeg_available():")
    is_valid, message = validate_ffmpeg_available()
    print(f"   FFmpeg valid: {is_valid}")
    print(f"   Message: {message}")


def main():
    """Run all tests."""
    print_separator("Video Validator Module Test Suite")

    try:
        test_video_validator()
        test_pre_render_validator()
        test_post_render_validator()
        test_convenience_functions()

        print_separator("All tests completed!")

    except Exception as e:
        print(f"\nError during testing: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()

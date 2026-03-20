#!/usr/bin/env python3
"""
Unit tests for VideoEncoder class.

Tests cover:
- Video compatibility checking
- Video normalization
- Video concatenation
- Parallel encoding
- FPS parsing
- Codec name mapping
"""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from config import CODEC_H264, CODEC_H265, COLOR_BT709, CodecConfig
from video_renderer.ffmpeg import VideoInfo
from video_renderer.video import VideoEncoder, encode_parallel


@pytest.mark.unit
class TestVideoEncoder:
    """Test suite for VideoEncoder class."""

    def test_init(self, mock_ffmpeg_runner):
        """Test VideoEncoder initialization."""
        encoder = VideoEncoder(
            runner=mock_ffmpeg_runner,
            codec_config=CODEC_H264,
            color_config=COLOR_BT709,
            width=1920,
            height=1080,
            fps=60,
        )

        assert encoder.runner == mock_ffmpeg_runner
        assert encoder.codec == CODEC_H264
        assert encoder.color == COLOR_BT709
        assert encoder.width == 1920
        assert encoder.height == 1080
        assert encoder.fps == 60

    def test_parse_fps_simple(self, mock_ffmpeg_runner):
        """Test FPS parsing for simple values."""
        encoder = VideoEncoder(mock_ffmpeg_runner, CODEC_H264, COLOR_BT709)

        assert encoder._parse_fps("60") == 60.0
        assert encoder._parse_fps("30") == 30.0
        assert encoder._parse_fps("59.94") == 59.94

    def test_parse_fps_fraction(self, mock_ffmpeg_runner):
        """Test FPS parsing for fraction values."""
        encoder = VideoEncoder(mock_ffmpeg_runner, CODEC_H264, COLOR_BT709)

        assert encoder._parse_fps("60/1") == 60.0
        assert encoder._parse_fps("30000/1001") == pytest.approx(29.97, rel=0.01)
        assert encoder._parse_fps("24000/1001") == pytest.approx(23.98, rel=0.01)

    def test_parse_fps_invalid(self, mock_ffmpeg_runner):
        """Test FPS parsing for invalid values."""
        encoder = VideoEncoder(mock_ffmpeg_runner, CODEC_H264, COLOR_BT709)

        assert encoder._parse_fps("invalid") == 0.0
        assert encoder._parse_fps("10/0") == 0.0

    def test_get_expected_codec_name_h264(self, mock_ffmpeg_runner):
        """Test codec name mapping for H.264."""
        encoder = VideoEncoder(mock_ffmpeg_runner, CODEC_H264, COLOR_BT709)
        assert encoder._get_expected_codec_name() == "h264"

    def test_get_expected_codec_name_h265(self, mock_ffmpeg_runner):
        """Test codec name mapping for H.265."""
        encoder = VideoEncoder(mock_ffmpeg_runner, CODEC_H265, COLOR_BT709)
        assert encoder._get_expected_codec_name() == "hevc"

    def test_get_expected_codec_name_av1(self, mock_ffmpeg_runner):
        """Test codec name mapping for AV1."""
        from video_renderer.config import CODEC_AV1

        encoder = VideoEncoder(mock_ffmpeg_runner, CODEC_AV1, COLOR_BT709)
        assert encoder._get_expected_codec_name() == "av1"

    def test_get_expected_codec_name_unknown(self, mock_ffmpeg_runner):
        """Test codec name mapping for unknown codec."""
        unknown_codec = CodecConfig("Unknown", "unknown_encoder", "fast", 20)
        encoder = VideoEncoder(mock_ffmpeg_runner, unknown_codec, COLOR_BT709)
        assert encoder._get_expected_codec_name() == "unknown"

    @pytest.mark.parametrize(
        "compatible, reason",
        [
            (True, "Uyumlu"),
            (False, "Cozunurluk farkli: 1280x720 -> 1920x1080"),
            (False, "Codec farkli: hevc -> h264"),
            (False, "FPS farkli: 30.00 -> 60"),
            (False, "Pixel format uygun degil: yuv422p"),
        ],
    )
    def test_check_compatibility_scenarios(self, mock_ffmpeg_runner, compatible, reason):
        """Test compatibility checking for various scenarios."""
        encoder = VideoEncoder(
            mock_ffmpeg_runner, CODEC_H264, COLOR_BT709, width=1920, height=1080, fps=60
        )

        # Mock different video info scenarios
        with patch("video_renderer.video.probe_video") as mock_probe:
            if compatible:
                mock_probe.return_value = VideoInfo(
                    codec="h264",
                    width=1920,
                    height=1080,
                    fps="60/1",
                    duration=120.0,
                    pix_fmt="yuv420p",
                    color_space="bt709",
                )
            else:
                # Parse reason to determine what to mock
                if "Cozunurluk" in reason:
                    mock_probe.return_value = VideoInfo(
                        codec="h264",
                        width=1280,
                        height=720,
                        fps="60/1",
                        duration=120.0,
                        pix_fmt="yuv420p",
                        color_space="bt709",
                    )
                elif "Codec" in reason:
                    mock_probe.return_value = VideoInfo(
                        codec="hevc",
                        width=1920,
                        height=1080,
                        fps="60/1",
                        duration=120.0,
                        pix_fmt="yuv420p",
                        color_space="bt709",
                    )
                elif "FPS" in reason:
                    mock_probe.return_value = VideoInfo(
                        codec="h264",
                        width=1920,
                        height=1080,
                        fps="30/1",
                        duration=120.0,
                        pix_fmt="yuv420p",
                        color_space="bt709",
                    )
                elif "Pixel" in reason:
                    mock_probe.return_value = VideoInfo(
                        codec="h264",
                        width=1920,
                        height=1080,
                        fps="60/1",
                        duration=120.0,
                        pix_fmt="yuv422p",
                        color_space="bt709",
                    )

            is_compat, result_reason = encoder.check_compatibility(Path("test.mp4"))
            assert is_compat == compatible
            # Reason should match expected pattern

    def test_check_compatibility_error_handling(self, mock_ffmpeg_runner):
        """Test compatibility check handles probe errors."""
        encoder = VideoEncoder(mock_ffmpeg_runner, CODEC_H264, COLOR_BT709)

        with patch("video_renderer.video.probe_video") as mock_probe:
            mock_probe.side_effect = Exception("Probe error")

            is_compat, reason = encoder.check_compatibility(Path("test.mp4"))
            assert is_compat is False
            assert "Analiz hatasi" in reason

    def test_is_compatible_wrapper(self, mock_ffmpeg_runner):
        """Test is_compatible legacy wrapper."""
        encoder = VideoEncoder(mock_ffmpeg_runner, CODEC_H264, COLOR_BT709)

        with patch("video_renderer.video.probe_video") as mock_probe:
            mock_probe.return_value = VideoInfo(
                codec="h264",
                width=1920,
                height=1080,
                fps="60/1",
                duration=120.0,
                pix_fmt="yuv420p",
                color_space="bt709",
            )

            assert encoder.is_compatible(Path("test.mp4")) is True

    def test_normalize_video_direct_copy_compatible(self, mock_ffmpeg_runner, temp_dir):
        """Test normalize_video with direct copy for compatible video."""
        encoder = VideoEncoder(
            mock_ffmpeg_runner, CODEC_H264, COLOR_BT709, width=1920, height=1080, fps=60
        )

        source = temp_dir / "source.mp4"
        output = temp_dir / "output.mp4"
        source.touch()

        with patch("video_renderer.video.probe_video") as mock_probe:
            mock_probe.return_value = VideoInfo(
                codec="h264",
                width=1920,
                height=1080,
                fps="60/1",
                duration=120.0,
                pix_fmt="yuv420p",
                color_space="bt709",
            )
            with patch("video_renderer.video.get_duration") as mock_duration:
                mock_duration.return_value = 120.0

                result = encoder.normalize_video(source, output)

                assert result == output
                mock_ffmpeg_runner.run.assert_not_called()

    def test_normalize_video_re_encode_incompatible(self, mock_ffmpeg_runner, temp_dir):
        """Test normalize_video with re-encoding for incompatible video."""
        encoder = VideoEncoder(
            mock_ffmpeg_runner, CODEC_H264, COLOR_BT709, width=1920, height=1080, fps=60
        )

        source = temp_dir / "source.mp4"
        output = temp_dir / "output.mp4"
        source.touch()

        with patch("video_renderer.video.probe_video") as mock_probe:
            mock_probe.return_value = VideoInfo(
                codec="hevc",
                width=1920,
                height=1080,
                fps="60/1",
                duration=120.0,
                pix_fmt="yuv420p",
                color_space="bt709",
            )
            with patch("video_renderer.video.get_duration") as mock_duration:
                mock_duration.return_value = 120.0

                result = encoder.normalize_video(source, output)

                assert result == output
                mock_ffmpeg_runner.run.assert_called_once()

    def test_normalize_video_with_progress_callback(self, mock_ffmpeg_runner, temp_dir):
        """Test normalize_video with progress callback."""
        encoder = VideoEncoder(
            mock_ffmpeg_runner, CODEC_H264, COLOR_BT709, width=1920, height=1080, fps=60
        )

        source = temp_dir / "source.mp4"
        output = temp_dir / "output.mp4"
        source.touch()

        callback = MagicMock()

        with patch("video_renderer.video.probe_video") as mock_probe:
            mock_probe.return_value = VideoInfo(
                codec="hevc",
                width=1920,
                height=1080,
                fps="60/1",
                duration=120.0,
                pix_fmt="yuv420p",
                color_space="bt709",
            )
            with patch("video_renderer.video.get_duration") as mock_duration:
                mock_duration.return_value = 120.0

                result = encoder.normalize_video(source, output, callback)

                assert result == output
                mock_ffmpeg_runner.set_progress_callback.assert_called_once_with(callback)

    def test_normalize_video_nvenc_detection(self, mock_ffmpeg_runner, temp_dir):
        """Test normalize_video detects NVENC encoder."""
        from video_renderer.config import CODEC_H264_NVENC

        encoder = VideoEncoder(
            mock_ffmpeg_runner, CODEC_H264_NVENC, COLOR_BT709, width=1920, height=1080, fps=60
        )

        source = temp_dir / "source.mp4"
        output = temp_dir / "output.mp4"
        source.touch()

        with patch("video_renderer.video.probe_video") as mock_probe:
            mock_probe.return_value = VideoInfo(
                codec="hevc",
                width=1920,
                height=1080,
                fps="60/1",
                duration=120.0,
                pix_fmt="yuv420p",
                color_space="bt709",
            )
            with patch("video_renderer.video.get_duration") as mock_duration:
                mock_duration.return_value = 120.0

                result = encoder.normalize_video(source, output)

                # Verify hwaccel args in the call
                call_args = mock_ffmpeg_runner.run.call_args[0][0]
                assert "-hwaccel" in call_args
                assert "cuda" in call_args

    def test_concat_videos_basic(self, mock_ffmpeg_runner, temp_dir):
        """Test basic video concatenation."""
        encoder = VideoEncoder(mock_ffmpeg_runner, CODEC_H264, COLOR_BT709)

        intro = temp_dir / "intro.mp4"
        loop = temp_dir / "loop.mp4"
        intro.touch()
        loop.touch()

        with patch("video_renderer.video.get_duration") as mock_duration:
            mock_duration.side_effect = [30.0, 60.0]  # intro, loop

            result = encoder.concat_videos(intro, loop, 3600, temp_dir)

            assert result == temp_dir / "video_only.mp4"
            mock_ffmpeg_runner.run.assert_called_once()

    def test_concat_videos_calculation(self, mock_ffmpeg_runner, temp_dir):
        """Test concat_videos calculates loop count correctly."""
        encoder = VideoEncoder(mock_ffmpeg_runner, CODEC_H264, COLOR_BT709)

        intro = temp_dir / "intro.mp4"
        loop = temp_dir / "loop.mp4"
        intro.touch()
        loop.touch()

        with patch("video_renderer.video.get_duration") as mock_duration:
            # 30s intro, 60s loop, target 3600s (1 hour)
            # Remaining: 3570s, need 60 loops
            mock_duration.side_effect = [30.0, 60.0]

            with patch("video_renderer.video.write_concat_list") as mock_write:
                result = encoder.concat_videos(intro, loop, 3600, temp_dir)

                # Should write concat list with intro + 60 loops
                concat_list_arg = mock_write.call_args[0][0]
                assert len(concat_list_arg) == 61  # 1 intro + 60 loops

    def test_concat_videos_with_progress(self, mock_ffmpeg_runner, temp_dir):
        """Test concat_videos with progress callback."""
        encoder = VideoEncoder(mock_ffmpeg_runner, CODEC_H264, COLOR_BT709)

        intro = temp_dir / "intro.mp4"
        loop = temp_dir / "loop.mp4"
        intro.touch()
        loop.touch()

        callback = MagicMock()

        with patch("video_renderer.video.get_duration") as mock_duration:
            mock_duration.side_effect = [30.0, 60.0]

            result = encoder.concat_videos(intro, loop, 3600, temp_dir, callback)

            mock_ffmpeg_runner.set_progress_callback.assert_called_once_with(callback)

    def test_concat_videos_zero_duration_loop(self, mock_ffmpeg_runner, temp_dir):
        """Test concat_videos handles zero duration loop."""
        encoder = VideoEncoder(mock_ffmpeg_runner, CODEC_H264, COLOR_BT709)

        intro = temp_dir / "intro.mp4"
        loop = temp_dir / "loop.mp4"
        intro.touch()
        loop.touch()

        with patch("video_renderer.video.get_duration") as mock_duration:
            mock_duration.side_effect = [30.0, 0.0]

            with patch("video_renderer.video.write_concat_list") as mock_write:
                result = encoder.concat_videos(intro, loop, 3600, temp_dir)

                # Should only have intro, no loops
                concat_list_arg = mock_write.call_args[0][0]
                assert len(concat_list_arg) == 1


@pytest.mark.unit
class TestEncodeParallel:
    """Test suite for parallel encoding function."""

    def test_encode_parallel_basic(self, mock_ffmpeg_runner, temp_dir):
        """Test basic parallel encoding."""
        encoder = VideoEncoder(mock_ffmpeg_runner, CODEC_H264, COLOR_BT709)

        source1 = temp_dir / "source1.mp4"
        source2 = temp_dir / "source2.mp4"
        output1 = temp_dir / "output1.mp4"
        output2 = temp_dir / "output2.mp4"

        source1.touch()
        source2.touch()

        with patch("video_renderer.video.probe_video") as mock_probe:
            mock_probe.return_value = VideoInfo(
                codec="hevc",
                width=1920,
                height=1080,
                fps="60/1",
                duration=120.0,
                pix_fmt="yuv420p",
                color_space="bt709",
            )

            results = encode_parallel(encoder, [(source1, output1), (source2, output2)])

            assert len(results) == 2
            assert output1 in results
            assert output2 in results

    def test_encode_parallel_with_callback(self, mock_ffmpeg_runner, temp_dir):
        """Test parallel encoding with progress callback."""
        encoder = VideoEncoder(mock_ffmpeg_runner, CODEC_H264, COLOR_BT709)

        source1 = temp_dir / "source1.mp4"
        source2 = temp_dir / "source2.mp4"
        output1 = temp_dir / "output1.mp4"
        output2 = temp_dir / "output2.mp4"

        source1.touch()
        source2.touch()

        callback = MagicMock()

        with patch("video_renderer.video.probe_video") as mock_probe:
            mock_probe.return_value = VideoInfo(
                codec="hevc",
                width=1920,
                height=1080,
                fps="60/1",
                duration=120.0,
                pix_fmt="yuv420p",
                color_space="bt709",
            )

            results = encode_parallel(
                encoder, [(source1, output1), (source2, output2)], progress_callback=callback
            )

            # Callback should be called multiple times
            assert callback.call_count > 0

    def test_encode_parallel_error_handling(self, mock_ffmpeg_runner, temp_dir):
        """Test parallel encoding error handling."""
        encoder = VideoEncoder(mock_ffmpeg_runner, CODEC_H264, COLOR_BT709)

        source1 = temp_dir / "source1.mp4"
        source2 = temp_dir / "source2.mp4"
        output1 = temp_dir / "output1.mp4"
        output2 = temp_dir / "output2.mp4"

        source1.touch()
        source2.touch()

        with patch("video_renderer.video.probe_video") as mock_probe:
            # Make one fail
            mock_probe.side_effect = [
                VideoInfo(
                    codec="h264",
                    width=1920,
                    height=1080,
                    fps="60/1",
                    duration=120.0,
                    pix_fmt="yuv420p",
                    color_space="bt709",
                ),
                Exception("Probe failed"),
            ]

            with pytest.raises(RuntimeError, match="Encoding failed"):
                encode_parallel(encoder, [(source1, output1), (source2, output2)])


@pytest.mark.unit
@pytest.mark.parametrize(
    "width,height,fps,codec,pix_fmt,expected",
    [
        (1920, 1080, 60, "h264", "yuv420p", True),
        (1280, 720, 60, "h264", "yuv420p", False),  # Wrong resolution
        (1920, 1080, 30, "h264", "yuv420p", False),  # Wrong FPS
        (1920, 1080, 60, "hevc", "yuv420p", False),  # Wrong codec
        (1920, 1080, 60, "h264", "yuv422p", False),  # Wrong pixel format
        (1920, 1080, 60, "hevc", "yuv420p10le", True),  # Valid for H.265
        (1920, 1080, 60, "av1", "yuv420p10le", True),  # Valid for AV1
    ],
)
def test_compatibility_matrix(mock_ffmpeg_runner, width, height, fps, codec, pix_fmt, expected):
    """Test compatibility matrix for different video configurations."""
    from video_renderer.config import CODEC_AV1, CODEC_H264, CODEC_H265

    codec_map = {"h264": CODEC_H264, "hevc": CODEC_H265, "av1": CODEC_AV1}
    encoder = VideoEncoder(
        mock_ffmpeg_runner, codec_map[codec], COLOR_BT709, width=1920, height=1080, fps=60
    )

    with patch("video_renderer.video.probe_video") as mock_probe:
        mock_probe.return_value = VideoInfo(
            codec=codec,
            width=width,
            height=height,
            fps=f"{fps}/1",
            duration=120.0,
            pix_fmt=pix_fmt,
            color_space="bt709",
        )

        is_compat, _ = encoder.check_compatibility(Path("test.mp4"))
        assert is_compat == expected

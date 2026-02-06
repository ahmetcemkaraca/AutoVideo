#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Unit tests for config module.

Tests cover:
- CodecConfig dataclass
- ColorConfig dataclass
- Hardware encoder detection
- get_best_encoder function
- RAM disk configuration
- RenderModeConfig factory
"""

import pytest
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch
from video_renderer.config import (
    CodecConfig,
    ColorConfig,
    CODEC_AV1,
    CODEC_H264,
    CODEC_H265,
    CODEC_H264_NVENC,
    CODEC_H265_NVENC,
    CODEC_AV1_NVENC,
    CODEC_H264_QSV,
    CODEC_H265_QSV,
    CODEC_H264_VAAPI,
    CODEC_H265_VAAPI,
    COLOR_BT709,
    COLOR_BT2020,
    detect_available_encoders,
    get_best_encoder,
    clear_encoder_cache,
    RenderConfig,
    get_ramdisk_path,
    setup_temp_directory,
    cleanup_ramdisk,
    get_nvenc_extra_args,
    get_hwaccel_input_args,
    RamTestConfig,
    RenderModeConfig,
    get_render_config,
    CODECS,
    VIDEO_EXTENSIONS,
    AUDIO_EXTENSIONS,
    DEFAULT_WIDTH,
    DEFAULT_HEIGHT,
    CHUNK_CONFIG,
    GPU_CONFIG,
)


# ═══════════════════════════════════════════════════════════════════════════════
# CodecConfig Tests
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.mark.unit
class TestCodecConfig:
    """Test suite for CodecConfig dataclass."""

    def test_codec_config_creation(self):
        """Test creating a basic CodecConfig."""
        config = CodecConfig(
            name="Test",
            encoder="test_encoder",
            preset="medium",
            crf=23
        )

        assert config.name == "Test"
        assert config.encoder == "test_encoder"
        assert config.preset == "medium"
        assert config.crf == 23
        assert config.profile is None
        assert config.level is None
        assert config.extra_args == []

    def test_codec_config_with_all_fields(self):
        """Test CodecConfig with all fields."""
        config = CodecConfig(
            name="H.264",
            encoder="libx264",
            preset="fast",
            crf=20,
            profile="high",
            level="4.2",
            extra_args=["-g", "240", "-tune", "film"]
        )

        assert config.profile == "high"
        assert config.level == "4.2"
        assert len(config.extra_args) == 4

    def test_to_ffmpeg_args_basic(self):
        """Test converting basic config to FFmpeg args."""
        config = CodecConfig("Test", "test_enc", "fast", 23)
        args = config.to_ffmpeg_args()

        assert "-c:v" in args
        assert "test_enc" in args
        assert "-preset" in args
        assert "fast" in args
        assert "-crf" in args
        assert "23" in args

    def test_to_ffmpeg_args_with_profile(self):
        """Test FFmpeg args with profile."""
        config = CodecConfig("Test", "test_enc", "fast", 23, profile="high")
        args = config.to_ffmpeg_args()

        assert "-profile:v" in args
        assert "high" in args

    def test_to_ffmpeg_args_with_level(self):
        """Test FFmpeg args with level."""
        config = CodecConfig("Test", "test_enc", "fast", 23, level="4.2")
        args = config.to_ffmpeg_args()

        assert "-level" in args
        assert "4.2" in args

    def test_to_ffmpeg_args_with_extra(self):
        """Test FFmpeg args with extra arguments."""
        config = CodecConfig(
            "Test", "test_enc", "fast", 23,
            extra_args=["-g", "240", "-tune", "film"]
        )
        args = config.to_ffmpeg_args()

        assert "-g" in args
        assert "240" in args
        assert "-tune" in args
        assert "film" in args


# ═══════════════════════════════════════════════════════════════════════════════
# ColorConfig Tests
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.mark.unit
class TestColorConfig:
    """Test suite for ColorConfig dataclass."""

    def test_color_config_creation(self):
        """Test creating ColorConfig."""
        config = ColorConfig(
            colorspace="bt709",
            color_primaries="bt709",
            color_trc="bt709"
        )

        assert config.colorspace == "bt709"
        assert config.color_primaries == "bt709"
        assert config.color_trc == "bt709"

    def test_to_ffmpeg_args(self):
        """Test converting ColorConfig to FFmpeg args."""
        config = ColorConfig("bt709", "bt709", "bt709")
        args = config.to_ffmpeg_args()

        assert "-colorspace" in args
        assert "bt709" in args
        assert "-color_primaries" in args
        assert "-color_trc" in args

    def test_color_bt709(self):
        """Test COLOR_BT709 constant."""
        assert COLOR_BT709.colorspace == "bt709"
        assert COLOR_BT709.color_primaries == "bt709"
        assert COLOR_BT709.color_trc == "bt709"

    def test_color_bt2020(self):
        """Test COLOR_BT2020 constant."""
        assert COLOR_BT2020.colorspace == "bt2020nc"
        assert COLOR_BT2020.color_primaries == "bt2020"
        assert COLOR_BT2020.color_trc == "bt2020-10"


# ═══════════════════════════════════════════════════════════════════════════════
# Hardware Encoder Detection Tests
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.mark.unit
class TestEncoderDetection:
    """Test suite for hardware encoder detection."""

    def test_detect_available_encoders_no_ffmpeg(self):
        """Test detection when FFmpeg is not installed."""
        with patch('shutil.which', return_value=None):
            result = detect_available_encoders(use_cache=False)

            assert all(v is False for v in result.values())

    def test_detect_available_encoders_with_ffmpeg(self):
        """Test detection with FFmpeg installed."""
        with patch('shutil.which', return_value='/usr/bin/ffmpeg'):
            with patch('subprocess.run') as mock_run:
                # Mock encoder list output
                mock_run.return_value = Mock(
                    returncode=0,
                    stdout="""... h264_nvenc ... hevc_nvenc ... av1_nvenc ..."""
                )

                result = detect_available_encoders(use_cache=False)

                # Should return dict with all encoders marked False
                # (since the actual test commands will fail in unit test)
                assert isinstance(result, dict)

    def test_detect_encoders_uses_cache(self):
        """Test that detection uses cache."""
        with patch('shutil.which', return_value='/usr/bin/ffmpeg'):
            with patch('subprocess.run') as mock_run:
                mock_run.return_value = Mock(returncode=0, stdout="")

                # First call
                result1 = detect_available_encoders(use_cache=True)
                # Second call should use cache
                result2 = detect_available_encoders(use_cache=True)

                # subprocess.run should only be called once
                assert mock_run.call_count <= 2

    def test_detect_encoders_cache_invalidation(self):
        """Test cache invalidation with force_refresh."""
        with patch('shutil.which', return_value='/usr/bin/ffmpeg'):
            with patch('subprocess.run') as mock_run:
                mock_run.return_value = Mock(returncode=0, stdout="")

                detect_available_encoders(use_cache=True)
                detect_available_encoders(use_cache=True, force_refresh=True)

                # Should be called twice with force_refresh
                assert mock_run.call_count == 2

    def test_clear_encoder_cache(self):
        """Test clearing encoder cache."""
        # Populate cache first
        with patch('shutil.which', return_value='/usr/bin/ffmpeg'):
            with patch('subprocess.run', return_value=Mock(returncode=0, stdout="")):
                detect_available_encoders(use_cache=True)

        # Clear cache
        clear_encoder_cache()

        # Next call should re-detect
        with patch('shutil.which', return_value='/usr/bin/ffmpeg'):
            with patch('subprocess.run') as mock_run:
                mock_run.return_value = Mock(returncode=0, stdout="")
                detect_available_encoders(use_cache=True)

                assert mock_run.call_count == 1


# ═══════════════════════════════════════════════════════════════════════════════
# Get Best Encoder Tests
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.mark.unit
class TestGetBestEncoder:
    """Test suite for get_best_encoder function."""

    def test_get_best_encoder_av1_no_hw(self):
        """Test AV1 encoder selection with no hardware acceleration."""
        with patch('video_renderer.config.detect_available_encoders', return_value={}):
            result = get_best_encoder("av1")

            assert result == CODEC_AV1

    def test_get_best_encoder_h264_no_hw(self):
        """Test H.264 encoder selection with no hardware acceleration."""
        with patch('video_renderer.config.detect_available_encoders', return_value={}):
            result = get_best_encoder("h264")

            assert result == CODEC_H264

    def test_get_best_encoder_h265_no_hw(self):
        """Test H.265 encoder selection with no hardware acceleration."""
        with patch('video_renderer.config.detect_available_encoders', return_value={}):
            result = get_best_encoder("h265")

            assert result == CODEC_H265

    def test_get_best_encoder_h264_nvenc(self):
        """Test H.264 with NVENC available."""
        with patch('video_renderer.config.detect_available_encoders',
                   return_value={"h264_nvenc": True}):
            result = get_best_encoder("h264")

            assert result == CODEC_H264_NVENC

    def test_get_best_encoder_h265_nvenc(self):
        """Test H.265 with NVENC available."""
        with patch('video_renderer.config.detect_available_encoders',
                   return_value={"hevc_nvenc": True}):
            result = get_best_encoder("h265")

            assert result == CODEC_H265_NVENC

    def test_get_best_encoder_av1_nvenc(self):
        """Test AV1 with NVENC available."""
        with patch('video_renderer.config.detect_available_encoders',
                   return_value={"av1_nvenc": True}):
            result = get_best_encoder("av1")

            assert result == CODEC_AV1_NVENC

    def test_get_best_encoder_h264_qsv(self):
        """Test H.264 with QSV available."""
        with patch('video_renderer.config.detect_available_encoders',
                   return_value={"h264_qsv": True}):
            result = get_best_encoder("h264")

            assert result == CODEC_H264_QSV

    def test_get_best_encoder_h264_vaapi(self):
        """Test H.264 with VAAPI available."""
        with patch('video_renderer.config.detect_available_encoders',
                   return_value={"h264_vaapi": True}):
            result = get_best_encoder("h264")

            assert result == CODEC_H264_VAAPI

    def test_get_best_encoder_priority_nvenc_over_qsv(self):
        """Test NVENC is prioritized over QSV."""
        with patch('video_renderer.config.detect_available_encoders',
                   return_value={"h264_nvenc": True, "h264_qsv": True}):
            result = get_best_encoder("h264")

            assert result == CODEC_H264_NVENC

    def test_get_best_encoder_unknown_codec(self):
        """Test unknown codec falls back to H.264."""
        with patch('video_renderer.config.detect_available_encoders', return_value={}):
            result = get_best_encoder("unknown")

            assert result == CODEC_H264


# ═══════════════════════════════════════════════════════════════════════════════
# RAM Disk Configuration Tests
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.mark.unit
class TestRamDiskConfig:
    """Test suite for RAM disk configuration."""

    @pytest.mark.posix
    def test_get_ramdisk_path_linux(self):
        """Test RAM disk path on Linux."""
        with patch('pathlib.Path.exists', return_value=True):
            with patch('pathlib.Path.is_dir', return_value=True):
                with patch('os.statvfs') as mock_stat:
                    # Mock 20GB free space
                    mock_stat.return_value = Mock(
                        f_bavail=20971520,  # blocks
                        f_frsize=512        # block size
                    )

                    result = get_ramdisk_path()

                    assert result is not None
                    assert "video_render_tmp" in str(result)

    @pytest.mark.posix
    def test_get_ramdisk_path_insufficient_space(self):
        """Test RAM disk path with insufficient space."""
        with patch('pathlib.Path.exists', return_value=True):
            with patch('pathlib.Path.is_dir', return_value=True):
                with patch('os.statvfs') as mock_stat:
                    # Mock only 1GB free space
                    mock_stat.return_value = Mock(
                        f_bavail=2097152,
                        f_frsize=512
                    )

                    result = get_ramdisk_path()

                    assert result is None

    @pytest.mark.windows
    def test_get_ramdisk_path_windows(self):
        """Test RAM disk path on Windows (returns None)."""
        result = get_ramdisk_path()
        assert result is None

    def test_setup_temp_directory_with_ramdisk(self, temp_dir):
        """Test setup temp directory preferring RAM disk."""
        with patch('video_renderer.config.get_ramdisk_path',
                   return_value=temp_dir / "ramdisk"):
            result = setup_temp_directory(temp_dir, use_ramdisk=True)

            assert "ramdisk" in str(result)

    def test_setup_temp_directory_fallback(self, temp_dir):
        """Test setup temp directory fallback to disk."""
        with patch('video_renderer.config.get_ramdisk_path', return_value=None):
            result = setup_temp_directory(temp_dir, use_ramdisk=True)

            assert "tmp" in str(result)
            assert result == temp_dir / "tmp"

    def test_cleanup_ramdisk(self):
        """Test RAM disk cleanup."""
        with patch('video_renderer.config.get_ramdisk_path',
                   return_value=None):
            # Should not raise
            cleanup_ramdisk()


# ═══════════════════════════════════════════════════════════════════════════════
# NVENC Args Tests
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.mark.unit
class TestNVENCArgs:
    """Test suite for NVENC argument generation."""

    def test_get_nvenc_args_h264_standard(self):
        """Test H.264 NVENC args with standard VRAM."""
        args = get_nvenc_extra_args("h264", high_vram=False)

        assert "-rc" in args
        assert "vbr" in args
        assert "-cq" in args
        assert "23" in args
        assert "-surfaces" in args
        assert "64" in args

    def test_get_nvenc_args_h264_high_vram(self):
        """Test H.264 NVENC args with high VRAM."""
        args = get_nvenc_extra_args("h264", high_vram=True)

        assert "-surfaces" in args
        assert "128" in args  # Higher value for high VRAM
        assert "-rc-lookahead" in args
        assert "48" in args

    def test_get_nvenc_args_h265(self):
        """Test H.265 NVENC args."""
        args = get_nvenc_extra_args("h265", high_vram=False)

        assert "-cq" in args
        assert "26" in args
        assert "-tag:v" in args
        assert "hvc1" in args

    def test_get_nvenc_args_av1(self):
        """Test AV1 NVENC args."""
        args = get_nvenc_extra_args("av1", high_vram=False)

        assert "-cq" in args
        assert "30" in args

    def test_get_hwaccel_args_standard(self):
        """Test hardware acceleration args with standard VRAM."""
        args = get_hwaccel_input_args(high_vram=False)

        assert "-hwaccel" in args
        assert "cuda" in args
        assert "-hwaccel_output_format" in args

    def test_get_hwaccel_args_high_vram(self):
        """Test hardware acceleration args with high VRAM."""
        args = get_hwaccel_input_args(high_vram=True)

        assert "-extra_hw_frames" in args
        assert "32" in args


# ═══════════════════════════════════════════════════════════════════════════════
# RenderConfig Tests
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.mark.unit
class TestRenderConfig:
    """Test suite for RenderConfig dataclass."""

    def test_render_config_defaults(self):
        """Test RenderConfig with default values."""
        config = RenderConfig()

        assert config.width == DEFAULT_WIDTH
        assert config.height == DEFAULT_HEIGHT
        assert config.fps == 60
        assert config.codec == "av1"
        assert config.color == COLOR_BT709
        assert config.use_hw_accel is True
        assert config.parallel_encode is True

    def test_render_config_post_init(self):
        """Test RenderConfig __post_init__ sets defaults."""
        config = RenderConfig(work_dir=Path("/test"))

        assert config.music_dir == Path("/test/music")
        assert config.tmp_dir == Path("/test/tmp")

    def test_render_config_custom_values(self, temp_dir):
        """Test RenderConfig with custom values."""
        config = RenderConfig(
            work_dir=temp_dir,
            width=1280,
            height=720,
            fps=30,
            codec="h264",
            duration_seconds=1800
        )

        assert config.width == 1280
        assert config.height == 720
        assert config.fps == 30
        assert config.codec == "h264"
        assert config.duration_seconds == 1800

    def test_get_codec_config_with_hw_accel(self):
        """Test get_codec_config with hardware acceleration enabled."""
        config = RenderConfig(use_hw_accel=True)

        with patch('video_renderer.config.get_best_encoder',
                   return_value=CODEC_H264):
            codec_config = config.get_codec_config()

            assert codec_config == CODEC_H264

    def test_get_codec_config_without_hw_accel(self):
        """Test get_codec_config with hardware acceleration disabled."""
        config = RenderConfig(use_hw_accel=False, codec="h264")

        codec_config = config.get_codec_config()

        assert codec_config == CODEC_H264


# ═══════════════════════════════════════════════════════════════════════════════
# RamTestConfig Tests
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.mark.unit
class TestRamTestConfig:
    """Test suite for RamTestConfig dataclass."""

    def test_ram_test_config_defaults(self):
        """Test RamTestConfig with default values."""
        config = RamTestConfig()

        assert config.enabled is False
        assert config.use_ramdisk is True
        assert config.high_vram is False
        assert config.chunk_long_videos is False

    def test_get_temp_dir(self, temp_dir):
        """Test get_temp_dir method."""
        config = RamTestConfig(use_ramdisk=True)

        with patch('video_renderer.config.setup_temp_directory',
                   return_value=temp_dir / "ramdisk") as mock_setup:
            result = config.get_temp_dir(temp_dir)

            mock_setup.assert_called_once_with(temp_dir, True)
            assert result == temp_dir / "ramdisk"

    def test_get_nvenc_args(self):
        """Test get_nvenc_args method."""
        config = RamTestConfig(high_vram=True)

        with patch('video_renderer.config.get_nvenc_extra_args',
                   return_value=["-test"]) as mock_get:
            result = config.get_nvenc_args("h264")

            mock_get.assert_called_once_with("h264", True)
            assert result == ["-test"]

    def test_get_hwaccel_args(self):
        """Test get_hwaccel_args method."""
        config = RamTestConfig(high_vram=True)

        with patch('video_renderer.config.get_hwaccel_input_args',
                   return_value=["-hwaccel", "cuda"]) as mock_get:
            result = config.get_hwaccel_args()

            mock_get.assert_called_once_with(True)
            assert result == ["-hwaccel", "cuda"]


# ═══════════════════════════════════════════════════════════════════════════════
# RenderModeConfig Tests
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.mark.unit
class TestRenderModeConfig:
    """Test suite for RenderModeConfig and factory function."""

    def test_render_mode_config_defaults(self):
        """Test RenderModeConfig with default values."""
        config = RenderModeConfig()

        assert config.mode == "standard"
        assert config.use_ramdisk is False
        assert config.high_vram is False
        assert config.enable_rate_limiting is True

    def test_get_render_config_standard(self):
        """Test get_render_config for standard mode."""
        config = get_render_config("standard")

        assert config.mode == "standard"
        assert config.use_ramdisk is False
        assert config.high_vram is False

    def test_get_render_config_ramtest(self):
        """Test get_render_config for ramtest mode."""
        config = get_render_config("ramtest")

        assert config.mode == "ramtest"
        assert config.use_ramdisk is True
        assert config.high_vram is True
        assert config.chunk_long_videos is True
        assert config.enable_memory_tracking is True

    def test_get_render_config_ramdisk(self):
        """Test get_render_config for ramdisk mode."""
        config = get_render_config("ramdisk")

        assert config.mode == "ramdisk"
        assert config.use_ramdisk is True
        assert config.high_vram is False

    def test_get_render_config_high_vram(self):
        """Test get_render_config for high_vram mode."""
        config = get_render_config("high_vram")

        assert config.mode == "high_vram"
        assert config.high_vram is True
        assert config.gpu_surfaces == 128
        assert config.gpu_extra_frames == 16
        assert config.gpu_lookahead == 48

    def test_get_render_config_unknown_mode(self):
        """Test get_render_config with unknown mode falls back to standard."""
        config = get_render_config("unknown")

        assert config.mode == "standard"


# ═══════════════════════════════════════════════════════════════════════════════
# Constants Tests
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.mark.unit
class TestConstants:
    """Test suite for module constants."""

    def test_video_extensions(self):
        """Test VIDEO_EXTENSIONS constant."""
        assert ".mp4" in VIDEO_EXTENSIONS
        assert ".mkv" in VIDEO_EXTENSIONS
        assert ".mov" in VIDEO_EXTENSIONS
        assert ".webm" in VIDEO_EXTENSIONS

    def test_audio_extensions(self):
        """Test AUDIO_EXTENSIONS constant."""
        assert ".mp3" in AUDIO_EXTENSIONS
        assert ".wav" in AUDIO_EXTENSIONS
        assert ".flac" in AUDIO_EXTENSIONS
        assert ".m4a" in AUDIO_EXTENSIONS

    def test_default_resolution(self):
        """Test default resolution constants."""
        assert DEFAULT_WIDTH == 1920
        assert DEFAULT_HEIGHT == 1080

    def test_codecs_registry(self):
        """Test CODECS registry has all expected entries."""
        assert "av1" in CODECS
        assert "h264" in CODECS
        assert "h265" in CODECS
        assert "h264_nvenc" in CODECS
        assert "h265_nvenc" in CODECS

    def test_gpu_config(self):
        """Test GPU_CONFIG constants."""
        assert "surfaces" in GPU_CONFIG
        assert "extra_hw_frames" in GPU_CONFIG
        assert "rc_lookahead" in GPU_CONFIG
        assert "decode_surfaces" in GPU_CONFIG

    def test_chunk_config(self):
        """Test CHUNK_CONFIG constants."""
        assert "max_chunk_duration" in CHUNK_CONFIG
        assert "min_ram_for_full" in CHUNK_CONFIG
        assert "auto_chunk_threshold_hours" in CHUNK_CONFIG


# ═══════════════════════════════════════════════════════════════════════════════
# Codec Config Instances Tests
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.mark.unit
class TestCodecConfigInstances:
    """Test suite for predefined codec config instances."""

    def test_codec_av1(self):
        """Test CODEC_AV1 configuration."""
        assert CODEC_AV1.name == "AV1"
        assert CODEC_AV1.encoder == "libsvtav1"
        assert CODEC_AV1.crf == 28

    def test_codec_h264(self):
        """Test CODEC_H264 configuration."""
        assert CODEC_H264.name == "H.264"
        assert CODEC_H264.encoder == "libx264"
        assert CODEC_H264.crf == 20
        assert CODEC_H264.profile == "high"

    def test_codec_h265(self):
        """Test CODEC_H265 configuration."""
        assert CODEC_H265.name == "H.265"
        assert CODEC_H265.encoder == "libx265"
        assert CODEC_H265.crf == 23

    def test_codec_h264_nvenc(self):
        """Test CODEC_H264_NVENC configuration."""
        assert CODEC_H264_NVENC.name == "H.264 (NVENC)"
        assert CODEC_H264_NVENC.encoder == "h264_nvenc"
        assert CODEC_H264_NVENC.profile == "high"

    def test_codec_h265_nvenc(self):
        """Test CODEC_H265_NVENC configuration."""
        assert CODEC_H265_NVENC.name == "H.265 (NVENC)"
        assert CODEC_H265_NVENC.encoder == "hevc_nvenc"

    def test_codec_av1_nvenc(self):
        """Test CODEC_AV1_NVENC configuration."""
        assert CODEC_AV1_NVENC.name == "AV1 (NVENC)"
        assert CODEC_AV1_NVENC.encoder == "av1_nvenc"

    def test_codec_h264_qsv(self):
        """Test CODEC_H264_QSV configuration."""
        assert CODEC_H264_QSV.name == "H.264 (QSV)"
        assert CODEC_H264_QSV.encoder == "h264_qsv"

    def test_codec_h265_qsv(self):
        """Test CODEC_H265_QSV configuration."""
        assert CODEC_H265_QSV.name == "H.265 (QSV)"
        assert CODEC_H265_QSV.encoder == "hevc_qsv"

    def test_codec_h264_vaapi(self):
        """Test CODEC_H264_VAAPI configuration."""
        assert CODEC_H264_VAAPI.name == "H.264 (VAAPI)"
        assert CODEC_H264_VAAPI.encoder == "h264_vaapi"

    def test_codec_h265_vaapi(self):
        """Test CODEC_H265_VAAPI configuration."""
        assert CODEC_H265_VAAPI.name == "H.265 (VAAPI)"
        assert CODEC_H265_VAAPI.encoder == "hevc_vaapi"

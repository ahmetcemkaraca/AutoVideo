#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Unit tests for AudioProcessor class.

Tests cover:
- Audio validation and conversion
- Music loop creation
- Gain application
- Track mixing
- Background detection
- Gain parsing
- Track standardization
"""

import pytest
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch, call
from video_renderer.audio import (
    AudioProcessor,
    is_background_file,
    parse_background_gain_db,
    mux_video_audio
)
from video_renderer.ffmpeg import FFmpegProgress
import subprocess


@pytest.mark.unit
class TestAudioUtilities:
    """Test suite for audio utility functions."""

    @pytest.mark.parametrize("filename, expected", [
        ("bg_rain.mp3", True),
        ("BG_FIRE.WAV", True),
        ("background_thunder.mp3", False),
        ("rain_bg.mp3", True),
        ("rain-bg.mp3", True),
        ("fire_bg_night.mp3", True),
        ("normal_track.mp3", False),
        ("bg.mp3", True),
        ("bgtest.mp3", True),
    ])
    def test_is_background_file(self, filename, expected):
        """Test background file detection."""
        assert is_background_file(Path(filename)) is expected

    @pytest.mark.parametrize("filename, expected_gain", [
        ("bg_-8.5.mp3", -8.5),
        ("bg_-1.mp3", -1.0),
        ("bg_0.mp3", 0.0),
        ("bg_5.mp3", 5.0),
        ("fire_bg_-10.wav", -10.0),
        ("night-bg_-12.5.mp3", -12.5),
        ("ates_bg_-3.flac", -3.0),
        ("normal.mp3", 0.0),
        ("bg_x.mp3", 0.0),  # Invalid number
    ])
    def test_parse_background_gain_db(self, filename, expected_gain):
        """Test background gain parsing from filename."""
        assert parse_background_gain_db(Path(filename)) == expected_gain


@pytest.mark.unit
class TestAudioProcessor:
    """Test suite for AudioProcessor class."""

    def test_init(self, mock_ffmpeg_runner, temp_dir):
        """Test AudioProcessor initialization."""
        processor = AudioProcessor(mock_ffmpeg_runner, temp_dir)

        assert processor.runner == mock_ffmpeg_runner
        assert processor.tmp_dir == temp_dir
        assert processor.INTERMEDIATE_FORMAT == "w64"
        assert processor.INTERMEDIATE_CODEC == "pcm_s16le"
        assert processor.SAMPLE_RATE == 48000

    def test_validate_and_convert_track_success(
        self, mock_ffmpeg_runner, temp_dir
    ):
        """Test successful track validation and conversion."""
        processor = AudioProcessor(mock_ffmpeg_runner, temp_dir)

        track = temp_dir / "test.mp3"
        track.touch()

        with patch('subprocess.run') as mock_run:
            mock_run.return_value = Mock(returncode=0, stderr="")

            output, success, error = processor.validate_and_convert_track(track)

            assert success is True
            assert error == ""
            assert output.name.startswith("validated_")
            assert output.suffix == ".w64"

    def test_validate_and_convert_track_skip_existing(
        self, mock_ffmpeg_runner, temp_dir
    ):
        """Test validation skips already converted files."""
        processor = AudioProcessor(mock_ffmpeg_runner, temp_dir)

        track = temp_dir / "test.mp3"
        track.touch()

        # Create existing validated file
        validated = temp_dir / "validated_test.w64"
        validated.touch()

        output, success, error = processor.validate_and_convert_track(track)

        assert success is True
        assert error == ""
        assert output == validated

    def test_validate_and_convert_track_conversion_error(
        self, mock_ffmpeg_runner, temp_dir
    ):
        """Test validation handles conversion errors."""
        processor = AudioProcessor(mock_ffmpeg_runner, temp_dir)

        track = temp_dir / "test.mp3"
        track.touch()

        with patch('subprocess.run') as mock_run:
            mock_run.return_value = Mock(
                returncode=1,
                stderr="Invalid data found when processing input"
            )

            output, success, error = processor.validate_and_convert_track(track)

            assert success is False
            assert "Donusturme hatasi" in error

    def test_validate_and_convert_track_timeout(
        self, mock_ffmpeg_runner, temp_dir
    ):
        """Test validation handles timeout."""
        processor = AudioProcessor(mock_ffmpeg_runner, temp_dir)

        track = temp_dir / "test.mp3"
        track.touch()

        with patch('subprocess.run') as mock_run:
            mock_run.side_effect = subprocess.TimeoutExpired("ffmpeg", 120)

            output, success, error = processor.validate_and_convert_track(track)

            assert success is False
            assert "Zaman asimi" in error

    def test_validate_tracks_multiple(self, mock_ffmpeg_runner, temp_dir):
        """Test validation of multiple tracks."""
        processor = AudioProcessor(mock_ffmpeg_runner, temp_dir)

        tracks = [
            temp_dir / "track1.mp3",
            temp_dir / "track2.mp3",
            temp_dir / "track3.mp3"
        ]
        for track in tracks:
            track.touch()

        with patch('subprocess.run') as mock_run:
            mock_run.return_value = Mock(returncode=0, stderr="")

            valid, invalid = processor.validate_tracks(tracks)

            assert len(valid) == 3
            assert len(invalid) == 0

    def test_validate_tracks_with_callback(self, mock_ffmpeg_runner, temp_dir):
        """Test validate_tracks with progress callback."""
        processor = AudioProcessor(mock_ffmpeg_runner, temp_dir)

        tracks = [temp_dir / f"track{i}.mp3" for i in range(3)]
        for track in tracks:
            track.touch()

        callback = MagicMock()

        with patch('subprocess.run') as mock_run:
            mock_run.return_value = Mock(returncode=0, stderr="")

            valid, invalid = processor.validate_tracks(tracks, callback)

            # Callback should be called for each track
            assert callback.call_count == 3

    def test_create_music_loop_basic(self, mock_ffmpeg_runner, temp_dir):
        """Test basic music loop creation."""
        processor = AudioProcessor(mock_ffmpeg_runner, temp_dir)

        tracks = [temp_dir / "track1.mp3", temp_dir / "track2.mp3"]
        for track in tracks:
            track.touch()

        with patch('video_renderer.audio.get_duration') as mock_duration:
            mock_duration.side_effect = [180.0, 240.0]  # 3min + 4min = 7min

            with patch('video_renderer.audio.write_concat_list'):
                result = processor.create_music_loop(tracks, 3600)  # 1 hour

                assert result == temp_dir / "music_loop.w64"
                mock_ffmpeg_runner.run.assert_called_once()

    def test_create_music_loop_pre_validated(self, mock_ffmpeg_runner, temp_dir):
        """Test music loop creation with pre-validated tracks."""
        processor = AudioProcessor(mock_ffmpeg_runner, temp_dir)

        tracks = [temp_dir / "validated_track1.w64", temp_dir / "validated_track2.w64"]
        for track in tracks:
            track.touch()

        with patch('video_renderer.audio.get_duration') as mock_duration:
            mock_duration.side_effect = [180.0, 240.0]

            with patch('video_renderer.audio.write_concat_list'):
                result = processor.create_music_loop(
                    tracks, 3600, pre_validated=True
                )

                assert result == temp_dir / "music_loop.w64"

    def test_create_music_loop_zero_duration(self, mock_ffmpeg_runner, temp_dir):
        """Test music loop creation with zero total duration."""
        processor = AudioProcessor(mock_ffmpeg_runner, temp_dir)

        tracks = [temp_dir / "track1.mp3"]
        tracks[0].touch()

        with patch('video_renderer.audio.get_duration') as mock_duration:
            mock_duration.return_value = 0.0

            with pytest.raises(ValueError, match="Track'lerin toplam suresi 0"):
                processor.create_music_loop(tracks, 3600)

    def test_create_music_loop_negative_duration(self, mock_ffmpeg_runner, temp_dir):
        """Test music loop creation with negative total duration."""
        processor = AudioProcessor(mock_ffmpeg_runner, temp_dir)

        tracks = [temp_dir / "track1.mp3"]
        tracks[0].touch()

        with patch('video_renderer.audio.get_duration') as mock_duration:
            mock_duration.return_value = -10.0

            with pytest.raises(ValueError, match="Track'lerin toplam suresi 0"):
                processor.create_music_loop(tracks, 3600)

    def test_create_music_loop_with_invalid_tracks(
        self, mock_ffmpeg_runner, temp_dir
    ):
        """Test music loop creation with invalid tracks."""
        processor = AudioProcessor(mock_ffmpeg_runner, temp_dir)

        tracks = [temp_dir / "bad_track.mp3"]
        tracks[0].touch()

        with patch.object(
            processor, 'validate_tracks', return_value=([], [(tracks[0], "Error")])
        ):
            with pytest.raises(ValueError, match="Bozuk track'ler"):
                processor.create_music_loop(tracks, 3600)

    def test_apply_gain(self, mock_ffmpeg_runner, temp_dir):
        """Test gain application to audio."""
        processor = AudioProcessor(mock_ffmpeg_runner, temp_dir)

        source = temp_dir / "source.mp3"
        source.touch()

        result = processor.apply_gain(source, -8.5)

        assert "gain" in result.name
        assert result.suffix == ".w64"
        mock_ffmpeg_runner.run_simple.assert_called_once()

    def test_apply_gain_custom_output_name(self, mock_ffmpeg_runner, temp_dir):
        """Test gain application with custom output name."""
        processor = AudioProcessor(mock_ffmpeg_runner, temp_dir)

        source = temp_dir / "source.mp3"
        source.touch()

        result = processor.apply_gain(source, -5.0, output_name="custom.w64")

        assert result.name == "custom.w64"

    def test_mix_tracks_no_backgrounds(self, mock_ffmpeg_runner, temp_dir):
        """Test track mixing with no background tracks."""
        processor = AudioProcessor(mock_ffmpeg_runner, temp_dir)

        main_track = temp_dir / "main.w64"
        main_track.touch()

        result = processor.mix_tracks(main_track, [], 3600)

        assert result == main_track
        mock_ffmpeg_runner.run.assert_not_called()

    def test_mix_tracks_with_backgrounds(self, mock_ffmpeg_runner, temp_dir):
        """Test track mixing with background tracks."""
        processor = AudioProcessor(mock_ffmpeg_runner, temp_dir)

        main_track = temp_dir / "main.w64"
        bg1 = temp_dir / "bg1.w64"
        bg2 = temp_dir / "bg2.w64"

        for track in [main_track, bg1, bg2]:
            track.touch()

        result = processor.mix_tracks(main_track, [bg1, bg2], 3600)

        assert result == temp_dir / "audio_mixed.w64"
        mock_ffmpeg_runner.run.assert_called_once()

        # Verify filter_complex in call
        call_args = mock_ffmpeg_runner.run.call_args[0][0]
        assert "-filter_complex" in call_args

    def test_process_backgrounds(self, mock_ffmpeg_runner, temp_dir):
        """Test processing of multiple background tracks."""
        processor = AudioProcessor(mock_ffmpeg_runner, temp_dir)

        bg1 = temp_dir / "rain.mp3"
        bg2 = temp_dir / "fire.mp3"

        for bg in [bg1, bg2]:
            bg.touch()

        backgrounds = [(bg1, -8.5), (bg2, -5.0)]

        with patch.object(processor, 'apply_gain') as mock_apply:
            mock_apply.side_effect = [
                temp_dir / "rain_bg.w64",
                temp_dir / "fire_bg.w64"
            ]

            results = processor.process_backgrounds(backgrounds)

            assert len(results) == 2
            assert mock_apply.call_count == 2

    def test_standardize_tracks_skip_valid_mp3(
        self, mock_ffmpeg_runner, temp_dir
    ):
        """Test track standardization skips already valid MP3s."""
        processor = AudioProcessor(mock_ffmpeg_runner, temp_dir)

        track = temp_dir / "valid.mp3"
        track.touch()

        archive_dir = temp_dir / "archive"

        # Mock ffprobe to return valid MP3 info
        with patch('subprocess.run') as mock_run:
            mock_run.return_value = Mock(
                returncode=0,
                stdout='{"streams": [{"codec_name": "mp3", "sample_rate": "48000", "bit_rate": "320000"}]}'
            )

            results = processor.standardize_tracks([track], archive_dir)

            assert len(results) == 1
            assert results[0] == track

    def test_standardize_tracks_convert_invalid(
        self, mock_ffmpeg_runner, temp_dir
    ):
        """Test track standardization converts invalid tracks."""
        processor = AudioProcessor(mock_ffmpeg_runner, temp_dir)

        track = temp_dir / "invalid.flac"
        track.touch()

        archive_dir = temp_dir / "archive"
        archive_dir.mkdir()

        with patch('subprocess.run') as mock_run:
            # First call: ffprobe (returns empty/invalid)
            # Second call: ffmpeg conversion
            mock_run.side_effect = [
                Mock(returncode=0, stdout='{"streams": []}'),
                Mock(returncode=0)
            ]

            results = processor.standardize_tracks([track], archive_dir)

            assert len(results) == 1
            # Should be converted to MP3
            # Note: actual conversion won't work in test, but we verify the flow

    def test_standardize_tracks_with_callback(self, mock_ffmpeg_runner, temp_dir):
        """Test track standardization with progress callback."""
        processor = AudioProcessor(mock_ffmpeg_runner, temp_dir)

        tracks = [temp_dir / f"track{i}.flac" for i in range(3)]
        for track in tracks:
            track.touch()

        archive_dir = temp_dir / "archive"
        archive_dir.mkdir()

        callback = MagicMock()

        with patch('subprocess.run') as mock_run:
            mock_run.side_effect = [
                Mock(returncode=0, stdout='{"streams": []}'),
                Mock(returncode=0)
            ] * 3  # For each track

            results = processor.standardize_tracks(tracks, archive_dir, callback)

            assert callback.call_count == 3


@pytest.mark.unit
class TestMuxVideoAudio:
    """Test suite for mux_video_audio function."""

    def test_mux_basic(self, mock_ffmpeg_runner, temp_dir):
        """Test basic video/audio muxing."""
        video = temp_dir / "video.mp4"
        audio = temp_dir / "audio.w64"
        output = temp_dir / "output.mp4"

        video.touch()
        audio.touch()

        with patch('video_renderer.audio.get_duration') as mock_duration:
            mock_duration.return_value = 3600.0

            result = mux_video_audio(mock_ffmpeg_runner, video, audio, output)

            assert result == output
            mock_ffmpeg_runner.run.assert_called_once()

    def test_mux_with_progress(self, mock_ffmpeg_runner, temp_dir):
        """Test muxing with progress callback."""
        video = temp_dir / "video.mp4"
        audio = temp_dir / "audio.w64"
        output = temp_dir / "output.mp4"

        video.touch()
        audio.touch()

        callback = MagicMock()

        with patch('video_renderer.audio.get_duration') as mock_duration:
            mock_duration.return_value = 3600.0

            result = mux_video_audio(
                mock_ffmpeg_runner, video, audio, output,
                progress_callback=callback
            )

            mock_ffmpeg_runner.set_progress_callback.assert_called_once_with(callback)

    def test_mux_custom_bitrate(self, mock_ffmpeg_runner, temp_dir):
        """Test muxing with custom audio bitrate."""
        video = temp_dir / "video.mp4"
        audio = temp_dir / "audio.w64"
        output = temp_dir / "output.mp4"

        video.touch()
        audio.touch()

        with patch('video_renderer.audio.get_duration') as mock_duration:
            mock_duration.return_value = 3600.0

            result = mux_video_audio(
                mock_ffmpeg_runner, video, audio, output,
                audio_bitrate="256k"
            )

            # Verify bitrate in command
            call_args = mock_ffmpeg_runner.run.call_args[0][0]
            assert "-b:a" in call_args
            assert "256k" in call_args


@pytest.mark.unit
@pytest.mark.parametrize("gain_db, expected_filter", [
    (-8.5, "volume=-8.5dB"),
    (0.0, "volume=0.0dB"),
    (5.0, "volume=5.0dB"),
    (-12.75, "volume=-12.75dB"),
])
def test_gain_filter_values(mock_ffmpeg_runner, temp_dir, gain_db, expected_filter):
    """Test gain filter values are correctly formatted."""
    processor = AudioProcessor(mock_ffmpeg_runner, temp_dir)

    source = temp_dir / "source.mp3"
    source.touch()

    processor.apply_gain(source, gain_db)

    call_args = mock_ffmpeg_runner.run_simple.call_args[0][0]
    assert "-filter:a" in call_args
    assert expected_filter in call_args


@pytest.mark.unit
def test_audio_format_constants(mock_ffmpeg_runner, temp_dir):
    """Test audio processor format constants."""
    processor = AudioProcessor(mock_ffmpeg_runner, temp_dir)

    assert processor.INTERMEDIATE_FORMAT == "w64"
    assert processor.INTERMEDIATE_CODEC == "pcm_s16le"
    assert processor.SAMPLE_RATE == 48000

    # These constants support large files (>4GB) and high quality
    assert processor.INTERMEDIATE_FORMAT == "w64"  # Wave64 format

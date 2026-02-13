import unittest
from pathlib import Path
from unittest.mock import MagicMock
import sys
import os

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from video_renderer.video import VideoEncoder
from video_renderer.ffmpeg import FFmpegRunner

class TestBitrateCommand(unittest.TestCase):
    def setUp(self):
        self.runner = MagicMock(spec=FFmpegRunner)
        # Mock codec config - just a simple object
        self.codec_config = MagicMock()
        self.codec_config.to_ffmpeg_args.return_value = ["-c:v", "libx264", "-b:v", "0"] # Default config has -b:v 0
        self.codec_config.encoder = "libx264"
        
        self.encoder = VideoEncoder(
            runner=self.runner,
            codec_config=self.codec_config,
            width=1920,
            height=1080,
            fps=30
        )
        # Mock other dependencies
        self.encoder.color = MagicMock()
        self.encoder.color.to_ffmpeg_args.return_value = []
        self.encoder._use_gpu = False # Simplified testing

    def test_bitrate_override(self):
        """Test that custom bitrate overrides default flags."""
        source = Path("input.mp4")
        output = Path("output.mp4")
        bitrate = "5000k"

        cmd = self.encoder._build_normalize_command(
            source, output, scale_algo="lanczos", bitrate=bitrate
        )

        # Print for debugging
        print("Command:", cmd)

        # Assertions
        self.assertIn("-b:v", cmd)
        self.assertIn("5000k", cmd)
        self.assertIn("-maxrate", cmd)
        self.assertIn("-bufsize", cmd)
        self.assertIn("10000k", cmd) # 2x 5000k
        
        # Check that we don't have conflicting bitrates
        # Count occurrences
        bv_count = cmd.count("-b:v")
        self.assertEqual(bv_count, 1, "Should have exactly one -b:v flag")

    def test_no_bitrate(self):
        """Test that no bitrate leaves default flags."""
        source = Path("input.mp4")
        output = Path("output.mp4")

        cmd = self.encoder._build_normalize_command(
            source, output, scale_algo="lanczos"
        )
        
        # Should retain the mocked default
        self.assertIn("-b:v", cmd)
        self.assertIn("0", cmd)

if __name__ == "__main__":
    unittest.main()

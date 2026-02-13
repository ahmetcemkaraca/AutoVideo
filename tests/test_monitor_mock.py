import unittest
import threading
import time
from pathlib import Path
import sys
import os

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from video_renderer.ffmpeg import FFmpegRunner

class TestMonitorCallbacks(unittest.TestCase):
    def test_log_callback(self):
        """Test that log lines are streamed through the callback."""
        received_lines = []
        
        def log_cb(line):
            received_lines.append(line.strip())
            
        runner = FFmpegRunner()
        runner.set_log_callback(log_cb)
        
        # We need a command generating output. 
        # Python script is safest.
        cmd = [sys.executable, "-c", "import sys; print('Line 1', file=sys.stderr); print('Line 2', file=sys.stderr)"]
        
        # FFmpegRunner expects stderr output for logs (ffmpeg standard).
        # run() captures stderr.
        
        try:
            runner.run(cmd, capture_progress=False)
        except Exception as e:
            # It might fail parsing progress if capture_progress=True (default).
            # But here capture_progress=False.
            pass
            
        print("Received Lines:", received_lines)
        
        self.assertIn("Line 1", received_lines)
        self.assertIn("Line 2", received_lines)

if __name__ == "__main__":
    unittest.main()

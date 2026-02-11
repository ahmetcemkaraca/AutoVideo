
import sys
import os
from pathlib import Path

# Add project root to path
sys.path.insert(0, os.getcwd())

try:
    print("Checking imports...")
    from video_renderer.main import run_batch_wizard, main
    from video_renderer.screens.batch import BatchScreen
    print("Imports successful.")
except ImportError as e:
    print(f"ImportError: {e}")
    sys.exit(1)
except SyntaxError as e:
    print(f"SyntaxError: {e}")
    sys.exit(1)

print("Verification complete.")

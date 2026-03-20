import os
import sys

# Add project root to path
sys.path.insert(0, os.getcwd())

try:
    print("Checking imports...")
    from video_renderer.main import main, run_batch_wizard
    from video_renderer.screens.batch import BatchScreen

    print("Imports successful.")
except ImportError as e:
    print(f"ImportError: {e}")
    sys.exit(1)
except SyntaxError as e:
    print(f"SyntaxError: {e}")
    sys.exit(1)

print("Verification complete.")

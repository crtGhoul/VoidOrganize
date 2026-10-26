import os
import sys
from pathlib import Path

# Set working directory to app folder
os.chdir(Path(__file__).parent)

from ui import launch_app

if __name__ == "__main__":
    target_dir = sys.argv[1] if len(sys.argv) > 1 and os.path.isdir(sys.argv[1]) else None
    launch_app(initial_dir=target_dir)

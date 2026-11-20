import sys
from pathlib import Path

# Let scripts import the `app` package when run as `python scripts/<name>.py`.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

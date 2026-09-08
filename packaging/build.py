"""Build a native Spacetime bundle with PyInstaller."""
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]

# Keep packaging reproducible by invoking the project's checked-in spec.
subprocess.check_call([sys.executable, "-m", "PyInstaller", str(ROOT / "packaging" / "spacetime.spec"), "--noconfirm"])

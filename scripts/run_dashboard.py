"""Запуск Streamlit dashboard."""
import subprocess
import sys
from pathlib import Path

root = Path(__file__).parent.parent
subprocess.run(
    [sys.executable, "-m", "streamlit", "run", str(root / "dashboard" / "app.py")],
    cwd=str(root),
)

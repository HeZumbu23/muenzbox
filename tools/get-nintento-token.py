"""Deprecated wrapper for backward compatibility.

Use `tools/get-nintendo-token.py` instead.
"""

from pathlib import Path
import runpy

if __name__ == "__main__":
    target = Path(__file__).with_name("get-nintendo-token.py")
    runpy.run_path(str(target), run_name="__main__")

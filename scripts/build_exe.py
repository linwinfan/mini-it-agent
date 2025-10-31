#!/usr/bin/env python3
"""Main entry point for EXE packaging tool."""

import sys
from pathlib import Path

# Add src to Python path to import minisweagent modules
src_path = Path(__file__).parent.parent / "src"
sys.path.insert(0, str(src_path))

from minisweagent.packaging.cli import app


if __name__ == "__main__":
    app()
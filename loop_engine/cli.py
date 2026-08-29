"""
loop_engine/cli.py
Module-level CLI Entrypoint for 10 SHADOWS (python -m loop_engine.cli).
"""

from __future__ import annotations

import sys
from pathlib import Path

# Redirect to canonical ts_run implementation
from ts_run import main

if __name__ == "__main__":
    sys.exit(main())

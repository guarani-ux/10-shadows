"""
scripts/check_fast.py
Fast Tier Local Quality & Invariant Gate for 10 SHADOWS.
Used frequently during iteration.
"""

from __future__ import annotations

import subprocess
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def run_step(name: str, cmd: list[str], cwd: Path = PROJECT_ROOT) -> bool:
    print(f"\n[FAST CHECK] >>> {name} ({' '.join(cmd)})")
    start = time.time()
    res = subprocess.run(cmd, cwd=cwd)
    elapsed = time.time() - start
    if res.returncode != 0:
        print(f"[FAST CHECK FAILED] {name} exited with code {res.returncode} ({elapsed:.2f}s)")
        return False
    print(f"[FAST CHECK PASSED] {name} ({elapsed:.2f}s)")
    return True


def main() -> int:
    print("=" * 60)
    print("10 SHADOWS — FAST CHECK PIPELINE")
    print("=" * 60)

    steps = [
        ("Python Linting (Ruff Check)", ["ruff", "check", "."]),
        ("Python Formatting (Ruff Format)", ["ruff", "format", "--check", "."]),
        ("Rust Formatting (rustfmt)", ["cargo", "fmt", "--check"]),
        ("Rust Static Analysis (clippy)", ["cargo", "clippy", "--workspace", "--all-targets", "--", "-D", "warnings"]),
        ("Rust Unit & Adversarial Tests", ["cargo", "test", "--workspace"]),
        (
            "Core Constitutional & Epistemic Tests",
            ["pytest", "tests/test_constitutional_foundation.py", "-q", "--tb=short"],
        ),
    ]

    for name, cmd in steps:
        if not run_step(name, cmd):
            return 1

    print("\n" + "=" * 60)
    print("[FAST CHECK PASSED] All fast-tier verification checks succeeded.")
    print("=" * 60)
    return 0


if __name__ == "__main__":
    sys.exit(main())

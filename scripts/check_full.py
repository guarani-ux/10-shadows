"""
scripts/check_full.py
Full Tier Qualification & Pre-Release Gate for 10 SHADOWS.
Used before promotion, release, or pull-request submission.
"""

from __future__ import annotations

import subprocess
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def run_step(name: str, cmd: list[str], cwd: Path = PROJECT_ROOT) -> bool:
    print(f"\n[FULL CHECK] >>> {name} ({' '.join(cmd)})")
    start = time.time()
    res = subprocess.run(cmd, cwd=cwd)
    elapsed = time.time() - start
    if res.returncode != 0:
        print(f"[FULL CHECK FAILED] {name} exited with code {res.returncode} ({elapsed:.2f}s)")
        return False
    print(f"[FULL CHECK PASSED] {name} ({elapsed:.2f}s)")
    return True


def check_git_cleanliness() -> bool:
    print("\n[FULL CHECK] >>> Verifying Working Tree Cleanliness")
    res = subprocess.run(["git", "status", "--porcelain"], cwd=PROJECT_ROOT, capture_output=True, text=True)
    uncommitted = res.stdout.strip()
    if uncommitted:
        print(f"[FULL CHECK FAILED] Uncommitted/dirty working directory detected:\n{uncommitted}")
        return False
    print("[FULL CHECK PASSED] Working directory is clean.")
    return True


def main() -> int:
    print("=" * 60)
    print("10 SHADOWS — FULL QUALIFICATION PIPELINE")
    print("=" * 60)

    steps = [
        ("Preflight Health Check", [sys.executable, "scripts/preflight.py"]),
        ("Python Linting (Ruff Check)", ["ruff", "check", "."]),
        ("Python Formatting (Ruff Format)", ["ruff", "format", "--check", "."]),
        ("Rust Formatting (rustfmt)", ["cargo", "fmt", "--check"]),
        ("Rust Static Analysis (clippy)", ["cargo", "clippy", "--workspace", "--all-targets", "--", "-D", "warnings"]),
        ("Rust Kernel Build & Tests", ["cargo", "test", "--workspace"]),
        ("Full Python Ecosystem Pytest Suite", [sys.executable, "-m", "pytest", "-q", "--tb=short"]),
    ]

    for name, cmd in steps:
        if not run_step(name, cmd):
            return 1

    if not check_git_cleanliness():
        return 1

    print("\n" + "=" * 60)
    print("[FULL QUALIFICATION PASSED] All systems, tests, and hygiene checks verified.")
    print("=" * 60)
    return 0


if __name__ == "__main__":
    sys.exit(main())

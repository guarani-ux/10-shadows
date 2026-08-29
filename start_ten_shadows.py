#!/usr/bin/env python3
"""Compatibility launcher that delegates governed execution to ``ts_run.py``.

Historically this file contained a second execution path that could call
``TenShadowsKernel.run_objective`` directly. That duplicated authority and could
produce receipts under semantics different from the canonical orchestrator.

This launcher now preserves the familiar command shape while delegating run and
receipt verification to the single public Python entrypoint. ``--mutate`` is
retained as a compatibility alias for the canonical ``--promote`` opt-in.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

from loop_engine.kernel_db import KernelDatabase

PROJECT_ROOT = Path(__file__).resolve().parent
CANONICAL_ENTRYPOINT = PROJECT_ROOT / "ts_run.py"


def _run_canonical(arguments: list[str]) -> int:
    return subprocess.run(
        [sys.executable, str(CANONICAL_ENTRYPOINT), *arguments],
        cwd=str(PROJECT_ROOT),
        check=False,
    ).returncode


def handle_run(target: str | None, objective: str | None, mutate: bool, provider: str, max_attempts: int) -> int:
    if not objective:
        try:
            objective = input("What do you want accomplished?\n> ").strip()
        except EOFError:
            objective = ""
    if not objective:
        print("[ERROR] Objective cannot be empty.", file=sys.stderr)
        return 1

    args = ["run", objective, "--builder", provider, "--max-attempts", str(max_attempts)]
    if target:
        args.extend(["--target", target])
    if mutate:
        args.append("--promote")
    return _run_canonical(args)


def handle_verify(receipt: str) -> int:
    return _run_canonical(["verify", receipt])


def handle_status() -> int:
    """Report persisted run records without upgrading them into capability claims."""
    kernel_db = KernelDatabase()
    with kernel_db.get_connection() as conn:
        runs = conn.execute(
            "SELECT run_id, task_id, status, started_at FROM runs ORDER BY rowid DESC LIMIT 10"
        ).fetchall()

    print("TEN SHADOWS — LOCAL KERNEL RECORDS")
    if not runs:
        print("No local run records found.")
        return 0
    for record in runs:
        print(
            f"[{record['status']}] {record['run_id']} "
            f"(task: {record['task_id']}, started: {record['started_at']})"
        )
    print("These are local records, not repository-wide capability certification.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Compatibility launcher; governed execution is delegated to ts_run.py"
    )
    subparsers = parser.add_subparsers(dest="command")

    run_parser = subparsers.add_parser("run", help="Execute through the canonical governed entrypoint")
    run_parser.add_argument("--target", "-t", type=str)
    run_parser.add_argument("--objective", "-o", type=str)
    run_parser.add_argument(
        "--mutate",
        "-m",
        action="store_true",
        help="Compatibility alias for explicit --promote authorization",
    )
    run_parser.add_argument(
        "--provider",
        "-p",
        default="deterministic",
        choices=["deterministic", "gemini", "antigravity"],
    )
    run_parser.add_argument("--max-attempts", type=int, default=3)

    verify_parser = subparsers.add_parser("verify-receipt", help="Verify a receipt through ts_run.py")
    verify_parser.add_argument("receipt", type=str)

    subparsers.add_parser("status", help="Show local persisted run records")

    args = parser.parse_args()
    if args.command == "run":
        return handle_run(args.target, args.objective, args.mutate, args.provider, args.max_attempts)
    if args.command == "verify-receipt":
        return handle_verify(args.receipt)
    if args.command == "status":
        return handle_status()

    parser.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())

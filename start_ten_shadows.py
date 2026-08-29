#!/usr/bin/env python3
"""
start_ten_shadows.py
Unified Human-Facing Launcher & Execution Authority Entrypoint for 10 SHADOWS.

Supports:
- Canonical Rust Trusted Kernel delegation (`ts`)
- Interactive operator ingress
- Receipt verification
- Status inspection
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Optional

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from loop_engine.execution_authority import (
    RunStatus,
    TenShadowsKernel,
    is_ten_shadows_execution,
    verify_execution_receipt,
)
from loop_engine.kernel_db import KernelDatabase


def find_ts_binary() -> Optional[Path]:
    """Finds the compiled ts kernel binary if present."""
    possible_paths = [
        PROJECT_ROOT / "crates" / "ten_shadows_kernel" / "target" / "release" / "ts.exe",
        PROJECT_ROOT / "crates" / "ten_shadows_kernel" / "target" / "release" / "ts",
        PROJECT_ROOT / "crates" / "ten_shadows_kernel" / "target" / "debug" / "ts.exe",
        PROJECT_ROOT / "crates" / "ten_shadows_kernel" / "target" / "debug" / "ts",
    ]
    for p in possible_paths:
        if p.exists() and p.is_file():
            return p

    # Check PATH
    which_ts = shutil.which("ts")
    if which_ts:
        return Path(which_ts)
    return None


def handle_run(
    target_str: Optional[str],
    objective_str: Optional[str],
    mutate: bool = False,
    provider: str = "deterministic",
    model: str = "deterministic-v1",
    strategy: Optional[str] = None,
) -> int:
    """Executes a fully governed Ten Shadows run via canonical trusted kernel."""
    print("========================================================", flush=True)
    print("       TEN SHADOWS CANONICAL KERNEL EXECUTION           ", flush=True)
    print("========================================================", flush=True)

    # 1. Gather target and objective
    if not target_str:
        try:
            target_str = input("Target path or repository: ").strip()
        except EOFError:
            print("[ERROR] No target supplied.", file=sys.stderr)
            return 1

    target_path = Path(target_str).resolve()
    if not target_path.exists():
        print(f"[ERROR] Target path does not exist: {target_path}", file=sys.stderr)
        return 1

    if not objective_str:
        try:
            print("What do you want accomplished?")
            objective_str = input("> ").strip()
        except EOFError:
            print("[ERROR] No objective supplied.", file=sys.stderr)
            return 1

    if not objective_str:
        print("[ERROR] Objective cannot be empty.", file=sys.stderr)
        return 1

    # 2. Check if canonical Rust binary is available
    ts_bin = find_ts_binary()
    if ts_bin:
        cmd = [
            str(ts_bin),
            "run",
            "--target",
            str(target_path),
            "--objective",
            objective_str,
            "--provider",
            provider,
            "--model",
            model,
        ]
        if mutate:
            cmd.append("--mutate")
        if strategy:
            cmd.extend(["--strategy", strategy])

        proc = subprocess.run(cmd, cwd=str(PROJECT_ROOT))
        return proc.returncode

    # 3. Fallback to Python Kernel Implementation
    print("\n[KERNEL] Initializing Ten Shadows Python Kernel...", flush=True)
    print(f"  Target:    {target_path}", flush=True)
    print(f"  Objective: {objective_str[:80]}...", flush=True)

    kernel = TenShadowsKernel()
    receipt = kernel.run_objective(
        objective=objective_str,
        target_path=target_path,
        provider_name=provider,
        model_name=model,
    )

    print("\n========================================================", flush=True)
    print("              TEN SHADOWS RUN CONCLUDED                 ", flush=True)
    print("========================================================", flush=True)
    print(f"Run ID:         {receipt.run_id}", flush=True)
    print(f"Status:         {receipt.final_status.value}", flush=True)
    print(f"Strategy:       {receipt.routing_strategy.value}", flush=True)
    print(f"Capabilities:   {', '.join(receipt.capabilities_selected)}", flush=True)
    print(f"Workers:        {len(receipt.worker_invocations)}", flush=True)
    if receipt.verification:
        print(
            f"Tests Passed:   {receipt.verification.tests_passed}/{receipt.verification.tests_collected} (Exit {receipt.verification.exit_code})",
            flush=True,
        )
    print(f"Signature:      {receipt.receipt_signature[:16]}...", flush=True)
    print(f"Receipt File:   .receipts/{receipt.run_id}_receipt.json\n", flush=True)

    is_valid = is_ten_shadows_execution(receipt.run_id, kernel_db=kernel.db)
    print(f"Mechanical Ten Shadows Execution Verified: {is_valid}", flush=True)

    return 0 if receipt.final_status in (RunStatus.VERIFIED_SUCCESS, RunStatus.COMPLETED_UNVERIFIED) else 1


def handle_verify(receipt_identifier: str) -> int:
    """Mechanically verifies a receipt file or run ID."""
    print("========================================================", flush=True)
    print("           TEN SHADOWS RECEIPT VERIFICATION            ", flush=True)
    print("========================================================", flush=True)
    print(f"Target: {receipt_identifier}\n", flush=True)

    ts_bin = find_ts_binary()
    if ts_bin:
        cmd = [str(ts_bin), "verify-receipt", receipt_identifier]
        proc = subprocess.run(cmd, cwd=str(PROJECT_ROOT))
        return proc.returncode

    kernel = TenShadowsKernel()
    target_path = Path(receipt_identifier)

    if target_path.exists():
        is_valid, errors = verify_execution_receipt(target_path, kernel_db=kernel.db)
    else:
        is_valid = is_ten_shadows_execution(receipt_identifier, kernel_db=kernel.db)
        receipt_file = PROJECT_ROOT / ".receipts" / f"{receipt_identifier}_receipt.json"
        if receipt_file.exists():
            _, errors = verify_execution_receipt(receipt_file, kernel_db=kernel.db)
        else:
            errors = ["Receipt file not found on disk; checked KernelDatabase."]

    if is_valid:
        print("[VERIFICATION PASSED] Valid kernel-governed execution receipt.", flush=True)
        return 0
    else:
        print("[VERIFICATION FAILED] Execution cannot be certified as Ten Shadows:", flush=True)
        for err in errors:
            print(f"  - {err}", flush=True)
        return 1


def handle_status() -> int:
    """Displays kernel database summary and active runs."""
    print("========================================================", flush=True)
    print("              TEN SHADOWS KERNEL STATUS                 ", flush=True)
    print("========================================================", flush=True)

    kernel_db = KernelDatabase()
    with kernel_db.get_connection() as conn:
        runs = conn.execute(
            "SELECT run_id, task_id, status, started_at FROM runs ORDER BY rowid DESC LIMIT 10"
        ).fetchall()
        receipts = conn.execute(
            "SELECT id, run_id, task_id, status, created_at FROM receipts ORDER BY id DESC LIMIT 5"
        ).fetchall()

    print(f"Recent Runs ({len(runs)}):", flush=True)
    for r in runs:
        print(f"  - [{r['status']}] {r['run_id']} (Task: {r['task_id']}) started {r['started_at']}", flush=True)

    print(f"\nRecent Sealed Receipts ({len(receipts)}):", flush=True)
    for rc in receipts:
        print(f"  - [{rc['status']}] Run: {rc['run_id']} (Receipt #{rc['id']}) sealed {rc['created_at']}", flush=True)

    print("\n========================================================\n", flush=True)
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Ten Shadows Execution Authority & Launcher")
    subparsers = parser.add_subparsers(dest="command")

    # 'run' subcommand
    run_parser = subparsers.add_parser("run", help="Execute an objective under Ten Shadows kernel authority")
    run_parser.add_argument("--target", "-t", type=str, help="Target repository or working directory")
    run_parser.add_argument("--objective", "-o", type=str, help="Goal or objective statement")
    run_parser.add_argument(
        "--mutate", "-m", action="store_true", help="Authorize governed workspace mutations and promotion"
    )
    run_parser.add_argument(
        "--provider",
        "-p",
        type=str,
        default="deterministic",
        help="Model/worker provider (deterministic, gemini, shadow:forge, shadow:alchemist, shadow:svris)",
    )
    run_parser.add_argument("--model", type=str, default="deterministic-v1", help="Requested model ID")
    run_parser.add_argument("--strategy", "-s", type=str, help="Routing strategy override")

    # 'verify-receipt' subcommand
    verify_parser = subparsers.add_parser("verify-receipt", help="Mechanically verify an execution receipt or run ID")
    verify_parser.add_argument("receipt", type=str, help="Path to receipt JSON file or run_id string")

    # 'status' subcommand
    subparsers.add_parser("status", help="Show kernel database status and recent runs")

    args = parser.parse_args()

    if args.command == "run":
        return handle_run(
            target_str=args.target,
            objective_str=args.objective,
            mutate=args.mutate,
            provider=args.provider,
            model=args.model,
            strategy=args.strategy,
        )
    elif args.command == "verify-receipt":
        return handle_verify(args.receipt)
    elif args.command == "status":
        return handle_status()
    else:
        return handle_run(
            target_str=None,
            objective_str=None,
            mutate=False,
            provider="deterministic",
            model="deterministic-v1",
        )


if __name__ == "__main__":
    sys.exit(main())

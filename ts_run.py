#!/usr/bin/env python3
"""
ts_run.py — Canonical Deterministic Public CLI Entrypoint for 10 SHADOWS.

Usage:
    python ts_run.py run "<objective>" [options]
    python ts_run.py run --file <objective_file.md> [options]
    python ts_run.py verify <receipt_path.json>
    python ts_run.py capabilities list [--status QUALIFIED|UNQUALIFIED]

Options:
    --target PATH       Target repository / directory (default: current working directory)
    --domain DOMAIN     Domain classification code (default: general_engineering)
    --builder PROVIDER  Builder provider: deterministic, gemini, antigravity (default: deterministic)
    --verifier PROVIDER Verifier provider: deterministic (default: deterministic)
    --max-attempts N    Maximum repair loop attempts (default: 3)
    --no-promote        Execute and verify inside governed workspace without modifying target
    --json              Emit structured JSON output

Invariants:
    NO VALID KERNEL-ISSUED EXECUTION RECEIPT = TEN SHADOWS DID NOT EXECUTE.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Ensure PROJECT_ROOT is on sys.path
PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from loop_engine.capability_registry import CapabilityRegistry
from loop_engine.execution_authority import verify_execution_receipt
from loop_engine.orchestrator import TenShadowsOrchestrator


def cmd_run(args: argparse.Namespace) -> int:
    # Resolve Objective Content
    if args.file:
        file_path = Path(args.file).resolve()
        if not file_path.exists():
            print(f"Error: Objective file '{args.file}' does not exist.", file=sys.stderr)
            return 1
        objective_text = file_path.read_text(encoding="utf-8").strip()
    elif args.objective:
        objective_text = args.objective.strip()
    else:
        print("Error: Either an objective string or --file <path> must be provided.", file=sys.stderr)
        return 1

    orchestrator = TenShadowsOrchestrator()
    try:
        report = orchestrator.run_objective(
            objective=objective_text,
            target_path=args.target,
            domain_code=args.domain,
            builder_provider=args.builder,
            verifier_provider=args.verifier,
            max_attempts=args.max_attempts,
            no_promote=args.no_promote,
        )

        if args.json:
            print(json.dumps(report.to_dict(), indent=2, sort_keys=True))
        else:
            report.print_summary()

        # Fails closed if receipt is not valid or objective failed
        if not report.receipt_valid or report.status != "VERIFIED_SUCCESS":
            return 1
        return 0

    except Exception as e:
        print(f"[FATAL] Orchestrator execution error: {e}", file=sys.stderr)
        return 1


def cmd_verify(args: argparse.Namespace) -> int:
    receipt_path = Path(args.receipt_path).resolve()
    if not receipt_path.exists():
        print(f"Error: Receipt file '{args.receipt_path}' does not exist.", file=sys.stderr)
        return 1

    is_valid, errors = verify_execution_receipt(receipt_path)
    if args.json:
        print(json.dumps({"receipt_path": str(receipt_path), "is_valid": is_valid, "errors": errors}, indent=2))
    else:
        print("=" * 60)
        print("10 SHADOWS — RECEIPT INDEPENDENT VERIFICATION")
        print("=" * 60)
        print(f"RECEIPT_PATH:       {receipt_path}")
        print(f"RECEIPT_VALID:      {is_valid}")
        print(f"ERRORS:             {', '.join(errors) or 'NONE'}")
        print("=" * 60)

    if not is_valid or errors:
        return 1
    return 0


def cmd_capabilities(args: argparse.Namespace) -> int:
    registry = CapabilityRegistry()
    caps = registry.list_capabilities(status_filter=args.status)
    if args.json:
        print(json.dumps([c.to_dict() for c in caps], indent=2, sort_keys=True))
    else:
        print("=" * 60)
        print("10 SHADOWS — CAPABILITY REGISTRY")
        print("=" * 60)
        if not caps:
            print("No capabilities found matching filter.")
        for c in caps:
            print(f"[{c.epistemic_status}] {c.capability_id} (v{c.version}) - {c.name}")
            print(f"  Purpose:      {c.declared_purpose}")
            print(f"  Artifacts:    {', '.join(c.artifact_paths)}")
            print(f"  Origin Run:   {c.originating_run_id}")
            print("-" * 60)
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="10 SHADOWS Canonical Sovereign Execution Entrypoint")
    subparsers = parser.add_subparsers(dest="subcommand", required=True)

    # Subcommand: run
    run_parser = subparsers.add_parser("run", help="Execute an objective through Ten Shadows Kernel")
    run_parser.add_argument("objective", nargs="?", default=None, help="Raw objective description string")
    run_parser.add_argument("--file", "-f", help="Path to markdown or text file containing objective")
    run_parser.add_argument("--target", "-t", default=str(PROJECT_ROOT), help="Target repository path")
    run_parser.add_argument("--domain", "-d", default="general_engineering", help="Domain classification code")
    run_parser.add_argument(
        "--builder", "-b", default="deterministic", help="Builder provider: deterministic, gemini, antigravity"
    )
    run_parser.add_argument("--verifier", "-v", default="deterministic", help="Verifier provider: deterministic")
    run_parser.add_argument("--max-attempts", "-m", type=int, default=3, help="Maximum repair loop attempts")
    run_parser.add_argument("--no-promote", action="store_true", help="Do not promote workspace changes to target")
    run_parser.add_argument("--json", action="store_true", help="Output execution report as JSON")

    # Subcommand: verify
    verify_parser = subparsers.add_parser("verify", help="Verify cryptographic integrity of an execution receipt")
    verify_parser.add_argument("receipt_path", help="Path to receipt JSON file")
    verify_parser.add_argument("--json", action="store_true", help="Output verification report as JSON")

    # Subcommand: capabilities
    cap_parser = subparsers.add_parser("capabilities", help="Inspect and query registered capabilities")
    cap_sub = cap_parser.add_subparsers(dest="cap_action", required=True)
    list_parser = cap_sub.add_parser("list", help="List registered capabilities")
    list_parser.add_argument(
        "--status", choices=["QUALIFIED", "UNQUALIFIED", "AUTHORITATIVE", "REJECTED"], help="Filter by status"
    )
    list_parser.add_argument("--json", action="store_true", help="Output list as JSON")

    args = parser.parse_args()

    if args.subcommand == "run":
        return cmd_run(args)
    elif args.subcommand == "verify":
        return cmd_verify(args)
    elif args.subcommand == "capabilities":
        return cmd_capabilities(args)
    else:
        parser.print_help()
        return 1


if __name__ == "__main__":
    sys.exit(main())

"""
tests/test_unsupported_objective_fail_closed.py
Adversarial test proving that an unknown or unsupported objective fails closed
and NEVER falsely reports VERIFIED_SUCCESS or SATISFIED.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

from loop_engine.capability_registry import CapabilityRegistry
from loop_engine.config import PROJECT_ROOT
from loop_engine.execution_authority import TenShadowsKernel
from loop_engine.kernel_db import KernelDatabase
from loop_engine.orchestrator import TenShadowsOrchestrator


def test_unsupported_historical_objective_fails_closed(tmp_path):
    """
    An objective with no deterministic synthesizer or domain oracle must fail closed.
    It must NEVER achieve VERIFIED_SUCCESS or SATISFIED status.
    """
    k_db = KernelDatabase(db_path=tmp_path / "kernel.db")
    receipts_dir = tmp_path / ".receipts"
    receipts_dir.mkdir(parents=True, exist_ok=True)
    registry = CapabilityRegistry(db_path=tmp_path / "capabilities.db")
    kernel = TenShadowsKernel(kernel_db=k_db, receipts_dir=receipts_dir)
    target_dir = tmp_path / "target_app"
    target_dir.mkdir(parents=True, exist_ok=True)

    orchestrator = TenShadowsOrchestrator(
        kernel=kernel,
        registry=registry,
        kernel_db=k_db,
        receipts_dir=receipts_dir,
    )

    unsupported_obj = (
        "Determine whether the Magna Carta directly caused the French Revolution "
        "and produce a historically verified conclusion."
    )

    report = orchestrator.run_objective(
        objective=unsupported_obj,
        target_path=target_dir,
        task_id="task_unsupported_history",
        max_attempts=1,
    )

    # MUST NOT be VERIFIED_SUCCESS
    assert report.status != "VERIFIED_SUCCESS", f"Defect: Unsupported objective achieved {report.status}"
    # MUST NOT be SATISFIED
    assert report.objective_status != "SATISFIED", f"Defect: Unsupported objective achieved {report.objective_status}"
    # Verification MUST NOT be PASS
    assert report.verification_status != "PASS", f"Defect: Verification status was {report.verification_status}"


def test_cli_unsupported_objective_exits_nonzero(tmp_path):
    """
    Running an unsupported objective via the canonical CLI (ts_run.py) must exit nonzero.
    """
    unsupported_obj = (
        "Determine whether the Magna Carta directly caused the French Revolution "
        "and produce a historically verified conclusion."
    )
    cmd = [
        sys.executable,
        str(PROJECT_ROOT / "ts_run.py"),
        "run",
        unsupported_obj,
        "--target",
        str(tmp_path / "target_cli"),
        "--max-attempts",
        "1",
    ]
    res = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8")
    assert res.returncode != 0, (
        f"Defect: CLI exited with 0 for unsupported objective. Output:\n{res.stdout}\n{res.stderr}"
    )

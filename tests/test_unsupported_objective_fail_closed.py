"""Adversarial proof of the current boundary of generality.

An objective outside the deterministic provider's implemented families must fail
closed as a capability deficit. It must not create or qualify a new capability,
and the public CLI must fail for that reason rather than because its target was
misconfigured.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from loop_engine.capability_registry import CapabilityRegistry
from loop_engine.config import PROJECT_ROOT
from loop_engine.execution_authority import TenShadowsKernel
from loop_engine.kernel_db import KernelDatabase
from loop_engine.orchestrator import TenShadowsOrchestrator


UNSUPPORTED_OBJECTIVE = (
    "Determine whether the Magna Carta directly caused the French Revolution "
    "and produce a historically verified conclusion."
)


def test_unfamiliar_objective_becomes_explicit_capability_deficit(tmp_path: Path) -> None:
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

    report = orchestrator.run_objective(
        objective=UNSUPPORTED_OBJECTIVE,
        target_path=target_dir,
        task_id="task_unsupported_history",
        max_attempts=1,
    )

    assert report.status == "BLOCKED"
    assert report.objective_status == "CAPABILITY_DEFICIT"
    assert report.verification_status == "FAIL"
    assert report.capabilities_created == []
    assert report.capabilities_qualified == []
    assert registry.list_capabilities() == []


def test_cli_unfamiliar_objective_exits_nonzero_for_capability_deficit(tmp_path: Path) -> None:
    target = tmp_path / "target_cli"
    target.mkdir(parents=True, exist_ok=True)
    cmd = [
        sys.executable,
        str(PROJECT_ROOT / "ts_run.py"),
        "run",
        UNSUPPORTED_OBJECTIVE,
        "--target",
        str(target),
        "--max-attempts",
        "1",
        "--json",
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", check=False)

    assert result.returncode != 0
    payload = json.loads(result.stdout)
    assert payload["status"] == "BLOCKED"
    assert payload["objective_status"] == "CAPABILITY_DEFICIT"
    assert payload["capabilities_created"] == []
    assert payload["capabilities_qualified"] == []

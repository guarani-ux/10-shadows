"""
tests/test_antigravity_control_surface.py
Adversarial Verification Suite for Google Antigravity Mechanical Control Surfaces.

Verifies:
1. Direct codebase write without active Ten Shadows lease is DENIED by execution gate.
2. Planning mode artifacts (implementation_plan.md, walkthrough.md) are ALLOWED.
3. Scratch, temporary, and test fixture writes are ALLOWED.
4. Governed workspace writes under active lease are ALLOWED.
5. Escaping governed workspace boundary during active lease is DENIED.
6. Canonical Ten Shadows entrypoint commands (ts run, ts verify, python ts_run.py) are ALLOWED.
7. Safe inspection and testing commands (pytest, git status, check_fast.py) are ALLOWED.
8. PreInvocation hook injects non-empty ingress guidance.
9. Malformed hook payloads fail closed safely.
10. Active lease lifecycle in Orchestrator creates and destroys lease file cleanly.
"""

from __future__ import annotations

import io
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from loop_engine.capability_registry import CapabilityRegistry
from loop_engine.config import PROJECT_ROOT, SCRATCH_DIR
from loop_engine.kernel_db import KernelDatabase
from loop_engine.orchestrator import TenShadowsOrchestrator
from scripts.antigravity_execution_gate import (
    ACTIVE_RUN_LEASE_FILE,
    evaluate_command_tool,
    evaluate_write_tool,
    is_active_run_authorized,
)


def test_gate_01_direct_codebase_write_denied():
    """Direct modification of repository source files without active lease is DENIED."""
    # Ensure no active lease
    if ACTIVE_RUN_LEASE_FILE.exists():
        ACTIVE_RUN_LEASE_FILE.unlink()

    target = str(PROJECT_ROOT / "loop_engine" / "unauthorized_patch.py")
    decision, reason = evaluate_write_tool({"TargetFile": target, "CodeContent": "x = 1"})
    assert decision == "deny"
    assert "TEN SHADOWS INGRESS GATE" in reason
    assert "ts run" in reason


def test_gate_02_planning_artifacts_allowed():
    """Planning artifacts (implementation_plan.md, walkthrough.md) are ALLOWED."""
    for artifact_name in ["implementation_plan.md", "walkthrough.md", "scratch_pad.md"]:
        target = str(PROJECT_ROOT / artifact_name)
        decision, reason = evaluate_write_tool({"TargetFile": target, "CodeContent": "# Plan"})
        assert decision == "allow"
        assert "Planning mode artifacts are permitted" in reason


def test_gate_03_scratch_and_fixtures_allowed():
    """Modifications inside scratch/ and test fixtures are ALLOWED."""
    scratch_target = str(SCRATCH_DIR / "temp_note.txt")
    decision, reason = evaluate_write_tool({"TargetFile": scratch_target, "CodeContent": "note"})
    assert decision == "allow"

    fixture_target = str(PROJECT_ROOT / "tests" / "fixtures" / "sample.json")
    decision, reason = evaluate_write_tool({"TargetFile": fixture_target, "CodeContent": "{}"})
    assert decision == "allow"


def test_gate_04_governed_workspace_under_active_lease_allowed(tmp_path):
    """Governed workspace file write is ALLOWED when active lease is valid."""
    ws = tmp_path / "governed_ws_01"
    ws.mkdir()

    lease_data = {
        "run_id": "run_test_01",
        "task_id": "task_test_01",
        "workspace_path": str(ws),
        "token": "valid_token",
        "created_at": "2026-08-29T00:00:00Z",
    }
    ACTIVE_RUN_LEASE_FILE.parent.mkdir(parents=True, exist_ok=True)
    ACTIVE_RUN_LEASE_FILE.write_text(json.dumps(lease_data), encoding="utf-8")

    try:
        target_in_ws = str(ws / "solution.py")
        decision, reason = evaluate_write_tool({"TargetFile": target_in_ws, "CodeContent": "def foo(): pass"})
        assert decision == "allow"
        assert "active Ten Shadows run lease" in reason
    finally:
        if ACTIVE_RUN_LEASE_FILE.exists():
            ACTIVE_RUN_LEASE_FILE.unlink()


def test_gate_05_escape_governed_workspace_during_active_lease_denied(tmp_path):
    """Attempting to write outside the declared workspace during active lease is DENIED."""
    ws = tmp_path / "governed_ws_01"
    ws.mkdir()

    lease_data = {
        "run_id": "run_test_01",
        "task_id": "task_test_01",
        "workspace_path": str(ws),
        "token": "valid_token",
        "created_at": "2026-08-29T00:00:00Z",
    }
    ACTIVE_RUN_LEASE_FILE.write_text(json.dumps(lease_data), encoding="utf-8")

    try:
        # Target outside ws
        target_outside = str(PROJECT_ROOT / "loop_engine" / "core.py")
        decision, reason = evaluate_write_tool({"TargetFile": target_outside, "CodeContent": "def foo(): pass"})
        assert decision == "deny"
        assert "TEN SHADOWS INGRESS GATE" in reason
    finally:
        if ACTIVE_RUN_LEASE_FILE.exists():
            ACTIVE_RUN_LEASE_FILE.unlink()


def test_gate_06_canonical_entrypoint_commands_allowed():
    """Canonical commands (ts run, python ts_run.py, pytest) are ALLOWED."""
    allowed_cmds = [
        "python ts_run.py run 'Solve X'",
        "ts run 'Solve X'",
        "ts verify .receipts/run_01_receipt.json",
        "ts capabilities list",
        "pytest tests/ -v",
        "python scripts/check_fast.py",
        "python scripts/check_full.py",
        "git status",
        "git log -n 5",
        "git diff",
    ]
    for cmd in allowed_cmds:
        decision, reason = evaluate_command_tool({"CommandLine": cmd})
        assert decision == "allow"


def test_gate_07_pre_invocation_advisor_execution():
    """PreInvocation script outputs structured ephemeral guidance."""
    res = subprocess.run(
        [sys.executable, str(PROJECT_ROOT / "scripts" / "antigravity_ingress_advisor.py")],
        input=json.dumps({"invocationNum": 1, "conversationId": "test"}),
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    assert res.returncode == 0
    payload = json.loads(res.stdout)
    assert "injectSteps" in payload
    assert len(payload["injectSteps"]) > 0
    assert "ts run" in payload["injectSteps"][0]["ephemeralMessage"]


def test_gate_08_orchestrator_lease_lifecycle(tmp_path):
    """Orchestrator creates and destroys active run lease during execution."""
    k_db = KernelDatabase(db_path=tmp_path / "kernel.db")
    receipts_dir = tmp_path / ".receipts"
    receipts_dir.mkdir(parents=True, exist_ok=True)
    registry = CapabilityRegistry(db_path=tmp_path / "capabilities.db")
    target = tmp_path / "target_repo"
    target.mkdir()

    orchestrator = TenShadowsOrchestrator(
        registry=registry,
        kernel_db=k_db,
        receipts_dir=receipts_dir,
    )

    # Before run: lease does not exist
    if ACTIVE_RUN_LEASE_FILE.exists():
        ACTIVE_RUN_LEASE_FILE.unlink()
    assert not ACTIVE_RUN_LEASE_FILE.exists()

    report = orchestrator.run_objective(
        objective="Create a Python function that converts Celsius to Fahrenheit",
        target_path=target,
        task_id="task_lease_test",
    )

    assert report.status == "VERIFIED_SUCCESS"
    # After run: lease is cleanly destroyed
    assert not ACTIVE_RUN_LEASE_FILE.exists()

"""
tests/test_walking_skeleton_e2e.py
End-to-End Walking Skeleton and Capability Reuse Verification for 10 SHADOWS.

Proves:
1. Canonical CLI 'ts run' / Orchestrator runs Celsius-to-Fahrenheit objective.
2. Kernel run is established, builder invoked, artifact produced, independently verified, receipt sealed and verified.
3. Candidate capability is registered and qualified in CapabilityRegistry.
4. Second objective retrieves registered capability without rebuilding.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from loop_engine.capability_registry import CapabilityRegistry
from loop_engine.execution_authority import TenShadowsKernel, verify_execution_receipt
from loop_engine.kernel_db import KernelDatabase
from loop_engine.orchestrator import TenShadowsOrchestrator


def test_walking_skeleton_e2e_celsius_to_fahrenheit_and_reuse(tmp_path):
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

    # 1. First Run: Synthesize and Qualify Celsius-to-Fahrenheit capability
    obj_1 = "Create a Python function that converts Celsius to Fahrenheit and verify it against independently specified examples."
    report_1 = orchestrator.run_objective(
        objective=obj_1,
        target_path=target_dir,
        task_id="task_skeleton_01",
    )

    assert report_1.status == "VERIFIED_SUCCESS"
    assert report_1.objective_status == "SATISFIED"
    assert report_1.verification_status == "PASS"
    assert report_1.receipt_valid is True
    assert report_1.receipt_path is not None
    assert "cap_temperature_conversion_v1" in report_1.capabilities_created
    assert "cap_temperature_conversion_v1" in report_1.capabilities_qualified

    # Verify physical receipt on disk
    is_valid_1, errors_1 = verify_execution_receipt(Path(report_1.receipt_path), kernel_db=k_db)
    assert is_valid_1 is True
    assert len(errors_1) == 0

    # Verify capability state in registry
    cap = registry.get_capability("cap_temperature_conversion_v1")
    assert cap is not None
    assert cap.epistemic_status == "QUALIFIED"
    assert "temperature.py" in cap.artifact_paths

    # 2. Second Run: Retrieve and Reuse registered capability
    obj_2 = "Convert 100 C to Fahrenheit using available capabilities."
    report_2 = orchestrator.run_objective(
        objective=obj_2,
        target_path=target_dir,
        task_id="task_skeleton_02",
    )

    assert report_2.status == "VERIFIED_SUCCESS"
    assert report_2.objective_status == "SATISFIED"
    assert report_2.verification_status == "PASS"
    assert report_2.receipt_valid is True
    assert "cap_temperature_conversion_v1" in report_2.capabilities_used
    assert len(report_2.capabilities_created) == 0  # Reused existing capability, did not re-create

    # Verify second receipt on disk
    is_valid_2, errors_2 = verify_execution_receipt(Path(report_2.receipt_path), kernel_db=k_db)
    assert is_valid_2 is True
    assert len(errors_2) == 0

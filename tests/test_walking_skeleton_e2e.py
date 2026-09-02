"""Walking-skeleton proof for the narrow deterministic capability-learning loop.

The first run creates and independently verifies a capability without promoting it
into the target. Ten Shadows preserves the qualified artifact in its capability
store. A later run against a different empty target retrieves and reuses that
artifact. This proves bounded persistence/reuse for this explicit fixture family;
it is not evidence of general autonomous capability expansion.
"""

from __future__ import annotations

from pathlib import Path

from loop_engine.capability_registry import CapabilityRegistry
from loop_engine.execution_authority import TenShadowsKernel, verify_execution_receipt
from loop_engine.kernel_db import KernelDatabase
from loop_engine.orchestrator import TenShadowsOrchestrator


def test_walking_skeleton_e2e_celsius_to_fahrenheit_and_reuse(tmp_path):
    kernel_db = KernelDatabase(db_path=tmp_path / "kernel.db")
    receipts_dir = tmp_path / ".receipts"
    receipts_dir.mkdir(parents=True, exist_ok=True)
    registry = CapabilityRegistry(db_path=tmp_path / "capabilities.db")
    kernel = TenShadowsKernel(kernel_db=kernel_db, receipts_dir=receipts_dir)
    first_target = tmp_path / "first_target"
    second_target = tmp_path / "second_target"
    first_target.mkdir(parents=True, exist_ok=True)
    second_target.mkdir(parents=True, exist_ok=True)

    orchestrator = TenShadowsOrchestrator(
        kernel=kernel,
        registry=registry,
        kernel_db=kernel_db,
        receipts_dir=receipts_dir,
    )

    first_report = orchestrator.run_objective(
        objective="Create a Python function that converts Celsius to Fahrenheit and verify it against independently specified examples.",
        target_path=first_target,
        task_id="task_skeleton_01",
        no_promote=True,
    )

    assert first_report.status == "VERIFIED_SUCCESS"
    assert first_report.objective_status == "BEHAVIORALLY_VERIFIED"
    assert first_report.verification_status == "PASS"
    assert first_report.receipt_valid is True
    assert first_report.receipt_path is not None
    assert "cap_temperature_conversion_v1" in first_report.capabilities_created
    assert "cap_temperature_conversion_v1" in first_report.capabilities_qualified
    assert not (first_target / "temperature.py").exists()

    first_valid, first_errors = verify_execution_receipt(Path(first_report.receipt_path), kernel_db=kernel_db)
    assert first_valid is True
    assert not first_errors

    capability = registry.get_capability("cap_temperature_conversion_v1")
    assert capability is not None
    assert capability.epistemic_status == "QUALIFIED"
    assert "temperature.py" in capability.artifact_paths
    preserved = tmp_path / "capability_artifacts" / "cap_temperature_conversion_v1" / "temperature.py"
    assert preserved.is_file()

    second_report = orchestrator.run_objective(
        objective="Convert 100 C to Fahrenheit using available capabilities.",
        target_path=second_target,
        task_id="task_skeleton_02",
        no_promote=True,
    )

    assert second_report.status == "VERIFIED_SUCCESS"
    assert second_report.objective_status == "BEHAVIORALLY_VERIFIED"
    assert second_report.verification_status == "PASS"
    assert second_report.receipt_valid is True
    assert "cap_temperature_conversion_v1" in second_report.capabilities_used
    assert not second_report.capabilities_created
    assert not (second_target / "temperature.py").exists()
    assert not (second_target / "eval_temperature.py").exists()

    second_valid, second_errors = verify_execution_receipt(Path(second_report.receipt_path), kernel_db=kernel_db)
    assert second_valid is True
    assert not second_errors

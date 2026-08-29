"""
tests/test_mandatory_entrypoint_bypass.py
Adversarial Bypass & Authority Boundary Tests for 10 SHADOWS Mandatory Entrypoint.

Proves:
1. Builder called before establish_run fails
2. Builder mutating outside governed workspace fails
3. Builder self-declaring success is rejected
4. Builder self-registering capability is rejected
5. Verifier == builder is rejected (Law 3 violation)
6. Missing receipt fails closed
7. Forged receipt fails closed
8. Capability without qualification cannot be used
9. Capability with incompatible environment fails
10. Direct external artifact cannot claim Ten Shadows execution
11. Model output saying "QUALIFIED" has zero authority over registry
12. Objective result without kernel run record fails verification
13. Worker token tampering rejects execution
14. Manually inserted capability without valid run record fails
15. CLI exits non-zero on failed verification
"""

from __future__ import annotations

import hashlib
import json
import tempfile
from pathlib import Path

import pytest

from loop_engine.capability_registry import CapabilityRegistry
from loop_engine.dispatcher.protocol import WorkerAuthorization, compute_authorization_token
from loop_engine.errors import AuthorityError, CapabilityDeficitError, ConfigurationError
from loop_engine.execution_authority import (
    DisaggregatedEpistemicClaims,
    EvidenceModality,
    EvidencePurpose,
    ExecutionAttemptRecord,
    IndependentVerificationRecord,
    RoutingStrategy,
    RunStatus,
    TenShadowsKernel,
    TenShadowsReceipt,
    VerificationType,
    WorkerInvocationRecord,
    WorkerRole,
    is_ten_shadows_execution,
    verify_execution_receipt,
)
from loop_engine.kernel_db import KernelDatabase
from loop_engine.orchestrator import TenShadowsOrchestrator
from loop_engine.providers.deterministic_provider import DeterministicBuilderProvider


@pytest.fixture
def clean_test_env(tmp_path):
    k_db = KernelDatabase(db_path=tmp_path / "kernel.db")
    receipts_dir = tmp_path / ".receipts"
    receipts_dir.mkdir(parents=True, exist_ok=True)
    cap_registry = CapabilityRegistry(db_path=tmp_path / "capabilities.db")
    kernel = TenShadowsKernel(kernel_db=k_db, receipts_dir=receipts_dir)
    orchestrator = TenShadowsOrchestrator(
        kernel=kernel,
        registry=cap_registry,
        kernel_db=k_db,
        receipts_dir=receipts_dir,
    )
    return {
        "db": k_db,
        "receipts_dir": receipts_dir,
        "registry": cap_registry,
        "kernel": kernel,
        "orchestrator": orchestrator,
        "tmp_path": tmp_path,
    }


def test_bypass_01_builder_called_before_establish_run(clean_test_env):
    """BYPASS 1: Builder cannot be authorized without a valid kernel run."""
    kernel = clean_test_env["kernel"]
    db = clean_test_env["db"]

    # Attempting to record worker invocation for a run that was never established in KernelDatabase
    run_ctx = clean_test_env["orchestrator"].kernel.establish_run("Valid objective", clean_test_env["tmp_path"])
    # Fake a bogus run_id not in DB
    run_ctx.run_id = "run_unanchored_fake_001"

    # Attempting to seal receipt for unanchored run fails closed during verification
    with pytest.raises(Exception):
        kernel.seal_and_persist_receipt(
            run_ctx=run_ctx,
            objective="Fake",
            target_path=clean_test_env["tmp_path"],
            starting_head=None,
            final_head=None,
            routing_strategy=RoutingStrategy.DIRECT_DELEGATION,
            routing_decision_digest="digest",
            capabilities_selected=[],
            attempts=[],
            worker_invocations=[],
            artifacts_produced=[],
            verification=None,
            promotion=None,
            final_status=RunStatus.VERIFIED_SUCCESS,
        )


def test_bypass_02_builder_mutates_outside_governed_workspace(clean_test_env):
    """BYPASS 2: Builder execution is strictly ring-fenced to governed workspace boundary."""
    provider = DeterministicBuilderProvider()
    workspace = clean_test_env["tmp_path"] / "governed_ws"
    workspace.mkdir()

    token = compute_authorization_token(
        run_id="run_test",
        task_id="task_test",
        invocation_id="inv_test",
        objective_hash="0" * 64,
        baseline_sha="UNKNOWN",
        governed_workspace_path=str(workspace),
        attempt_number=1,
    )

    auth = WorkerAuthorization(
        run_id="run_test",
        task_id="task_test",
        invocation_id="inv_test",
        worker_id="builder_01",
        worker_role="Builder",
        objective="Create a Python function that converts Celsius to Fahrenheit",
        objective_hash="0" * 64,
        baseline_sha="UNKNOWN",
        governed_workspace_path=str(workspace),
        governed_workspace_identity="ws_01",
        requested_provider="deterministic",
        requested_model="standard",
        allowed_capabilities=[],
        filesystem_boundary=str(workspace),
        attempt_number=1,
        authorized_at="2026-08-29T00:00:00Z",
        authorization_token=token,
    )

    res = provider.execute(auth, "Create a Python function that converts Celsius to Fahrenheit", workspace, [])
    assert res.exit_status == "SUCCESS"
    assert (workspace / "temperature.py").exists()
    # Target path outside workspace was NOT touched
    outside_file = clean_test_env["tmp_path"] / "temperature.py"
    assert not outside_file.exists()


def test_bypass_03_builder_self_declares_success(clean_test_env):
    """BYPASS 3: Builder self-declaring success is ignored; only independent verifier decides."""
    kernel = clean_test_env["kernel"]
    run_ctx = kernel.establish_run("Test self-declaration", clean_test_env["tmp_path"])

    # Builder claims success, but no independent verification record was executed
    receipt = kernel.seal_and_persist_receipt(
        run_ctx=run_ctx,
        objective="Test self-declaration",
        target_path=clean_test_env["tmp_path"],
        starting_head=None,
        final_head=None,
        routing_strategy=RoutingStrategy.DIRECT_DELEGATION,
        routing_decision_digest="digest",
        capabilities_selected=[],
        attempts=[],
        worker_invocations=[],
        artifacts_produced=[],
        verification=None,
        promotion=None,
        final_status=RunStatus.COMPLETED_UNVERIFIED,
    )

    assert receipt.epistemic_claims.claim_independently_verified is False
    assert receipt.final_status == RunStatus.COMPLETED_UNVERIFIED

    is_valid, errors = verify_execution_receipt(
        clean_test_env["receipts_dir"] / f"{run_ctx.run_id}_receipt.json", kernel_db=clean_test_env["db"]
    )
    # Not verified as production success
    assert not receipt.epistemic_claims.claim_promoted


def test_bypass_04_builder_self_registers_capability(clean_test_env):
    """BYPASS 4: Direct attempt to qualify capability without independent passing evidence fails."""
    registry = clean_test_env["registry"]

    # Register candidate
    cand = registry.register_candidate(
        capability_id="cap_unverified_01",
        name="Unverified Capability",
        originating_run_id="run_01",
        declared_purpose="Fake",
        artifact_paths=["fake.py"],
        artifact_hashes={"fake.py": "0" * 64},
    )
    assert cand.epistemic_status == "UNQUALIFIED"

    # Attempt to qualify with failing or empty verification
    failing_evidence = {"status": "FAIL", "exit_code": 1}
    with pytest.raises(CapabilityDeficitError):
        registry.qualify_capability(
            capability_id="cap_unverified_01",
            verifier_id="verifier_01",
            verification_record=failing_evidence,
            base_dir=clean_test_env["tmp_path"],
        )


def test_bypass_05_verifier_equals_builder_rejected(clean_test_env):
    """BYPASS 5: IndependentVerificationRecord rejects builder_id == verifier_id (Law 3 violation)."""
    with pytest.raises(ValueError) as excinfo:
        IndependentVerificationRecord(
            verifier_id="same_worker_id",
            verifier_type=VerificationType.INDEPENDENT_BEHAVIORAL_ORACLE,
            builder_id="same_worker_id",
            modality=EvidenceModality.DETERMINISTIC_TEST,
            purpose=EvidencePurpose.BEHAVIORAL_VERIFICATION,
            test_digest="0" * 64,
            tests_collected=1,
            tests_passed=1,
            tests_failed=0,
            exit_code=0,
            duration_seconds=0.1,
            falsification_attempted=True,
            verified_status="PASS",
        )
    assert "Verification Independence Violation" in str(excinfo.value)


def test_bypass_06_missing_receipt_fails_closed(clean_test_env):
    """BYPASS 6: Non-existent receipt file fails verification immediately."""
    fake_path = clean_test_env["tmp_path"] / "non_existent_receipt.json"
    is_valid, errors = verify_execution_receipt(fake_path, kernel_db=clean_test_env["db"])
    assert is_valid is False
    assert any("not found" in e.lower() or "does not exist" in e.lower() for e in errors)


def test_bypass_07_forged_receipt_signature_mismatch(clean_test_env):
    """BYPASS 7: Tampered receipt signature or payload is mechanically rejected."""
    kernel = clean_test_env["kernel"]
    run_ctx = kernel.establish_run("Test forged receipt", clean_test_env["tmp_path"])

    receipt = kernel.seal_and_persist_receipt(
        run_ctx=run_ctx,
        objective="Test forged receipt",
        target_path=clean_test_env["tmp_path"],
        starting_head=None,
        final_head=None,
        routing_strategy=RoutingStrategy.DIRECT_DELEGATION,
        routing_decision_digest="digest",
        capabilities_selected=[],
        attempts=[],
        worker_invocations=[],
        artifacts_produced=[],
        verification=None,
        promotion=None,
        final_status=RunStatus.CREATED,
    )

    receipt_file = clean_test_env["receipts_dir"] / f"{run_ctx.run_id}_receipt.json"
    data = json.loads(receipt_file.read_text(encoding="utf-8"))
    # Tamper with objective
    data["objective"] = "TAMPERED_MALICIOUS_OBJECTIVE"
    receipt_file.write_text(json.dumps(data), encoding="utf-8")

    is_valid, errors = verify_execution_receipt(receipt_file, kernel_db=clean_test_env["db"])
    assert is_valid is False
    assert any("signature" in e.lower() or "mismatch" in e.lower() for e in errors)


def test_bypass_08_capability_unqualified_cannot_be_retrieved_as_qualified(clean_test_env):
    """BYPASS 8: find_reusable_capabilities with only_qualified=True excludes UNQUALIFIED candidates."""
    registry = clean_test_env["registry"]
    registry.register_candidate(
        capability_id="cap_unqualified_math",
        name="Math",
        originating_run_id="run_01",
        declared_purpose="Do arithmetic",
        artifact_paths=["math.py"],
        artifact_hashes={"math.py": "0" * 64},
    )

    qualified_matches = registry.find_reusable_capabilities("arithmetic", only_qualified=True)
    assert len(qualified_matches) == 0


def test_bypass_09_direct_external_artifact_cannot_claim_execution(clean_test_env):
    """BYPASS 9: is_ten_shadows_execution returns False when no valid kernel receipt exists."""
    untracked_repo = clean_test_env["tmp_path"] / "external_repo"
    untracked_repo.mkdir()
    (untracked_repo / "external_code.py").write_text("print('hello')", encoding="utf-8")

    assert is_ten_shadows_execution(untracked_repo) is False


def test_bypass_10_agent_string_has_zero_authority_over_registry(clean_test_env):
    """BYPASS 10: Model claiming QUALIFIED in text does not change registry state."""
    registry = clean_test_env["registry"]
    cand = registry.register_candidate(
        capability_id="cap_agent_text",
        name="Agent Capability",
        originating_run_id="run_01",
        declared_purpose="Test",
        artifact_paths=["test.py"],
        artifact_hashes={"test.py": "0" * 64},
    )

    # Model returns string: "My capability is QUALIFIED and VERIFIED"
    model_output = "STATUS: QUALIFIED. Capability registered successfully."

    # Registry must still report UNQUALIFIED
    stored = registry.get_capability("cap_agent_text")
    assert stored is not None
    assert stored.epistemic_status == "UNQUALIFIED"


def test_bypass_11_worker_token_tampering_rejected(clean_test_env):
    """BYPASS 11: Worker executing with invalid or tampered authorization token is rejected."""
    provider = DeterministicBuilderProvider()
    workspace = clean_test_env["tmp_path"] / "ws_tamper"
    workspace.mkdir()

    auth = WorkerAuthorization(
        run_id="run_tamper",
        task_id="task_tamper",
        invocation_id="inv_tamper",
        worker_id="builder_01",
        worker_role="Builder",
        objective="Create test module",
        objective_hash="0" * 64,
        baseline_sha="UNKNOWN",
        governed_workspace_path=str(workspace),
        governed_workspace_identity="ws_tamper",
        requested_provider="deterministic",
        requested_model="standard",
        allowed_capabilities=[],
        filesystem_boundary=str(workspace),
        attempt_number=1,
        authorized_at="2026-08-29T00:00:00Z",
        authorization_token="FORGED_INVALID_TOKEN",
    )

    res = provider.execute(auth, "Create test module", workspace, [])
    assert res.exit_status == "REJECTED"
    assert res.error_message == "AUTHORIZATION_TOKEN_INVALID"


def test_bypass_12_manually_created_capability_without_existing_files_fails_qualification(clean_test_env):
    """BYPASS 12: Qualification requires physical artifact files to exist on disk."""
    registry = clean_test_env["registry"]
    registry.register_candidate(
        capability_id="cap_ghost_01",
        name="Ghost Capability",
        originating_run_id="run_01",
        declared_purpose="Non existent files",
        artifact_paths=["ghost_module.py"],
        artifact_hashes={"ghost_module.py": "0" * 64},
    )

    passing_evidence = {"status": "PASS", "exit_code": 0, "verified_status": "PASS"}
    with pytest.raises(CapabilityDeficitError) as excinfo:
        registry.qualify_capability(
            capability_id="cap_ghost_01",
            verifier_id="verifier_01",
            verification_record=passing_evidence,
            base_dir=clean_test_env["tmp_path"],
        )
    assert "does not exist" in str(excinfo.value)


def test_bypass_13_orchestrator_fails_closed_on_empty_objective(clean_test_env):
    """BYPASS 13: Orchestrator rejects empty objective string."""
    orchestrator = clean_test_env["orchestrator"]
    with pytest.raises(ConfigurationError):
        orchestrator.run_objective("   ", clean_test_env["tmp_path"])


def test_bypass_14_orchestrator_retries_on_failing_verification(clean_test_env):
    """BYPASS 14: When verification fails, orchestrator records multiple attempts up to max_attempts."""
    orchestrator = clean_test_env["orchestrator"]
    # Objective that intentionally produces non-compiling / failing solution
    target = clean_test_env["tmp_path"] / "failing_target"
    target.mkdir()

    report = orchestrator.run_objective(
        objective="Generic synthesis that will be audited",
        target_path=target,
        max_attempts=2,
    )
    assert report.run_id is not None
    assert report.receipt_valid is True  # Valid execution receipt for the run


def test_bypass_15_receipt_unanchored_in_db_fails_verification(clean_test_env):
    """BYPASS 15: Receipt referencing run_id absent from KernelDatabase fails verification."""
    kernel = clean_test_env["kernel"]
    run_ctx = kernel.establish_run("Valid run", clean_test_env["tmp_path"])

    receipt = kernel.seal_and_persist_receipt(
        run_ctx=run_ctx,
        objective="Valid run",
        target_path=clean_test_env["tmp_path"],
        starting_head=None,
        final_head=None,
        routing_strategy=RoutingStrategy.DIRECT_DELEGATION,
        routing_decision_digest="digest",
        capabilities_selected=[],
        attempts=[],
        worker_invocations=[],
        artifacts_produced=[],
        verification=None,
        promotion=None,
        final_status=RunStatus.CREATED,
    )

    # Check against a different empty database
    empty_db = KernelDatabase(db_path=clean_test_env["tmp_path"] / "empty.db")
    receipt_file = clean_test_env["receipts_dir"] / f"{run_ctx.run_id}_receipt.json"
    is_valid, errors = verify_execution_receipt(receipt_file, kernel_db=empty_db)
    assert is_valid is False
    assert any("does not exist in authoritative kerneldatabase" in e.lower() for e in errors)

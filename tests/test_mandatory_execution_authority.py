"""
tests/test_mandatory_execution_authority.py
Adversarial & Regression Test Suite for Mandatory Ten Shadows Execution Authority.

Verifies:
1. Core Invariant: NO VALID KERNEL-ISSUED EXECUTION RECEIPT = TEN SHADOWS DID NOT EXECUTE.
2. Inversion of Authority: Kernel creates run in SQLite WAL before worker execution.
3. Tests A through J (Adversarial Bypass & Anti-Laundering Tests).
4. Positive End-to-End Smoke Test on fixture target.
5. Negative Control: Exact JobHunter Failure Mode Reproduction.
"""
from __future__ import annotations

import json
import os
import shutil
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path

import pytest

from loop_engine.execution_authority import (
    TenShadowsKernel,
    TenShadowsReceipt,
    RunStatus,
    RoutingStrategy,
    WorkerRole,
    WorkerInvocationRecord,
    IndependentVerificationRecord,
    is_ten_shadows_execution,
    verify_execution_receipt,
)
from loop_engine.kernel_db import KernelDatabase


@pytest.fixture
def temp_kernel(tmp_path):
    """Provides an isolated KernelDatabase and receipts directory."""
    db_file = tmp_path / "test_kernel.db"
    receipts_dir = tmp_path / "receipts"
    receipts_dir.mkdir(parents=True, exist_ok=True)
    db = KernelDatabase(db_path=db_file)
    kernel = TenShadowsKernel(kernel_db=db, receipts_dir=receipts_dir)
    return kernel


@pytest.fixture
def target_repo(tmp_path):
    """Creates a temporary target fixture directory with tests."""
    target_dir = tmp_path / "target_project"
    target_dir.mkdir(parents=True, exist_ok=True)
    (target_dir / "src").mkdir()
    (target_dir / "tests").mkdir()

    (target_dir / "src" / "app.py").write_text("def run(): return 42\n", encoding="utf-8")
    (target_dir / "tests" / "test_app.py").write_text(
        "from src.app import run\ndef test_run(): assert run() == 42\n", encoding="utf-8"
    )
    return target_dir


# ===========================================================================
# Section 1: Inversion of Authority & Run Pre-Creation
# ===========================================================================

class TestRunCreationAuthority:
    def test_run_created_in_database_before_execution(self, temp_kernel, target_repo):
        """Kernel must create a persistent run record in SQLite WAL before any worker runs."""
        objective = "Refactor calculation module for deterministic output."
        run_ctx = temp_kernel.establish_run(objective=objective, target_path=target_repo)

        # Inspect raw database directly
        db_record = temp_kernel.db.get_run(run_ctx.run_id)
        assert db_record is not None
        assert db_record["run_id"] == run_ctx.run_id
        assert db_record["status"] == RunStatus.CREATED.value
        assert db_record["objective_hash"] == run_ctx.objective_hash

    def test_routing_decision_persisted_as_kernel_authority(self, temp_kernel, target_repo):
        """Routing decision must be authored and persisted by the kernel, not inferred by model."""
        objective = "Harden database persistence and concurrency with WAL mode."
        run_ctx = temp_kernel.establish_run(objective=objective, target_path=target_repo)
        strategy, caps, digest = temp_kernel.determine_route(run_ctx, objective)

        assert strategy == RoutingStrategy.CODE_HARDENING
        assert "PERSISTENCE_HARDENING" in caps
        assert len(digest) == 64

        db_record = temp_kernel.db.get_run(run_ctx.run_id)
        assert db_record["status"] == RunStatus.ROUTED.value


# ===========================================================================
# Section 2: Adversarial Bypass Tests (A through J)
# ===========================================================================

class TestAdversarialBypassAttempts:
    def test_bypass_A_fabricated_receipt_file_rejected(self, temp_kernel, tmp_path):
        """A. Model fabricates a receipt-shaped JSON file without kernel DB anchor -> must return False."""
        fake_receipt = tmp_path / "fake_receipt.json"
        fake_data = {
            "receipt_version": "2.0.0",
            "kernel_version": "10_SHADOWS_KERNEL_v3.0",
            "run_id": "TS-FAKED-99999",
            "task_id": "task_faked",
            "objective": "Fabricated run",
            "objective_hash": "a" * 64,
            "target_path": "C:\\fake",
            "routing_strategy": "DIRECT_DELEGATION",
            "routing_decision_digest": "b" * 64,
            "capabilities_selected": ["DIRECT_EXECUTION"],
            "worker_invocations": [],
            "artifacts_produced": [],
            "final_status": "COMPLETED_UNVERIFIED",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "sealed_at": datetime.now(timezone.utc).isoformat(),
            "env_fingerprint": {},
            "receipt_signature": "c" * 64,
        }
        fake_receipt.write_text(json.dumps(fake_data), encoding="utf-8")

        is_valid, errors = verify_execution_receipt(fake_receipt, kernel_db=temp_kernel.db)
        assert is_valid is False
        assert any("KernelDatabase" in e or "signature mismatch" in e for e in errors)
        assert is_ten_shadows_execution(fake_receipt, kernel_db=temp_kernel.db) is False

    def test_bypass_B_commit_message_claim_does_not_establish_execution(self, temp_kernel):
        """B. Model writes 'Ten Shadows' into commit message -> must not establish execution."""
        run_id = "commit_claim_run_id_nonexistent"
        assert is_ten_shadows_execution(run_id, kernel_db=temp_kernel.db) is False

    def test_bypass_C_reading_skills_does_not_establish_execution(self, temp_kernel):
        """C. Model reads all Ten Shadows skill files but never enters kernel -> must not establish execution."""
        # Unanchored run ID
        assert is_ten_shadows_execution("run_model_read_all_skills_123", kernel_db=temp_kernel.db) is False

    def test_bypass_D_builder_claims_tests_passed_without_evidence_fails_closed(self, temp_kernel, target_repo):
        """D. Builder claims tests passed without physical test evidence -> must fail closed."""
        objective = "Consequential code change."
        run_ctx = temp_kernel.establish_run(objective=objective, target_path=target_repo)
        strategy, caps, digest = temp_kernel.determine_route(run_ctx, objective)

        # Attempt to seal VERIFIED_SUCCESS with NO verification record
        with pytest.raises(Exception):
            # Model validation or verify_execution_receipt will fail closed
            receipt = temp_kernel.seal_and_persist_receipt(
                run_ctx=run_ctx,
                objective=objective,
                target_path=target_repo,
                starting_head=None,
                final_head=None,
                routing_strategy=strategy,
                routing_decision_digest=digest,
                capabilities_selected=caps,
                worker_invocations=[],
                artifacts_produced=[],
                verification=None,  # MISSING verification!
                promotion=None,
                final_status=RunStatus.VERIFIED_SUCCESS,
            )
            is_valid, errors = verify_execution_receipt(receipt.model_dump(), kernel_db=temp_kernel.db)
            assert is_valid is False
            assert "verification evidence" in errors[0].lower()

    def test_bypass_E_builder_self_certification_rejected(self, temp_kernel, target_repo):
        """E. Builder creates its own verification result (builder_id == verifier_id) -> rejected."""
        objective = "Consequential change with self-certified verifier."
        run_ctx = temp_kernel.establish_run(objective=objective, target_path=target_repo)
        strategy, caps, digest = temp_kernel.determine_route(run_ctx, objective)

        self_certified_verification = IndependentVerificationRecord(
            verifier_id="builder_agent_alpha",
            verifier_type="SELF_REPORT",
            builder_id="builder_agent_alpha",  # VIOLATION: builder_id == verifier_id
            test_digest="d" * 64,
            tests_collected=5,
            tests_passed=5,
            tests_failed=0,
            exit_code=0,
            duration_seconds=0.1,
            falsification_attempted=False,
            verified_status="PASS",
        )

        receipt = temp_kernel.seal_and_persist_receipt(
            run_ctx=run_ctx,
            objective=objective,
            target_path=target_repo,
            starting_head=None,
            final_head=None,
            routing_strategy=strategy,
            routing_decision_digest=digest,
            capabilities_selected=caps,
            worker_invocations=[],
            artifacts_produced=[],
            verification=self_certified_verification,
            promotion=None,
            final_status=RunStatus.VERIFIED_SUCCESS,
        )

        is_valid, errors = verify_execution_receipt(receipt.model_dump(), kernel_db=temp_kernel.db)
        assert is_valid is False
        assert any("Self-certification" in e or "Independence Violation" in e for e in errors)
        assert is_ten_shadows_execution(receipt.run_id, kernel_db=temp_kernel.db) is False

    def test_bypass_F_mismatched_head_fails_closed(self, temp_kernel, target_repo):
        """F. Receipt references invalid or corrupted HEAD SHA -> fails closed."""
        objective = "Refactor with invalid HEAD"
        run_ctx = temp_kernel.establish_run(objective=objective, target_path=target_repo)
        strategy, caps, digest = temp_kernel.determine_route(run_ctx, objective)

        receipt = temp_kernel.seal_and_persist_receipt(
            run_ctx=run_ctx,
            objective=objective,
            target_path=target_repo,
            starting_head="INVALID_CORRUPTED_SHORT_HEAD",
            final_head=None,
            routing_strategy=strategy,
            routing_decision_digest=digest,
            capabilities_selected=caps,
            worker_invocations=[],
            artifacts_produced=[],
            verification=None,
            promotion=None,
            final_status=RunStatus.COMPLETED_UNVERIFIED,
        )

        is_valid, errors = verify_execution_receipt(receipt.model_dump(), kernel_db=temp_kernel.db)
        assert is_valid is False
        assert any("starting_head format" in e for e in errors)

    def test_bypass_H_interrupted_run_does_not_qualify(self, temp_kernel, target_repo):
        """H. Run interrupted before promotion -> must remain CREATED/RUNNING, never VERIFIED_SUCCESS."""
        objective = "Interrupted task"
        run_ctx = temp_kernel.establish_run(objective=objective, target_path=target_repo)

        # Query database status
        db_rec = temp_kernel.db.get_run(run_ctx.run_id)
        assert db_rec["status"] == RunStatus.CREATED.value
        # Incomplete run has no receipt and cannot be verified
        assert is_ten_shadows_execution(run_ctx.run_id, kernel_db=temp_kernel.db) is False

    def test_bypass_I_minimal_sufficient_capabilities_qualify(self, temp_kernel, target_repo):
        """I. A valid run with only minimum required capabilities qualifies without ceremonial bloat."""
        objective = "Minimal sufficient verification."
        receipt = temp_kernel.run_objective(
            objective=objective,
            target_path=target_repo,
            custom_verifier_cmd=["python", "-c", "import sys; sys.exit(0)"],
        )

        assert receipt.final_status == RunStatus.VERIFIED_SUCCESS
        assert len(receipt.capabilities_selected) >= 1
        assert is_ten_shadows_execution(receipt.run_id, kernel_db=temp_kernel.db) is True

    def test_bypass_J_direct_delegation_for_trivial_task(self, temp_kernel, target_repo):
        """J. Direct delegation is selected by kernel for trivial task -> recorded as COMPLETED_UNVERIFIED."""
        objective = "trivial: echo ping"
        receipt = temp_kernel.run_objective(
            objective=objective,
            target_path=target_repo,
        )

        assert receipt.routing_strategy == RoutingStrategy.DIRECT_DELEGATION
        assert receipt.final_status == RunStatus.COMPLETED_UNVERIFIED
        assert receipt.verification is None
        assert is_ten_shadows_execution(receipt.run_id, kernel_db=temp_kernel.db) is True


# ===========================================================================
# Section 3: Positive End-to-End Smoke Test
# ===========================================================================

class TestPositiveEndToEndExecution:
    def test_positive_e2e_run_lifecycle(self, temp_kernel, target_repo):
        """
        Positive End-to-End Smoke Test:
        1. Objective entered through Ten Shadows.
        2. Kernel creates run in KernelDatabase before worker execution.
        3. Routing decision persisted.
        4. Worker execution recorded with input/output digests.
        5. Independent verification executes test suite and captures test digest.
        6. Promotion decision recorded.
        7. Authoritative sealed receipt written to .receipts/ and KernelDatabase.
        8. is_ten_shadows_execution(run_id) returns True.
        """
        objective = "Harden target application functions."

        def mock_builder(ctx, path):
            # Worker creates an improvement in target
            target_file = path / "src" / "app.py"
            target_file.write_text("def run(): return 42\ndef helper(): return True\n", encoding="utf-8")
            return [{"path": str(target_file), "status": "MODIFIED"}]

        receipt = temp_kernel.run_objective(
            objective=objective,
            target_path=target_repo,
            builder_fn=mock_builder,
            provider_name="mock_gemini",
            model_name="mock_gemini_flash",
        )

        # Verify receipt properties
        assert receipt.final_status == RunStatus.VERIFIED_SUCCESS
        assert receipt.routing_strategy == RoutingStrategy.CODE_HARDENING
        assert len(receipt.worker_invocations) == 1
        assert receipt.worker_invocations[0].role == WorkerRole.BUILDER
        assert receipt.worker_invocations[0].provider == "mock_gemini"
        assert receipt.verification is not None
        assert receipt.verification.exit_code == 0
        assert receipt.verification.tests_passed >= 1
        assert receipt.verification.builder_id != receipt.verification.verifier_id

        # Verify file persisted
        receipt_file = temp_kernel.receipts_dir / f"{receipt.run_id}_receipt.json"
        assert receipt_file.exists()

        # Verify mechanical predicate returns TRUE
        assert is_ten_shadows_execution(receipt.run_id, kernel_db=temp_kernel.db) is True
        assert is_ten_shadows_execution(receipt_file, kernel_db=temp_kernel.db) is True


# ===========================================================================
# Section 4: Negative Control — JobHunter Failure Mode Reproduction
# ===========================================================================

class TestJobHunterNegativeControl:
    def test_jobhunter_failure_mode_reproduction(self, temp_kernel, target_repo, tmp_path):
        """
        Recreates the exact failure mode observed in the JobHunter hardening pass:
        - An external model reads skills and edits target.
        - Writes and passes developer tests.
        - Claims in text/commit 'feat(hardening): apply 10 shadows zero-trust'.
        - Even generates a fake receipt file.
        - BUT never initialized the run inside the Ten Shadows kernel.

        EXPECTED: is_ten_shadows_execution(...) == False.
        """
        # Step 1: Model modifies target
        (target_repo / "src" / "app.py").write_text("def run(): return 100\n", encoding="utf-8")
        (target_repo / "tests" / "test_app.py").write_text("from src.app import run\ndef test_run(): assert run() == 100\n", encoding="utf-8")

        # Step 2: Model creates arbitrary receipt file without kernel database record
        fake_receipt_file = tmp_path / "jobhunter_fake_receipt.json"
        fake_data = {
            "receipt_version": "2.0.0",
            "kernel_version": "10_SHADOWS_KERNEL_v3.0",
            "run_id": "TS-JOBHUNTER-RUN-3d5b2b2c",
            "task_id": "job_hunter_hardening",
            "objective": "Harden job hunter repository under 10 shadows principles",
            "objective_hash": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
            "target_path": str(target_repo),
            "routing_strategy": "CODE_HARDENING",
            "routing_decision_digest": "0" * 64,
            "capabilities_selected": ["PERSISTENCE_HARDENING"],
            "worker_invocations": [],
            "artifacts_produced": [],
            "verification": {
                "verifier_id": "model_self_verifier",
                "verifier_type": "PYTEST",
                "builder_id": "model_self_verifier",  # Self-certified!
                "test_digest": "f" * 64,
                "tests_collected": 83,
                "tests_passed": 83,
                "tests_failed": 0,
                "exit_code": 0,
                "duration_seconds": 1.62,
                "falsification_attempted": True,
                "verified_status": "PASS",
            },
            "final_status": "VERIFIED_SUCCESS",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "sealed_at": datetime.now(timezone.utc).isoformat(),
            "env_fingerprint": {},
            "receipt_signature": "bad_signature",
        }
        fake_receipt_file.write_text(json.dumps(fake_data), encoding="utf-8")

        # Mechanical Verification MUST REJECT
        assert is_ten_shadows_execution("TS-JOBHUNTER-RUN-3d5b2b2c", kernel_db=temp_kernel.db) is False
        assert is_ten_shadows_execution(fake_receipt_file, kernel_db=temp_kernel.db) is False

        is_valid, errors = verify_execution_receipt(fake_receipt_file, kernel_db=temp_kernel.db)
        assert is_valid is False
        assert len(errors) >= 1

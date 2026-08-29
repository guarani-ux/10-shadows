"""
tests/test_mandatory_execution_authority.py
Comprehensive Adversarial Regression Suite for Substrate Laws & Mandatory Execution Authority.

Tests Mission J Requirements (Tests 1 through 12):
1. False Ten Shadows Invocation
2. Fabricated Provider Execution
3. Zero-Duration / Synthetic Worker
4. Self-Verification
5. Generic False-Success Oracle
6. Evidence Upgrade Attack
7. Wrong HEAD
8. Stale Receipt Replay
9. Interrupted Run
10. Minimum Capability Routing
11. Direct Delegation
12. Real Governed Software Mutation
Plus Positive E2E and Negative Control Tests.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path

import pytest

from loop_engine.epistemic import SemanticLaunderingError
from loop_engine.execution_authority import (
    DisaggregatedEpistemicClaims,
    EvidenceModality,
    EvidencePurpose,
    ExecutionAttemptRecord,
    IndependentVerificationRecord,
    ProviderExecutionReceipt,
    RoutingStrategy,
    RunStatus,
    TenShadowsKernel,
    TenShadowsReceipt,
    VerificationType,
    WorkerInvocationRecord,
    WorkerRole,
    assert_evidence_monotonicity,
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


@pytest.fixture
def disposable_git_repo(tmp_path):
    """Creates a disposable Git repository fixture (never touches main repo)."""
    repo_dir = tmp_path / "disposable_repo"
    repo_dir.mkdir(parents=True, exist_ok=True)
    (repo_dir / "src").mkdir()
    (repo_dir / "tests").mkdir()

    subprocess.run(["git", "init", "-b", "main"], cwd=str(repo_dir), check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "ZeroTrustBot"], cwd=str(repo_dir), check=True)
    subprocess.run(["git", "config", "user.email", "bot@zero.trust"], cwd=str(repo_dir), check=True)

    (repo_dir / "src" / "calc.py").write_text("def compute(): return 10\n", encoding="utf-8")
    (repo_dir / "tests" / "test_calc.py").write_text(
        "from src.calc import compute\ndef test_compute(): assert compute() == 10\n", encoding="utf-8"
    )

    subprocess.run(["git", "add", "."], cwd=str(repo_dir), check=True)
    subprocess.run(["git", "commit", "-m", "init: base release"], cwd=str(repo_dir), check=True)
    return repo_dir


# ===========================================================================
# Mission J: Adversarial Regression Tests (1 through 12)
# ===========================================================================


class TestMissionJAdversarialSuite:
    def test_01_false_ten_shadows_invocation(self, temp_kernel, tmp_path):
        """1. Model reads skills, writes code, passes tests, puts 'Ten Shadows' in commit, but no kernel run."""
        fake_receipt = tmp_path / "fake_receipt.json"
        fake_data = {
            "receipt_version": "2.1.0",
            "kernel_version": "10_SHADOWS_KERNEL_v3.0",
            "run_id": "TS-UNANCHORED-12345",
            "task_id": "task_fake",
            "objective": "Touting Ten Shadows in prompt",
            "objective_hash": "a" * 64,
            "target_path": "C:\\fake",
            "routing_strategy": "DIRECT_DELEGATION",
            "routing_decision_digest": "b" * 64,
            "capabilities_selected": ["DIRECT_EXECUTION"],
            "attempts": [],
            "worker_invocations": [],
            "artifacts_produced": [],
            "epistemic_claims": {
                "claim_kernel_run_created": True,
                "claim_kernel_routed": True,
                "claim_worker_executed": False,
                "claim_empirical_provider_invoked": False,
                "claim_candidate_mutated": False,
                "claim_independently_verified": False,
                "claim_promoted": False,
                "claim_target_behaviorally_tested": False,
                "claim_semantic_objective_satisfied": False,
            },
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
        assert is_ten_shadows_execution("TS-UNANCHORED-12345", kernel_db=temp_kernel.db) is False

    def test_02_fabricated_provider_execution(self, temp_kernel, target_repo):
        """2. Worker claims provider=gemini and modality=EMPIRICAL but no valid ProviderExecutionReceipt."""
        run_ctx = temp_kernel.establish_run(objective="Test empirical claims", target_path=target_repo)

        with pytest.raises(ValueError) as exc:
            WorkerInvocationRecord(
                invocation_id="inv_fake_01",
                worker_id="worker_gemini",
                provider="gemini",
                model="gemini-2.5-flash",
                role=WorkerRole.BUILDER,
                modality=EvidenceModality.EMPIRICAL,
                input_digest="e" * 64,
                output_digest="f" * 64,
                started_at=datetime.now(timezone.utc).isoformat(),
                ended_at=datetime.now(timezone.utc).isoformat(),
                duration_seconds=1.5,
                status="SUCCESS",
                provider_receipt=None,  # ILLEGAL: Missing provider_receipt for EMPIRICAL!
            )
        assert "must provide non-null provider_receipt" in str(exc.value)

    def test_03_zero_duration_synthetic_worker(self, temp_kernel, target_repo):
        """3. Structural/mock worker fixture records instantaneous execution -> must be STRUCTURAL, not EMPIRICAL."""
        # Valid structural worker with zero duration
        structural_worker = WorkerInvocationRecord(
            invocation_id="inv_struct_01",
            worker_id="mock_ast_builder",
            provider="mock_synthetic",
            model="deterministic_v1",
            role=WorkerRole.BUILDER,
            modality=EvidenceModality.STRUCTURAL,  # Correctly labeled STRUCTURAL
            input_digest="1" * 64,
            output_digest="2" * 64,
            started_at=datetime.now(timezone.utc).isoformat(),
            ended_at=datetime.now(timezone.utc).isoformat(),
            duration_seconds=0.0,
            status="SUCCESS",
            provider_receipt=None,
        )
        assert structural_worker.modality == EvidenceModality.STRUCTURAL

        # Cannot declare EMPIRICAL with 0.0 duration in provider receipt
        with pytest.raises(ValueError):
            ProviderExecutionReceipt(
                provider="gemini",
                model="gemini-2.5-flash",
                transaction_id="tx_real_12345",
                started_at=datetime.now(timezone.utc).isoformat(),
                ended_at=datetime.now(timezone.utc).isoformat(),
                duration_seconds=0.0,  # ILLEGAL for empirical
                modality=EvidenceModality.EMPIRICAL,
                raw_response_digest="3" * 64,
            )

    def test_04_self_verification_rejected(self, temp_kernel, target_repo):
        """4. Builder creates candidate and builder-authored verification result (builder_id == verifier_id)."""
        with pytest.raises(ValueError) as exc:
            IndependentVerificationRecord(
                verifier_id="builder_agent_alpha",
                verifier_type=VerificationType.INDEPENDENT_BEHAVIORAL_ORACLE,
                builder_id="builder_agent_alpha",  # Self-certification violation
                modality=EvidenceModality.DETERMINISTIC_TEST,
                purpose=EvidencePurpose.BEHAVIORAL_VERIFICATION,
                test_digest="d" * 64,
                tests_collected=5,
                tests_passed=5,
                tests_failed=0,
                exit_code=0,
                duration_seconds=0.1,
                falsification_attempted=True,
                verified_status="PASS",
            )
        assert "Self-certification" in str(exc.value)

    def test_05_generic_false_success_oracle(self, temp_kernel, target_repo):
        """5. Candidate returns superficially valid output but fails independent behavioral verification."""
        # Builder introduces a bug in target
        (target_repo / "src" / "app.py").write_text("def run(): return 999  # Broken logic\n", encoding="utf-8")

        receipt = temp_kernel.run_objective(
            objective="Improve calculation logic",
            target_path=target_repo,
        )

        assert receipt.final_status == RunStatus.FAILED
        assert receipt.verification.exit_code != 0
        assert receipt.verification.tests_failed >= 1
        assert receipt.epistemic_claims.claim_independently_verified is False
        assert receipt.epistemic_claims.claim_promoted is False

    def test_06_evidence_upgrade_attack(self):
        """6. Attempt to upgrade SIMULATED -> EMPIRICAL or STRUCTURAL -> EMPIRICAL without observation."""
        with pytest.raises(SemanticLaunderingError) as exc:
            assert_evidence_monotonicity(
                declared_modality=EvidenceModality.SIMULATED,
                claimed_modality=EvidenceModality.EMPIRICAL,
            )
        assert "Evidence Monotonicity Violation" in str(exc.value)

        with pytest.raises(SemanticLaunderingError):
            assert_evidence_monotonicity(
                declared_modality=EvidenceModality.STRUCTURAL,
                claimed_modality=EvidenceModality.EMPIRICAL,
            )

    def test_07_wrong_head_fails_closed(self, temp_kernel, target_repo):
        """7. Receipt references corrupted or mismatched starting Git HEAD."""
        run_ctx = temp_kernel.establish_run(objective="Target HEAD check", target_path=target_repo)
        strategy, caps, digest = temp_kernel.determine_route(run_ctx, "Target HEAD check")

        receipt = temp_kernel.seal_and_persist_receipt(
            run_ctx=run_ctx,
            objective="Target HEAD check",
            target_path=target_repo,
            starting_head="CORRUPT_SHORT_SHA",  # Not 40 chars
            final_head=None,
            routing_strategy=strategy,
            routing_decision_digest=digest,
            capabilities_selected=caps,
            attempts=[],
            worker_invocations=[],
            artifacts_produced=[],
            verification=None,
            promotion=None,
            final_status=RunStatus.COMPLETED_UNVERIFIED,
        )

        is_valid, errors = verify_execution_receipt(receipt.model_dump(), kernel_db=temp_kernel.db)
        assert is_valid is False
        assert any("starting_head format" in e for e in errors)

    def test_08_stale_receipt_replay(self, temp_kernel, target_repo, tmp_path):
        """8. Copying a previously valid receipt into a new run without DB registration fails closed."""
        run_ctx = temp_kernel.establish_run(objective="First valid run", target_path=target_repo)
        strategy, caps, digest = temp_kernel.determine_route(run_ctx, "First valid run")

        valid_receipt = temp_kernel.seal_and_persist_receipt(
            run_ctx=run_ctx,
            objective="First valid run",
            target_path=target_repo,
            starting_head=None,
            final_head=None,
            routing_strategy=strategy,
            routing_decision_digest=digest,
            capabilities_selected=caps,
            attempts=[],
            worker_invocations=[],
            artifacts_produced=[],
            verification=None,
            promotion=None,
            final_status=RunStatus.COMPLETED_UNVERIFIED,
        )

        # Attacker replays receipt for an unregistered run ID
        replayed_data = valid_receipt.model_dump()
        replayed_data["run_id"] = "TS-REPLAYED-RUN-999"
        replayed_data["receipt_signature"] = valid_receipt.receipt_signature  # Signature won't match or DB missing

        replayed_file = tmp_path / "replayed.json"
        replayed_file.write_text(json.dumps(replayed_data), encoding="utf-8")

        is_valid, errors = verify_execution_receipt(replayed_file, kernel_db=temp_kernel.db)
        assert is_valid is False
        assert is_ten_shadows_execution("TS-REPLAYED-RUN-999", kernel_db=temp_kernel.db) is False

    def test_09_interrupted_run(self, temp_kernel, target_repo):
        """9. Run interrupted before verification or promotion never receives VERIFIED_SUCCESS."""
        run_ctx = temp_kernel.establish_run(objective="Interrupted work", target_path=target_repo)
        strategy, caps, digest = temp_kernel.determine_route(run_ctx, "Interrupted work")

        db_rec = temp_kernel.db.get_run(run_ctx.run_id)
        assert db_rec["status"] == RunStatus.ROUTED.value
        assert is_ten_shadows_execution(run_ctx.run_id, kernel_db=temp_kernel.db) is False

    def test_10_minimum_capability_routing(self, temp_kernel, target_repo):
        """10. Kernel selects only the minimum required capabilities; qualifies without ceremonial bloat."""
        objective = "Assess security boundaries"
        receipt = temp_kernel.run_objective(
            objective=objective,
            target_path=target_repo,
            custom_verifier_cmd=["python", "-c", "import sys; sys.exit(0)"],
        )

        assert receipt.final_status == RunStatus.VERIFIED_SUCCESS
        assert receipt.routing_strategy == RoutingStrategy.ADVERSARIAL_AUDIT
        assert len(receipt.capabilities_selected) == 3
        assert is_ten_shadows_execution(receipt.run_id, kernel_db=temp_kernel.db) is True

    def test_11_direct_delegation(self, temp_kernel, target_repo):
        """11. Trivial objective is deliberately delegated by kernel -> recorded as COMPLETED_UNVERIFIED."""
        receipt = temp_kernel.run_objective(
            objective="trivial: ping service",
            target_path=target_repo,
        )

        assert receipt.routing_strategy == RoutingStrategy.DIRECT_DELEGATION
        assert receipt.final_status == RunStatus.COMPLETED_UNVERIFIED
        assert receipt.epistemic_claims.claim_independently_verified is False
        assert is_ten_shadows_execution(receipt.run_id, kernel_db=temp_kernel.db) is True

    def test_12_real_governed_software_mutation(self, temp_kernel, disposable_git_repo):
        """12. Real governed mutation on a disposable Git repository fixture -> starting HEAD != final HEAD."""
        starting_head = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=str(disposable_git_repo), text=True
        ).strip()

        def builder_mutator(ctx, path):
            calc_file = path / "src" / "calc.py"
            calc_file.write_text("def compute(): return 10\ndef add(a, b): return a + b\n", encoding="utf-8")
            test_file = path / "tests" / "test_calc.py"
            test_file.write_text(
                "from src.calc import compute, add\ndef test_compute(): assert compute() == 10\ndef test_add(): assert add(2, 3) == 5\n",
                encoding="utf-8",
            )
            subprocess.run(["git", "add", "."], cwd=str(path), check=True)
            subprocess.run(["git", "commit", "-m", "feat: add add helper"], cwd=str(path), check=True)
            return [{"file": str(calc_file), "status": "MODIFIED"}]

        receipt = temp_kernel.run_objective(
            objective="Harden calculation engine with addition function",
            target_path=disposable_git_repo,
            builder_fn=builder_mutator,
        )

        assert receipt.final_status == RunStatus.VERIFIED_SUCCESS
        assert receipt.starting_head == starting_head
        assert receipt.final_head is not None
        assert receipt.final_head != starting_head
        assert receipt.verification.tests_passed == 2
        assert receipt.epistemic_claims.claim_promoted is True
        assert is_ten_shadows_execution(receipt.run_id, kernel_db=temp_kernel.db) is True


# ===========================================================================
# Mission L & M: Positive Acceptance Test & Negative Control
# ===========================================================================


class TestAcceptanceAndNegativeControl:
    def test_positive_e2e_acceptance_flow(self, temp_kernel, disposable_git_repo):
        """Mission L: Positive End-to-End Acceptance Test on disposable Git fixture."""
        objective = "Zero trust hardening of calculation module"

        def mock_builder(ctx, path):
            app_file = path / "src" / "calc.py"
            app_file.write_text("def compute(): return 10\ndef is_safe(): return True\n", encoding="utf-8")
            test_file = path / "tests" / "test_calc.py"
            test_file.write_text(
                "from src.calc import compute, is_safe\ndef test_compute(): assert compute() == 10\ndef test_safe(): assert is_safe() is True\n",
                encoding="utf-8",
            )
            subprocess.run(["git", "add", "."], cwd=str(path), check=True)
            subprocess.run(
                ["git", "commit", "-m", "feat(hardening): apply zero trust checks"], cwd=str(path), check=True
            )
            return [{"path": str(app_file), "action": "HARDENED"}]

        receipt = temp_kernel.run_objective(
            objective=objective,
            target_path=disposable_git_repo,
            builder_fn=mock_builder,
            provider_name="gemini_adapter_fixture",
            model_name="gemini-2.5-flash",
        )

        assert receipt.final_status == RunStatus.VERIFIED_SUCCESS
        assert receipt.verification.tests_passed == 2
        assert receipt.verification.exit_code == 0
        assert is_ten_shadows_execution(receipt.run_id, kernel_db=temp_kernel.db) is True
        assert len(receipt.attempts) == 1
        assert receipt.attempts[0].status == "PASS"

    def test_negative_control_jobhunter_simulation(self, temp_kernel, disposable_git_repo, tmp_path):
        """Mission M: Negative control reproducing fake prompt-only run outside kernel."""
        # 1. External actor mutates repository directly
        (disposable_git_repo / "src" / "calc.py").write_text("def compute(): return 99\n", encoding="utf-8")
        (disposable_git_repo / "tests" / "test_calc.py").write_text(
            "from src.calc import compute\ndef test_compute(): assert compute() == 99\n", encoding="utf-8"
        )
        subprocess.run(["git", "add", "."], cwd=str(disposable_git_repo), check=True)
        subprocess.run(
            ["git", "commit", "-m", "feat(hardening): apply 10 shadows zero-trust in prompt"],
            cwd=str(disposable_git_repo),
            check=True,
        )

        # 2. External actor fabricates a receipt file
        fake_receipt = tmp_path / "external_model_receipt.json"
        fake_payload = {
            "receipt_version": "2.1.0",
            "kernel_version": "10_SHADOWS_KERNEL_v3.0",
            "run_id": "TS-UNAUTHORIZED-SESSION-001",
            "task_id": "task_external",
            "objective": "Harden outside kernel",
            "objective_hash": "d" * 64,
            "target_path": str(disposable_git_repo),
            "routing_strategy": "CODE_HARDENING",
            "routing_decision_digest": "e" * 64,
            "capabilities_selected": ["PERSISTENCE_HARDENING"],
            "attempts": [],
            "worker_invocations": [],
            "artifacts_produced": [],
            "verification": {
                "verifier_id": "model_self",
                "verifier_type": "BUILDER_TEST",
                "builder_id": "model_self",
                "modality": "DETERMINISTIC_TEST",
                "purpose": "BEHAVIORAL_VERIFICATION",
                "test_digest": "f" * 64,
                "tests_collected": 1,
                "tests_passed": 1,
                "tests_failed": 0,
                "exit_code": 0,
                "duration_seconds": 0.05,
                "falsification_attempted": False,
                "verified_status": "PASS",
            },
            "epistemic_claims": {
                "claim_kernel_run_created": True,
                "claim_kernel_routed": True,
                "claim_worker_executed": True,
                "claim_empirical_provider_invoked": False,
                "claim_candidate_mutated": True,
                "claim_independently_verified": True,
                "claim_promoted": True,
                "claim_target_behaviorally_tested": True,
                "claim_semantic_objective_satisfied": False,
            },
            "final_status": "VERIFIED_SUCCESS",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "sealed_at": datetime.now(timezone.utc).isoformat(),
            "env_fingerprint": {},
            "receipt_signature": "invalid_sig",
        }
        fake_receipt.write_text(json.dumps(fake_payload), encoding="utf-8")

        # Must evaluate to FALSE
        assert is_ten_shadows_execution("TS-UNAUTHORIZED-SESSION-001", kernel_db=temp_kernel.db) is False
        assert is_ten_shadows_execution(fake_receipt, kernel_db=temp_kernel.db) is False

        is_valid, errors = verify_execution_receipt(fake_receipt, kernel_db=temp_kernel.db)
        assert is_valid is False
        assert len(errors) >= 1

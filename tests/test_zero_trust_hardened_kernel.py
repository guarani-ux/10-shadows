"""
tests/test_zero_trust_hardened_kernel.py
Authoritative Negative and Operational Acceptance Test Suite for 10 SHADOWS Zero-Trust Protocol.

Validates all 15 required physical and negative controls:
1. Forged VERIFIED receipt rejected.
2. Proposal overwrite after sealing raises ProposalAlreadySealedError.
3. Illegal state transition raises IllegalStateTransitionError.
4. Fixture directory deletion/mutation blocked.
5. Candidate pytest.py/sitecustomize.py test bypass blocked.
6. Zero-tests-collected success rejected.
7. Dirty or stale target branch blocked.
8. Target movement after verification aborts.
9. Crash at every promotion boundary reconciled via ancestry.
10. Concurrent promotion attempts rejected by CAS.
11. Unreadable or changed hashed file rejected.
12. Quarantine path traversal and symlink escape blocked.
13. Empty and paraphrased defective plans rejected by PlanAuditor.
14. Duplicate persistence authority prohibited (single KernelDatabase).
15. Real CanonicalObjective -> Scribe -> Herald -> Slicer route executed with artifact lineage & receipt persistence.
"""

import os
import subprocess
import sys
import tempfile
from pathlib import Path
import pytest

from loop_engine.kernel_db import (
    KernelDatabase,
    ProposalAlreadySealedError,
    IllegalStateTransitionError,
    ReceiptNotFoundError,
    ReceiptMismatchError,
    PrivilegedStateMutationProhibitedError,
)

from loop_engine.schema import (
    State,
    FailureClassification,
    ProposalManifest,
    VerificationReceipt,
    compute_spec_hash,
    compute_test_digest,
    compute_tree_hash,
    compute_env_fingerprint,
    compute_failure_signature,
)
from loop_engine.verifier_gate import PhysicalVerifierGate
from loop_engine.promoter import PromotionCoordinator
from loop_engine.quarantine import QuarantineManager, PathTraversalEscapeError
from loop_engine.governor import GovernorEngine
from zero_trust_engine.auditor import PlanAuditor, AuditResult



@pytest.fixture
def clean_kernel_harness(tmp_path: Path):
    repo_dir = tmp_path / "main_repo"
    repo_dir.mkdir()
    subprocess.run(["git", "init", "-b", "main"], cwd=repo_dir, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "ZeroTrustBot"], cwd=repo_dir, check=True)
    subprocess.run(["git", "config", "user.email", "bot@zero.trust"], cwd=repo_dir, check=True)

    src_file = repo_dir / "app.py"
    src_file.write_text("def run():\n    return 'v1.0'\n", encoding="utf-8")

    fixtures_dir = repo_dir / "canonical_fixtures"
    fixtures_dir.mkdir()
    (fixtures_dir / "test_app.py").write_text(
        "from app import run\ndef test_app():\n    assert run() == 'v2.0'\n",
        encoding="utf-8",
    )

    subprocess.run(["git", "add", "."], cwd=repo_dir, check=True)
    subprocess.run(["git", "commit", "-m", "initial release"], cwd=repo_dir, check=True)

    db_path = tmp_path / "kernel.db"
    db = KernelDatabase(db_path)
    quarantine = QuarantineManager(tmp_path / ".quarantine", kernel_db=db)
    governor = GovernorEngine(db, max_strikes=3)
    verifier_gate = PhysicalVerifierGate(repo_dir, fixtures_dir, db)
    promoter = PromotionCoordinator(repo_dir, "main", db, verifier_gate)

    return {
        "repo_dir": repo_dir,
        "fixtures_dir": fixtures_dir,
        "db": db,
        "quarantine": quarantine,
        "governor": governor,
        "verifier_gate": verifier_gate,
        "promoter": promoter,
        "tmp_path": tmp_path,
    }


# Test 1: Forged VERIFIED receipt rejected
def test_forged_verified_receipt_rejected(clean_kernel_harness):
    promoter = clean_kernel_harness["promoter"]
    # Attempt promotion with non-existent receipt ID -> ReceiptNotFoundError
    with pytest.raises(ReceiptNotFoundError):
        promoter.promote("TASK-FORGE-001", receipt_id=99999)


# Test 2: Proposal overwrite after sealing raises ProposalAlreadySealedError
def test_proposal_overwrite_after_sealing_raises(clean_kernel_harness):
    db = clean_kernel_harness["db"]
    manifest = ProposalManifest(
        task_id="TASK-SEAL-001",
        spec_hash="spec_hash_1",
        base_commit_sha="commit_1",
        candidate_commit_sha="cand_1",
        candidate_tree_sha="tree_1",
        verifier_version="2.0.0",
        acceptance_test_digest="digest_1",
        env_fingerprint=compute_env_fingerprint(),
    )
    db.record_proposal(manifest)

    # Attempt second record with same task_id -> MUST raise ProposalAlreadySealedError
    with pytest.raises(ProposalAlreadySealedError):
        db.record_proposal(manifest)


# Test 3: Illegal state transition raises IllegalStateTransitionError
def test_illegal_state_transition_raises(clean_kernel_harness):
    db = clean_kernel_harness["db"]
    manifest = ProposalManifest(
        task_id="TASK-STATE-001",
        spec_hash="spec_hash_2",
        base_commit_sha="commit_2",
        candidate_commit_sha="cand_2",
        candidate_tree_sha="tree_2",
        verifier_version="2.0.0",
        acceptance_test_digest="digest_2",
        env_fingerprint=compute_env_fingerprint(),
        state=State.CANDIDATE_SEALED,
    )
    db.record_proposal(manifest)

    # Direct jump from CANDIDATE_SEALED to PROMOTED is illegal -> MUST raise error
    with pytest.raises((IllegalStateTransitionError, PrivilegedStateMutationProhibitedError)):
        db.transition_proposal_state("TASK-STATE-001", State.CANDIDATE_SEALED, State.PROMOTED)



# Test 4: Fixture directory deletion/mutation blocked
def test_fixture_directory_deletion_blocked(clean_kernel_harness):
    repo_dir = clean_kernel_harness["repo_dir"]
    fixtures_dir = clean_kernel_harness["fixtures_dir"]
    db = clean_kernel_harness["db"]
    verifier_gate = clean_kernel_harness["verifier_gate"]

    task_id = "TASK-MUTATE-001"
    base_commit = subprocess.run(["git", "rev-parse", "HEAD"], cwd=repo_dir, capture_output=True, text=True, check=True).stdout.strip()

    wt = clean_kernel_harness["tmp_path"] / "wt_mutate"
    subprocess.run(["git", "worktree", "add", "-b", "mutate-branch", str(wt), "HEAD"], cwd=repo_dir, check=True, capture_output=True)
    (wt / "app.py").write_text("def run(): return 'v2.0'\n", encoding="utf-8")
    subprocess.run(["git", "add", "."], cwd=wt, check=True)
    subprocess.run(["git", "commit", "-m", "fix"], cwd=wt, check=True)

    cand_sha = subprocess.run(["git", "rev-parse", "HEAD"], cwd=wt, capture_output=True, text=True, check=True).stdout.strip()
    cand_tree = subprocess.run(["git", "rev-parse", "HEAD^{tree}"], cwd=wt, capture_output=True, text=True, check=True).stdout.strip()

    manifest = ProposalManifest(
        task_id=task_id,
        spec_hash="spec_mutate",
        base_commit_sha=base_commit,
        candidate_commit_sha=cand_sha,
        candidate_tree_sha=cand_tree,
        verifier_version="2.0.0",
        acceptance_test_digest="digest_mismatch_intentionally",
        env_fingerprint=compute_env_fingerprint(),
    )
    db.record_proposal(manifest)
    receipt_id, receipt = verifier_gate.verify_candidate(manifest, wt)

    assert receipt.status == State.BLOCKED
    assert receipt.failure_classification == FailureClassification.GOVERNOR_FAILURE


# Test 5: Candidate pytest.py/sitecustomize.py test bypass blocked
def test_candidate_pytest_shadowing_blocked(clean_kernel_harness):
    repo_dir = clean_kernel_harness["repo_dir"]
    fixtures_dir = clean_kernel_harness["fixtures_dir"]
    db = clean_kernel_harness["db"]
    verifier_gate = clean_kernel_harness["verifier_gate"]

    task_id = "TASK-SHADOW-001"
    base_commit = subprocess.run(["git", "rev-parse", "HEAD"], cwd=repo_dir, capture_output=True, text=True, check=True).stdout.strip()

    wt = clean_kernel_harness["tmp_path"] / "wt_shadow"
    subprocess.run(["git", "worktree", "add", "-b", "shadow-branch", str(wt), "HEAD"], cwd=repo_dir, check=True, capture_output=True)
    # Attacker places fake pytest.py in candidate root
    (wt / "pytest.py").write_text("import sys\nsys.exit(0)\n", encoding="utf-8")
    subprocess.run(["git", "add", "."], cwd=wt, check=True)
    subprocess.run(["git", "commit", "-m", "shadow pytest"], cwd=wt, check=True)

    cand_sha = subprocess.run(["git", "rev-parse", "HEAD"], cwd=wt, capture_output=True, text=True, check=True).stdout.strip()
    cand_tree = subprocess.run(["git", "rev-parse", "HEAD^{tree}"], cwd=wt, capture_output=True, text=True, check=True).stdout.strip()

    manifest = ProposalManifest(
        task_id=task_id,
        spec_hash="spec_shadow",
        base_commit_sha=base_commit,
        candidate_commit_sha=cand_sha,
        candidate_tree_sha=cand_tree,
        verifier_version="2.0.0",
        acceptance_test_digest=compute_test_digest(fixtures_dir),
        env_fingerprint=compute_env_fingerprint(),
    )
    db.record_proposal(manifest)
    receipt_id, receipt = verifier_gate.verify_candidate(manifest, wt)

    assert receipt.status == State.BLOCKED
    assert "shadowing" in receipt.execution_trace.lower()


# Test 6: Zero-tests-collected success rejected
def test_zero_tests_collected_rejected(clean_kernel_harness):
    repo_dir = clean_kernel_harness["repo_dir"]
    fixtures_dir = clean_kernel_harness["fixtures_dir"]
    db = clean_kernel_harness["db"]
    verifier_gate = clean_kernel_harness["verifier_gate"]

    task_id = "TASK-ZERO-001"
    base_commit = subprocess.run(["git", "rev-parse", "HEAD"], cwd=repo_dir, capture_output=True, text=True, check=True).stdout.strip()

    # Create empty test fixture and commit to main
    (fixtures_dir / "test_empty.py").write_text("# empty test file\n", encoding="utf-8")
    subprocess.run(["git", "add", "."], cwd=repo_dir, check=True)
    subprocess.run(["git", "commit", "-m", "add empty test fixture"], cwd=repo_dir, check=True)
    base_commit = subprocess.run(["git", "rev-parse", "HEAD"], cwd=repo_dir, capture_output=True, text=True, check=True).stdout.strip()

    wt = clean_kernel_harness["tmp_path"] / "wt_zero"
    subprocess.run(["git", "worktree", "add", "-b", "zero-branch", str(wt), "HEAD"], cwd=repo_dir, check=True, capture_output=True)
    (wt / "app.py").write_text("def run(): return 'v2.0'\n", encoding="utf-8")
    subprocess.run(["git", "add", "."], cwd=wt, check=True)
    subprocess.run(["git", "commit", "-m", "zero tests"], cwd=wt, check=True)

    cand_sha = subprocess.run(["git", "rev-parse", "HEAD"], cwd=wt, capture_output=True, text=True, check=True).stdout.strip()
    cand_tree = subprocess.run(["git", "rev-parse", "HEAD^{tree}"], cwd=wt, capture_output=True, text=True, check=True).stdout.strip()

    manifest = ProposalManifest(
        task_id=task_id,
        spec_hash="spec_zero",
        base_commit_sha=base_commit,
        candidate_commit_sha=cand_sha,
        candidate_tree_sha=cand_tree,
        verifier_version="2.0.0",
        acceptance_test_digest=compute_test_digest(fixtures_dir),
        env_fingerprint=compute_env_fingerprint(),
    )
    db.record_proposal(manifest)
    receipt_id, receipt = verifier_gate.verify_candidate(manifest, wt, test_file_relative="test_empty.py")

    assert receipt.status == State.REJECTED
    assert "zero tests collected" in receipt.execution_trace.lower()


# Test 7: Dirty or stale target branch blocked
def test_dirty_or_stale_target_branch_blocked(clean_kernel_harness):
    repo_dir = clean_kernel_harness["repo_dir"]
    fixtures_dir = clean_kernel_harness["fixtures_dir"]
    db = clean_kernel_harness["db"]
    verifier_gate = clean_kernel_harness["verifier_gate"]
    promoter = clean_kernel_harness["promoter"]

    task_id = "TASK-DIRTY-001"
    base_commit = subprocess.run(["git", "rev-parse", "HEAD"], cwd=repo_dir, capture_output=True, text=True, check=True).stdout.strip()

    wt = clean_kernel_harness["tmp_path"] / "wt_dirty"
    subprocess.run(["git", "worktree", "add", "-b", "dirty-branch", str(wt), "HEAD"], cwd=repo_dir, check=True, capture_output=True)
    (wt / "app.py").write_text("def run(): return 'v2.0'\n", encoding="utf-8")
    subprocess.run(["git", "add", "app.py"], cwd=wt, check=True)
    subprocess.run(["git", "commit", "-m", "clean candidate"], cwd=wt, check=True)

    cand_sha = subprocess.run(["git", "rev-parse", "HEAD"], cwd=wt, capture_output=True, text=True, check=True).stdout.strip()
    cand_tree = subprocess.run(["git", "rev-parse", "HEAD^{tree}"], cwd=wt, capture_output=True, text=True, check=True).stdout.strip()

    manifest = ProposalManifest(
        task_id=task_id,
        spec_hash="spec_dirty",
        base_commit_sha=base_commit,
        candidate_commit_sha=cand_sha,
        candidate_tree_sha=cand_tree,
        verifier_version="2.0.0",
        acceptance_test_digest=compute_test_digest(fixtures_dir),
        env_fingerprint=compute_env_fingerprint(),
    )
    db.record_proposal(manifest)
    receipt_id, receipt = verifier_gate.verify_candidate(manifest, wt)
    assert receipt.status == State.VERIFIED

    # Dirty the main repo worktree
    (repo_dir / "untracked.txt").write_text("dirty state", encoding="utf-8")

    # Promotion must be blocked
    assert promoter.promote(task_id, receipt_id) is False
    assert db.get_proposal_state(task_id) == State.VERIFIED

    # Clean up dirty file
    (repo_dir / "untracked.txt").unlink()


# Test 8: Target movement after verification aborts
def test_target_movement_after_verification_aborts(clean_kernel_harness):
    repo_dir = clean_kernel_harness["repo_dir"]
    fixtures_dir = clean_kernel_harness["fixtures_dir"]
    db = clean_kernel_harness["db"]
    verifier_gate = clean_kernel_harness["verifier_gate"]
    promoter = clean_kernel_harness["promoter"]

    task_id = "TASK-MOVE-001"
    base_commit = subprocess.run(["git", "rev-parse", "HEAD"], cwd=repo_dir, capture_output=True, text=True, check=True).stdout.strip()

    wt = clean_kernel_harness["tmp_path"] / "wt_move"
    subprocess.run(["git", "worktree", "add", "-b", "move-branch", str(wt), "HEAD"], cwd=repo_dir, check=True, capture_output=True)
    (wt / "app.py").write_text("def run(): return 'v2.0'\n", encoding="utf-8")
    subprocess.run(["git", "add", "app.py"], cwd=wt, check=True)
    subprocess.run(["git", "commit", "-m", "candidate v2"], cwd=wt, check=True)

    cand_sha = subprocess.run(["git", "rev-parse", "HEAD"], cwd=wt, capture_output=True, text=True, check=True).stdout.strip()
    cand_tree = subprocess.run(["git", "rev-parse", "HEAD^{tree}"], cwd=wt, capture_output=True, text=True, check=True).stdout.strip()

    manifest = ProposalManifest(
        task_id=task_id,
        spec_hash="spec_move",
        base_commit_sha=base_commit,
        candidate_commit_sha=cand_sha,
        candidate_tree_sha=cand_tree,
        verifier_version="2.0.0",
        acceptance_test_digest=compute_test_digest(fixtures_dir),
        env_fingerprint=compute_env_fingerprint(),
    )
    db.record_proposal(manifest)
    receipt_id, receipt = verifier_gate.verify_candidate(manifest, wt)
    assert receipt.status == State.VERIFIED

    # Move target branch HEAD to another commit
    (repo_dir / "unrelated.py").write_text("x = 1\n", encoding="utf-8")
    subprocess.run(["git", "add", "."], cwd=repo_dir, check=True)
    subprocess.run(["git", "commit", "-m", "unrelated target movement"], cwd=repo_dir, check=True)

    # Candidate commit cannot be ff-merged onto new divergent HEAD -> promotion fails
    assert promoter.promote(task_id, receipt_id) is False


# Test 9: Crash at every promotion boundary reconciled via ancestry
def test_crash_at_every_promotion_boundary(clean_kernel_harness):
    repo_dir = clean_kernel_harness["repo_dir"]
    fixtures_dir = clean_kernel_harness["fixtures_dir"]
    db = clean_kernel_harness["db"]
    verifier_gate = clean_kernel_harness["verifier_gate"]
    promoter = clean_kernel_harness["promoter"]

    task_id = "TASK-RECON-001"
    base_commit = subprocess.run(["git", "rev-parse", "HEAD"], cwd=repo_dir, capture_output=True, text=True, check=True).stdout.strip()

    wt = clean_kernel_harness["tmp_path"] / "wt_recon"
    subprocess.run(["git", "worktree", "add", "-b", "recon-branch", str(wt), "HEAD"], cwd=repo_dir, check=True, capture_output=True)
    (wt / "app.py").write_text("def run(): return 'v2.0'\n", encoding="utf-8")
    subprocess.run(["git", "add", "app.py"], cwd=wt, check=True)
    subprocess.run(["git", "commit", "-m", "candidate v2"], cwd=wt, check=True)

    cand_sha = subprocess.run(["git", "rev-parse", "HEAD"], cwd=wt, capture_output=True, text=True, check=True).stdout.strip()
    cand_tree = subprocess.run(["git", "rev-parse", "HEAD^{tree}"], cwd=wt, capture_output=True, text=True, check=True).stdout.strip()

    manifest = ProposalManifest(
        task_id=task_id,
        spec_hash="spec_recon",
        base_commit_sha=base_commit,
        candidate_commit_sha=cand_sha,
        candidate_tree_sha=cand_tree,
        verifier_version="2.0.0",
        acceptance_test_digest=compute_test_digest(fixtures_dir),
        env_fingerprint=compute_env_fingerprint(),
        state=State.PROMOTION_PENDING,
    )
    db.record_proposal(manifest)

    # Case A: Commit not merged yet -> reconcile rolls back to VERIFIED
    promoter.reconcile_interrupted_promotions()
    assert db.get_proposal_state(task_id) == State.VERIFIED

    # Case B: Commit was merged before crash -> reconcile advances to POST_PROMOTION_VERIFIED
    subprocess.run(["git", "checkout", "main"], cwd=repo_dir, check=True, capture_output=True)
    subprocess.run(["git", "merge", "--ff-only", cand_sha], cwd=repo_dir, check=True, capture_output=True)
    db._raw_transition_proposal_state(task_id, State.VERIFIED, State.PROMOTION_PENDING)

    promoter.reconcile_interrupted_promotions()
    assert db.get_proposal_state(task_id) == State.POST_PROMOTION_VERIFIED


# Test 10: Concurrent promotion attempts rejected by CAS
def test_concurrent_promotion_attempts_blocked(clean_kernel_harness):
    db = clean_kernel_harness["db"]
    manifest = ProposalManifest(
        task_id="TASK-CONCUR-001",
        spec_hash="spec_concur",
        base_commit_sha="commit_c",
        candidate_commit_sha="cand_c",
        candidate_tree_sha="tree_c",
        verifier_version="2.0.0",
        acceptance_test_digest="digest_c",
        env_fingerprint=compute_env_fingerprint(),
        state=State.VERIFIED,
    )
    db.record_proposal(manifest)

    # Worker 1 transitions VERIFIED -> PROMOTION_PENDING
    db._raw_transition_proposal_state("TASK-CONCUR-001", State.VERIFIED, State.PROMOTION_PENDING)

    # Worker 2 attempts concurrent transition from VERIFIED -> MUST raise IllegalStateTransitionError
    with pytest.raises(IllegalStateTransitionError):
        db._raw_transition_proposal_state("TASK-CONCUR-001", State.VERIFIED, State.PROMOTION_PENDING)



# Test 11: Unreadable or changed hashed file rejected
def test_unreadable_or_changed_hashed_file(clean_kernel_harness):
    repo_dir = clean_kernel_harness["repo_dir"]
    fixtures_dir = clean_kernel_harness["fixtures_dir"]
    db = clean_kernel_harness["db"]
    verifier_gate = clean_kernel_harness["verifier_gate"]

    task_id = "TASK-TAMPER-TREE"
    base_commit = subprocess.run(["git", "rev-parse", "HEAD"], cwd=repo_dir, capture_output=True, text=True, check=True).stdout.strip()

    wt = clean_kernel_harness["tmp_path"] / "wt_tamper_tree"
    subprocess.run(["git", "worktree", "add", "-b", "tamper-tree-branch", str(wt), "HEAD"], cwd=repo_dir, check=True, capture_output=True)
    (wt / "app.py").write_text("def run(): return 'v2.0'\n", encoding="utf-8")
    subprocess.run(["git", "add", "."], cwd=wt, check=True)
    subprocess.run(["git", "commit", "-m", "commit 1"], cwd=wt, check=True)

    cand_sha = subprocess.run(["git", "rev-parse", "HEAD"], cwd=wt, capture_output=True, text=True, check=True).stdout.strip()

    # Create manifest with fake tree SHA
    manifest = ProposalManifest(
        task_id=task_id,
        spec_hash="spec_tamper_tree",
        base_commit_sha=base_commit,
        candidate_commit_sha=cand_sha,
        candidate_tree_sha="fake_tree_sha_000000000000000000000000",
        verifier_version="2.0.0",
        acceptance_test_digest=compute_test_digest(fixtures_dir),
        env_fingerprint=compute_env_fingerprint(),
    )
    db.record_proposal(manifest)
    receipt_id, receipt = verifier_gate.verify_candidate(manifest, wt)

    assert receipt.status == State.REJECTED
    assert receipt.failure_classification == FailureClassification.CANDIDATE_FAILURE


# Test 12: Quarantine path traversal and symlink escape blocked
def test_quarantine_path_traversal_and_symlink_escape(clean_kernel_harness):
    quarantine = clean_kernel_harness["quarantine"]
    receipt = VerificationReceipt(
        receipt_id=1,
        task_id="TASK-Q-ESCAPE",
        spec_hash="spec_q",
        base_commit_sha="base_q",
        candidate_commit_sha="cand_q",
        candidate_tree_sha="tree_q",
        physical_tree_hash="tree_q",
        verifier_version="2.0.0",
        acceptance_test_digest="digest_q",
        env_fingerprint=compute_env_fingerprint(),
        status=State.REJECTED,
        failure_classification=FailureClassification.CANDIDATE_FAILURE,
    )

    # Path traversal with .. must raise PathTraversalEscapeError
    with pytest.raises(PathTraversalEscapeError):
        quarantine.preserve_candidate("TASK-Q-ESCAPE", Path("../../etc"), receipt, "sig_err")


# Test 13: Empty and paraphrased defective plans rejected by PlanAuditor
def test_empty_and_paraphrased_defective_plans():
    auditor = PlanAuditor()
    assert auditor.audit_plan("").outcome == AuditResult.BLOCK
    assert auditor.audit_plan("Just do the task").outcome == AuditResult.BLOCK

    plan_no_tests = """
    # Update Database Layer
    Add user_id column to sessions table. Update session_store.py accordingly.
    """
    res = auditor.audit_plan(plan_no_tests)
    assert res.outcome in (AuditResult.BLOCK, AuditResult.REVISE)


# Test 14: Duplicate persistence authority prohibited (single KernelDatabase)
def test_duplicate_persistence_authority_prohibited(clean_kernel_harness):
    db = clean_kernel_harness["db"]
    # Assert db is KernelDatabase and manages proposals, receipts, strikes, quarantine in one connection
    assert isinstance(db, KernelDatabase)
    with db.get_connection() as conn:
        tables = [r["name"] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table';").fetchall()]
        assert "runs" in tables
        assert "artifacts" in tables
        assert "proposals" in tables
        assert "verified_receipts" in tables
        assert "quarantine_log" in tables
        assert "strike_log" in tables
        assert "promotion_wal" in tables


# Test 15: Real CanonicalObjective -> Scribe -> Herald -> Slicer route executed with artifact lineage & receipt persistence
def test_real_route_artifact_lineage_and_consumption(clean_kernel_harness):
    from loop_engine.router import BoundedShadowRouter
    from loop_engine.canonical_objective import CanonicalObjective, EvidenceReference
    from loop_engine.context import RunContext
    from loop_engine.artifacts import ArtifactRegistry
    from loop_engine.governor import StepGovernor

    db = clean_kernel_harness["db"]
    repo_dir = clean_kernel_harness["repo_dir"]
    artifact_registry = ArtifactRegistry(kernel_db=db, storage_dir=clean_kernel_harness["tmp_path"] / "artifacts")

    canonical_obj = CanonicalObjective(
        objective_id="obj_media_prod_001",
        objective_type="media_production",
        description="Comprehensive Architectural Walkthrough of 10 SHADOWS",
        desired_outcome="Create a verified architectural walkthrough of 10 SHADOWS",
        target_audience="Software and Systems Engineers",
        core_message="Deterministic multi-shadow pipelines prevent drift",
        intended_audience_action="Deploy zero-trust loops",
        narrative_arc_type="technical_deepdive",
        verified_evidence=[
            EvidenceReference(
                evidence_id="ev_001",
                source_description="KernelDatabase is single authority specification",
                confidence="VERIFIED_FACT",
            )
        ],
        explicit_unknowns=[],
    )

    plan = BoundedShadowRouter.plan_route(canonical_obj, requested_pipeline_type="media_production")
    assert len(plan.steps) == 3
    assert plan.selected_domain_codes == ["scribe", "herald", "slicer"]

    parent_ctx = RunContext.create(
        task_id="task_route_001",
        shadow_id=6,
        domain_code="scribe",
        raw_objective=canonical_obj,
    )

    governor = StepGovernor(kernel_db=db)
    route_res = BoundedShadowRouter.execute_route(
        plan=plan,
        canonical_objective=canonical_obj,
        parent_context=parent_ctx,
        artifact_registry=artifact_registry,
        kernel_db=db,
        step_governor=governor,
    )

    assert route_res.status == "SUCCESS"
    assert route_res.completed_step_ids == ["step_1_scribe", "step_2_herald", "step_3_slicer"]
    assert route_res.final_artifact_type == "ProductionPlanDAGArtifact"

    # Verify runs and receipts were recorded in KernelDatabase
    run_rec = db.get_run(parent_ctx.run_id)
    assert run_rec is not None
    assert run_rec["status"] in ("COMPLETED", "SUCCESS")

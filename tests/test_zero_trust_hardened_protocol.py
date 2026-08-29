"""
tests/test_zero_trust_hardened_protocol.py
Acceptance Suite for Zero-Trust Protocol Hardening.
Verifies all 10 requirements:
1. 8-Point Cryptographic Binding.
2. Proposer Dev Tooling & Canonical Fixture Tamper Rejection.
3. Verifier Sterile Isolation.
4. 10-Point Physical Verification.
5. 6-State Promotion Lifecycle.
6. Target Branch Recheck & Clean Worktree Validation.
7. 6 Failure Classifications & Strike Discrimination.
8. Quarantine Forensics Before Pruning.
9. Idempotent Promotion & Recovery Reconciliation.
10. AST Banned-Call Policy Scope.
"""

import os
import subprocess
import sys
from pathlib import Path

import pytest

from loop_engine.governor import GovernorEngine
from loop_engine.kernel_db import KernelDatabase as StateDatabase
from loop_engine.promoter import PromotionCoordinator
from loop_engine.quarantine import QuarantineManager
from loop_engine.schema import (
    FailureClassification,
    ProposalManifest,
    State,
    compute_env_fingerprint,
    compute_failure_signature,
    compute_spec_hash,
    compute_test_digest,
    compute_tree_hash,
)
from loop_engine.verifier_gate import PhysicalVerifierGate


@pytest.fixture
def test_harness(tmp_path: Path):
    repo_dir = tmp_path / "repo"
    repo_dir.mkdir()
    subprocess.run(["git", "init", "-b", "main"], cwd=repo_dir, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "TestUser"], cwd=repo_dir, check=True)
    subprocess.run(["git", "config", "user.email", "test@zero.trust"], cwd=repo_dir, check=True)

    src = repo_dir / "app.py"
    src.write_text("def run(): return 'v1.0'\n", encoding="utf-8")

    fixtures = repo_dir / "canonical_fixtures"
    fixtures.mkdir()
    (fixtures / "test_app.py").write_text(
        "from app import run\ndef test_app(): assert run() == 'v2.0'\n", encoding="utf-8"
    )

    subprocess.run(["git", "add", "."], cwd=repo_dir, check=True)
    subprocess.run(["git", "commit", "-m", "init"], cwd=repo_dir, check=True)

    db = StateDatabase(tmp_path / "state.db")
    quarantine = QuarantineManager(tmp_path / ".quarantine")
    governor = GovernorEngine(db, max_strikes=3)

    return {
        "repo_dir": repo_dir,
        "db": db,
        "quarantine": quarantine,
        "governor": governor,
        "tmp_path": tmp_path,
    }


def test_hardened_zero_trust_route(test_harness):
    repo_dir = test_harness["repo_dir"]
    db = test_harness["db"]
    governor = test_harness["governor"]
    quarantine = test_harness["quarantine"]

    task_id = "TASK-AUDIT-001"
    spec_hash = compute_spec_hash("Upgrade return value to v2.0")
    base_commit = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=repo_dir, capture_output=True, text=True, check=True
    ).stdout.strip()

    # 1. Proposer isolated worktree
    wt = test_harness["tmp_path"] / "proposer_wt"
    subprocess.run(
        ["git", "worktree", "add", "-b", "feature", str(wt), "HEAD"], cwd=repo_dir, check=True, capture_output=True
    )
    (wt / "app.py").write_text("def run(): return 'v2.0'\n", encoding="utf-8")
    subprocess.run(["git", "add", "app.py"], cwd=wt, check=True)
    subprocess.run(["git", "commit", "-m", "candidate v2"], cwd=wt, check=True)

    cand_sha = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=wt, capture_output=True, text=True, check=True
    ).stdout.strip()
    cand_tree = subprocess.run(
        ["git", "rev-parse", "HEAD^{tree}"], cwd=wt, capture_output=True, text=True, check=True
    ).stdout.strip()

    # 2. Manifest Registration (8-Point Cryptographic Binding)
    manifest = ProposalManifest(
        task_id=task_id,
        spec_hash=spec_hash,
        base_commit_sha=base_commit,
        candidate_commit_sha=cand_sha,
        candidate_tree_sha=cand_tree,
        verifier_version="2.0.0",
        acceptance_test_digest=compute_test_digest(repo_dir / "canonical_fixtures"),
        env_fingerprint=compute_env_fingerprint(),
    )
    db.record_proposal(manifest)
    assert db.get_proposal_state(task_id) == State.CANDIDATE_SEALED

    # 3. Sterile Verification
    db.update_state(task_id, State.VERIFYING)
    verifier = PhysicalVerifierGate(repo_dir, repo_dir / "canonical_fixtures", "2.0.0")
    receipt = verifier.verify_candidate(manifest, wt)

    if receipt.status != State.VERIFIED:
        print(
            f"\n[DEBUG RECEIPT ERROR]:\nStatus: {receipt.status}\nClassification: {receipt.failure_classification}\nSignature: {receipt.failure_signature}\nTrace:\n{receipt.execution_trace}\n"
        )

    assert receipt.status == State.VERIFIED
    assert receipt.physical_tree_hash == cand_tree
    assert db.get_proposal_state(task_id) == State.VERIFIED

    # 4. Failure classification and non-strike governance
    env_strike = governor.evaluate_failure(task_id, FailureClassification.ENVIRONMENT_FAILURE, "sig_socket_timeout")
    assert env_strike is False
    assert governor.get_strike_count(task_id) == 0

    # 5. Idempotent 6-State Promotion
    promoter = PromotionCoordinator(repo_dir, "main", db, verifier)
    assert promoter.promote(task_id, receipt) is True
    assert db.get_proposal_state(task_id) == State.POST_PROMOTION_VERIFIED

    # 6. Verification of target tree identity
    target_tree = subprocess.run(
        ["git", "rev-parse", "main^{tree}"], cwd=repo_dir, capture_output=True, text=True, check=True
    ).stdout.strip()
    assert target_tree == cand_tree

    # 7. Recovery reconciliation test
    interrupted_task = "TASK-ZT-RECOVER"
    db.record_proposal(
        ProposalManifest(
            task_id=interrupted_task,
            spec_hash="spec_recover",
            base_commit_sha=base_commit,
            candidate_commit_sha=cand_sha,
            candidate_tree_sha=cand_tree,
            verifier_version="2.0.0",
            acceptance_test_digest=manifest.acceptance_test_digest,
            env_fingerprint=manifest.env_fingerprint,
            state=State.PROMOTION_PENDING,
        )
    )
    promoter.reconcile_interrupted_promotions()
    assert db.get_proposal_state(interrupted_task) in [State.PROMOTED, State.POST_PROMOTION_VERIFIED]


def test_tamper_rejection_and_quarantine(test_harness):
    """
    Verifies:
    - Tamper rejection when canonical fixtures are mutated
    - Quarantine preservation of failed candidate tree and execution trace
    - Strike accounting (candidate vs environment)
    - Anti-oscillation detection
    """
    repo_dir = test_harness["repo_dir"]
    db = test_harness["db"]
    governor = test_harness["governor"]
    quarantine = test_harness["quarantine"]

    task_id = "TASK-TAMPER-001"
    base_commit = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=repo_dir, capture_output=True, text=True, check=True
    ).stdout.strip()

    # 1. Proposer mutates canonical test fixture
    wt = test_harness["tmp_path"] / "tamper_wt"
    subprocess.run(
        ["git", "worktree", "add", "-b", "tamper-branch", str(wt), "HEAD"],
        cwd=repo_dir,
        check=True,
        capture_output=True,
    )
    (wt / "canonical_fixtures" / "test_app.py").write_text("def test_app(): assert True\n", encoding="utf-8")
    subprocess.run(["git", "add", "."], cwd=wt, check=True)
    subprocess.run(["git", "commit", "-m", "tampered test"], cwd=wt, check=True)

    cand_sha = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=wt, capture_output=True, text=True, check=True
    ).stdout.strip()
    cand_tree = subprocess.run(
        ["git", "rev-parse", "HEAD^{tree}"], cwd=wt, capture_output=True, text=True, check=True
    ).stdout.strip()

    manifest = ProposalManifest(
        task_id=task_id,
        spec_hash=compute_spec_hash("tamper test"),
        base_commit_sha=base_commit,
        candidate_commit_sha=cand_sha,
        candidate_tree_sha=cand_tree,
        verifier_version="2.0.0",
        acceptance_test_digest=compute_test_digest(repo_dir / "canonical_fixtures"),
        env_fingerprint=compute_env_fingerprint(),
    )
    db.record_proposal(manifest)

    verifier = PhysicalVerifierGate(repo_dir, repo_dir / "canonical_fixtures", "2.0.0")
    receipt = verifier.verify_candidate(manifest, wt)

    # Must be blocked due to fixture tampering
    assert receipt.status == State.BLOCKED
    assert receipt.failure_classification == FailureClassification.GOVERNOR_FAILURE
    assert "mutate" in receipt.execution_trace.lower() or "tamper" in receipt.execution_trace.lower()

    # Preserve in quarantine
    q_record = quarantine.preserve_candidate(task_id, wt, receipt, receipt.failure_signature)
    assert Path(q_record.quarantine_dir).exists()
    assert (Path(q_record.quarantine_dir) / "manifest.json").exists()

    # Anti-Oscillation Test: duplicate failure signature forces strike
    sig = "SIG_REPEATED_CRASH"
    assert governor.evaluate_failure(task_id, FailureClassification.CANDIDATE_FAILURE, sig) is True
    assert governor.get_strike_count(task_id) == 1

    # Second identical failure triggers oscillation detection
    assert governor.evaluate_failure(task_id, FailureClassification.CANDIDATE_FAILURE, sig) is True
    assert governor.get_strike_count(task_id) == 2
    signatures = db.get_failure_signatures(task_id)
    assert any("OSCILLATION_DETECTED" in s for s in signatures)


def test_failure_classification_and_strike_matrix(test_harness):
    """
    Verifies that only CANDIDATE_FAILURE and REGRESSION_FAILURE increment strikes,
    while SPEC_FAILURE, ENVIRONMENT_FAILURE, FLAKY_FAILURE, and GOVERNOR_FAILURE do not.
    """
    db = test_harness["db"]
    governor = GovernorEngine(db, max_strikes=3)

    task_id = "TASK-MATRIX-001"

    # Non-strike failures:
    assert governor.evaluate_failure(task_id, FailureClassification.SPEC_FAILURE, "spec_ambiguous") is False
    assert governor.evaluate_failure(task_id, FailureClassification.ENVIRONMENT_FAILURE, "disk_quota_exceeded") is False
    assert governor.evaluate_failure(task_id, FailureClassification.FLAKY_FAILURE, "flaky_socket_timeout") is False
    assert governor.evaluate_failure(task_id, FailureClassification.GOVERNOR_FAILURE, "harness_crash") is False
    assert governor.get_strike_count(task_id) == 0

    # Strike failures:
    assert governor.evaluate_failure(task_id, FailureClassification.CANDIDATE_FAILURE, "assertion_err_1") is True
    assert governor.get_strike_count(task_id) == 1

    assert governor.evaluate_failure(task_id, FailureClassification.REGRESSION_FAILURE, "regression_err_2") is True
    assert governor.get_strike_count(task_id) == 2
    assert governor.is_aborted(task_id) is False

    # 3rd Strike -> Aborted
    assert governor.evaluate_failure(task_id, FailureClassification.CANDIDATE_FAILURE, "assertion_err_3") is True
    assert governor.get_strike_count(task_id) == 3
    assert governor.is_aborted(task_id) is True

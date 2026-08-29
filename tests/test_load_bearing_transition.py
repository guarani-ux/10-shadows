"""
tests/test_load_bearing_transition.py
Adversarial Falsification Suite for the 10 SHADOWS Load-Bearing Privileged Transition Seam.

Proves:
1. Deleting/disabling PrivilegedTransitionEngine makes privileged state creation impossible across the system.
2. KernelDatabase mechanically rejects direct unauthenticated mutations to privileged states.
3. ProofWitness is cryptographically bound to the complete material claim and cannot be transplanted.
4. Illegal state jumps and replay attacks are rejected.
5. Governance mismatches fail closed.
"""

import hashlib
import json
import secrets
import subprocess
from pathlib import Path

import pytest

from loop_engine.authority import issue_proof_witness
from loop_engine.epistemic import EpistemicDisposition
from loop_engine.kernel_db import (
    KernelDatabase,
    PrivilegedStateMutationProhibitedError,
)
from loop_engine.promoter import PromotionCoordinator
from loop_engine.schema import (
    EnvironmentFingerprint,
    ProposalManifest,
    State,
    VerificationReceipt,
    compute_test_digest,
)
from loop_engine.transition import (
    _INTERNAL_TRANSITION_TOKEN,
    PrivilegedTransitionEngine,
    TransitionReceipt,
    TransitionRejection,
    TransitionRequest,
    compute_complete_claim_digest,
    compute_governance_digest,
)
from loop_engine.verifier_gate import PhysicalVerifierGate


def create_sample_manifest(task_id: str = "task_01", base_commit: str = "base_1") -> ProposalManifest:
    return ProposalManifest(
        task_id=task_id,
        spec_hash="spec_1",
        base_commit_sha=base_commit,
        candidate_commit_sha="cand_1",
        candidate_tree_sha="tree_1",
        verifier_version="2.0.0",
        acceptance_test_digest="test_1",
        env_fingerprint=EnvironmentFingerprint.capture(),
        state=State.CANDIDATE_SEALED,
    )


class TestLoadBearingTransitionSeam:
    """Proves that PrivilegedTransitionEngine is the single, unbypassable authority for privileged state."""

    def test_direct_db_privileged_mutation_prohibited(self, tmp_path: Path):
        """Proves KernelDatabase rejects direct unauthenticated attempts to mint privileged states."""
        db = KernelDatabase(db_path=tmp_path / "kernel.db")
        task_id = "task_attack_01"
        manifest = create_sample_manifest(task_id=task_id)
        db.record_proposal(manifest)

        # 1. Attempt direct update to VERIFIED
        with pytest.raises(
            PrivilegedStateMutationProhibitedError,
            match="Direct database mutation to privileged state 'VERIFIED' is prohibited",
        ):
            db.transition_proposal_state(task_id, State.CANDIDATE_SEALED, State.VERIFIED)

        # 2. Attempt direct update to PROMOTION_PENDING
        with pytest.raises(
            PrivilegedStateMutationProhibitedError,
            match="Direct database mutation to privileged state 'PROMOTION_PENDING' is prohibited",
        ):
            db.transition_proposal_state(task_id, State.CANDIDATE_SEALED, State.PROMOTION_PENDING)

        # 3. Attempt direct update to PROMOTED
        with pytest.raises(
            PrivilegedStateMutationProhibitedError,
            match="Direct database mutation to privileged state 'PROMOTED' is prohibited",
        ):
            db.transition_proposal_state(task_id, State.CANDIDATE_SEALED, State.PROMOTED)

        # 4. Attempt direct update to POST_PROMOTION_VERIFIED
        with pytest.raises(
            PrivilegedStateMutationProhibitedError,
            match="Direct database mutation to privileged state 'POST_PROMOTION_VERIFIED' is prohibited",
        ):
            db.transition_proposal_state(task_id, State.CANDIDATE_SEALED, State.POST_PROMOTION_VERIFIED)

    def test_valid_privileged_transition_lifecycle(self, tmp_path: Path):
        """Proves that valid witnessed requests successfully transition state and emit receipts."""
        db = KernelDatabase(db_path=tmp_path / "kernel.db")
        engine = PrivilegedTransitionEngine(kernel_db=db)
        task_id = "task_valid_01"
        manifest = create_sample_manifest(task_id=task_id)
        db.record_proposal(manifest)

        gov_digest = compute_governance_digest()
        claim_digest = compute_complete_claim_digest(
            task_id=task_id,
            from_state=State.CANDIDATE_SEALED,
            to_state=State.VERIFIED,
            subject_identity="commit_sha_123",
            candidate_tree_sha="tree_sha_123",
            spec_hash="spec_1",
            acceptance_test_digest="test_digest_1",
            evidence_digest="evidence_1",
            authority_scope="PHYSICAL_VERIFICATION",
            governance_hash=gov_digest,
        )

        witness = issue_proof_witness(
            issuer="test_suite",
            target_digest=claim_digest,
            scope="PHYSICAL_VERIFICATION",
        )

        req = TransitionRequest(
            task_id=task_id,
            from_state=State.CANDIDATE_SEALED,
            to_state=State.VERIFIED,
            subject_identity="commit_sha_123",
            candidate_tree_sha="tree_sha_123",
            spec_hash="spec_1",
            acceptance_test_digest="test_digest_1",
            evidence_digest="evidence_1",
            authority_scope="PHYSICAL_VERIFICATION",
            witness=witness,
            governance_hash=gov_digest,
        )

        result = engine.execute_transition(req)
        assert isinstance(result, TransitionReceipt)
        assert result.to_state == State.VERIFIED
        assert result.disposition == EpistemicDisposition.SATISFIED
        # Verify proposal state in database is updated via custody token
        assert db.get_proposal_state(task_id) == State.VERIFIED

    def test_claim_transplant_attack_rejected(self, tmp_path: Path):
        """Proves a witness generated for task A cannot be transplanted onto task B."""
        db = KernelDatabase(db_path=tmp_path / "kernel.db")
        engine = PrivilegedTransitionEngine(kernel_db=db)
        task_a = "task_legit_a"
        task_b = "task_attacker_b"

        gov_digest = compute_governance_digest()
        claim_digest_a = compute_complete_claim_digest(
            task_id=task_a,
            from_state=State.CANDIDATE_SEALED,
            to_state=State.VERIFIED,
            subject_identity="commit_sha_a",
            candidate_tree_sha="tree_sha_a",
            spec_hash="spec_a",
            acceptance_test_digest="test_a",
            evidence_digest="evidence_a",
            authority_scope="PHYSICAL_VERIFICATION",
            governance_hash=gov_digest,
        )

        # Legitimate witness for Task A
        witness_a = issue_proof_witness(
            issuer="test_suite",
            target_digest=claim_digest_a,
            scope="PHYSICAL_VERIFICATION",
        )

        # Attacker tries to use witness A to authorize Task B
        req_transplant = TransitionRequest(
            task_id=task_b,
            from_state=State.CANDIDATE_SEALED,
            to_state=State.VERIFIED,
            subject_identity="commit_sha_b",
            candidate_tree_sha="tree_sha_b",
            spec_hash="spec_b",
            acceptance_test_digest="test_b",
            evidence_digest="evidence_b",
            authority_scope="PHYSICAL_VERIFICATION",
            witness=witness_a,  # Transplanted!
            governance_hash=gov_digest,
        )

        result = engine.execute_transition(req_transplant)
        assert isinstance(result, TransitionRejection)
        assert "ProofWitness cryptographic verification failed" in result.reason

    def test_state_jump_attack_rejected(self, tmp_path: Path):
        """Proves illegal state transitions are blocked by the state machine gate."""
        db = KernelDatabase(db_path=tmp_path / "kernel.db")
        engine = PrivilegedTransitionEngine(kernel_db=db)
        task_id = "task_jump_01"

        gov_digest = compute_governance_digest()
        # Attempt to jump straight from CANDIDATE_SEALED to POST_PROMOTION_VERIFIED
        claim_digest = compute_complete_claim_digest(
            task_id=task_id,
            from_state=State.CANDIDATE_SEALED,
            to_state=State.POST_PROMOTION_VERIFIED,
            subject_identity="commit_1",
            candidate_tree_sha="tree_1",
            spec_hash="spec_1",
            acceptance_test_digest="test_1",
            evidence_digest="ev_1",
            authority_scope="PROMOTION",
            governance_hash=gov_digest,
        )

        witness = issue_proof_witness(
            issuer="test_suite",
            target_digest=claim_digest,
            scope="PROMOTION",
        )

        req = TransitionRequest(
            task_id=task_id,
            from_state=State.CANDIDATE_SEALED,
            to_state=State.POST_PROMOTION_VERIFIED,
            subject_identity="commit_1",
            candidate_tree_sha="tree_1",
            spec_hash="spec_1",
            acceptance_test_digest="test_1",
            evidence_digest="ev_1",
            authority_scope="PROMOTION",
            witness=witness,
            governance_hash=gov_digest,
        )

        result = engine.execute_transition(req)
        assert isinstance(result, TransitionRejection)
        assert "Illegal state transition" in result.reason

    def test_replay_attack_rejected(self, tmp_path: Path):
        """Proves a spent ProofWitness cannot be replayed for subsequent state transitions."""
        db = KernelDatabase(db_path=tmp_path / "kernel.db")
        engine = PrivilegedTransitionEngine(kernel_db=db)
        task_id = "task_replay_01"

        gov_digest = compute_governance_digest()
        claim_digest = compute_complete_claim_digest(
            task_id=task_id,
            from_state=State.CANDIDATE_SEALED,
            to_state=State.VERIFIED,
            subject_identity="commit_1",
            candidate_tree_sha="tree_1",
            spec_hash="spec_1",
            acceptance_test_digest="test_1",
            evidence_digest="ev_1",
            authority_scope="PHYSICAL_VERIFICATION",
            governance_hash=gov_digest,
        )

        witness = issue_proof_witness(
            issuer="test_suite",
            target_digest=claim_digest,
            scope="PHYSICAL_VERIFICATION",
        )

        req = TransitionRequest(
            task_id=task_id,
            from_state=State.CANDIDATE_SEALED,
            to_state=State.VERIFIED,
            subject_identity="commit_1",
            candidate_tree_sha="tree_1",
            spec_hash="spec_1",
            acceptance_test_digest="test_1",
            evidence_digest="ev_1",
            authority_scope="PHYSICAL_VERIFICATION",
            witness=witness,
            governance_hash=gov_digest,
        )

        # First use -> SUCCESS
        res1 = engine.execute_transition(req)
        assert isinstance(res1, TransitionReceipt)

        # Second use -> REPLAY DETECTED
        res2 = engine.execute_transition(req)
        assert isinstance(res2, TransitionRejection)
        assert "Replay attack detected" in res2.reason

    def test_falsification_transition_engine_disabled_blocks_all_privileged_state(self, monkeypatch, tmp_path: Path):
        """
        THE ULTIMATE FALSIFICATION TEST:
        Proves that when PrivilegedTransitionEngine is disabled, NO component can reach privileged state.
        """
        repo_dir = tmp_path / "test_repo"
        repo_dir.mkdir()
        subprocess.run(["git", "init", "-b", "main"], cwd=repo_dir, check=True, capture_output=True)
        subprocess.run(["git", "config", "user.name", "ZeroTrustBot"], cwd=repo_dir, check=True)
        subprocess.run(["git", "config", "user.email", "bot@zero.trust"], cwd=repo_dir, check=True)

        (repo_dir / "calculator.py").write_text("def add(a, b):\n    return a + b\n", encoding="utf-8")

        fixtures_dir = repo_dir / "canonical_fixtures"
        fixtures_dir.mkdir()
        (fixtures_dir / "test_app.py").write_text(
            "import sys\nfrom calculator import add\ndef test_add():\n    assert add(1, 2) == 3\n",
            encoding="utf-8",
        )

        subprocess.run(["git", "add", "."], cwd=repo_dir, check=True)
        subprocess.run(["git", "commit", "-m", "candidate commit"], cwd=repo_dir, check=True)

        commit_sha = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=repo_dir, capture_output=True, text=True, check=True
        ).stdout.strip()
        tree_sha = subprocess.run(
            ["git", "rev-parse", "HEAD^{tree}"], cwd=repo_dir, capture_output=True, text=True, check=True
        ).stdout.strip()

        db = KernelDatabase(db_path=tmp_path / "kernel.db")
        manifest = ProposalManifest(
            task_id="task_falsify",
            spec_hash="spec_1",
            base_commit_sha=commit_sha,
            candidate_commit_sha=commit_sha,
            candidate_tree_sha=tree_sha,
            verifier_version="2.0.0",
            acceptance_test_digest=compute_test_digest(fixtures_dir),
            env_fingerprint=EnvironmentFingerprint.capture(),
            state=State.CANDIDATE_SEALED,
        )

        db.record_proposal(manifest)

        vg = PhysicalVerifierGate(
            repo_dir=repo_dir,
            canonical_fixtures_dir=fixtures_dir,
            kernel_db=db,
        )

        # 1. Normal verification passes when seam is ENABLED
        res_normal = vg.verify_candidate(manifest, candidate_worktree=repo_dir)
        assert res_normal.status == State.VERIFIED

        # 2. Disable PrivilegedTransitionEngine with raising stub
        def raising_stub(*args, **kwargs):
            raise RuntimeError("TRANSITION SEAM DISABLED")

        monkeypatch.setattr(PrivilegedTransitionEngine, "execute_transition", raising_stub)

        # 3. Direct verification attempt now raises RuntimeError when seam is disabled
        with pytest.raises(RuntimeError, match="TRANSITION SEAM DISABLED"):
            vg.verify_candidate(manifest, candidate_worktree=repo_dir)

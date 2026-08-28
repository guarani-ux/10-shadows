"""
tests/test_transition_engine.py
Adversarial TDD Suite for Privileged Transition Engine (Reverse Jenga Floor-Raising Seam).
Verifies that all privileged state transitions must pass through cryptographic witness validation,
anti-replay guards, and legal state machine invariants.
"""

import hashlib
import pytest
from loop_engine.authority import issue_proof_witness
from loop_engine.kernel_db import KernelDatabase
from loop_engine.schema import State
from loop_engine.transition import (
    PrivilegedTransitionEngine,
    TransitionReceipt,
    TransitionRejection,
    TransitionRequest,
    compute_complete_claim_digest,
    compute_governance_digest,
)


class TestPrivilegedTransitionEngine:
    @pytest.fixture
    def engine(self, tmp_path):
        db_path = tmp_path / "test_kernel.db"
        db = KernelDatabase(db_path=db_path)
        return PrivilegedTransitionEngine(kernel_db=db)

    def test_valid_transition_request_succeeds(self, engine):
        task_id = "task_valid_001"
        subject_identity = "cand_commit_sha_12345"
        candidate_tree_sha = "tree_sha_12345"
        spec_hash = "spec_hash_1"
        acceptance_test_digest = "test_digest_1"
        evidence_digest = "test_run_digest_67890"
        authority_scope = "PHYSICAL_VERIFICATION"
        gov_digest = compute_governance_digest()

        target_digest = compute_complete_claim_digest(
            task_id=task_id,
            from_state=State.CANDIDATE_SEALED,
            to_state=State.VERIFIED,
            subject_identity=subject_identity,
            candidate_tree_sha=candidate_tree_sha,
            spec_hash=spec_hash,
            acceptance_test_digest=acceptance_test_digest,
            evidence_digest=evidence_digest,
            authority_scope=authority_scope,
            governance_hash=gov_digest,
        )

        witness = issue_proof_witness(
            issuer="loop_engine.verifier_gate",
            target_digest=target_digest,
            scope=authority_scope,
        )

        request = TransitionRequest(
            task_id=task_id,
            from_state=State.CANDIDATE_SEALED,
            to_state=State.VERIFIED,
            subject_identity=subject_identity,
            candidate_tree_sha=candidate_tree_sha,
            spec_hash=spec_hash,
            acceptance_test_digest=acceptance_test_digest,
            evidence_digest=evidence_digest,
            authority_scope=authority_scope,
            witness=witness,
            governance_hash=gov_digest,
        )

        result = engine.execute_transition(request)
        assert isinstance(result, TransitionReceipt)
        assert result.to_state == State.VERIFIED
        assert result.witness_id == witness.witness_id

    def test_forged_witness_rejected(self, engine):
        from loop_engine.authority import ProofWitness
        forged_witness = ProofWitness(
            witness_id="wit_forged",
            issuer="attacker",
            target_digest="fake_digest",
            scope="PHYSICAL_VERIFICATION",
            timestamp=100.0,
            signature="forged_sig",
        )

        gov_digest = compute_governance_digest()
        request = TransitionRequest(
            task_id="task_hack",
            from_state=State.CANDIDATE_SEALED,
            to_state=State.VERIFIED,
            subject_identity="cand_sha",
            candidate_tree_sha="tree_sha",
            spec_hash="spec_hash",
            acceptance_test_digest="test_digest",
            evidence_digest="evidence_digest",
            authority_scope="PHYSICAL_VERIFICATION",
            witness=forged_witness,
            governance_hash=gov_digest,
        )

        result = engine.execute_transition(request)
        assert isinstance(result, TransitionRejection)
        assert "ProofWitness cryptographic verification failed" in result.reason

    def test_replay_attack_rejected(self, engine):
        task_id = "task_replay_001"
        subject_identity = "cand_sha_replay"
        candidate_tree_sha = "tree_sha_replay"
        spec_hash = "spec_hash_replay"
        acceptance_test_digest = "test_digest_replay"
        evidence_digest = "evidence_digest_replay"
        authority_scope = "PHYSICAL_VERIFICATION"
        gov_digest = compute_governance_digest()

        target_digest = compute_complete_claim_digest(
            task_id=task_id,
            from_state=State.CANDIDATE_SEALED,
            to_state=State.VERIFIED,
            subject_identity=subject_identity,
            candidate_tree_sha=candidate_tree_sha,
            spec_hash=spec_hash,
            acceptance_test_digest=acceptance_test_digest,
            evidence_digest=evidence_digest,
            authority_scope=authority_scope,
            governance_hash=gov_digest,
        )

        witness = issue_proof_witness(
            issuer="loop_engine.verifier_gate",
            target_digest=target_digest,
            scope=authority_scope,
        )

        request = TransitionRequest(
            task_id=task_id,
            from_state=State.CANDIDATE_SEALED,
            to_state=State.VERIFIED,
            subject_identity=subject_identity,
            candidate_tree_sha=candidate_tree_sha,
            spec_hash=spec_hash,
            acceptance_test_digest=acceptance_test_digest,
            evidence_digest=evidence_digest,
            authority_scope=authority_scope,
            witness=witness,
            governance_hash=gov_digest,
        )

        # First transition succeeds
        res1 = engine.execute_transition(request)
        assert isinstance(res1, TransitionReceipt)

        # Attempting to replay the exact same witness fails
        res2 = engine.execute_transition(request)
        assert isinstance(res2, TransitionRejection)
        assert "Replay attack detected" in res2.reason

    def test_illegal_state_transition_rejected(self, engine):
        # Directly trying to jump from CANDIDATE_SEALED to POST_PROMOTION_VERIFIED
        witness = issue_proof_witness(
            issuer="attacker",
            target_digest="any_digest",
            scope="PROMOTION",
        )

        gov_digest = compute_governance_digest()
        request = TransitionRequest(
            task_id="task_jump",
            from_state=State.CANDIDATE_SEALED,
            to_state=State.POST_PROMOTION_VERIFIED,
            subject_identity="cand_sha",
            candidate_tree_sha="tree_sha",
            spec_hash="spec_hash",
            acceptance_test_digest="test_digest",
            evidence_digest="evidence_digest",
            authority_scope="PROMOTION",
            witness=witness,
            governance_hash=gov_digest,
        )

        result = engine.execute_transition(request)
        assert isinstance(result, TransitionRejection)
        assert "Illegal state transition" in result.reason

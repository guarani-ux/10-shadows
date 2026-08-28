"""
tests/test_reverse_jenga_mutations.py
Reverse Jenga Mutation Testing Suite for 10 SHADOWS.
Deliberately tests that mutating or bypassing governing invariants results in immediate test failure.
"""

import hashlib
import pytest
from loop_engine.authority import ProofWitness, issue_proof_witness
from loop_engine.disposition import ActionDisposition, evaluate_execution_disposition
from loop_engine.kernel_db import KernelDatabase
from loop_engine.schema import State
from loop_engine.transition import (
    PrivilegedTransitionEngine,
    TransitionReceipt,
    TransitionRejection,
    TransitionRequest,
)


class TestReverseJengaMutations:
    @pytest.fixture
    def setup_kernel(self, tmp_path):
        db = KernelDatabase(db_path=tmp_path / "kernel.db")
        engine = PrivilegedTransitionEngine(kernel_db=db)
        return db, engine

    def test_mutant_tampered_claim_digest_turns_red(self, setup_kernel):
        db, engine = setup_kernel
        task_id = "task_mutant_01"
        subject_id = "cand_sha_original"
        evidence_digest = "evidence_digest_original"
        authority_scope = "PHYSICAL_VERIFICATION"

        combined_claim = f"{subject_id}:{evidence_digest}"
        target_digest = hashlib.sha256(combined_claim.encode("utf-8")).hexdigest()

        witness = issue_proof_witness(
            issuer="loop_engine.verifier_gate",
            target_digest=target_digest,
            scope=authority_scope,
        )

        # Mutant: Attacker alters subject_id in request while reusing original witness
        tampered_request = TransitionRequest(
            task_id=task_id,
            from_state=State.CANDIDATE_SEALED,
            to_state=State.VERIFYING,
            subject_identity="cand_sha_TAMPERED",
            evidence_digest=evidence_digest,
            authority_scope=authority_scope,
            witness=witness,
        )

        result = engine.execute_transition(tampered_request)
        assert isinstance(result, TransitionRejection)
        assert "ProofWitness cryptographic verification failed" in result.reason

    def test_mutant_spent_witness_replay_turns_red(self, setup_kernel):
        db, engine = setup_kernel
        task_id = "task_mutant_02"
        subject_id = "cand_sha_replay"
        evidence_digest = "evidence_digest_replay"
        authority_scope = "PHYSICAL_VERIFICATION"

        combined_claim = f"{subject_id}:{evidence_digest}"
        target_digest = hashlib.sha256(combined_claim.encode("utf-8")).hexdigest()

        witness = issue_proof_witness(
            issuer="loop_engine.verifier_gate",
            target_digest=target_digest,
            scope=authority_scope,
        )

        request = TransitionRequest(
            task_id=task_id,
            from_state=State.CANDIDATE_SEALED,
            to_state=State.VERIFYING,
            subject_identity=subject_id,
            evidence_digest=evidence_digest,
            authority_scope=authority_scope,
            witness=witness,
        )

        # First execution passes
        res1 = engine.execute_transition(request)
        assert isinstance(res1, TransitionReceipt)

        # Second execution (mutant replay) must turn red
        res2 = engine.execute_transition(request)
        assert isinstance(res2, TransitionRejection)
        assert "Replay attack detected" in res2.reason

    def test_mutant_unearned_build_turns_red(self):
        # Caller passing booleans without VerificationContractWitness
        spec = {
            "task_id": "mutant_build",
            "intent": "Build without proof",
            "intent_type": "code_generation",
            "has_verification_contract": True,
            "has_grounded_requirements": True,
        }
        res = evaluate_execution_disposition(spec, verification_contract=None)
        assert res.disposition == ActionDisposition.EXPOSE_DEFICIT
        assert res.is_build_earned is False

    def test_mutant_illegal_state_jump_turns_red(self, setup_kernel):
        db, engine = setup_kernel
        witness = issue_proof_witness(
            issuer="attacker",
            target_digest="any",
            scope="PROMOTION",
        )
        request = TransitionRequest(
            task_id="task_mutant_jump",
            from_state=State.VERIFYING,
            to_state=State.PROMOTED,  # Illegal jump: must go through VERIFIED -> PROMOTION_PENDING
            subject_identity="cand_sha",
            evidence_digest="ev_digest",
            authority_scope="PROMOTION",
            witness=witness,
        )
        result = engine.execute_transition(request)
        assert isinstance(result, TransitionRejection)
        assert "Illegal state transition" in result.reason

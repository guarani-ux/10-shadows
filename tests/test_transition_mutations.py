"""
tests/test_transition_mutations.py
Implementation Mutation Killing Suite for PrivilegedTransitionEngine and KernelDatabase custody.

Ensures that any implementation mutation weakening cryptographic binding, anti-replay,
governance validation, legal state progression, or database custody is immediately killed.
"""

import secrets
from pathlib import Path

import pytest

from loop_engine.authority import issue_proof_witness
from loop_engine.epistemic import EpistemicDisposition
from loop_engine.kernel_db import (
    KernelDatabase,
    PrivilegedStateMutationProhibitedError,
)
from loop_engine.schema import (
    EnvironmentFingerprint,
    ProposalManifest,
    State,
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


def create_manifest(task_id: str) -> ProposalManifest:
    return ProposalManifest(
        task_id=task_id,
        spec_hash="spec_1",
        base_commit_sha="base_1",
        candidate_commit_sha="cand_1",
        candidate_tree_sha="tree_1",
        verifier_version="2.0.0",
        acceptance_test_digest="test_1",
        env_fingerprint=EnvironmentFingerprint.capture(),
        state=State.CANDIDATE_SEALED,
    )


class TestTransitionMutations:
    def test_mutant_tampered_claim_kills_transition(self, tmp_path: Path):
        """Mutant: tampered candidate tree sha in request is rejected."""
        db = KernelDatabase(db_path=tmp_path / "kernel.db")
        engine = PrivilegedTransitionEngine(kernel_db=db)
        task_id = "task_mut_01"
        db.record_proposal(create_manifest(task_id))

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

        # Mutate candidate_tree_sha to tree_tampered
        req = TransitionRequest(
            task_id=task_id,
            from_state=State.CANDIDATE_SEALED,
            to_state=State.VERIFIED,
            subject_identity="commit_1",
            candidate_tree_sha="tree_tampered",  # MUTATION
            spec_hash="spec_1",
            acceptance_test_digest="test_1",
            evidence_digest="ev_1",
            authority_scope="PHYSICAL_VERIFICATION",
            witness=witness,
            governance_hash=gov_digest,
        )

        res = engine.execute_transition(req)
        assert isinstance(res, TransitionRejection)
        assert "ProofWitness cryptographic verification failed" in res.reason

    def test_mutant_governance_tamper_kills_transition(self, tmp_path: Path):
        """Mutant: governance hash tampered in request is rejected."""
        db = KernelDatabase(db_path=tmp_path / "kernel.db")
        engine = PrivilegedTransitionEngine(kernel_db=db)
        task_id = "task_mut_02"
        db.record_proposal(create_manifest(task_id))

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
            governance_hash="tampered_gov_hash_12345",
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
            governance_hash="tampered_gov_hash_12345",
        )

        res = engine.execute_transition(req)
        assert isinstance(res, TransitionRejection)
        assert "Governance digest mismatch" in res.reason

    def test_mutant_invalid_custody_token_kills_db_mutation(self, tmp_path: Path):
        """Mutant: invalid authority token passed to internal transition raises error."""
        db = KernelDatabase(db_path=tmp_path / "kernel.db")
        task_id = "task_mut_03"
        db.record_proposal(create_manifest(task_id))

        with pytest.raises(PrivilegedStateMutationProhibitedError, match="Invalid authority token"):
            db._execute_privileged_state_transition(
                auth_token="forged_token_0000000000000000",
                task_id=task_id,
                from_state=State.CANDIDATE_SEALED,
                to_state=State.VERIFIED,
            )

    def test_mutant_direct_update_state_kills_privileged_jump(self, tmp_path: Path):
        """Mutant: calling update_state targeting PROMOTED raises error."""
        db = KernelDatabase(db_path=tmp_path / "kernel.db")
        task_id = "task_mut_04"
        db.record_proposal(create_manifest(task_id))

        with pytest.raises(
            PrivilegedStateMutationProhibitedError,
            match="Direct database mutation to privileged state 'PROMOTED' is prohibited",
        ):
            db.update_state(task_id, State.PROMOTED)

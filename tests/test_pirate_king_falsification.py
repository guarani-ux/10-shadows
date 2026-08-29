"""
tests/test_pirate_king_falsification.py
Adversarial Falsification Suite for Pirate King Self-Transcendence Pass.
Attacks every privileged state minting vector, receipt replay vector, and epistemic bypass.
"""

import pytest

from loop_engine.authority import (
    InvalidWitnessError,
    PrivilegedMintingError,
    ProofWitness,
    create_verification_contract_witness,
    issue_proof_witness,
)
from loop_engine.epistemic import (
    EpistemicDisposition,
    EpistemicStatus,
    EvidenceOrigin,
    SemanticLaunderingError,
    canonical_json_digest,
    create_envelope,
    create_unverified_envelope,
    mint_verified_envelope,
    transform_envelope,
)


class TestPrivilegedMintingAttacks:
    def test_caller_cannot_assert_verified_status(self):
        with pytest.raises(PrivilegedMintingError, match="Privileged status 'VERIFIED' cannot be created"):
            create_unverified_envelope(
                payload={"data": "fake proof"},
                origin=EvidenceOrigin.MODEL_INFERENCE,
                status=EpistemicStatus.VERIFIED,
                source_id="attacker",
            )

    def test_caller_cannot_assert_physical_observation(self):
        with pytest.raises(PrivilegedMintingError, match="Privileged origin 'PHYSICAL_OBSERVATION' cannot be asserted"):
            create_envelope(
                payload={"data": "fake observation"},
                origin=EvidenceOrigin.PHYSICAL_OBSERVATION,
                status=EpistemicStatus.HYPOTHESIS,
                source_id="attacker",
            )

    def test_mint_verified_with_forged_witness_fails(self):
        payload = {"data": "candidate payload"}
        forged_witness = ProofWitness(
            witness_id="wit_fake",
            issuer="attacker",
            target_digest=canonical_json_digest(payload),
            scope="EVIDENCE_VERIFICATION",
            timestamp=12345.0,
            signature="forged_signature_hex",
        )

        with pytest.raises(InvalidWitnessError, match="ProofWitness cryptographic verification failed"):
            mint_verified_envelope(
                payload=payload,
                origin=EvidenceOrigin.PHYSICAL_OBSERVATION,
                source_id="verifier_step",
                witness=forged_witness,
            )

    def test_mint_verified_with_valid_witness_succeeds(self):
        payload = {"verified_metric": 42}
        payload_digest = canonical_json_digest(payload)
        witness = issue_proof_witness(
            issuer="loop_engine.verifier_gate",
            target_digest=payload_digest,
            scope="EVIDENCE_VERIFICATION",
        )

        env = mint_verified_envelope(
            payload=payload,
            origin=EvidenceOrigin.PHYSICAL_OBSERVATION,
            source_id="verifier_gate",
            witness=witness,
        )
        assert env.status == EpistemicStatus.VERIFIED
        assert env.origin == EvidenceOrigin.PHYSICAL_OBSERVATION
        assert env.disposition == EpistemicDisposition.SATISFIED


class TestEpistemicDAGAndLatticeAttacks:
    def test_multi_parent_dag_lineage_tracking(self):
        env_a = create_unverified_envelope(
            payload={"doc_a": 1},
            origin=EvidenceOrigin.DECLARED_SPEC,
            status=EpistemicStatus.HYPOTHESIS,
            source_id="source_a",
        )
        env_b = create_unverified_envelope(
            payload={"doc_b": 2},
            origin=EvidenceOrigin.MODEL_INFERENCE,
            status=EpistemicStatus.INFERRED,
            source_id="source_b",
        )

        child = transform_envelope(
            parent_envelope=[env_a, env_b],
            new_payload={"merged": 3},
            new_source_id="combiner",
        )

        assert env_a.envelope_hash in child.parent_hashes
        assert env_b.envelope_hash in child.parent_hashes
        assert len(child.parent_hashes) == 2

    def test_contradicted_parent_poisons_downstream_child(self):
        env_good = create_unverified_envelope(
            payload={"fact": "good"},
            origin=EvidenceOrigin.DECLARED_SPEC,
            status=EpistemicStatus.INFERRED,
            source_id="source_good",
        )
        env_bad = create_unverified_envelope(
            payload={"fact": "falsified"},
            origin=EvidenceOrigin.MODEL_INFERENCE,
            status=EpistemicStatus.CONTRADICTED,
            source_id="falsified_source",
        )

        child = transform_envelope(
            parent_envelope=[env_good, env_bad],
            new_payload={"result": "derived"},
            new_source_id="downstream_combiner",
            new_disposition=EpistemicDisposition.SATISFIED,
        )

        # Lattice forces CONTRADICTED status and UNRESOLVED disposition
        assert child.status == EpistemicStatus.CONTRADICTED
        assert child.disposition == EpistemicDisposition.UNRESOLVED

    def test_confidence_cannot_be_inflated_without_witness(self):
        env_low_conf = create_unverified_envelope(
            payload={"data": 1},
            origin=EvidenceOrigin.MODEL_INFERENCE,
            status=EpistemicStatus.INFERRED,
            source_id="low_conf_source",
            confidence=0.4,
        )

        child = transform_envelope(
            parent_envelope=env_low_conf,
            new_payload={"data": 1},
            new_source_id="inflator",
            new_confidence=0.99,  # Attempting to artificially inflate confidence
        )

        assert child.confidence == 0.4  # Bounded to parent confidence

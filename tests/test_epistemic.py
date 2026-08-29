"""
tests/test_epistemic.py
Adversarial TDD Acceptance Suite for Epistemic Dispositions and Evidence Envelope.
Enforces Pirate King Constraints:
1. No False Victory
4. No Silent Assumption Promotion
5. No Semantic Laundering
6. No Unverifiable Success Disguised as Verified Success
9. No Synthetic Evidence Masquerading as Reality
11. No Unknown-Domain Bluffing
29. No Degradation into Plausible BS
30. No Inability to Know Its Own Boundary
"""

import pytest

from loop_engine.authority import (
    ProofWitness,
    issue_proof_witness,
)
from loop_engine.epistemic import (
    EpistemicDisposition,
    EpistemicStatus,
    EvidenceEnvelope,
    EvidenceOrigin,
    SemanticLaunderingError,
    canonical_json_digest,
    create_unverified_envelope,
    mint_verified_envelope,
    transform_envelope,
)


class TestEvidenceOriginAndStatus:
    def test_evidence_origin_types(self):
        assert EvidenceOrigin.PHYSICAL_OBSERVATION.value == "PHYSICAL_OBSERVATION"
        assert EvidenceOrigin.SYNTHETIC_FIXTURE.value == "SYNTHETIC_FIXTURE"
        assert EvidenceOrigin.MODEL_INFERENCE.value == "MODEL_INFERENCE"
        assert EvidenceOrigin.DERIVED_TRANSFORM.value == "DERIVED_TRANSFORM"
        assert EvidenceOrigin.DECLARED_SPEC.value == "DECLARED_SPEC"

    def test_epistemic_status_hierarchy(self):
        assert EpistemicStatus.VERIFIED.value == "VERIFIED"
        assert EpistemicStatus.INFERRED.value == "INFERRED"
        assert EpistemicStatus.HYPOTHESIS.value == "HYPOTHESIS"
        assert EpistemicStatus.UNKNOWN.value == "UNKNOWN"
        assert EpistemicStatus.CONTRADICTED.value == "CONTRADICTED"


class TestEvidenceEnvelopeImmutabilityAndLineage:
    def test_create_envelope_deterministic_hash(self):
        env1 = create_unverified_envelope(
            payload={"key": "value", "count": 10},
            origin=EvidenceOrigin.DECLARED_SPEC,
            status=EpistemicStatus.INFERRED,
            source_id="obs_001",
        )
        env2 = create_unverified_envelope(
            payload={"key": "value", "count": 10},
            origin=EvidenceOrigin.DECLARED_SPEC,
            status=EpistemicStatus.INFERRED,
            source_id="obs_001",
        )
        assert env1.envelope_hash == env2.envelope_hash
        assert len(env1.envelope_hash) == 64

    def test_envelope_is_immutable(self):
        env = create_unverified_envelope(
            payload={"data": [1, 2, 3]},
            origin=EvidenceOrigin.MODEL_INFERENCE,
            status=EpistemicStatus.INFERRED,
            source_id="agent_step",
        )
        with pytest.raises(Exception):
            env.status = EpistemicStatus.VERIFIED  # Frozen dataclass mutation blocked

    def test_transform_envelope_preserves_lineage(self):
        parent = create_unverified_envelope(
            payload={"raw_text": "sample source text"},
            origin=EvidenceOrigin.DECLARED_SPEC,
            status=EpistemicStatus.INFERRED,
            source_id="raw_doc",
        )

        child = transform_envelope(
            parent_envelope=parent,
            new_payload={"token_count": 3},
            new_source_id="tokenizer_step",
        )

        assert child.parent_hash == parent.envelope_hash
        assert parent.envelope_hash in child.parent_hashes
        assert child.origin == EvidenceOrigin.DERIVED_TRANSFORM
        assert child.status == EpistemicStatus.INFERRED


class TestSemanticLaunderingRejection:
    def test_infer_to_verified_without_verifier_raises_laundering_error(self):
        parent = create_unverified_envelope(
            payload={"claim": "System is ultra fast"},
            origin=EvidenceOrigin.MODEL_INFERENCE,
            status=EpistemicStatus.HYPOTHESIS,
            source_id="model_prompt",
        )

        with pytest.raises(SemanticLaunderingError, match="Semantic laundering detected"):
            transform_envelope(
                parent_envelope=parent,
                new_payload={"claim": "System is ultra fast"},
                new_status=EpistemicStatus.VERIFIED,
                new_source_id="unauthorized_step",
            )

    def test_synthetic_origin_cannot_upgrade_to_physical_observation(self):
        parent = create_unverified_envelope(
            payload={"mock_data": True},
            origin=EvidenceOrigin.SYNTHETIC_FIXTURE,
            status=EpistemicStatus.INFERRED,
            source_id="mock_fixture",
        )

        with pytest.raises(
            SemanticLaunderingError, match="Synthetic evidence cannot masquerade as physical observation"
        ):
            transform_envelope(
                parent_envelope=parent,
                new_payload={"mock_data": True},
                new_origin=EvidenceOrigin.PHYSICAL_OBSERVATION,
                new_source_id="fake_promotion",
            )


class TestEpistemicDispositions:
    def test_all_deficit_dispositions_exist(self):
        deficits = [
            EpistemicDisposition.SATISFIED,
            EpistemicDisposition.CONDITIONALLY_SUPPORTED,
            EpistemicDisposition.SEMANTIC_BINDING_DEFICIT,
            EpistemicDisposition.INSUFFICIENT_EVIDENCE,
            EpistemicDisposition.CAPABILITY_DEFICIT,
            EpistemicDisposition.EXTERNAL_AUTHORITY_REQUIRED,
            EpistemicDisposition.UNRESOLVED,
        ]
        assert len(deficits) == 7

    def test_deficit_envelope_serializability(self):
        env = create_unverified_envelope(
            payload={"missing_domain": "quantum_encryption"},
            origin=EvidenceOrigin.DECLARED_SPEC,
            status=EpistemicStatus.UNKNOWN,
            source_id="spec_evaluator",
            disposition=EpistemicDisposition.CAPABILITY_DEFICIT,
        )
        d = env.to_dict()
        assert d["disposition"] == "CAPABILITY_DEFICIT"
        assert d["status"] == "UNKNOWN"
        assert d["envelope_hash"] == env.envelope_hash

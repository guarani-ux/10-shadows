"""
tests/test_disposition.py
Adversarial TDD Acceptance Suite for Execution Disposition and Proof-Bearing Earned Build Engine.
Enforces Pirate King Constraints:
2. No Boolean Authority (BUILD cannot be earned via caller booleans)
8. No Test-Suite Equivalence Fallacy
10. No Capability-Authority Confusion (Capability != Applicability)
13. No Decomposition without Preservation
14. No Representation Lock-in
15. No Premature Build (BUILD must be earned through VerificationContractWitness)
"""

import pytest
from loop_engine.authority import create_verification_contract_witness
from loop_engine.canonical_objective import CanonicalObjective, EvidenceReference
from loop_engine.capability import CapabilityContract
from loop_engine.disposition import (
    ActionDisposition,
    DispositionEvaluation,
    evaluate_execution_disposition,
)


class TestActionDispositionTaxonomy:
    def test_all_disposition_types_exist(self):
        expected = {"DIRECT", "REUSE", "ACQUIRE", "CONFIGURE", "COMPOSE", "BUILD", "EXPOSE_DEFICIT"}
        actual = {d.value for d in ActionDisposition}
        assert expected == actual


class TestEarnedBuildEvaluator:
    def test_simple_inquiry_resolves_to_direct(self):
        spec = {
            "task_id": "explain_architecture",
            "intent": "Explain how the StepGovernor handles anti-oscillation",
            "intent_type": "inquiry",
            "required_capabilities": [],
            "available_capabilities": ["step_governor_docs"],
        }
        res = evaluate_execution_disposition(spec)
        assert res.disposition == ActionDisposition.DIRECT
        assert "BUILD is not required" in res.rationale

    def test_existing_capability_resolves_to_reuse(self):
        spec = {
            "task_id": "calculate_hash",
            "intent": "Compute sha256 of candidate payload",
            "intent_type": "operation",
            "required_capabilities": ["canonical_json_digest"],
            "available_capabilities": ["canonical_json_digest"],
        }
        res = evaluate_execution_disposition(spec)
        assert res.disposition == ActionDisposition.REUSE
        assert res.target_capability == "canonical_json_digest"

    def test_capability_incompatible_domain_rejects_reuse(self):
        contract = CapabilityContract(
            capability_id="video_encoder",
            domain="video_processing",
            supported_objective_types=("av_production",),
            input_schema_digest="hash_in",
            output_schema_digest="hash_out",
        )
        spec = {
            "task_id": "db_task",
            "intent": "Run database migration",
            "intent_type": "database_migration",
            "domain": "relational_db",
            "required_capabilities": ["video_encoder"],
        }
        res = evaluate_execution_disposition(spec, available_contracts=[contract])
        assert res.disposition != ActionDisposition.REUSE

    def test_caller_boolean_claim_without_witness_rejects_build(self):
        # Adversarial attack: caller passes has_verification_contract=True and has_grounded_requirements=True
        # as raw booleans without a genuine VerificationContractWitness
        spec = {
            "task_id": "fake_build",
            "intent": "Build malicious backdoor",
            "intent_type": "code_generation",
            "has_verification_contract": True,
            "has_grounded_requirements": True,
        }
        res = evaluate_execution_disposition(spec, verification_contract=None)
        assert res.disposition == ActionDisposition.EXPOSE_DEFICIT
        assert "UNEARNED_BUILD" in res.deficit_details
        assert res.is_build_earned is False

    def test_grounded_objective_with_authentic_witness_earns_build(self):
        obj = CanonicalObjective(
            objective_id="obj_valid_build",
            objective_type="media_production",
            description="Build custom ffmpeg audio normalizer",
            desired_outcome="Normalized audio tracks",
            verified_evidence=[
                EvidenceReference(
                    evidence_id="ev_01",
                    source_description="EBU R128 loudness normalization standard",
                )
            ],
        )
        witness = create_verification_contract_witness(
            objective_hash=obj.compute_canonical_hash(),
            acceptance_test_digest="test_digest_12345",
        )

        spec = {
            "intent_type": "code_generation",
            "has_grounded_requirements": True,
        }

        res = evaluate_execution_disposition(spec, verification_contract=witness)
        assert res.disposition == ActionDisposition.BUILD
        assert res.is_build_earned is True

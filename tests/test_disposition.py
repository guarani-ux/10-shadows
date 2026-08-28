"""
tests/test_disposition.py
Adversarial TDD Acceptance Suite for Execution Disposition and Earned Build Engine.
Enforces Pirate King Constraints:
8. No Test-Suite Equivalence Fallacy
10. No Capability-Authority Confusion
13. No Decomposition without Preservation
14. No Representation Lock-in
15. No Premature Build (BUILD must be earned)
"""

import pytest
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

    def test_missing_unregistered_domain_resolves_to_expose_deficit(self):
        spec = {
            "task_id": "quantum_simulate",
            "intent": "Run quantum circuit simulation on qubits",
            "intent_type": "compute",
            "required_capabilities": ["quantum_simulator_engine"],
            "available_capabilities": ["kernel_db", "verifier_gate"],
        }
        res = evaluate_execution_disposition(spec)
        assert res.disposition == ActionDisposition.EXPOSE_DEFICIT
        assert res.deficit_details is not None
        assert "quantum_simulator_engine" in res.deficit_details

    def test_grounded_unimplemented_requirement_earns_build(self):
        spec = {
            "task_id": "build_new_parser",
            "intent": "Implement custom protobuf wire serializer",
            "intent_type": "code_generation",
            "required_capabilities": ["protobuf_serializer"],
            "available_capabilities": ["python_ast", "pytest_harness"],
            "has_verification_contract": True,
            "has_grounded_requirements": True,
        }
        res = evaluate_execution_disposition(spec)
        assert res.disposition == ActionDisposition.BUILD
        assert res.is_build_earned is True

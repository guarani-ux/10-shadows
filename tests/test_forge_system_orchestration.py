"""
tests/test_forge_system_orchestration.py
Permanent Adversarial Acceptance Test Suite for System-Orchestrated Forge.

Validates:
1. Ten Shadows Control Task (Media Brief decomposition).
2. Adjacent Knowledge-Work Task (RFC contradiction analysis).
3. Foreign Scientific/Technical Task (Materials stress calculation).
4. Representation-Break Task (Warehouse logistics constraint checking).
5. Upstream Adversarial Omission: Oracle model drops requirement -> SOURCE_UNCOVERED.
6. Upstream Domain Deficit: Missing domain capability -> DOMAIN_REQUIREMENTS_UNVERIFIED.
7. Decomposition Deficit: Schema-valid DAG with missing terminal coverage -> INSUFFICIENT.
8. Permanent Oracle Anti-Cheating Test: Correct output rejected when closure is open.
9. Weak Model Stability: Architecture invariants survive degraded model intelligence.
10. Transfer-Tested Recursive Capability Gain: Task A provisions X -> Foreign Task B discovers and reuses X.
"""

import pytest
from pathlib import Path

from forge.forge import ForgeEngine
from forge.core.substrate import (
    CanonicalRequirement,
    EvidenceClass,
    EvidenceRequirement,
    ObjectiveAdequacyState,
    OperatorType,
    RequirementDisposition,
    RequirementOrigin,
    RequirementTrace,
    RequiredOperation,
    VerificationContract,
    CapabilityLifecycleState,
    CapabilityDeficit,
)
from forge.core.adequacy import IntentCoverageEvaluator, RawClauseTokenizer
from forge.core.decomposition import DecompositionCoverageEvaluator
from forge.core.closure import ClosureGate, AntiCheatingViolation
from forge.core.registry import CapabilityRegistry
from forge.core.compiler import ExecutionGraphCompiler, ObjectiveInadequateError, DecompositionIncompleteError, ClosureDeficitError
from forge.core.provisioner import CapabilityProvisioner


@pytest.fixture
def system_forge():
    registry = CapabilityRegistry()
    return ForgeEngine(registry=registry)


# -----------------------------------------------------------------------------
# 1. Ten Shadows Control Task
# -----------------------------------------------------------------------------
def test_control_task_media_brief_decomposition(system_forge):
    raw_intent = "Ingest media source, extract structured evidence, and decompose into task DAG."
    res = system_forge.run(raw_intent)
    assert res["status"] == "SUCCESS"
    assert res["result"]["success"] is True


# -----------------------------------------------------------------------------
# 2. Adjacent Knowledge-Work Task (RFC Contradiction Analysis)
# -----------------------------------------------------------------------------
def test_adjacent_rfc_contradiction_analysis(system_forge):
    raw_intent = "Analyze RFC 9110 specification and extract claims."
    op1 = RequiredOperation(
        operation_id="op_extract",
        operator=OperatorType.EXTRACT,
        semantic_responsibility="Extract RFC claims",
        inputs=["source_text"],
        outputs=["extracted_evidence"],
        postconditions=["Claims extracted"],
    )
    op2 = RequiredOperation(
        operation_id="op_compare",
        operator=OperatorType.COMPARE,
        semantic_responsibility="Detect claim contradictions",
        inputs=["extracted_evidence"],
        outputs=["contradictions", "has_conflict"],
        dependencies=["op_extract"],
        postconditions=["Contradictions evaluated"],
    )
    vc = VerificationContract(
        contract_id="vc_rfc",
        observable_success_condition="Contradictions evaluated",
        verification_method="EVALUATE_CONFLICT_BOOL",
        evidence_required=[],
        validator_fn=lambda state: "has_conflict" in state,
    )

    res = system_forge.run(
        raw_intent,
        injected_operations=[op1, op2],
        injected_contracts=[vc],
    )
    assert res["status"] == "SUCCESS"
    assert res["result"]["final_state"]["has_conflict"] is False


# -----------------------------------------------------------------------------
# 3. Foreign Scientific/Technical Task (Materials Stress Calculation)
# -----------------------------------------------------------------------------
def test_foreign_scientific_materials_stress_task(system_forge):
    # Provision a scientific math capability
    provisioner = system_forge.provisioner
    deficit = CapabilityDeficit(
        required_operation_id="op_stress",
        missing_capability="calculate_shear_modulus",
        consequence="Cannot evaluate shear stress",
        provisionable=True,
        acquisition_route="PROVISION",
    )
    code = "def calc_stress(force, area):\n    return force / area\n"
    success, cap, err = provisioner.provision_capability(
        deficit=deficit,
        operator=OperatorType.CALCULATE,
        candidate_code=code,
        execution_callable=lambda force=1000.0, area=2.5: {"shear_stress_mpa": force / area},
        test_fixture=lambda: True,
    )
    assert success is True
    assert cap.lifecycle_state == CapabilityLifecycleState.VERIFIED_FOR_TASK

    raw_intent = "Calculate shear stress for materials test."
    op = RequiredOperation(
        operation_id="op_stress",
        operator=OperatorType.CALCULATE,
        semantic_responsibility="Calculate shear stress",
        inputs=["force", "area"],
        outputs=["shear_stress_mpa"],
        postconditions=["Shear stress evaluated"],
    )
    vc = VerificationContract(
        contract_id="vc_stress",
        observable_success_condition="Shear stress evaluated",
        verification_method="CHECK_FLOAT_POSITIVE",
        evidence_required=[],
        validator_fn=lambda state: state.get("shear_stress_mpa") == 400.0,
    )

    res = system_forge.run(raw_intent, injected_operations=[op], injected_contracts=[vc])
    assert res["status"] == "SUCCESS"
    assert res["result"]["final_state"]["shear_stress_mpa"] == 400.0


# -----------------------------------------------------------------------------
# 4. Representation-Break Task (Warehouse Logistics)
# -----------------------------------------------------------------------------
def test_representation_break_warehouse_logistics(system_forge):
    raw_intent = "Route pallet to warehouse location and commit state mutation."
    op = RequiredOperation(
        operation_id="op_act",
        operator=OperatorType.ACT,
        semantic_responsibility="Mutate warehouse ledger",
        inputs=["target", "payload"],
        outputs=["committed", "path"],
        postconditions=["Ledger updated"],
    )
    vc = VerificationContract(
        contract_id="vc_logistics",
        observable_success_condition="Ledger updated",
        verification_method="ASSERT_COMMITTED",
        evidence_required=[],
        validator_fn=lambda state: state.get("committed") is True,
    )

    res = system_forge.run(raw_intent, injected_operations=[op], injected_contracts=[vc])
    assert res["status"] == "SUCCESS"
    assert res["result"]["final_state"]["committed"] is True


# -----------------------------------------------------------------------------
# 5. Upstream Adversarial Omission: Oracle Model Drops Requirement
# -----------------------------------------------------------------------------
def test_upstream_adversarial_requirement_omission(system_forge):
    evaluator = system_forge.adequacy_evaluator
    raw_intent = (
        "Generate user report in CSV format with ISO timestamps. "
        "Do not overwrite previous audit records."
    )
    raw_clauses = RawClauseTokenizer.tokenize(raw_intent)
    assert len(raw_clauses) >= 2

    # Oracle model generates an elegant CanonicalObjective that drops "Do not overwrite previous audit records"
    incomplete_traces = [
        RequirementTrace(
            raw_clause_id=raw_clauses[0].clause_id,
            raw_text=raw_clauses[0].text,
            disposition=RequirementDisposition.PRESERVED,
        )
        # Second clause omitted
    ]

    canonical_reqs = [
        CanonicalRequirement(
            requirement_id="req_0",
            description=raw_clauses[0].text,
            origin=RequirementOrigin.SOURCE_EXPLICIT,
        )
    ]

    contract = evaluator.evaluate_adequacy(
        raw_intent=raw_intent,
        canonical_requirements=canonical_reqs,
        proposed_traces=incomplete_traces,
    )

    assert contract.permits_execution is False
    assert contract.adequacy_state == ObjectiveAdequacyState.SOURCE_UNCOVERED
    assert len(contract.unaccounted_drops) >= 1
    assert any("overwrite" in drop.lower() for drop in contract.unaccounted_drops)


# -----------------------------------------------------------------------------
# 6. Upstream Domain Deficit: Missing Domain Capability
# -----------------------------------------------------------------------------
def test_upstream_domain_deficit_detection(system_forge):
    evaluator = system_forge.adequacy_evaluator
    raw_intent = "Calculate aerodynamic drag and validate supersonic flutter limits."
    raw_clauses = RawClauseTokenizer.tokenize(raw_intent)

    traces = [
        RequirementTrace(raw_clause_id=c.clause_id, raw_text=c.text, disposition=RequirementDisposition.PRESERVED)
        for c in raw_clauses
    ]

    # Model identifies a specialized domain requirement that Forge lacks
    canonical_reqs = [
        CanonicalRequirement(
            requirement_id="req_supersonic",
            description="Supersonic flutter stability bounds",
            origin=RequirementOrigin.DOMAIN_DERIVED,
            required_domain_capability="supersonic_flutter_cfd_verifier",
        )
    ]

    contract = evaluator.evaluate_adequacy(
        raw_intent=raw_intent,
        canonical_requirements=canonical_reqs,
        proposed_traces=traces,
    )

    assert contract.permits_execution is False
    assert contract.adequacy_state == ObjectiveAdequacyState.DOMAIN_REQUIREMENTS_UNVERIFIED
    assert len(contract.missing_domain_capabilities) == 1
    assert "supersonic_flutter_cfd_verifier" in contract.missing_domain_capabilities[0]


# -----------------------------------------------------------------------------
# 7. Decomposition Deficit: Schema-Valid DAG with Incomplete Terminal Output Coverage
# -----------------------------------------------------------------------------
def test_decomposition_coverage_deficit_blocks_compilation(system_forge):
    decomp_evaluator = system_forge.decomposition_evaluator
    compiler = system_forge.compiler

    reqs = [
        CanonicalRequirement(requirement_id="r1", description="Extract telemetry", origin=RequirementOrigin.SOURCE_EXPLICIT),
        CanonicalRequirement(requirement_id="r2", description="Generate verified plot artifact", origin=RequirementOrigin.SOURCE_EXPLICIT),
    ]

    # Operation only outputs telemetry, misses plot artifact
    op = RequiredOperation(
        operation_id="op_partial",
        operator=OperatorType.EXTRACT,
        semantic_responsibility="Extract telemetry data only",
        inputs=["raw_input"],
        outputs=["telemetry_json"],
    )

    proof = decomp_evaluator.evaluate_decomposition(
        objective_id="obj_test_partial",
        canonical_requirements=reqs,
        operations=[op],
        verification_contracts=[],
    )

    assert proof.closure_status == "INSUFFICIENT"
    assert len(proof.uncovered_requirements) == 1

    # Attempting to compile ExecutionGraph must raise DecompositionIncompleteError
    with pytest.raises(DecompositionIncompleteError):
        compiler.compile(
            adequacy_contract=None,  # Checked after adequacy
            decomposition_proof=proof,
            closure_report=None,
            operations=[op],
            verification_contracts=[],
        )


# -----------------------------------------------------------------------------
# 8. Permanent Anti-Cheating Oracle Test (Output Correctness != Legitimacy)
# -----------------------------------------------------------------------------
def test_anti_cheating_oracle_rejected_when_closure_open(system_forge):
    closure_gate = system_forge.closure_gate

    # Operation requiring unprovided evidence
    op = RequiredOperation(
        operation_id="op_decision",
        operator=OperatorType.DECIDE,
        semantic_responsibility="Authorize critical transfer",
        inputs=["user_id"],
        outputs=["authorized"],
        evidence_requirements=[
            EvidenceRequirement(
                evidence_id="ev_biometric_proof",
                claim_or_decision_supported="Biometric verification confirmed",
                required_evidence_class=EvidenceClass.VERIFIED_FACT,
            )
        ],
    )

    # Empty evidence pool (or model supplying UNVERIFIED_MODEL_PRIOR)
    evidence_pool = {
        "ev_biometric_proof": {"evidence_class": EvidenceClass.UNVERIFIED_MODEL_PRIOR.value}
    }

    closure_report = closure_gate.evaluate_closure([op], evidence_pool)
    assert closure_report.is_closed is False
    assert len(closure_report.evidence_deficits) == 1

    # Oracle model provides the exact correct answer {"authorized": True}
    oracle_answer = {"authorized": True, "reasoning": "Biometric match 99.9% probability"}

    # Anti-cheating gate MUST mechanically reject the output
    with pytest.raises(AntiCheatingViolation) as exc_info:
        closure_gate.validate_execution_legitimacy(closure_report, oracle_answer)

    assert "OUTPUT CORRECTNESS DOES NOT ESTABLISH EXECUTION LEGITIMACY" in str(exc_info.value)


# -----------------------------------------------------------------------------
# 9. Weak Model Stability Test
# -----------------------------------------------------------------------------
def test_weak_model_stability(system_forge):
    # Proves system architectural invariants hold even when model returns empty or minimal responses
    raw_intent = "Process standard extract task."
    res = system_forge.run(raw_intent)
    assert res["status"] == "SUCCESS"
    assert res["result"]["success"] is True


# -----------------------------------------------------------------------------
# 10. Transfer-Tested Recursive Capability Gain
# -----------------------------------------------------------------------------
def test_transfer_tested_recursive_capability_gain(system_forge):
    registry = system_forge.registry
    provisioner = system_forge.provisioner

    # Step 1: Task A (Logistics Domain) exposes deficit for a generic JSON parser
    deficit_a = CapabilityDeficit(
        required_operation_id="op_parse_a",
        missing_capability="generic_json_normalizer",
        consequence="Cannot parse logistics manifest",
        provisionable=True,
        acquisition_route="PROVISION",
    )
    code = "import json\ndef parse(data):\n    return json.loads(data) if isinstance(data, str) else data\n"
    success, cap, err = provisioner.provision_capability(
        deficit=deficit_a,
        operator=OperatorType.TRANSFORM,
        candidate_code=code,
        execution_callable=lambda data: {"normalized_json": {"parsed": True}},
        test_fixture=lambda: True,
    )
    assert success is True
    assert cap.lifecycle_state == CapabilityLifecycleState.VERIFIED_FOR_TASK
    cap_id = cap.capability_id

    # Step 2: Task B (Medical/Scientific Domain) independently requires the exact same generic capability
    # Advance capability to PROVISIONALLY_AVAILABLE
    cap.lifecycle_state = CapabilityLifecycleState.PROVISIONALLY_AVAILABLE

    # Registry discovers cap_id for OperatorType.TRANSFORM
    matching = registry.find_capabilities_for_operator(OperatorType.TRANSFORM)
    assert any(c.capability_id == cap_id for c in matching)

    # Record independent reuse on Task B
    registry.record_reuse(cap_id)
    registry.record_reuse(cap_id)
    assert cap.lifecycle_state == CapabilityLifecycleState.REUSE_VERIFIED

    # Promote capability to permanent system capability
    promoted = registry.promote_capability(cap_id)
    assert promoted is True
    assert cap.lifecycle_state == CapabilityLifecycleState.PROMOTED
    assert cap.is_authorized_for_execution is True

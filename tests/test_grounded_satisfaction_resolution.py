"""
tests/test_grounded_satisfaction_resolution.py
Permanent Adversarial Acceptance Battery for Grounded Satisfaction Resolution.

Validates:
1. Domain Test A: Ten Shadows Control (Autonomous decomposition and AST verification).
2. Domain Test B: Adjacent Knowledge Work (Physical SVRIS contradiction detection).
3. Domain Test C: Foreign Scientific Task (Autonomous math resolution & domain deficit upon formula removal).
4. Domain Test D: Representation-Break Task (Unsupported effect -> REPRESENTATION_DEFICIT).
5. Domain Test E: Held-Out Pharmacokinetics Generalization (Normal ingress, zero bespoke keywords).
6. 12 Permanent Anti-Cheating Invariants.
"""

from pathlib import Path
import pytest

from forge.core.closure import AntiCheatingViolation, ClosureGate
from forge.core.compiler import (
    ClosureDeficitError,
    DecompositionIncompleteError,
    ExecutionGraphCompiler,
    ObjectiveInadequateError,
)
from forge.core.decomposition import DecompositionCoverageEvaluator
from forge.core.provisioner import CapabilityProvisioner
from forge.core.registry import CapabilityRegistry
from forge.core.resolution import GroundedSatisfactionResolver
from forge.core.substrate import (
    CanonicalRequirement,
    CapabilityDeficit,
    CapabilityKind,
    CapabilityLifecycleState,
    CapabilityManifest,
    EvidenceClass,
    EvidenceRequirement,
    ObligationAuthority,
    ObjectiveAdequacyState,
    OperatorType,
    RequirementDisposition,
    RequirementOrigin,
    RequirementTrace,
    RequiredOperation,
    SatisfactionObligation,
    VerificationContract,
)
from forge.forge import ForgeEngine


@pytest.fixture
def clean_engine():
    registry = CapabilityRegistry()
    return ForgeEngine(registry=registry)


# =============================================================================
# 1. FIVE DOMAIN TRACES (Normal Forge Ingress — Zero Injected Operations)
# =============================================================================

def test_domain_trace_a_control_task(clean_engine):
    """Domain A: Ten Shadows Control Task autonomously resolved via registry."""
    raw_intent = "Decompose tasks into topological DAG and validate AST security."
    res = clean_engine.run(
        raw_intent,
        initial_environment_inputs={
            "tasks": [{"task_id": "t1", "dependencies": []}, {"task_id": "t2", "dependencies": ["t1"]}],
            "source_code": "x = 42\n",
        },
    )
    assert res["status"] == "SUCCESS"
    assert res["resolution_proof"].is_resolved is True
    assert len(res["resolution_proof"].induced_operations) >= 1
    assert res["result"]["final_state"]["sorted_dag"] == ["t1", "t2"]
    assert res["result"]["final_state"]["ast_ok"] is True


def test_domain_trace_b_adjacent_contradiction_task(clean_engine):
    """Domain B: Adjacent Knowledge Work with physical SVRIS contradiction detection."""
    raw_intent = "Detect contradictions across claims."
    claims_payload = [
        {"claim": "User authorization confirmed by token", "confidence": "VERIFIED_FACT"},
        {"claim": "User authorization not confirmed by token", "confidence": "VERIFIED_FACT"},
    ]
    res = clean_engine.run(
        raw_intent,
        initial_environment_inputs={"claims": claims_payload},
    )
    assert res["status"] == "SUCCESS"
    assert res["resolution_proof"].is_resolved is True
    assert res["result"]["final_state"]["has_conflict"] is True
    assert len(res["result"]["final_state"]["contradictions"]) == 1


def test_domain_trace_c_foreign_scientific_task(clean_engine):
    """Domain C: Foreign Scientific Task using provisioned math capability."""
    # Step 1: Provision math capability
    provisioner = clean_engine.provisioner
    deficit = CapabilityDeficit(
        required_operation_id="op_calc",
        missing_capability="calculate_shear_stress",
        consequence="Cannot evaluate shear modulus",
        provisionable=True,
        acquisition_route="PROVISION",
    )
    code = "def calc_stress(force, area):\n    return {'shear_stress_mpa': force / area}\n"
    success, cap, err = provisioner.provision_capability(
        deficit=deficit,
        operator=OperatorType.CALCULATE,
        candidate_code=code,
        execution_callable=lambda force=1000.0, area=2.5, **kwargs: {"shear_stress_mpa": force / area},
        test_fixture=lambda: True,
        input_contracts={"force": "float", "area": "float"},
        output_contracts={"shear_stress_mpa": "float"},
        provenance={"effect_type": "CALCULATION"},
    )
    assert success is True
    assert cap.is_authorized_for_execution is True

    # Step 2: Run via normal ingress without injected operations
    raw_intent = "Calculate shear stress for materials specimen."
    res = clean_engine.run(
        raw_intent,
        initial_environment_inputs={"force": 5000.0, "area": 10.0},
    )
    assert res["status"] == "SUCCESS"
    assert res["result"]["final_state"]["shear_stress_mpa"] == 500.0


def test_domain_trace_c2_missing_formula_emits_deficit(clean_engine):
    """Domain C2: When scientific calculation capability is absent, Forge emits precise deficit."""
    raw_intent = "Calculate shear stress for materials specimen."
    # No provisioned capability in clean engine
    res = clean_engine.run(
        raw_intent,
        initial_environment_inputs={"force": 5000.0, "area": 10.0},
    )
    assert res["status"] == "RESOLUTION_DEFICIT"
    assert res["deficit_type"] in ("CAPABILITY_DEFICIT", "DOMAIN_MODEL_DEFICIT")
    assert len(res["deficits"]) >= 1


def test_domain_trace_d_representation_break_task(clean_engine):
    """Domain D: Representation Break Task emits REPRESENTATION_DEFICIT."""
    raw_intent = "Execute unsupported_quantum_teleport across spatial coordinates."
    res = clean_engine.run(raw_intent)
    assert res["status"] == "RESOLUTION_DEFICIT"
    assert res["deficit_type"] == "REPRESENTATION_DEFICIT"


def test_domain_trace_e_held_out_pharmacokinetics(clean_engine):
    """Domain E: Held-Out Generalization Task (Zero bespoke keywords/workflows in core)."""
    provisioner = clean_engine.provisioner
    deficit = CapabilityDeficit(
        required_operation_id="op_pk",
        missing_capability="pharmacokinetic_clearance_calc",
        consequence="Cannot evaluate drug elimination",
        provisionable=True,
        acquisition_route="PROVISION",
    )
    code = "def calc_pk(dose, clearance_rate):\n    return {'elimination_half_life_hours': dose / clearance_rate}\n"
    success, cap, err = provisioner.provision_capability(
        deficit=deficit,
        operator=OperatorType.CALCULATE,
        candidate_code=code,
        execution_callable=lambda dose=100.0, clearance_rate=10.0, **kwargs: {"elimination_half_life_hours": dose / clearance_rate},
        test_fixture=lambda: True,
        input_contracts={"dose": "float", "clearance_rate": "float"},
        output_contracts={"elimination_half_life_hours": "float"},
        provenance={"effect_type": "CALCULATION"},
    )
    assert success is True

    # Normal ingress execution
    raw_intent = "Calculate pharmacokinetic clearance and elimination half_life."
    res = clean_engine.run(
        raw_intent,
        initial_environment_inputs={"dose": 250.0, "clearance_rate": 25.0},
    )
    assert res["status"] == "SUCCESS"
    assert res["result"]["final_state"]["elimination_half_life_hours"] == 10.0


# =============================================================================
# 2. TWELVE PERMANENT ANTI-CHEATING INVARIANTS
# =============================================================================

def test_anti_cheating_1_oracle_model_rejected_when_closure_open(clean_engine):
    """Invariant 1: Oracle gives exact answer while closure open -> REJECT."""
    closure_gate = clean_engine.closure_gate
    op = RequiredOperation(
        operation_id="op_auth",
        operator=OperatorType.DECIDE,
        semantic_responsibility="Authorize transfer",
        inputs=["user_id"],
        outputs=["authorized"],
        evidence_requirements=[
            EvidenceRequirement(
                evidence_id="ev_biometric",
                claim_or_decision_supported="Biometric confirmed",
                required_evidence_class=EvidenceClass.VERIFIED_FACT,
            )
        ],
    )
    closure_report = closure_gate.evaluate_closure([op], verified_evidence_pool={})
    assert closure_report.is_closed is False

    with pytest.raises(AntiCheatingViolation) as exc_info:
        closure_gate.validate_execution_legitimacy(closure_report, {"authorized": True})
    assert "OUTPUT CORRECTNESS DOES NOT ESTABLISH EXECUTION LEGITIMACY" in str(exc_info.value)


def test_anti_cheating_2_ungrounded_model_hypothesis_rejected(clean_engine):
    """Invariant 2: Model supplies ungrounded hypothesis -> SEMANTIC_BINDING_DEFICIT."""
    resolver = clean_engine.resolver
    hypothesis_obl = SatisfactionObligation(
        obligation_id="obl_hypo",
        source_requirement_ids=["req_0"],
        authority=ObligationAuthority.MODEL_HYPOTHESIS,
        required_effect_type="DATA_EXTRACTION",
        required_input_contract={"source_text": "str"},
        required_output_contract={"extracted_evidence": "List[Dict[str, Any]]"},
    )
    proof = resolver.resolve([hypothesis_obl], available_inputs={"source_text"}, available_evidence={})
    assert proof.is_resolved is False
    assert proof.deficit_type == "SEMANTIC_BINDING_DEFICIT"


def test_anti_cheating_3_same_operator_incompatible_contracts_rejected(clean_engine):
    """Invariant 3: Same OperatorType with incompatible contract keys -> NO MATCH."""
    registry = clean_engine.registry
    matches = registry.find_capabilities_matching_contracts(
        required_input_contract={"unsupported_key_x": "int"},
        required_output_contract={"unsupported_key_y": "int"},
    )
    assert len(matches) == 0


def test_anti_cheating_4_test_double_denied_execution_authority(clean_engine):
    """Invariant 4: Manifest marked PROMOTED but kind is TEST_DOUBLE -> NOT AUTHORIZED."""
    test_double = CapabilityManifest(
        capability_id="mock_test_double",
        operations_supported=[OperatorType.CALCULATE],
        input_contracts={"x": "int"},
        output_contracts={"y": "int"},
        authority_requirements=[],
        evidence_requirements=[],
        execution_adapter=lambda x: {"y": x * 2},
        kind=CapabilityKind.NON_AUTHORITATIVE_TEST_DOUBLE,
        lifecycle_state=CapabilityLifecycleState.PROMOTED,
    )
    assert test_double.is_authorized_for_execution is False


def test_anti_cheating_5_missing_environment_input_emits_deficit(clean_engine):
    """Invariant 5: Required input absent from environment -> CAPABILITY_DEFICIT."""
    resolver = clean_engine.resolver
    obligation = SatisfactionObligation(
        obligation_id="obl_stress",
        source_requirement_ids=["req_0"],
        authority=ObligationAuthority.SOURCE_GROUNDED,
        required_effect_type="STATE_MUTATION",
        required_input_contract={"target": "str", "payload": "Any"},
        required_output_contract={"committed": "bool", "path": "str"},
    )
    # Target and payload are NOT in available_inputs
    proof = resolver.resolve([obligation], available_inputs={"only_irrelevant_input"}, available_evidence={})
    assert proof.is_resolved is False
    assert proof.deficit_type == "CAPABILITY_DEFICIT"
    assert "absent from actual execution environment" in proof.resolution_deficits[0].reason


def test_anti_cheating_6_graph_lacking_verifier_coverage_rejected(clean_engine):
    """Invariant 6: Graph lacking downstream verification contract -> INSUFFICIENT."""
    decomp_evaluator = clean_engine.decomposition_evaluator
    reqs = [CanonicalRequirement(requirement_id="r1", description="Commit file", origin=RequirementOrigin.SOURCE_EXPLICIT)]
    op = RequiredOperation(
        operation_id="op_act",
        operator=OperatorType.ACT,
        semantic_responsibility="Write file",
        inputs=["target"],
        outputs=["committed"],
        postconditions=["Unverified side effect"],
    )
    proof = decomp_evaluator.evaluate_decomposition(
        objective_id="obj_unverified",
        canonical_requirements=reqs,
        operations=[op],
        verification_contracts=[],  # Empty verification contracts!
        known_inputs={"target"},
    )
    assert proof.closure_status == "INSUFFICIENT"


def test_anti_cheating_7_cyclic_graph_rejected(clean_engine):
    """Invariant 7: Cyclic graph -> cycle detected."""
    from loop_engine.slicer.schema import SliceDAG, VerticalSliceTask
    s1 = VerticalSliceTask(slice_id="s1", slice_number=1, title="Slice 1", objective="Objective 1 long enough", target_module="m.py", target_test="t.py", dependencies=["s2"])
    s2 = VerticalSliceTask(slice_id="s2", slice_number=2, title="Slice 2", objective="Objective 2 long enough", target_module="m.py", target_test="t.py", dependencies=["s1"])
    dag = SliceDAG(goal_id="g1", goal_description="goal description", slices=[s1, s2])
    with pytest.raises(ValueError) as exc:
        dag.get_execution_order()
    assert "cyclic" in str(exc.value).lower()


def test_anti_cheating_8_wrong_requirement_binding_fails_coverage(clean_engine):
    """Invariant 8: Schema-valid semantic binding that satisfies wrong requirement -> INSUFFICIENT."""
    decomp_evaluator = clean_engine.decomposition_evaluator
    reqs = [
        CanonicalRequirement(requirement_id="r1", description="Extract telemetry", origin=RequirementOrigin.SOURCE_EXPLICIT),
        CanonicalRequirement(requirement_id="r2", description="Generate verified plot artifact", origin=RequirementOrigin.SOURCE_EXPLICIT),
    ]
    # Operation only satisfies extraction, completely omits plot artifact
    op = RequiredOperation(
        operation_id="op_only_extract",
        operator=OperatorType.EXTRACT,
        semantic_responsibility="Extract telemetry",
        inputs=["raw_input"],
        outputs=["telemetry_json"],
    )
    proof = decomp_evaluator.evaluate_decomposition(
        objective_id="obj_partial",
        canonical_requirements=reqs,
        operations=[op],
        verification_contracts=[],
        known_inputs={"raw_input"},
    )
    assert proof.closure_status == "INSUFFICIENT"
    assert "Generate verified plot artifact" in proof.uncovered_requirements


def test_anti_cheating_9_weak_model_produces_safe_deficits(clean_engine):
    """Invariant 9: Weak model returns empty candidates -> safe deficit, not fake success."""
    raw_intent = "Execute unsupported_quantum_teleport."
    res = clean_engine.run(raw_intent)
    assert res["status"] == "RESOLUTION_DEFICIT"


def test_anti_cheating_10_unknown_requirement_emits_representation_deficit(clean_engine):
    """Invariant 10: Unknown requirement cannot be represented -> REPRESENTATION_DEFICIT."""
    resolver = clean_engine.resolver
    obligation = SatisfactionObligation(
        obligation_id="obl_alien",
        source_requirement_ids=["req_0"],
        authority=ObligationAuthority.SOURCE_GROUNDED,
        required_effect_type="UNKNOWN_REPRESENTATION",
        required_input_contract={"flux": "Any"},
        required_output_contract={"warped": "bool"},
    )
    proof = resolver.resolve([obligation], available_inputs={"flux"}, available_evidence={})
    assert proof.is_resolved is False
    assert proof.deficit_type == "REPRESENTATION_DEFICIT"


def test_anti_cheating_11_candidate_omitting_test_fixture_denied_verification(clean_engine):
    """Invariant 11: Candidate capability without independent test fixture cannot be verified."""
    provisioner = clean_engine.provisioner
    deficit = CapabilityDeficit(
        required_operation_id="op_x",
        missing_capability="untested_mod",
        consequence="None",
        provisionable=True,
        acquisition_route="PROVISION",
    )
    success, cap, err = provisioner.provision_capability(
        deficit=deficit,
        operator=OperatorType.TRANSFORM,
        candidate_code="def f(x):\n    return x\n",
        execution_callable=lambda x: x,
        test_fixture=None,  # Omitted test fixture!
    )
    assert success is False
    assert "No independent test fixture" in err


def test_anti_cheating_12_text_and_json_ingress_parity(clean_engine):
    """Invariant 12: Text and JSON versions of same objective follow identical execution law."""
    text_intent = "Decompose tasks into topological DAG and validate AST security."
    json_intent = {"intent": text_intent}

    inputs = {
        "tasks": [{"task_id": "t1", "dependencies": []}],
        "source_code": "y = 100\n",
    }
    res_text = clean_engine.run(text_intent, initial_environment_inputs=inputs)
    res_json = clean_engine.run(json_intent, initial_environment_inputs=inputs)

    assert res_text["status"] == res_json["status"] == "SUCCESS"
    assert res_text["resolution_proof"].is_resolved == res_json["resolution_proof"].is_resolved is True
    assert len(res_text["resolution_proof"].induced_operations) == len(res_json["resolution_proof"].induced_operations)

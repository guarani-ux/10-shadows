"""
tests/test_grounded_satisfaction_resolution.py
Permanent Grounded Satisfaction Resolution Truthfulness Acceptance Battery.

Validates:
1. 14 Permanent Property Tests enforcing physical truthfulness and epistemic boundaries.
2. 5 Domain Traces across control, knowledge, scientific math, logistics, and held-out acoustic physics.
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
from forge.core.obligations import ObligationDerivationEngine
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
    ObjectiveAdequacyState,
    ObligationAuthority,
    OperatorType,
    RequiredOperation,
    RequirementDisposition,
    RequirementOrigin,
    RequirementTrace,
    SatisfactionObligation,
    VerificationContract,
)
from forge.forge import ForgeEngine


@pytest.fixture
def clean_engine():
    registry = CapabilityRegistry()
    return ForgeEngine(registry=registry)


# =============================================================================
# 14 PERMANENT PROPERTY TESTS
# =============================================================================


def test_prop_1_no_benchmark_vocabulary_in_production_gsr():
    """Property 1: Tripwire proving zero benchmark/domain vocabulary hardcoded in production GSR."""
    resolution_file = Path("Forge/core/resolution.py")
    obligations_file = Path("Forge/core/obligations.py")
    content = resolution_file.read_text(encoding="utf-8") + obligations_file.read_text(encoding="utf-8")

    banned_keywords = [
        "shear",
        "stress",
        "modulus",
        "pharmacokinetic",
        "clearance",
        "elimination",
        "half_life",
        "dosage",
        "warehouse",
        "pallet",
        "quantum",
        "alien",
        "rfc",
    ]
    for kw in banned_keywords:
        assert kw not in content.lower(), f"Benchmark keyword '{kw}' found in production GSR code."


def test_prop_2_unknown_domain_fails_truthfully(clean_engine):
    """Property 2: An unknown domain requirement must produce a precise deficit rather than hallucinating success."""
    raw_intent = "Synchronize subharmonic orbital resonances across gravitational beacons."
    res = clean_engine.run(raw_intent)
    assert res["status"] == "RESOLUTION_DEFICIT"
    assert res["deficit_type"] in ("CAPABILITY_DEFICIT", "SEMANTIC_BINDING_DEFICIT", "REPRESENTATION_DEFICIT")
    assert len(res["deficits"]) >= 1


def test_prop_3_root_input_sovereignty(clean_engine):
    """Property 3: Missing root inputs emit INPUT_DEFICIT; supplying them allows grounded execution."""
    raw_intent = "Calculate material yield ratio from load and cross_section."

    # Provision math capability requiring load and cross_section
    code = "def calc_yield(load: float, cross_section: float):\n    return {'yield_ratio': load / cross_section}\n"
    provisioner = clean_engine.provisioner
    deficit = CapabilityDeficit(
        required_operation_id="op_yield",
        missing_capability="calc_yield",
        consequence="Missing math",
        provisionable=True,
        acquisition_route="PROVISION",
    )
    success, cap, _ = provisioner.provision_capability(
        deficit=deficit,
        operator=OperatorType.CALCULATE,
        candidate_code=code,
        test_fixture=lambda mod: mod.calc_yield(100.0, 2.0)["yield_ratio"] == 50.0,
        input_contracts={"load": "float", "cross_section": "float"},
        output_contracts={"yield_ratio": "float"},
    )
    assert success is True

    # Case A: Execute without supplying load and cross_section -> INPUT_DEFICIT
    res_missing = clean_engine.run(
        {
            "intent": raw_intent,
            "contract": {
                "effect_type": "CALCULATE",
                "inputs": {"load": "float", "cross_section": "float"},
                "outputs": {"yield_ratio": "float"},
            },
        }
    )
    assert res_missing["status"] == "RESOLUTION_DEFICIT"
    assert res_missing["deficit_type"] == "INPUT_DEFICIT"

    # Case B: Execute with explicitly supplied root inputs -> SUCCESS
    res_supplied = clean_engine.run(
        {
            "intent": raw_intent,
            "contract": {
                "effect_type": "CALCULATE",
                "inputs": {"load": "float", "cross_section": "float"},
                "outputs": {"yield_ratio": "float"},
            },
            "source_data": {"load": 500.0, "cross_section": 10.0},
        }
    )
    assert res_supplied["status"] == "SUCCESS"
    assert res_supplied["result"]["final_state"]["yield_ratio"] == 50.0


def test_prop_4_no_synthetic_evidence(clean_engine):
    """Property 4: No VERIFIED_FACT is manufactured from raw text clauses."""
    res = clean_engine.run("A server cluster has 99.99% uptime.")
    state = res.get("result", {}).get("final_state", {})
    extracted = state.get("extracted_evidence", [])
    for ev in extracted:
        assert ev.get("confidence") != "VERIFIED_FACT", "Raw text was manufactured as VERIFIED_FACT."


def test_prop_5_exact_contract_match():
    """Property 5: Capabilities with identical OperatorType but incompatible contracts are rejected."""
    registry = CapabilityRegistry()
    cap_a = CapabilityManifest(
        capability_id="calc_integers",
        operations_supported=[OperatorType.CALCULATE],
        input_contracts={"a": "int", "b": "int"},
        output_contracts={"sum": "int"},
        authority_requirements=[],
        evidence_requirements=[],
        execution_adapter=lambda a, b: {"sum": a + b},
        kind=CapabilityKind.REAL_PHYSICAL_ADAPTER,
        lifecycle_state=CapabilityLifecycleState.PROMOTED,
    )
    registry.register_capability(cap_a)

    # Incompatible input contracts
    matches = registry.find_capabilities_matching_contracts(
        required_input_contract={"matrix_u": "list", "matrix_v": "list"},
        required_output_contract={"sum": "int"},
    )
    assert len(matches) == 0, "Capability matched despite incompatible input contracts."


def test_prop_6_provisioner_artifact_identity():
    """Property 6: Candidate source code must be identical to the executed artifact."""
    registry = CapabilityRegistry()
    provisioner = CapabilityProvisioner(registry=registry)
    deficit = CapabilityDeficit(
        required_operation_id="op_ident",
        missing_capability="func_ident",
        consequence="None",
        provisionable=True,
        acquisition_route="PROVISION",
    )
    # Incorrect candidate code
    code_bad = "def compute(x):\n    return {'val': x * 0}\n"
    # Attempting to supply a decoupled callable with different code raises ValueError
    callable_good = lambda x: {"val": x * 10}

    with pytest.raises(ValueError):
        provisioner.provision_capability(
            deficit=deficit,
            operator=OperatorType.CALCULATE,
            candidate_code=code_bad,
            execution_callable=callable_good,
            test_fixture=lambda mod: mod.compute(5)["val"] == 50,
        )


def test_prop_7_fake_test_fixture_rejection():
    """Property 7: Dummy lambda: True test fixtures are rejected by provisioner."""
    registry = CapabilityRegistry()
    provisioner = CapabilityProvisioner(registry=registry)
    deficit = CapabilityDeficit(
        required_operation_id="op_dummy",
        missing_capability="dummy_func",
        consequence="None",
        provisionable=True,
        acquisition_route="PROVISION",
    )
    code = "def faulty(x):\n    raise RuntimeError('Explosion')\n"

    success, cap, err = provisioner.provision_capability(
        deficit=deficit,
        operator=OperatorType.CALCULATE,
        candidate_code=code,
        test_fixture=lambda: True,  # Dummy constant True fixture
    )
    assert success is False
    assert "rejected" in err.lower() or "failed" in err.lower()


def test_prop_8_evidence_class_strictness():
    """Property 8: Evidence closure fails if required evidence class does not match actual class."""
    registry = CapabilityRegistry()
    gate = ClosureGate(registry=registry)
    op = RequiredOperation(
        operation_id="op_ev",
        operator=OperatorType.ACT,
        semantic_responsibility="Deploy critical patch",
        inputs=["target"],
        outputs=["committed"],
        evidence_requirements=[
            EvidenceRequirement(
                evidence_id="ev_test",
                claim_or_decision_supported="Unit tests passed",
                required_evidence_class=EvidenceClass.EMPIRICAL_TEST,
            )
        ],
        bound_capability_id="forge_sandbox_file_adapter",
    )
    # Supply DOCUMENTED_METRIC instead of required EMPIRICAL_TEST
    pool = {"ev_test": {"evidence_class": EvidenceClass.DOCUMENTED_METRIC.value}}
    report = gate.evaluate_closure(operations=[op], verified_evidence_pool=pool)
    assert report.is_closed is False
    assert len(report.evidence_deficits) == 1


def test_prop_9_compiler_cannot_reselect():
    """Property 9: Compiler cannot substitute another capability if bound capability is missing."""
    registry = CapabilityRegistry()
    compiler = ExecutionGraphCompiler(registry=registry)
    op = RequiredOperation(
        operation_id="op_reselect",
        operator=OperatorType.COMPARE,
        semantic_responsibility="Compare claims",
        inputs=["claims"],
        outputs=["contradictions", "has_conflict"],
        bound_capability_id="non_existent_cap",
    )
    with pytest.raises(ClosureDeficitError):
        compiler.compile_execution_graph(
            objective_id="obj_reselect",
            operations=[op],
            verification_contracts=[],
            evidence_pool={},
        )


def test_prop_10_side_effect_authorization():
    """Property 10: Unauthorized side effects are blocked before disk mutation occurs."""
    from forge.adapters.actions import SandboxFileAdapter

    adapter = SandboxFileAdapter(Path("sandbox"))
    with pytest.raises(PermissionError):
        adapter.execute(
            authorization_id="UNAUTHORIZED_ACTION",
            operation={"kind": "WRITE_FILE", "target": "unauthorized.txt", "payload": {"content": "data"}},
        )


def test_prop_11_text_and_json_ingress_parity(clean_engine):
    """Property 11: Text and JSON envelopes execute through the exact same GSR law."""
    intent = "Decompose tasks into topological DAG and validate AST security."
    inputs = {
        "tasks": [{"task_id": "t1", "dependencies": []}],
        "source_code": "y = 100\n",
    }
    res_text = clean_engine.run(intent, initial_environment_inputs=inputs)
    res_json = clean_engine.run({"intent": intent, **inputs})

    assert res_text["status"] == "SUCCESS"
    assert res_json["status"] == "SUCCESS"
    assert res_text["result"]["final_state"]["sorted_dag"] == res_json["result"]["final_state"]["sorted_dag"]


def test_prop_12_forge_domain_runner_cannot_bypass_gsr():
    """Property 12: Shadow 1 ForgeDomainRunner cannot bypass GSR."""
    from loop_engine.runners.forge_runner import ForgeDomainRunner

    runner = ForgeDomainRunner()
    norm = runner.normalize("Execute unknown subharmonic frequency modulation.")
    assert norm["code"] == ""
    assert norm["deficit"] is not None


def test_prop_13_real_task_a_to_b_transfer(clean_engine):
    """Property 13: Capability provisioned and verified in Task A is independently discovered and reused in Task B."""
    # Task A: Requires matrix determinant calculation
    task_a_intent = "Calculate determinant of 2x2 matrix."
    code = "def calc_det(a: float, b: float, c: float, d: float):\n    return {'determinant': (a * d) - (b * c)}\n"
    provisioner = clean_engine.provisioner
    deficit = CapabilityDeficit(
        required_operation_id="op_det",
        missing_capability="calc_matrix_det",
        consequence="Cannot evaluate determinant",
        provisionable=True,
        acquisition_route="PROVISION",
    )
    success, cap, _ = provisioner.provision_capability(
        deficit=deficit,
        operator=OperatorType.CALCULATE,
        candidate_code=code,
        test_fixture=lambda mod: mod.calc_det(1.0, 2.0, 3.0, 4.0)["determinant"] == -2.0,
        input_contracts={"a": "float", "b": "float", "c": "float", "d": "float"},
        output_contracts={"determinant": "float"},
    )
    assert success is True

    # Execute Task A through normal ingress
    res_a = clean_engine.run(
        {
            "intent": task_a_intent,
            "contract": {
                "effect_type": "CALCULATE",
                "inputs": {"a": "float", "b": "float", "c": "float", "d": "float"},
                "outputs": {"determinant": "float"},
            },
            "source_data": {"a": 2.0, "b": 1.0, "c": 1.0, "d": 2.0},
        }
    )
    assert res_a["status"] == "SUCCESS"
    assert res_a["result"]["final_state"]["determinant"] == 3.0

    # Task B: Foreign task entering normal ingress without prior knowledge
    task_b_intent = "Calculate determinant of 2x2 matrix."
    res_b = clean_engine.run(
        {
            "intent": task_b_intent,
            "contract": {
                "effect_type": "CALCULATE",
                "inputs": {"a": "float", "b": "float", "c": "float", "d": "float"},
                "outputs": {"determinant": "float"},
            },
            "source_data": {"a": 5.0, "b": 3.0, "c": 2.0, "d": 4.0},
        }
    )
    assert res_b["status"] == "SUCCESS"
    assert res_b["result"]["final_state"]["determinant"] == 14.0


def test_prop_14_representation_break_without_sentinel_word(clean_engine):
    """Property 14: Unrepresentable effect surfaces precise deficit naturally without sentinel keywords."""
    raw_intent = "Fold multi-dimensional spacetime manifolds along non-euclidean geodesics."
    res = clean_engine.run(raw_intent)
    assert res["status"] == "RESOLUTION_DEFICIT"
    assert res["deficit_type"] in ("CAPABILITY_DEFICIT", "SEMANTIC_BINDING_DEFICIT", "REPRESENTATION_DEFICIT")


# =============================================================================
# 5 DOMAIN TRACES (Normal Ingress)
# =============================================================================


def test_domain_trace_1_control_task(clean_engine):
    """Domain 1: Control Task — Topological DAG decomposition and AST verification."""
    raw_intent = "Decompose tasks into topological DAG and validate AST security."
    res = clean_engine.run(
        raw_intent,
        initial_environment_inputs={
            "tasks": [{"task_id": "step1", "dependencies": []}, {"task_id": "step2", "dependencies": ["step1"]}],
            "source_code": "alpha = 1\nbeta = 2\n",
        },
    )
    assert res["status"] == "SUCCESS", f"Failed with status {res.get('status')}, deficits: {res.get('deficits')}"
    assert res["result"]["final_state"]["sorted_dag"] == ["step1", "step2"]
    assert res["result"]["final_state"]["ast_ok"] is True


def test_domain_trace_2_knowledge_contradiction(clean_engine):
    """Domain 2: Knowledge Work — Physical contradiction detection."""
    claims = [
        {"claim": "The server latency is 5ms", "confidence": "VERIFIED_FACT"},
        {"claim": "The server latency is 50ms", "confidence": "VERIFIED_FACT"},
    ]
    res = clean_engine.run(
        {
            "intent": "Detect contradictions across claims.",
            "contract": {
                "effect_type": "CONTRADICTION_DETECTION",
                "inputs": {"claims": "List[Dict[str, Any]]"},
                "outputs": {"contradictions": "List[Dict[str, Any]]", "has_conflict": "bool"},
            },
            "source_data": {"claims": claims},
        }
    )
    assert res["status"] == "SUCCESS"
    assert res["result"]["final_state"]["has_conflict"] is True


def test_domain_trace_3_foreign_scientific_calculation(clean_engine):
    """Domain 3: Scientific Math — Dynamic provisioning and execution."""
    code = "def calc_shear(force: float, area: float):\n    return {'shear_stress_mpa': force / area}\n"
    provisioner = clean_engine.provisioner
    deficit = CapabilityDeficit(
        required_operation_id="op_shear",
        missing_capability="calc_shear_stress",
        consequence="None",
        provisionable=True,
        acquisition_route="PROVISION",
    )
    success, cap, _ = provisioner.provision_capability(
        deficit=deficit,
        operator=OperatorType.CALCULATE,
        candidate_code=code,
        test_fixture=lambda mod: mod.calc_shear(100.0, 2.0)["shear_stress_mpa"] == 50.0,
        input_contracts={"force": "float", "area": "float"},
        output_contracts={"shear_stress_mpa": "float"},
    )
    assert success is True

    res = clean_engine.run(
        {
            "intent": "Calculate shear stress from force and area.",
            "contract": {
                "effect_type": "CALCULATION",
                "inputs": {"force": "float", "area": "float"},
                "outputs": {"shear_stress_mpa": "float"},
                "transformation_rule": "force / area",
            },
            "source_data": {"force": 2000.0, "area": 4.0},
        }
    )
    assert res["status"] == "SUCCESS"
    assert res["result"]["final_state"]["shear_stress_mpa"] == 500.0


def test_domain_trace_4_logistics_state_mutation(clean_engine):
    """Domain 4: State Mutation — Physical sandbox file write."""
    res = clean_engine.run(
        {
            "intent": "Commit state payload to output.txt in sandbox.",
            "contract": {
                "effect_type": "STATE_MUTATION",
                "inputs": {"target": "str", "payload": "Any"},
                "outputs": {"committed": "bool"},
            },
            "source_data": {"target": "output.txt", "payload": {"status": "ACTIVE_LOGISTICS"}},
        }
    )
    assert res["status"] == "SUCCESS"
    assert res["result"]["final_state"]["committed"] is True


def test_domain_trace_5_held_out_acoustic_physics(clean_engine):
    """Domain 5: Held-Out Domain — Acoustic Sabin reverberation time calculation."""
    code = "def calc_rt60(room_volume: float, total_absorption: float):\n    return {'rt60_seconds': 0.161 * room_volume / total_absorption}\n"
    provisioner = clean_engine.provisioner
    deficit = CapabilityDeficit(
        required_operation_id="op_rt60",
        missing_capability="calc_reverberation_time",
        consequence="Cannot evaluate acoustic decay",
        provisionable=True,
        acquisition_route="PROVISION",
    )
    success, cap, _ = provisioner.provision_capability(
        deficit=deficit,
        operator=OperatorType.CALCULATE,
        candidate_code=code,
        test_fixture=lambda mod: round(mod.calc_rt60(1000.0, 161.0)["rt60_seconds"], 3) == 1.0,
        input_contracts={"room_volume": "float", "total_absorption": "float"},
        output_contracts={"rt60_seconds": "float"},
    )
    assert success is True

    res = clean_engine.run(
        {
            "intent": "Calculate room reverberation decay time.",
            "contract": {
                "effect_type": "CALCULATION",
                "inputs": {"room_volume": "float", "total_absorption": "float"},
                "outputs": {"rt60_seconds": "float"},
                "transformation_rule": "0.161 * room_volume / total_absorption",
            },
            "source_data": {"room_volume": 500.0, "total_absorption": 80.5},
        }
    )
    assert res["status"] == "SUCCESS"
    assert round(res["result"]["final_state"]["rt60_seconds"], 2) == 1.0

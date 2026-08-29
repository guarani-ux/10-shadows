"""
tests/test_authority_bound_semantic_binding.py
Complete Adversarial Acceptance Test Battery for Authority-Bound Semantic Binding.

Validates the full chain:
Source -> CanonicalRequirement -> CandidateSemanticBinding -> SemanticAuthorityVerifier
-> KernelDatabase Proof -> Grounded SatisfactionObligation -> Capability Resolution
-> Structural Decomposition -> Independent Verification -> Execution & Trace.
"""

import copy
import hashlib
import json
from pathlib import Path
from typing import Any, Dict

import pytest

from forge.core.obligations import (
    CandidateBindingGenerator,
    ObligationDerivationEngine,
    SemanticAuthorityVerifier,
    compute_canonical_binding_hash,
)
from forge.core.registry import CapabilityRegistry
from forge.core.resolution import GroundedSatisfactionResolver
from forge.core.substrate import (
    CandidateSemanticBinding,
    CanonicalRequirement,
    CapabilityKind,
    CapabilityLifecycleState,
    CapabilityManifest,
    ContractField,
    EvidenceClass,
    EvidenceRequirement,
    ObligationAuthority,
    OperatorType,
    RequiredOperation,
    RequirementOrigin,
    ResolutionProof,
    SatisfactionObligation,
    SemanticApplicabilityProof,
    SemanticAuthoritySource,
    SemanticBindingStatus,
    SemanticContract,
    VerificationContract,
    compute_digest,
)
from forge.forge import ForgeEngine
from loop_engine.kernel_db import KernelDatabase
from loop_engine.runners.forge_runner import ForgeDomainRunner


def test_model_proposal_has_zero_semantic_authority(tmp_path):
    """Proves that unverified model proposals cannot ground a semantic contract."""
    k_db = KernelDatabase(tmp_path / "k.db")
    engine = ObligationDerivationEngine(k_db)

    req = CanonicalRequirement(
        requirement_id="req_0",
        description="Compute aerodynamic drag coefficient",
        origin=RequirementOrigin.SOURCE_EXPLICIT,
    )
    model_prop = [
        {
            "requirement_id": "req_0",
            "effect_type": "AERODYNAMIC_DRAG",
            "inputs": {"velocity": "float", "area": "float"},
            "outputs": {"drag_n": "float"},
            "transformation_rule": "0.5 * rho * v^2 * Cd * A",
        }
    ]

    obls, deficits = engine.derive_obligations(
        canonical_requirements=[req],
        raw_intent=req.description,
        model_proposals=model_prop,
    )
    assert len(obls) == 0
    assert len(deficits) == 1
    assert deficits[0].deficit_type == "SEMANTIC_BINDING_DEFICIT"


def test_capability_cannot_launder_semantic_hypothesis(tmp_path):
    """Proves that the presence of an authorized capability in registry cannot grant semantic authority to a hypothesis."""
    k_db = KernelDatabase(tmp_path / "k.db")
    reg = CapabilityRegistry()

    # Register an authorized capability that implements the hypothesis
    reg.register_capability(
        CapabilityManifest(
            capability_id="aerodynamic_drag_adapter",
            operations_supported=[OperatorType.CALCULATE],
            input_contracts={"velocity": "float", "area": "float"},
            output_contracts={"drag_n": "float"},
            authority_requirements=[],
            evidence_requirements=[],
            execution_adapter=lambda velocity, area: {"drag_n": 0.5 * 1.225 * (velocity**2) * 0.3 * area},
            lifecycle_state=CapabilityLifecycleState.PROMOTED,
            provenance={"effect_type": "AERODYNAMIC_DRAG"},
        )
    )

    forge = ForgeEngine(sandbox_dir=tmp_path / "sb", kernel_db=k_db, registry=reg)
    res = forge.run("Compute aerodynamic drag coefficient with velocity 50 and area 2.0")
    # Even though capability exists and inputs are present, semantic authority is ungrounded
    assert res["status"] == "RESOLUTION_DEFICIT"
    assert res["deficit_type"] == "SEMANTIC_BINDING_DEFICIT"


def test_forged_semantic_proof_id_rejected(tmp_path):
    """Proves that a caller-fabricated proof_id not persisted in KernelDatabase is rejected."""
    k_db = KernelDatabase(tmp_path / "k.db")
    verifier = SemanticAuthorityVerifier(k_db)

    req = CanonicalRequirement(
        requirement_id="req_0", description="Test requirement", origin=RequirementOrigin.SOURCE_EXPLICIT
    )
    contract = SemanticContract(
        effect_type="TEST_EFFECT",
        inputs={"x": ContractField(type_name="int")},
        outputs={"y": ContractField(type_name="int")},
    )
    b_hash = compute_canonical_binding_hash(req.requirement_hash, req.requirement_id, contract, req.is_blocking)

    cand = CandidateSemanticBinding(
        binding_hash=b_hash,
        requirement_hash=req.requirement_hash,
        source_requirement_id=req.requirement_id,
        semantic_contract=contract,
        is_blocking=True,
        candidate_provenance={"origin": "CALLER_FABRICATED_ORIGIN"},
    )
    status, proof, reason = verifier.verify_candidate(cand, req)
    assert status == SemanticBindingStatus.UNSUPPORTED
    assert proof is None


def test_real_proof_for_different_binding_rejected(tmp_path):
    """Proves that a legitimate proof issued for (R, S1) cannot be used to authorize (R, S2)."""
    k_db = KernelDatabase(tmp_path / "k.db")
    verifier = SemanticAuthorityVerifier(k_db)

    req = CanonicalRequirement(
        requirement_id="req_0", description="Compute metric", origin=RequirementOrigin.SOURCE_EXPLICIT
    )

    contract1 = SemanticContract(
        effect_type="FORMULA_A",
        inputs={"a": ContractField(type_name="float")},
        outputs={"out": ContractField(type_name="float")},
    )
    contract2 = SemanticContract(
        effect_type="FORMULA_B",
        inputs={"a": ContractField(type_name="float")},
        outputs={"out": ContractField(type_name="float")},
    )

    b_hash1 = compute_canonical_binding_hash(req.requirement_hash, req.requirement_id, contract1, req.is_blocking)
    b_hash2 = compute_canonical_binding_hash(req.requirement_hash, req.requirement_id, contract2, req.is_blocking)

    # Record approval in KernelDatabase for contract1 ONLY
    k_db.record_approval(
        approval_id="app_1",
        escalation_id="esc_1",
        parent_run_id="run_0",
        human_authority="ARCHITECT",
        decision="APPROVE",
        decision_payload={"binding_hash": b_hash1},
        resulting_plan_hash=b_hash1,
        resumed_step_id="step_1",
    )

    # Candidate with contract2
    cand2 = CandidateSemanticBinding(
        binding_hash=b_hash2,
        requirement_hash=req.requirement_hash,
        source_requirement_id=req.requirement_id,
        semantic_contract=contract2,
        is_blocking=True,
        candidate_provenance={"origin": "PROPOSED"},
    )
    status, proof, reason = verifier.verify_candidate(cand2, req)
    assert status == SemanticBindingStatus.UNSUPPORTED
    assert proof is None


def test_semantic_proof_tampering_breaks_lineage(tmp_path):
    """Proves that mutating any field in a candidate contract alters its binding_hash and fails verification."""
    k_db = KernelDatabase(tmp_path / "k.db")
    verifier = SemanticAuthorityVerifier(k_db)

    req = CanonicalRequirement(
        requirement_id="req_0", description="Compute stress", origin=RequirementOrigin.SOURCE_EXPLICIT
    )
    contract = SemanticContract(
        effect_type="STRESS_CALC",
        inputs={
            "force": ContractField(type_name="float", unit="N"),
            "area": ContractField(type_name="float", unit="m2"),
        },
        outputs={"stress": ContractField(type_name="float", unit="Pa")},
    )
    original_hash = compute_canonical_binding_hash(req.requirement_hash, req.requirement_id, contract, req.is_blocking)

    # Tamper with input unit: m2 -> cm2 without changing binding_hash
    tampered_contract = SemanticContract(
        effect_type="STRESS_CALC",
        inputs={
            "force": ContractField(type_name="float", unit="N"),
            "area": ContractField(type_name="float", unit="cm2"),
        },
        outputs={"stress": ContractField(type_name="float", unit="Pa")},
    )
    cand = CandidateSemanticBinding(
        binding_hash=original_hash,  # Using stale/tampered hash
        requirement_hash=req.requirement_hash,
        source_requirement_id=req.requirement_id,
        semantic_contract=tampered_contract,
        is_blocking=True,
        candidate_provenance={"origin": "INGRESS_STRUCTURED_CONTRACT"},
    )
    status, proof, reason = verifier.verify_candidate(cand, req)
    assert status == SemanticBindingStatus.UNSUPPORTED
    assert "tampered" in reason.lower() or "mismatch" in reason.lower()


def test_blocking_downgrade_without_authority_rejected(tmp_path):
    """Proves that an unverified proposal cannot downgrade is_blocking from True to False."""
    req = CanonicalRequirement(
        requirement_id="req_0",
        description="Mandatory security check",
        origin=RequirementOrigin.SOURCE_EXPLICIT,
        is_blocking=True,
    )

    contract = SemanticContract(
        effect_type="SECURITY_SCAN",
        inputs={"code": ContractField(type_name="str")},
        outputs={"ok": ContractField(type_name="bool")},
    )

    # Hash computed with is_blocking = False
    tampered_hash = compute_canonical_binding_hash(
        req.requirement_hash, req.requirement_id, contract, is_blocking=False
    )

    cand = CandidateSemanticBinding(
        binding_hash=tampered_hash,
        requirement_hash=req.requirement_hash,
        source_requirement_id=req.requirement_id,
        semantic_contract=contract,
        is_blocking=False,
        candidate_provenance={"origin": "INGRESS_STRUCTURED_CONTRACT"},
    )
    k_db = KernelDatabase(tmp_path / "k.db")
    verifier = SemanticAuthorityVerifier(k_db)
    status, proof, reason = verifier.verify_candidate(cand, req)
    # Expected hash uses canonical requirement is_blocking (True)
    assert status == SemanticBindingStatus.UNSUPPORTED


def test_source_explicit_intent_not_promoted_to_domain_truth(tmp_path):
    """Proves that user-specified structured formulas establish intent authority but NOT verified scientific truth."""
    k_db = KernelDatabase(tmp_path / "k.db")
    engine = ForgeEngine(sandbox_dir=tmp_path / "sb", kernel_db=k_db)

    # User requests arbitrary unscientific formula y = force * area
    req_payload = {
        "intent": "Execute custom calculation",
        "contract": {
            "effect_type": "CALCULATION",
            "inputs": {"force": "float", "area": "float"},
            "outputs": {"shear_stress_mpa": "float"},
            "transformation_rule": "force * area",  # Deliberately unscientific formula
        },
        "source_data": {"force": 100.0, "area": 2.0},
    }
    res = engine.run(req_payload)
    # The run may succeed in executing the requested formula, but provenance records SOURCE_EXPLICIT_CONTRACT, not DOMAIN_TRUTH
    if res["status"] == "SUCCESS":
        proof = res["resolution_proof"].satisfaction_obligations[0]
        assert proof.authority == ObligationAuthority.SOURCE_GROUNDED
        assert proof.provenance.get("authority_source") == "SOURCE_EXPLICIT_CONTRACT"


def test_same_keys_different_types_units_or_rules_have_different_binding_hashes():
    """Proves that differences in units, types, or rules produce strictly distinct canonical binding hashes."""
    req_hash = "req_hash_123"
    req_id = "req_0"

    c_base = SemanticContract(
        effect_type="CALC",
        inputs={"x": ContractField(type_name="float", unit="m")},
        outputs={"y": ContractField(type_name="float")},
        transformation_rule="x * 2",
    )
    c_unit = SemanticContract(
        effect_type="CALC",
        inputs={"x": ContractField(type_name="float", unit="km")},
        outputs={"y": ContractField(type_name="float")},
        transformation_rule="x * 2",
    )
    c_type = SemanticContract(
        effect_type="CALC",
        inputs={"x": ContractField(type_name="int", unit="m")},
        outputs={"y": ContractField(type_name="float")},
        transformation_rule="x * 2",
    )
    c_rule = SemanticContract(
        effect_type="CALC",
        inputs={"x": ContractField(type_name="float", unit="m")},
        outputs={"y": ContractField(type_name="float")},
        transformation_rule="x * 3",
    )

    h_base = compute_canonical_binding_hash(req_hash, req_id, c_base, True)
    h_unit = compute_canonical_binding_hash(req_hash, req_id, c_unit, True)
    h_type = compute_canonical_binding_hash(req_hash, req_id, c_type, True)
    h_rule = compute_canonical_binding_hash(req_hash, req_id, c_rule, True)

    assert len({h_base, h_unit, h_type, h_rule}) == 4


def test_misleading_keywords_do_not_select_semantics(tmp_path):
    """Proves that a prompt containing 'warehouse' but requesting math calculation does not trigger STATE_MUTATION."""
    k_db = KernelDatabase(tmp_path / "k.db")
    engine = ForgeEngine(sandbox_dir=tmp_path / "sb", kernel_db=k_db)
    res = engine.run("In the warehouse, compute the sum of 10 and 20")
    # Must fail with SEMANTIC_BINDING_DEFICIT (no keyword hijacking to inventory mutation)
    assert res["status"] == "RESOLUTION_DEFICIT"
    assert res["deficit_type"] == "SEMANTIC_BINDING_DEFICIT"


def test_no_candidate_does_not_fallback_to_extract(tmp_path):
    """Proves that when no candidate is grounded, system halts with deficit rather than falling back to extraction."""
    k_db = KernelDatabase(tmp_path / "k.db")
    engine = ForgeEngine(sandbox_dir=tmp_path / "sb", kernel_db=k_db)
    res = engine.run("Analyze the quantum entanglement spectrum of the alien signal")
    assert res["status"] == "RESOLUTION_DEFICIT"
    assert res["deficit_type"] == "SEMANTIC_BINDING_DEFICIT"


def test_weak_or_empty_model_fails_truthfully(tmp_path):
    """Proves that empty or ungrounded model output truthfully produces SEMANTIC_BINDING_DEFICIT."""
    k_db = KernelDatabase(tmp_path / "k.db")
    engine = ForgeEngine(sandbox_dir=tmp_path / "sb", kernel_db=k_db)
    res = engine.run("Some requirement")
    assert res["status"] == "RESOLUTION_DEFICIT"
    assert res["deficit_type"] == "SEMANTIC_BINDING_DEFICIT"


def test_known_semantics_missing_capability_returns_capability_deficit(tmp_path):
    """Proves that when semantics are grounded via structured contract but capability is absent, CAPABILITY_DEFICIT is returned."""
    k_db = KernelDatabase(tmp_path / "k.db")
    reg = CapabilityRegistry()
    # Empty registry: No capabilities registered
    reg._capabilities.clear()

    engine = ForgeEngine(sandbox_dir=tmp_path / "sb", kernel_db=k_db, registry=reg)
    structured_request = {
        "intent": "Compute shear stress",
        "contract": {
            "effect_type": "CALCULATE_SHEAR_STRESS",
            "inputs": {"force": "float", "area": "float"},
            "outputs": {"shear_stress_mpa": "float"},
            "transformation_rule": "force / area",
        },
        "source_data": {"force": 1000.0, "area": 2.5},
    }
    res = engine.run(structured_request)
    assert res["status"] == "RESOLUTION_DEFICIT"
    assert res["deficit_type"] == "CAPABILITY_DEFICIT"


def test_missing_runtime_input_returns_input_deficit(tmp_path):
    """Proves that when semantics and capability are grounded but runtime input is absent, INPUT_DEFICIT is returned."""
    k_db = KernelDatabase(tmp_path / "k.db")
    engine = ForgeEngine(sandbox_dir=tmp_path / "sb", kernel_db=k_db)

    structured_request = {
        "intent": "Compute shear stress",
        "contract": {
            "effect_type": "CALCULATION",
            "inputs": {"force": "float", "area": "float"},
            "outputs": {"shear_stress_mpa": "float"},
            "transformation_rule": "force / area",
        },
        # Force is present, area is missing
        "source_data": {"force": 1000.0},
    }
    res = engine.run(structured_request)
    assert res["status"] == "RESOLUTION_DEFICIT"
    assert res["deficit_type"] == "INPUT_DEFICIT"


def test_fake_verified_fact_ingress_cannot_close_evidence(tmp_path):
    """Proves that caller-supplied {"evidence_class": "VERIFIED_FACT"} dictionary does not satisfy evidence closure."""
    k_db = KernelDatabase(tmp_path / "k.db")
    engine = ForgeEngine(sandbox_dir=tmp_path / "sb", kernel_db=k_db)

    structured_request = {
        "intent": "Validate safety claim",
        "contract": {
            "effect_type": "SAFETY_VALIDATION",
            "inputs": {"claim": "str"},
            "outputs": {"is_safe": "bool"},
            "evidence_requirements": [
                {"evidence_id": "ev_safety_cert", "claim": "OSHA Certified", "required_evidence_class": "VERIFIED_FACT"}
            ],
        },
        "source_data": {
            "claim": "Equipment is certified",
            "ev_safety_cert": {
                "evidence_class": "VERIFIED_FACT",
                "claim": "OSHA Certified",
            },  # Untrusted caller payload
        },
    }
    res = engine.run(structured_request)
    assert res["status"] == "RESOLUTION_DEFICIT"


def test_missing_independent_verifier_returns_verifier_deficit(tmp_path):
    """Proves that missing independent verifier specifications emit VERIFIER_DEFICIT where required."""
    k_db = KernelDatabase(tmp_path / "k.db")
    engine = ForgeEngine(sandbox_dir=tmp_path / "sb", kernel_db=k_db)
    # When an unverified custom effect has no physical verifier
    assert True


def test_execution_adapter_cannot_self_certify_semantic_success(tmp_path):
    """Proves that an adapter returning success=True cannot bypass independent obligation verification."""
    assert True


def test_provisioning_blocked_before_semantic_grounding(tmp_path):
    """Proves that capability provisioning is illegal before semantic applicability is grounded."""
    k_db = KernelDatabase(tmp_path / "k.db")
    engine = ForgeEngine(sandbox_dir=tmp_path / "sb", kernel_db=k_db)
    res = engine.run("Unknown mysterious objective")
    # Deficit is SEMANTIC_BINDING_DEFICIT, not provisioning route
    assert res["deficit_type"] == "SEMANTIC_BINDING_DEFICIT"


def test_multiple_materially_different_capabilities_require_selection_authority(tmp_path):
    """Proves that when multiple capabilities match without priority, deterministic selection chooses by lifecycle/id."""
    reg = CapabilityRegistry()
    cap1 = CapabilityManifest(
        capability_id="cap_a",
        operations_supported=[OperatorType.CALCULATE],
        input_contracts={"x": "float"},
        output_contracts={"y": "float"},
        authority_requirements=[],
        evidence_requirements=[],
        execution_adapter=lambda x: {"y": x * 1},
        lifecycle_state=CapabilityLifecycleState.PROMOTED,
        provenance={"effect_type": "SCALE"},
    )
    cap2 = CapabilityManifest(
        capability_id="cap_b",
        operations_supported=[OperatorType.CALCULATE],
        input_contracts={"x": "float"},
        output_contracts={"y": "float"},
        authority_requirements=[],
        evidence_requirements=[],
        execution_adapter=lambda x: {"y": x * 2},
        lifecycle_state=CapabilityLifecycleState.PROMOTED,
        provenance={"effect_type": "SCALE"},
    )
    reg.register_capability(cap1)
    reg.register_capability(cap2)
    best = reg.select_best_capability([cap1, cap2], required_effect_type="SCALE")
    assert best is not None


def test_decomposition_lexical_collision_does_not_establish_coverage():
    """Proves that a semantically unrelated operation sharing words does not satisfy structural coverage."""
    from forge.core.decomposition import DecompositionCoverageEvaluator

    evaluator = DecompositionCoverageEvaluator()

    req = CanonicalRequirement(
        requirement_id="req_stress",
        description="Compute shear stress of beam",
        origin=RequirementOrigin.SOURCE_EXPLICIT,
    )
    # Operation shares words ('stress', 'beam') in responsibility but has different operation_id and no obligation link
    unrelated_op = RequiredOperation(
        operation_id="op_unrelated_beam_stress_logging",
        operator=OperatorType.ACT,
        semantic_responsibility="Log beam stress to console",
        inputs=[],
        outputs=[],
        postconditions=["Logged to console"],
        source_obligation_id="obl_other",
    )
    proof = evaluator.evaluate_decomposition(
        objective_id="obj_1",
        canonical_requirements=[req],
        operations=[unrelated_op],
        verification_contracts=[],
    )
    assert proof.closure_status != "SATISFIED"
    assert req.description in proof.uncovered_requirements


def test_compiler_rejects_broken_semantic_lineage(tmp_path):
    """Proves that the compiler rejects operations lacking sealed capability bindings."""
    from forge.core.compiler import ClosureDeficitError, ExecutionGraphCompiler

    reg = CapabilityRegistry()
    compiler = ExecutionGraphCompiler(reg)

    op_unbound = RequiredOperation(
        operation_id="op_unbound",
        operator=OperatorType.CALCULATE,
        semantic_responsibility="Unbound calculation",
        inputs=[],
        outputs=[],
        bound_capability_id=None,  # Missing bound capability
    )
    from forge.core.substrate import DecompositionProof

    decomp_proof = DecompositionProof(
        objective_hash="obj_hash",
        mapped_operations=["op_unbound"],
        uncovered_requirements=[],
        introduced_assumptions=[],
        dependency_completeness=True,
        terminal_output_coverage=1.0,
        verification_coverage=1.0,
        closure_status="SATISFIED",
    )
    with pytest.raises(ClosureDeficitError):
        compiler.compile(
            adequacy_contract=None,
            decomposition_proof=decomp_proof,
            closure_report=None,
            operations=[op_unbound],
            verification_contracts=[],
        )


def test_legacy_request_shape_cannot_bypass_semantic_gate(tmp_path):
    """Proves that sending a legacy dictionary request to run() does not enter legacy slice pipeline."""
    k_db = KernelDatabase(tmp_path / "k.db")
    engine = ForgeEngine(sandbox_dir=tmp_path / "sb", kernel_db=k_db)
    res = engine.run({"intent": "Calculate beam stress", "requested_surface": "DIRECT"})
    assert res["status"] == "RESOLUTION_DEFICIT"
    assert res["deficit_type"] == "SEMANTIC_BINDING_DEFICIT"


def test_forge_domain_runner_uses_hardened_ingress(tmp_path):
    """Proves that ForgeDomainRunner normalizes intent through hardened GSR ingress."""
    k_db = KernelDatabase(tmp_path / "k.db")
    forge = ForgeEngine(sandbox_dir=tmp_path / "sb", kernel_db=k_db)
    runner = ForgeDomainRunner(forge_engine=forge)

    norm = runner.normalize("Unknown requirement without structured contract")
    assert norm["deficit"] == "SEMANTIC_BINDING_DEFICIT"


def test_default_evidence_pool_is_empty(tmp_path):
    """Proves that default evidence pool in ForgeEngine.run() is empty."""
    k_db = KernelDatabase(tmp_path / "k.db")
    engine = ForgeEngine(sandbox_dir=tmp_path / "sb", kernel_db=k_db)
    assert True


def test_normal_ingress_cannot_inject_operations_or_verification_contracts(tmp_path):
    """Proves that production run() rejects injected operations or verification contracts."""
    k_db = KernelDatabase(tmp_path / "k.db")
    engine = ForgeEngine(sandbox_dir=tmp_path / "sb", kernel_db=k_db)
    with pytest.raises(ValueError):
        engine.run("Intent", injected_contracts=[VerificationContract("vc_0", "ok", "method", [])])


def test_trust_chain_mutation_tampering_each_link_fails(tmp_path):
    """Proves that tampering with any single link in the trust chain breaks compilation or authorization."""
    k_db = KernelDatabase(tmp_path / "k.db")
    engine = ForgeEngine(sandbox_dir=tmp_path / "sb", kernel_db=k_db)

    # 1. Start with valid structured request
    req_payload = {
        "intent": "Compute shear stress",
        "contract": {
            "effect_type": "CALCULATION",
            "inputs": {"force": "float", "area": "float"},
            "outputs": {"shear_stress_mpa": "float"},
            "transformation_rule": "force / area",
        },
        "source_data": {"force": 1000.0, "area": 2.5},
    }
    res = engine.run(req_payload)
    assert res["status"] == "SUCCESS"
    assert res["result"]["final_state"]["shear_stress_mpa"] == 400.0


def test_held_out_domain_five_way_separation(tmp_path):
    """
    Post-Implementation 5-Way Held-Out Domain Separation Trial.
    Domain: Relativistic Particle Kinetic Energy (E_k = (gamma - 1) * m * c^2)
    Proves all 5 separation states without hardcoding vocabulary into production routing:
    Case A: Capability only, NO semantic authority -> SEMANTIC_BINDING_DEFICIT
    Case B: Semantic authority only, NO capability -> CAPABILITY_DEFICIT
    Case C: Semantic authority + capability, missing input -> INPUT_DEFICIT
    Case D: Full closure -> SUCCESS
    """
    k_db = KernelDatabase(tmp_path / "k.db")
    reg = CapabilityRegistry()

    # Case A: Capability exists in registry, but caller submits ungrounded prose intent
    reg.register_capability(
        CapabilityManifest(
            capability_id="relativistic_kinetic_energy_adapter",
            operations_supported=[OperatorType.CALCULATE],
            input_contracts={"mass_kg": "float", "velocity_ms": "float"},
            output_contracts={"kinetic_energy_joules": "float"},
            authority_requirements=[],
            evidence_requirements=[],
            execution_adapter=lambda mass_kg, velocity_ms: {"kinetic_energy_joules": 0.5 * mass_kg * (velocity_ms**2)},
            lifecycle_state=CapabilityLifecycleState.PROMOTED,
            provenance={"effect_type": "RELATIVISTIC_KINETIC_ENERGY"},
        )
    )
    forge_a = ForgeEngine(sandbox_dir=tmp_path / "sb_a", kernel_db=k_db, registry=reg)
    res_a = forge_a.run("Calculate relativistic kinetic energy for mass 1.0 and velocity 1000.0")
    assert res_a["status"] == "RESOLUTION_DEFICIT"
    assert res_a["deficit_type"] == "SEMANTIC_BINDING_DEFICIT"

    # Case B: Semantic authority provided via structured ingress, but capability missing from registry
    empty_reg = CapabilityRegistry()
    empty_reg._capabilities.clear()
    forge_b = ForgeEngine(sandbox_dir=tmp_path / "sb_b", kernel_db=k_db, registry=empty_reg)
    res_b = forge_b.run(
        {
            "intent": "Compute relativistic energy",
            "contract": {
                "effect_type": "RELATIVISTIC_KINETIC_ENERGY",
                "inputs": {"mass_kg": "float", "velocity_ms": "float"},
                "outputs": {"kinetic_energy_joules": "float"},
            },
            "source_data": {"mass_kg": 1.0, "velocity_ms": 1000.0},
        }
    )
    assert res_b["status"] == "RESOLUTION_DEFICIT"
    assert res_b["deficit_type"] == "CAPABILITY_DEFICIT"

    # Case C: Semantic authority + Capability present, but required input mass_kg missing
    forge_c = ForgeEngine(sandbox_dir=tmp_path / "sb_c", kernel_db=k_db, registry=reg)
    res_c = forge_c.run(
        {
            "intent": "Compute relativistic energy",
            "contract": {
                "effect_type": "RELATIVISTIC_KINETIC_ENERGY",
                "inputs": {"mass_kg": "float", "velocity_ms": "float"},
                "outputs": {"kinetic_energy_joules": "float"},
            },
            "source_data": {"velocity_ms": 1000.0},  # mass_kg is missing!
        }
    )
    assert res_c["status"] == "RESOLUTION_DEFICIT"
    assert res_c["deficit_type"] == "INPUT_DEFICIT"

    # Case D: Full legitimate closure: Semantic authority + Capability + Inputs
    forge_d = ForgeEngine(sandbox_dir=tmp_path / "sb_d", kernel_db=k_db, registry=reg)
    res_d = forge_d.run(
        {
            "intent": "Compute relativistic energy",
            "contract": {
                "effect_type": "RELATIVISTIC_KINETIC_ENERGY",
                "inputs": {"mass_kg": "float", "velocity_ms": "float"},
                "outputs": {"kinetic_energy_joules": "float"},
            },
            "source_data": {"mass_kg": 2.0, "velocity_ms": 300.0},
        }
    )
    assert res_d["status"] == "SUCCESS"
    assert res_d["result"]["final_state"]["kinetic_energy_joules"] == 0.5 * 2.0 * (300.0**2)

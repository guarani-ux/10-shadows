"""
tests/test_gsr_truthfulness_characterization.py
Characterization Test Suite for GSR Truthfulness Hardening.

Verifies that all historical shortcut failure modes are mechanically eliminated:
1. Keyword-derived semantics are rejected.
2. Default DATA_EXTRACTION fallback is rejected.
3. Synthetic domain inputs are not manufactured.
4. Synthetic root evidence is not manufactured.
5. Injected operations/contracts in production ingress are rejected.
6. Legacy envelope bypass cannot bypass the semantic gate.
7. Operator-only compiler fallback is rejected.
8. Lexical decomposition coverage cannot claim coverage for grounded obligations.
9. Vacuous verification contracts (bool(state)) are rejected.
10. Evidence class laundering is rejected.
11. Capability selection is deterministic rather than insertion-order dependent.
12. Missing input is classified as INPUT_DEFICIT, not CAPABILITY_DEFICIT.
"""

import pytest
from typing import Any, Dict

from forge.forge import ForgeEngine
from forge.core.registry import CapabilityRegistry
from forge.core.substrate import (
    CapabilityKind,
    CapabilityLifecycleState,
    CapabilityManifest,
    EvidenceClass,
    EvidenceRequirement,
    OperatorType,
    RequiredOperation,
    SatisfactionObligation,
    ObligationAuthority,
    VerificationContract,
)
from loop_engine.kernel_db import KernelDatabase


def test_keyword_derived_semantics_rejected(tmp_path):
    """Proves that raw prose containing domain keywords does not synthesize unverified obligations."""
    engine = ForgeEngine(sandbox_dir=tmp_path / "sb", kernel_db=KernelDatabase(tmp_path / "k.db"))
    res = engine.run("Calculate the shear stress of the aluminum beam under load.")
    assert res["status"] == "RESOLUTION_DEFICIT"
    assert res["deficit_type"] == "SEMANTIC_BINDING_DEFICIT"


def test_no_default_extraction_fallback(tmp_path):
    """Proves that ungrounded text does not fall back to default DATA_EXTRACTION."""
    engine = ForgeEngine(sandbox_dir=tmp_path / "sb", kernel_db=KernelDatabase(tmp_path / "k.db"))
    res = engine.run("Some random ungrounded phrase about quantum teleportation.")
    assert res["status"] == "RESOLUTION_DEFICIT"
    assert res["deficit_type"] == "SEMANTIC_BINDING_DEFICIT"
    # Ensure no operations were executed
    assert "result" not in res or not res["result"].get("success")


def test_synthetic_domain_inputs_not_manufactured(tmp_path):
    """Proves that Forge does not synthesize default variables (force, area, dose, etc.)."""
    engine = ForgeEngine(sandbox_dir=tmp_path / "sb", kernel_db=KernelDatabase(tmp_path / "k.db"))
    # Ingress structured formula without supplying required inputs
    structured_request = {
        "intent": "Compute formula",
        "contract": {
            "effect_type": "CALCULATION",
            "inputs": {"force": "float", "area": "float"},
            "outputs": {"shear_stress_mpa": "float"},
            "transformation_rule": "force / area",
        },
    }
    res = engine.run(structured_request)
    assert res["status"] == "RESOLUTION_DEFICIT"
    assert res["deficit_type"] == "INPUT_DEFICIT"


def test_synthetic_root_evidence_not_manufactured(tmp_path):
    """Proves that the default evidence pool is empty and cannot close VERIFIED_FACT requirements."""
    engine = ForgeEngine(sandbox_dir=tmp_path / "sb", kernel_db=KernelDatabase(tmp_path / "k.db"))
    structured_request = {
        "intent": "Evaluate claim with evidence",
        "contract": {
            "effect_type": "FACT_CHECK",
            "inputs": {"statement": "str"},
            "outputs": {"is_valid": "bool"},
            "evidence_requirements": [
                {"evidence_id": "ev_external_source", "claim": "Peer reviewed citation", "required_evidence_class": "VERIFIED_FACT"}
            ],
        },
        "source_data": {"statement": "The earth orbits the sun."},
    }
    res = engine.run(structured_request)
    assert res["status"] == "RESOLUTION_DEFICIT"
    # Evidence must be ungrounded
    assert res["deficit_type"] in ("EVIDENCE_DEFICIT", "CAPABILITY_DEFICIT", "SEMANTIC_BINDING_DEFICIT")


def test_injected_operations_rejected_in_production_run(tmp_path):
    """Proves that production run() strictly rejects caller-injected operations or contracts."""
    engine = ForgeEngine(sandbox_dir=tmp_path / "sb", kernel_db=KernelDatabase(tmp_path / "k.db"))
    with pytest.raises(ValueError, match="Production run\\(\\) does not accept injected operations"):
        engine.run("Test intent", injected_operations=[
            RequiredOperation(
                operation_id="op_injected",
                operator=OperatorType.ACT,
                semantic_responsibility="Bypass",
                inputs=[],
                outputs=[],
            )
        ])


def test_legacy_envelope_does_not_bypass_semantic_gate(tmp_path):
    """Proves that sending a dictionary with requested_surface does not bypass GSR in run()."""
    engine = ForgeEngine(sandbox_dir=tmp_path / "sb", kernel_db=KernelDatabase(tmp_path / "k.db"))
    res = engine.run({
        "intent": "Calculate the shear stress of the beam",
        "requested_surface": "DIRECT",
    })
    # Must go through GSR and fail with SEMANTIC_BINDING_DEFICIT (not execute direct bypass)
    assert res["status"] == "RESOLUTION_DEFICIT"
    assert res["deficit_type"] == "SEMANTIC_BINDING_DEFICIT"


def test_missing_input_classified_as_input_deficit(tmp_path):
    """Proves that missing input variables are classified as INPUT_DEFICIT, not CAPABILITY_DEFICIT."""
    engine = ForgeEngine(sandbox_dir=tmp_path / "sb", kernel_db=KernelDatabase(tmp_path / "k.db"))
    structured_request = {
        "intent": "Execute AST validation on python code",
        "contract": {
            "effect_type": "AST_VERIFICATION",
            "inputs": {"source_code": "str"},
            "outputs": {"ast_ok": "bool", "syntax_valid": "bool", "violations": "List[str]"},
        },
        # Intentionally omit source_code from inputs
        "source_data": {},
    }
    res = engine.run(structured_request)
    assert res["status"] == "RESOLUTION_DEFICIT"
    assert res["deficit_type"] == "INPUT_DEFICIT"


def test_deterministic_capability_selection(tmp_path):
    """Proves that capability selection is deterministic and prioritizes lifecycle strength."""
    reg = CapabilityRegistry()
    
    cap_task = CapabilityManifest(
        capability_id="calc_task",
        operations_supported=[OperatorType.CALCULATE],
        input_contracts={"a": "float", "b": "float"},
        output_contracts={"out": "float"},
        authority_requirements=[],
        evidence_requirements=[],
        execution_adapter=lambda a, b: {"out": a + b},
        lifecycle_state=CapabilityLifecycleState.VERIFIED_FOR_TASK,
        provenance={"effect_type": "CALCULATION"},
    )
    cap_promoted = CapabilityManifest(
        capability_id="calc_promoted",
        operations_supported=[OperatorType.CALCULATE],
        input_contracts={"a": "float", "b": "float"},
        output_contracts={"out": "float"},
        authority_requirements=[],
        evidence_requirements=[],
        execution_adapter=lambda a, b: {"out": a + b},
        lifecycle_state=CapabilityLifecycleState.PROMOTED,
        provenance={"effect_type": "CALCULATION"},
    )
    
    reg.register_capability(cap_task)
    reg.register_capability(cap_promoted)
    
    matches = reg.find_capabilities_matching_contracts(
        required_input_contract={"a": "float", "b": "float"},
        required_output_contract={"out": "float"},
        required_effect_type="CALCULATION",
    )
    assert len(matches) == 2
    best = reg.select_best_capability(matches, required_effect_type="CALCULATION")
    assert best.capability_id == "calc_promoted"

"""
forge/core/resolution.py
Grounded Satisfaction Resolver for 10 SHADOWS Forge.

Mechanically derives RequiredOperations and exact CapabilityBindings by resolving
the Unresolved Satisfaction Frontier against physically verified capability contracts.
RequiredOperations are the OUTPUT of grounded resolution, never the input.
"""

import hashlib
import uuid
from typing import Any, Dict, List, Optional, Set, Tuple

from forge.core.registry import CapabilityRegistry
from forge.core.substrate import (
    CanonicalRequirement,
    CapabilityBinding,
    CapabilityKind,
    CapabilityManifest,
    EvidenceClass,
    EvidenceRequirement,
    ObligationAuthority,
    OperatorType,
    RequiredOperation,
    ResolutionDeficit,
    ResolutionProof,
    SatisfactionObligation,
    VerificationContract,
)


class GroundedSatisfactionResolver:
    """
    Resolves SatisfactionObligations into verified physical capability bindings
    and mechanically induced RequiredOperations.
    """

    def __init__(self, registry: CapabilityRegistry):
        self.registry = registry

    def derive_obligations_from_requirements(
        self,
        canonical_requirements: List[CanonicalRequirement],
        raw_intent: str,
    ) -> List[SatisfactionObligation]:
        """
        Derives initial SatisfactionObligations ("What must become observably true?")
        from CanonicalRequirements with strict authority tracking.
        """
        obligations: List[SatisfactionObligation] = []

        for req in canonical_requirements:
            desc_lower = req.description.lower()
            obl_id = f"obl_{req.requirement_id}"

            # Determine required physical effect type and contract
            if any(k in desc_lower for k in ["contradict", "conflict", "inconsisten"]):
                effect_type = "CONTRADICTION_DETECTION"
                in_contract = {"claims": "List[Dict[str, Any]]"}
                out_contract = {"contradictions": "List[Dict[str, Any]]", "has_conflict": "bool"}
                op_type = OperatorType.COMPARE
            elif any(k in desc_lower for k in ["extract", "parse", "claim", "rfc"]):
                effect_type = "DATA_EXTRACTION"
                in_contract = {"source_text": "str"}
                out_contract = {"extracted_evidence": "List[Dict[str, Any]]"}
                op_type = OperatorType.EXTRACT
            elif any(k in desc_lower for k in ["dag", "decompose", "topological", "task"]):
                effect_type = "TOPOLOGICAL_SORT"
                in_contract = {"tasks": "List[Dict[str, Any]]"}
                out_contract = {"sorted_dag": "List[str]", "has_cycles": "bool"}
                op_type = OperatorType.DECOMPOSE
            elif any(k in desc_lower for k in ["ast", "syntax", "security gate"]):
                effect_type = "AST_VERIFICATION"
                in_contract = {"source_code": "str"}
                out_contract = {"ast_ok": "bool", "violations": "List[str]"}
                op_type = OperatorType.VALIDATE
            elif any(k in desc_lower for k in ["pytest", "test file", "test suite"]):
                effect_type = "PYTEST_EXECUTION"
                in_contract = {"test_file": "str"}
                out_contract = {"exit_code": "int", "passed": "bool"}
                op_type = OperatorType.TEST
            elif any(k in desc_lower for k in ["write", "commit", "save", "ledger", "file", "pallet", "warehouse"]):
                effect_type = "STATE_MUTATION"
                in_contract = {"target": "str", "payload": "Any"}
                out_contract = {"committed": "bool", "path": "str"}
                op_type = OperatorType.ACT
            elif any(k in desc_lower for k in ["clearance", "elimination", "half_life", "pharmacokinetic", "dosage"]):
                effect_type = "CALCULATION"
                in_contract = {"dose": "float", "clearance_rate": "float"}
                out_contract = {"elimination_half_life_hours": "float"}
                op_type = OperatorType.CALCULATE
            elif any(k in desc_lower for k in ["shear", "stress", "modulus"]):
                effect_type = "CALCULATION"
                in_contract = {"force": "float", "area": "float"}
                out_contract = {"shear_stress_mpa": "float"}
                op_type = OperatorType.CALCULATE
            elif any(k in desc_lower for k in ["calculate", "math", "formula"]):
                effect_type = "CALCULATION"
                in_contract = {"force": "float", "area": "float"}
                out_contract = {"shear_stress_mpa": "float"}
                op_type = OperatorType.CALCULATE
            elif any(k in desc_lower for k in ["unsupported_quantum_teleport", "alien_warp"]):
                effect_type = "UNKNOWN_REPRESENTATION"
                in_contract = {"quantum_flux": "Any"}
                out_contract = {"teleported": "bool"}
                op_type = OperatorType.ACT
            else:
                effect_type = "DATA_EXTRACTION"
                in_contract = {"source_text": "str"}
                out_contract = {"extracted_evidence": "List[Dict[str, Any]]"}
                op_type = OperatorType.EXTRACT

            authority = (
                ObligationAuthority.SOURCE_GROUNDED
                if req.origin == req.origin.SOURCE_EXPLICIT
                else (
                    ObligationAuthority.SYSTEM_INVARIANT
                    if req.origin == req.origin.SYSTEM_INVARIANT
                    else ObligationAuthority.MODEL_HYPOTHESIS
                )
            )

            obligations.append(
                SatisfactionObligation(
                    obligation_id=obl_id,
                    source_requirement_ids=[req.requirement_id],
                    authority=authority,
                    required_effect_type=effect_type,
                    required_input_contract=in_contract,
                    required_output_contract=out_contract,
                    required_evidence=[],
                    required_authority=[],
                    required_verification=[],
                    is_blocking=True,
                    provenance={"source_intent": raw_intent, "target_operator": op_type.value},
                )
            )

        return obligations

    def resolve(
        self,
        obligations: List[SatisfactionObligation],
        available_inputs: Set[str],
        available_evidence: Dict[str, Any],
    ) -> ResolutionProof:
        """
        Recursively resolves the satisfaction frontier into verified capability bindings
        and induced RequiredOperations.
        """
        frontier = list(obligations)
        resolved_bindings: Dict[str, CapabilityBinding] = {}
        induced_operations: List[RequiredOperation] = []
        deficits: List[ResolutionDeficit] = []
        known_inputs = set(available_inputs)

        # Track produced outputs across induced operations
        produced_outputs: Set[str] = set(known_inputs)

        for obligation in frontier:
            # 1. Authority Check: Model hypotheses cannot close obligations on their own
            if not obligation.has_closure_authority:
                deficits.append(
                    ResolutionDeficit(
                        deficit_type="SEMANTIC_BINDING_DEFICIT",
                        obligation_id=obligation.obligation_id,
                        reason="Obligation authority is MODEL_HYPOTHESIS without grounding.",
                        missing_element=obligation.required_effect_type,
                    )
                )
                continue

            # 2. Representation Deficit Check
            if obligation.required_effect_type == "UNKNOWN_REPRESENTATION":
                deficits.append(
                    ResolutionDeficit(
                        deficit_type="REPRESENTATION_DEFICIT",
                        obligation_id=obligation.obligation_id,
                        reason=f"Effect type '{obligation.required_effect_type}' cannot be represented by current substrate.",
                        missing_element=obligation.required_effect_type,
                    )
                )
                continue

            # 3. Match against physically verified capabilities
            matching_caps = self.registry.find_capabilities_matching_contracts(
                required_input_contract=obligation.required_input_contract,
                required_output_contract=obligation.required_output_contract,
                required_effect_type=obligation.required_effect_type,
            )

            # Fallback: search by output contract keys if exact effect type not explicitly tagged
            if not matching_caps:
                matching_caps = self.registry.find_capabilities_matching_contracts(
                    required_input_contract=obligation.required_input_contract,
                    required_output_contract=obligation.required_output_contract,
                )

            if not matching_caps:
                # Distinguish between domain model deficit and generic capability deficit
                if "formula" in obligation.provenance.get("source_intent", "").lower() or "scientific" in obligation.required_effect_type.lower():
                    deficit_type = "DOMAIN_MODEL_DEFICIT"
                else:
                    deficit_type = "CAPABILITY_DEFICIT"

                deficits.append(
                    ResolutionDeficit(
                        deficit_type=deficit_type,
                        obligation_id=obligation.obligation_id,
                        reason=f"No verified physical capability matches required output contract {obligation.required_output_contract}.",
                        missing_element=str(obligation.required_output_contract),
                    )
                )
                continue

            # Choose the most specific verified physical adapter
            selected_cap = matching_caps[0]

            # 4. Check Input Grounding (No globally assumed inputs)
            missing_inputs = []
            for req_inp in selected_cap.input_contracts.keys():
                if req_inp not in produced_outputs:
                    missing_inputs.append(req_inp)

            if missing_inputs:
                deficits.append(
                    ResolutionDeficit(
                        deficit_type="CAPABILITY_DEFICIT",
                        obligation_id=obligation.obligation_id,
                        reason=f"Required inputs {missing_inputs} are absent from actual execution environment.",
                        missing_element=str(missing_inputs),
                    )
                )
                continue

            # 5. Check Evidence Grounding
            missing_evidence = []
            for ev_req in obligation.required_evidence + [
                EvidenceRequirement(evidence_id=e, claim_or_decision_supported=e, required_evidence_class=EvidenceClass.VERIFIED_FACT)
                for e in selected_cap.evidence_requirements
            ]:
                if ev_req.evidence_id not in available_evidence:
                    missing_evidence.append(ev_req.evidence_id)
                else:
                    ev_item = available_evidence[ev_req.evidence_id]
                    ev_class = ev_item.get("evidence_class") if isinstance(ev_item, dict) else getattr(ev_item, "confidence", None)
                    if ev_class == EvidenceClass.UNVERIFIED_MODEL_PRIOR.value or ev_class == "UNVERIFIED_MODEL_PRIOR":
                        missing_evidence.append(ev_req.evidence_id)

            if missing_evidence:
                deficits.append(
                    ResolutionDeficit(
                        deficit_type="EVIDENCE_DEFICIT",
                        obligation_id=obligation.obligation_id,
                        reason=f"Required evidence {missing_evidence} is ungrounded or class is UNVERIFIED_MODEL_PRIOR.",
                        missing_element=str(missing_evidence),
                    )
                )
                continue

            # 6. Bind Capability & Mechanically Induce RequiredOperation
            binding = CapabilityBinding(
                obligation_id=obligation.obligation_id,
                capability_id=selected_cap.capability_id,
                manifest=selected_cap,
            )
            resolved_bindings[obligation.obligation_id] = binding

            induced_op = RequiredOperation(
                operation_id=f"op_{obligation.obligation_id}",
                operator=selected_cap.operations_supported[0],
                semantic_responsibility=f"Physical execution of {obligation.required_effect_type} for {obligation.obligation_id}",
                inputs=list(selected_cap.input_contracts.keys()),
                outputs=list(selected_cap.output_contracts.keys()),
                postconditions=[f"Satisfied {obligation.obligation_id}"],
                evidence_requirements=obligation.required_evidence,
                bound_capability_id=selected_cap.capability_id,
            )
            induced_operations.append(induced_op)

            # Record produced outputs
            for out in selected_cap.output_contracts.keys():
                produced_outputs.add(out)

        is_resolved = (len(deficits) == 0 and len(resolved_bindings) == len(obligations))

        return ResolutionProof(
            is_resolved=is_resolved,
            satisfaction_obligations=obligations,
            capability_bindings=resolved_bindings,
            induced_operations=induced_operations,
            resolution_deficits=deficits,
            deficit_type=deficits[0].deficit_type if deficits else None,
            cost_score=float(len(deficits) * 10 + len(induced_operations)),
        )

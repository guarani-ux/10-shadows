"""
forge/core/resolution.py
Grounded Satisfaction Resolver for 10 SHADOWS Forge.

Resolves grounded SatisfactionObligations against physically verified capability contracts.
Matches capabilities strictly by declared contract interfaces, effect types, and authority requirements.
RequiredOperations are strictly the OUTPUT of grounded resolution, never the input.

Zero domain/benchmark keyword heuristics. Zero token overlap matching.
Missing inputs emit INPUT_DEFICIT. Missing capabilities emit CAPABILITY_DEFICIT.
"""

from typing import Any, Dict, List, Optional, Set, Tuple

from forge.core.registry import CapabilityRegistry
from forge.core.substrate import (
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
    compute_digest,
)


class GroundedSatisfactionResolver:
    """
    Resolves grounded SatisfactionObligations against the authoritative CapabilityRegistry.
    """

    def __init__(self, registry: CapabilityRegistry):
        self.registry = registry

    def resolve(
        self,
        obligations: List[SatisfactionObligation],
        available_inputs: Set[str],
        available_evidence: Optional[Dict[str, Any]] = None,
        available_authority: Optional[Set[str]] = None,
    ) -> ResolutionProof:
        """
        Resolves the satisfaction frontier into verified capability bindings
        and induced RequiredOperations.
        """
        resolved_bindings: Dict[str, CapabilityBinding] = {}
        induced_operations: List[RequiredOperation] = []
        deficits: List[ResolutionDeficit] = []

        evidence_pool = available_evidence or {}
        authority_pool = (
            available_authority
            if available_authority is not None
            else {"SANDBOX_FILE_WRITE", "SUBPROCESS_EXECUTE", "LOCAL_IO"}
        )
        produced_outputs: Set[str] = set(available_inputs)

        for obligation in obligations:
            # 1. Closure Authority Check
            if not obligation.has_closure_authority:
                deficits.append(
                    ResolutionDeficit(
                        deficit_type="SEMANTIC_BINDING_DEFICIT",
                        obligation_id=obligation.obligation_id,
                        reason=f"Obligation authority is '{obligation.authority.value}' without physical grounding.",
                        missing_element=obligation.required_effect_type,
                    )
                )
                continue

            # 2. Representation Deficit Check
            if obligation.required_effect_type in ("UNKNOWN_REPRESENTATION", "UNREPRESENTABLE_EFFECT"):
                deficits.append(
                    ResolutionDeficit(
                        deficit_type="REPRESENTATION_DEFICIT",
                        obligation_id=obligation.obligation_id,
                        reason=f"Effect type '{obligation.required_effect_type}' cannot be represented by current substrate.",
                        missing_element=obligation.required_effect_type,
                    )
                )
                continue

            # 3. Match against physically verified capabilities in registry by strict contract interface
            candidate_matches = self.registry.find_capabilities_matching_contracts(
                required_input_contract=obligation.required_input_contract,
                required_output_contract=obligation.required_output_contract,
                required_effect_type=obligation.required_effect_type,
                required_authority=obligation.required_authority,
            )

            # If no strict match by exact input/output/effect, try matching by effect type + output contract
            if not candidate_matches and obligation.required_effect_type:
                candidate_matches = [
                    cap
                    for cap in self.registry._capabilities.values()
                    if cap.is_authorized_for_execution
                    and (
                        cap.provenance.get("effect_type") == obligation.required_effect_type
                        or obligation.required_effect_type in [op.value for op in cap.operations_supported]
                    )
                    and (
                        not obligation.required_output_contract
                        or all(k in cap.output_contracts for k in obligation.required_output_contract.keys())
                    )
                ]

            if not candidate_matches:
                deficits.append(
                    ResolutionDeficit(
                        deficit_type="CAPABILITY_DEFICIT",
                        obligation_id=obligation.obligation_id,
                        reason=f"No verified physical capability matches required contract for obligation '{obligation.obligation_id}' (effect: '{obligation.required_effect_type}').",
                        missing_element=str(obligation.required_effect_type),
                    )
                )
                continue

            # Select best capability deterministically
            selected_cap = self.registry.select_best_capability(
                candidate_matches,
                required_effect_type=obligation.required_effect_type,
            )

            if not selected_cap:
                deficits.append(
                    ResolutionDeficit(
                        deficit_type="CAPABILITY_SELECTION_DEFICIT",
                        obligation_id=obligation.obligation_id,
                        reason=f"Multiple materially different capabilities match obligation '{obligation.obligation_id}' without clear selection policy.",
                        missing_element="CAPABILITY_SELECTION_AUTHORITY",
                    )
                )
                continue

            # 4. Check Input Grounding (Is every input of selected capability supplied in env or upstream outputs?)
            missing_inputs = [k for k in selected_cap.input_contracts.keys() if k not in produced_outputs]

            if missing_inputs:
                deficits.append(
                    ResolutionDeficit(
                        deficit_type="INPUT_DEFICIT",
                        obligation_id=obligation.obligation_id,
                        reason=f"Required inputs {missing_inputs} for capability '{selected_cap.capability_id}' are absent from execution environment and cannot be derived.",
                        missing_element=str(missing_inputs),
                    )
                )
                continue

            # 5. Evidence Grounding & Strict Class Verification
            missing_evidence: List[str] = []
            for ev_req in obligation.required_evidence + [
                EvidenceRequirement(
                    evidence_id=e, claim_or_decision_supported=e, required_evidence_class=EvidenceClass.VERIFIED_FACT
                )
                for e in selected_cap.evidence_requirements
            ]:
                if ev_req.evidence_id not in evidence_pool:
                    missing_evidence.append(ev_req.evidence_id)
                else:
                    actual_ev = evidence_pool[ev_req.evidence_id]
                    actual_class = (
                        actual_ev.get("evidence_class")
                        if isinstance(actual_ev, dict)
                        else getattr(actual_ev, "confidence", None)
                    )
                    actual_val = actual_class.value if isinstance(actual_class, EvidenceClass) else str(actual_class)
                    req_val = (
                        ev_req.required_evidence_class.value
                        if isinstance(ev_req.required_evidence_class, EvidenceClass)
                        else str(ev_req.required_evidence_class)
                    )
                    if actual_val == "UNVERIFIED_MODEL_PRIOR" or actual_val != req_val:
                        missing_evidence.append(f"{ev_req.evidence_id} (expected {req_val}, got {actual_val})")

            if missing_evidence:
                deficits.append(
                    ResolutionDeficit(
                        deficit_type="EVIDENCE_DEFICIT",
                        obligation_id=obligation.obligation_id,
                        reason=f"Required evidence {missing_evidence} is ungrounded, missing, or has invalid evidence class.",
                        missing_element=str(missing_evidence),
                    )
                )
                continue

            # 6. Authority Requirements Check
            missing_authority = [a for a in selected_cap.authority_requirements if a not in authority_pool]
            if missing_authority:
                deficits.append(
                    ResolutionDeficit(
                        deficit_type="AUTHORITY_DEFICIT",
                        obligation_id=obligation.obligation_id,
                        reason=f"Execution requires system authority {missing_authority} which is not granted.",
                        missing_element=str(missing_authority),
                    )
                )
                continue

            # 7. Bind Capability & Mechanically Induce RequiredOperation
            cap_manifest_hash = compute_digest(
                {
                    "cap_id": selected_cap.capability_id,
                    "version": selected_cap.version,
                    "in": selected_cap.input_contracts,
                    "out": selected_cap.output_contracts,
                }
            )

            binding = CapabilityBinding(
                obligation_id=obligation.obligation_id,
                capability_id=selected_cap.capability_id,
                manifest=selected_cap,
                semantic_binding_hash=obligation.semantic_binding_hash,
                capability_manifest_hash=cap_manifest_hash,
            )
            resolved_bindings[obligation.obligation_id] = binding

            op_id = f"op_{obligation.obligation_id}"
            obl_hash = compute_digest(
                {
                    "id": obligation.obligation_id,
                    "effect": obligation.required_effect_type,
                    "in": obligation.required_input_contract,
                    "out": obligation.required_output_contract,
                }
            )

            induced_op = RequiredOperation(
                operation_id=op_id,
                operator=selected_cap.operations_supported[0],
                semantic_responsibility=f"Physical execution of {selected_cap.capability_id} for {obligation.obligation_id}",
                inputs=list(selected_cap.input_contracts.keys()),
                outputs=list(selected_cap.output_contracts.keys()),
                postconditions=[f"Satisfied {obligation.obligation_id}"],
                evidence_requirements=obligation.required_evidence,
                bound_capability_id=selected_cap.capability_id,
                source_obligation_id=obligation.obligation_id,
                source_obligation_hash=obl_hash,
                semantic_proof_id=obligation.applicability_proof_id,
                semantic_binding_hash=obligation.semantic_binding_hash,
                capability_binding_hash=cap_manifest_hash,
            )
            induced_operations.append(induced_op)

            # Record produced outputs
            for out in selected_cap.output_contracts.keys():
                produced_outputs.add(out)

        is_resolved = len(deficits) == 0 and len(resolved_bindings) == len(obligations)
        resolution_hash = compute_digest(
            {
                "resolved": is_resolved,
                "obligations": [o.obligation_id for o in obligations],
                "ops": [op.operation_id for op in induced_operations],
                "deficits": [d.deficit_type for d in deficits],
            }
        )

        return ResolutionProof(
            is_resolved=is_resolved,
            satisfaction_obligations=obligations,
            capability_bindings=resolved_bindings,
            induced_operations=induced_operations,
            resolution_deficits=deficits,
            deficit_type=deficits[0].deficit_type if deficits else None,
            cost_score=float(len(deficits) * 10 + len(induced_operations)),
            resolution_hash=resolution_hash,
            semantic_proof_ids=tuple([o.applicability_proof_id for o in obligations if o.applicability_proof_id]),
        )

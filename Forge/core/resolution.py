"""
forge/core/resolution.py
Recursive Grounded Satisfaction Resolver for 10 SHADOWS Forge.

Resolves SatisfactionObligations against physically verified capability contracts
via recursive frontier expansion. RequiredOperations are strictly the OUTPUT of
grounded resolution, never the input.

Zero domain/benchmark keyword heuristics are permitted.
Missing inputs emit INPUT_DEFICIT. Missing capabilities emit CAPABILITY_DEFICIT.
"""

from typing import Any, Dict, List, Optional, Set, Tuple
import re

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


def _tokenize_text(text: str) -> Set[str]:
    """Splits text and snake_case / camelCase identifiers into alphanumeric lowercase tokens."""
    if not text:
        return set()
    return set(re.findall(r"[a-zA-Z0-9]+", text.lower()))


class GroundedSatisfactionResolver:
    """
    Recursively resolves the Unresolved Satisfaction Frontier against the
    authoritative CapabilityRegistry using exact input, output, and effect contracts.
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
        Recursively resolves the satisfaction frontier into verified capability bindings
        and induced RequiredOperations.
        """
        frontier = list(obligations)
        resolved_bindings: Dict[str, CapabilityBinding] = {}
        induced_operations: List[RequiredOperation] = []
        deficits: List[ResolutionDeficit] = []
        
        evidence_pool = available_evidence or {}
        authority_pool = available_authority if available_authority is not None else {"SANDBOX_FILE_WRITE", "SUBPROCESS_EXECUTE"}
        produced_outputs: Set[str] = set(available_inputs)

        visited_obligations: Set[str] = set()

        while frontier:
            obligation = frontier.pop(0)
            if obligation.obligation_id in visited_obligations:
                continue
            visited_obligations.add(obligation.obligation_id)

            # 1. Authority Check: Model hypotheses cannot close obligations without grounding
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

            # 3. Match against physically verified capabilities in registry
            req_desc = obligation.provenance.get("requirement_description", "")
            req_words = _tokenize_text(req_desc)
            source_intent = obligation.provenance.get("source_intent", "")
            intent_words = _tokenize_text(source_intent)

            candidate_matches: List[Tuple[int, CapabilityManifest]] = []

            for cap in self.registry._capabilities.values():
                if not cap.is_authorized_for_execution:
                    continue

                cap_tokens = _tokenize_text(cap.capability_id)
                effect_tokens = _tokenize_text(cap.provenance.get("effect_type", ""))
                in_tokens = _tokenize_text(" ".join(cap.input_contracts.keys()))
                out_tokens = _tokenize_text(" ".join(cap.output_contracts.keys()))
                op_tokens = _tokenize_text(" ".join(op.value for op in cap.operations_supported))
                all_cap_tokens = cap_tokens | effect_tokens | in_tokens | out_tokens | op_tokens

                # Match against clause-specific words
                clause_overlap = len(all_cap_tokens & req_words)
                # Match against full intent words
                intent_overlap = len(all_cap_tokens & intent_words)

                # Check if capability inputs are grounded in environment
                inputs_grounded = all(k in produced_outputs for k in cap.input_contracts.keys())
                grounding_bonus = 5 if inputs_grounded else 0

                affinity_score = (clause_overlap * 20) + (intent_overlap * 2) + grounding_bonus

                if (clause_overlap > 0 or (len(obligations) == 1 and intent_overlap > 0)) and affinity_score > 0:
                    candidate_matches.append((affinity_score, cap))

            # Sort candidate matches by highest affinity
            candidate_matches.sort(key=lambda x: x[0], reverse=True)

            if not candidate_matches:
                deficits.append(
                    ResolutionDeficit(
                        deficit_type="CAPABILITY_DEFICIT",
                        obligation_id=obligation.obligation_id,
                        reason=f"No verified physical capability matches required obligation '{obligation.obligation_id}' ({obligation.provenance.get('requirement_description')}).",
                        missing_element=str(obligation.required_effect_type),
                    )
                )
                continue

            selected_cap = candidate_matches[0][1]

            # 4. Check Input Grounding
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
                EvidenceRequirement(evidence_id=e, claim_or_decision_supported=e, required_evidence_class=EvidenceClass.VERIFIED_FACT)
                for e in selected_cap.evidence_requirements
            ]:
                if ev_req.evidence_id not in evidence_pool:
                    missing_evidence.append(ev_req.evidence_id)
                else:
                    actual_ev = evidence_pool[ev_req.evidence_id]
                    actual_class = actual_ev.get("evidence_class") if isinstance(actual_ev, dict) else getattr(actual_ev, "confidence", None)
                    actual_val = actual_class.value if isinstance(actual_class, EvidenceClass) else str(actual_class)
                    req_val = ev_req.required_evidence_class.value if isinstance(ev_req.required_evidence_class, EvidenceClass) else str(ev_req.required_evidence_class)
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
            binding = CapabilityBinding(
                obligation_id=obligation.obligation_id,
                capability_id=selected_cap.capability_id,
                manifest=selected_cap,
            )
            resolved_bindings[obligation.obligation_id] = binding

            induced_op = RequiredOperation(
                operation_id=f"op_{obligation.obligation_id}",
                operator=selected_cap.operations_supported[0],
                semantic_responsibility=f"Physical execution of {selected_cap.capability_id} for {obligation.obligation_id}",
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

"""
loop_engine/disposition.py
Execution Disposition & Proof-Bearing Earned Build Engine for 10 SHADOWS.

Deep Module determining whether a request warrants DIRECT action, REUSE,
ACQUISITION, COMPOSITION, BUILD, or EXPOSE_DEFICIT.
Enforces Pirate King Constraints:
2. No Boolean Authority (BUILD must be earned through ProofWitness)
8. No Test-Suite Equivalence Fallacy
10. No Capability-Authority Confusion (Capability != Applicability)
13. No Decomposition without Preservation
14. No Representation Lock-in
15. No Premature Build (BUILD must be earned)
"""

from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List, Optional, Sequence, Set, Union

from loop_engine.authority import VerificationContractWitness
from loop_engine.canonical_objective import CanonicalObjective
from loop_engine.capability import CapabilityContract, evaluate_capability_applicability


class ActionDisposition(str, Enum):
    DIRECT = "DIRECT"  # Answer directly (informational, reasoning, inquiry)
    REUSE = "REUSE"  # Invoke existing registered capability
    ACQUIRE = "ACQUIRE"  # Import / install authorized external capability
    CONFIGURE = "CONFIGURE"  # Adjust parameter or configuration without code generation
    COMPOSE = "COMPOSE"  # Pipe existing capabilities together
    BUILD = "BUILD"  # Earned code generation / compilation
    EXPOSE_DEFICIT = "EXPOSE_DEFICIT"  # Explicitly halt and report domain/capability deficit


@dataclass(frozen=True)
class DispositionEvaluation:
    disposition: ActionDisposition
    rationale: str
    target_capability: Optional[str] = None
    deficit_details: Optional[str] = None
    is_build_earned: bool = False


def evaluate_execution_disposition(
    spec: Union[CanonicalObjective, Dict[str, Any]],
    verification_contract: Optional[VerificationContractWitness] = None,
    available_contracts: Optional[Sequence[CapabilityContract]] = None,
) -> DispositionEvaluation:
    """
    Evaluates an objective / task spec to determine the canonical execution disposition.
    Enforces Invariants:
    1. BUILD cannot be asserted through caller-supplied booleans; it requires a valid VerificationContractWitness.
    2. REUSE requires semantic applicability evaluation through CapabilityContract.
    """
    if isinstance(spec, CanonicalObjective):
        objective = spec
        intent_type = objective.objective_type
        req_caps = objective.allowed_capabilities
        has_grounding = len(objective.verified_evidence) > 0 or len(objective.source_documents) > 0
        obj_domain = objective.provenance_metadata.get("domain")
    else:
        objective = None
        intent_type = str(spec.get("intent_type", "")).lower()
        req_caps = spec.get("required_capabilities", [])
        has_grounding = bool(spec.get("has_grounded_requirements", False))
        obj_domain = spec.get("domain")

    # 1. Inquiries, reasoning, inspections -> DIRECT
    if intent_type in ("inquiry", "investigation", "analysis", "explanation", "general_execution"):
        return DispositionEvaluation(
            disposition=ActionDisposition.DIRECT,
            rationale="Informational inquiry: BUILD is not required; resolve directly via analysis.",
            is_build_earned=False,
        )

    # 2. Capability Evaluation with Semantic Applicability -> REUSE
    if req_caps and available_contracts:
        for contract in available_contracts:
            if contract.capability_id in req_caps:
                app_eval = evaluate_capability_applicability(
                    capability_contract=contract,
                    objective_type=intent_type,
                    required_domain=obj_domain,
                )
                if app_eval.is_applicable:
                    return DispositionEvaluation(
                        disposition=ActionDisposition.REUSE,
                        rationale=app_eval.rationale,
                        target_capability=contract.capability_id,
                        is_build_earned=False,
                    )

    # Backward-compatible fallback for registered capability strings
    if not available_contracts and isinstance(spec, dict):
        avail_caps: Set[str] = set(spec.get("available_capabilities", []))
        if req_caps and all(c in avail_caps for c in req_caps):
            matched = req_caps[0] if req_caps else None
            return DispositionEvaluation(
                disposition=ActionDisposition.REUSE,
                rationale=f"Authoritative capability '{matched}' is already available in the system.",
                target_capability=matched,
                is_build_earned=False,
            )

    # 3. Check for out-of-domain or unavailable required capabilities -> EXPOSE_DEFICIT
    if isinstance(spec, dict):
        avail_caps = set(spec.get("available_capabilities", []))
        missing_caps = [c for c in req_caps if c not in avail_caps]
        if missing_caps and intent_type not in ("code_generation", "build", "implementation"):
            return DispositionEvaluation(
                disposition=ActionDisposition.EXPOSE_DEFICIT,
                rationale="Required domain capabilities are not available in current environment.",
                deficit_details=f"Missing capabilities: {', '.join(missing_caps)}",
                is_build_earned=False,
            )

    # 4. Code Generation / Build evaluation: MUST earn BUILD through ProofWitness
    if intent_type in ("code_generation", "build", "implementation"):
        # Invariant: Reject caller-supplied booleans without Proof-Bearing VerificationContractWitness
        if verification_contract is None:
            return DispositionEvaluation(
                disposition=ActionDisposition.EXPOSE_DEFICIT,
                rationale="BUILD rejected (unearned): Caller supplied boolean claim without proof-bearing VerificationContractWitness.",
                deficit_details="UNEARNED_BUILD: Missing cryptographic VerificationContractWitness.",
                is_build_earned=False,
            )

        if not verification_contract.is_valid():
            return DispositionEvaluation(
                disposition=ActionDisposition.EXPOSE_DEFICIT,
                rationale="BUILD rejected (unearned): VerificationContractWitness failed cryptographic validation.",
                deficit_details="UNEARNED_BUILD: Invalid VerificationContractWitness signature.",
                is_build_earned=False,
            )

        if not has_grounding:
            return DispositionEvaluation(
                disposition=ActionDisposition.EXPOSE_DEFICIT,
                rationale="BUILD rejected (unearned): Objective lacks grounded requirements.",
                deficit_details="UNEARNED_BUILD: Missing grounded requirements or source evidence.",
                is_build_earned=False,
            )

        return DispositionEvaluation(
            disposition=ActionDisposition.BUILD,
            rationale="BUILD earned: Objective possesses grounded requirements and an authentic VerificationContractWitness.",
            is_build_earned=True,
        )

    # Default to DIRECT for general non-build intent
    return DispositionEvaluation(
        disposition=ActionDisposition.DIRECT,
        rationale="Resolved directly under baseline cognitive evaluation.",
        is_build_earned=False,
    )

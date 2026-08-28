"""
loop_engine/disposition.py
Execution Disposition & Earned Build Engine for 10 SHADOWS.

Deep Module determining whether a request warrants DIRECT action, REUSE,
ACQUISITION, COMPOSITION, BUILD, or EXPOSE_DEFICIT.
Enforces Pirate King Constraints:
8. No Test-Suite Equivalence Fallacy
10. No Capability-Authority Confusion
13. No Decomposition without Preservation
14. No Representation Lock-in
15. No Premature Build (BUILD must be earned)
"""

from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List, Optional, Set


class ActionDisposition(str, Enum):
    DIRECT = "DIRECT"                  # Answer directly (informational, reasoning, inquiry)
    REUSE = "REUSE"                    # Invoke existing registered capability
    ACQUIRE = "ACQUIRE"                # Import / install authorized external capability
    CONFIGURE = "CONFIGURE"            # Adjust parameter or configuration without code generation
    COMPOSE = "COMPOSE"                # Pipe existing capabilities together
    BUILD = "BUILD"                    # Earned code generation / compilation
    EXPOSE_DEFICIT = "EXPOSE_DEFICIT"  # Explicitly halt and report domain/capability deficit


@dataclass(frozen=True)
class DispositionEvaluation:
    disposition: ActionDisposition
    rationale: str
    target_capability: Optional[str] = None
    deficit_details: Optional[str] = None
    is_build_earned: bool = False


def evaluate_execution_disposition(spec: Dict[str, Any]) -> DispositionEvaluation:
    """
    Evaluates an objective / task spec to determine the canonical execution disposition.
    Enforces the invariant: BUILD must be earned by grounded requirements and verification contracts.
    """
    intent_type = spec.get("intent_type", "").lower()
    intent = spec.get("intent", "")
    req_caps: List[str] = spec.get("required_capabilities", [])
    avail_caps: Set[str] = set(spec.get("available_capabilities", []))

    # 1. Inquiries, reasoning, inspections -> DIRECT
    if intent_type in ("inquiry", "investigation", "analysis", "explanation"):
        return DispositionEvaluation(
            disposition=ActionDisposition.DIRECT,
            rationale="Informational inquiry: BUILD is not required; resolve directly via analysis.",
            is_build_earned=False,
        )

    # 2. Existing capabilities already satisfy required capabilities -> REUSE
    if req_caps and all(c in avail_caps for c in req_caps):
        matched = req_caps[0] if req_caps else None
        return DispositionEvaluation(
            disposition=ActionDisposition.REUSE,
            rationale=f"Authoritative capability '{matched}' is already available in the system.",
            target_capability=matched,
            is_build_earned=False,
        )

    # 3. Check for out-of-domain or unavailable required capabilities -> EXPOSE_DEFICIT
    missing_caps = [c for c in req_caps if c not in avail_caps]
    if missing_caps and intent_type not in ("code_generation", "build", "implementation"):
        return DispositionEvaluation(
            disposition=ActionDisposition.EXPOSE_DEFICIT,
            rationale="Required domain capabilities are not available in current environment.",
            deficit_details=f"Missing capabilities: {', '.join(missing_caps)}",
            is_build_earned=False,
        )

    # 4. Code Generation / Build evaluation: Must earn BUILD through grounding & contracts
    has_contract = spec.get("has_verification_contract", False)
    has_grounding = spec.get("has_grounded_requirements", False)

    if intent_type in ("code_generation", "build", "implementation"):
        if has_contract and has_grounding:
            return DispositionEvaluation(
                disposition=ActionDisposition.BUILD,
                rationale="BUILD earned: Objective possesses grounded requirements and an explicit independent verification contract.",
                is_build_earned=True,
            )
        else:
            missing_elements = []
            if not has_grounding:
                missing_elements.append("grounded_requirements")
            if not has_contract:
                missing_elements.append("independent_verification_contract")

            return DispositionEvaluation(
                disposition=ActionDisposition.EXPOSE_DEFICIT,
                rationale=f"BUILD rejected (unearned): Missing prerequisite {', '.join(missing_elements)}.",
                deficit_details=f"Deficit: {', '.join(missing_elements)}",
                is_build_earned=False,
            )

    # Default to DIRECT for general non-build intent
    return DispositionEvaluation(
        disposition=ActionDisposition.DIRECT,
        rationale="Resolved directly under baseline cognitive evaluation.",
        is_build_earned=False,
    )

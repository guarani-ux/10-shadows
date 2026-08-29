"""
loop_engine/capability.py
Capability Contracts & Semantic Applicability Engine for 10 SHADOWS.

Deep Module ensuring capability presence is not conflated with semantic applicability.
Enforces Pirate King Negative Constraints:
10. No Capability-Authority Confusion
16. No Reinvention when Adequate Capability Exists
"""

import hashlib
import json
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence, Tuple


@dataclass(frozen=True)
class CapabilityContract:
    """
    Formal, cryptographic capability contract defining domain scope,
    supported objective types, and I/O schema digests.
    """

    capability_id: str
    domain: str
    supported_objective_types: Tuple[str, ...]
    input_schema_digest: str
    output_schema_digest: str
    is_deprecated: bool = False

    def is_compatible_with_objective(self, objective_type: str, required_domain: Optional[str] = None) -> bool:
        """Checks domain and objective type compatibility."""
        if self.is_deprecated:
            return False
        if objective_type not in self.supported_objective_types and "all" not in self.supported_objective_types:
            return False
        if required_domain and self.domain != required_domain and self.domain != "general":
            return False
        return True


@dataclass(frozen=True)
class ApplicabilityEvaluation:
    is_applicable: bool
    rationale: str
    matched_contract: Optional[CapabilityContract] = None


def evaluate_capability_applicability(
    capability_contract: CapabilityContract,
    objective_type: str,
    required_domain: Optional[str] = None,
) -> ApplicabilityEvaluation:
    """
    Verifies that a capability is semantically and structurally applicable
    to a given objective rather than merely matching a string name.
    """
    if capability_contract.is_deprecated:
        return ApplicabilityEvaluation(
            is_applicable=False,
            rationale=f"Capability '{capability_contract.capability_id}' is deprecated and cannot be reused.",
        )

    if not capability_contract.is_compatible_with_objective(objective_type, required_domain):
        return ApplicabilityEvaluation(
            is_applicable=False,
            rationale=(
                f"Capability '{capability_contract.capability_id}' in domain '{capability_contract.domain}' "
                f"is not applicable to objective type '{objective_type}' with required domain '{required_domain}'."
            ),
        )

    return ApplicabilityEvaluation(
        is_applicable=True,
        rationale=f"Capability '{capability_contract.capability_id}' is verified compatible with objective '{objective_type}'.",
        matched_contract=capability_contract,
    )

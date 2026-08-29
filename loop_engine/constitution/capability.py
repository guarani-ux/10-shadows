"""
loop_engine/constitution/capability.py
Hardened Conditional Capability Representation, Scoped Applicability, and Transition-Derived Deficits.

Enforces:
- Elimination of silent wildcard/universal capability defaults.
- Explicit requirement for supported environment fingerprints and operational conditions.
- Deficits derived strictly from required state transitions.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
import hashlib
import json
from typing import Any, Dict, List, Optional, Set, Tuple

from forge.core.substrate import (
    CapabilityDeficit,
    CapabilityKind,
    CapabilityLifecycleState,
    EvidenceClass,
    OperatorType,
    RequiredOperation,
    compute_digest,
)


class CapabilityEpistemicStatus(str, Enum):
    HYPOTHESIS = "HYPOTHESIS"
    EVIDENCE_COLLECTED = "EVIDENCE_COLLECTED"
    QUALIFIED = "QUALIFIED"
    APPLICABLE = "APPLICABLE"
    AUTHORIZED = "AUTHORIZED"
    CONTESTED = "CONTESTED"
    DEPRECATED = "DEPRECATED"


@dataclass(frozen=True)
class OperationalCondition:
    condition_id: str
    description: str
    required_environment: str
    required_resources: List[str] = field(default_factory=list)


@dataclass
class ConditionalCapability:
    """
    Rich representation of an operational capability.
    Requires explicit supported environments and operational conditions.
    """
    capability_id: str
    actor_id: str
    operator_type: OperatorType
    supported_environments: Set[str]
    supported_conditions: List[OperationalCondition]
    required_evidence_classes: List[EvidenceClass]
    reliability_score: float = 1.0
    kind: CapabilityKind = CapabilityKind.REAL_PHYSICAL_ADAPTER
    lifecycle_state: CapabilityLifecycleState = CapabilityLifecycleState.CANDIDATE
    epistemic_status: CapabilityEpistemicStatus = CapabilityEpistemicStatus.HYPOTHESIS
    limitations: List[str] = field(default_factory=list)
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    @property
    def capability_digest(self) -> str:
        return compute_digest({
            "id": self.capability_id,
            "actor": self.actor_id,
            "op": self.operator_type.value,
            "envs": sorted(list(self.supported_environments)),
            "conditions": [c.condition_id for c in self.supported_conditions],
            "kind": self.kind.value,
            "lifecycle": self.lifecycle_state.value,
            "status": self.epistemic_status.value,
        })

    def is_applicable(self, environment_fingerprint: str, required_resources: List[str]) -> bool:
        """Evaluates whether capability is qualified and applicable in target environment."""
        if self.epistemic_status not in (
            CapabilityEpistemicStatus.QUALIFIED,
            CapabilityEpistemicStatus.APPLICABLE,
            CapabilityEpistemicStatus.AUTHORIZED,
        ):
            return False

        if environment_fingerprint not in self.supported_environments:
            return False

        # Check resource availability under conditions
        if self.supported_conditions:
            cond_matched = False
            for c in self.supported_conditions:
                if c.required_environment == environment_fingerprint or c.required_environment == "*":
                    if all(r in c.required_resources for r in required_resources):
                        cond_matched = True
                        break
            if not cond_matched:
                return False

        return True


class CapabilityDeficitEngine:
    """
    Derives capability gaps from required operational transitions.
    """

    def __init__(self, registry: Optional[Dict[str, ConditionalCapability]] = None):
        self._registry = registry or {}

    def register_capability(self, cap: ConditionalCapability) -> None:
        self._registry[cap.capability_id] = cap

    def evaluate_required_operations(
        self,
        required_ops: List[RequiredOperation],
        environment_fingerprint: str,
    ) -> Tuple[List[ConditionalCapability], List[CapabilityDeficit]]:
        """
        Matches required operations against registered conditional capabilities.
        Produces bound capabilities or explicit CAPABILITY_DEFICITs.
        """
        bound_caps: List[ConditionalCapability] = []
        deficits: List[CapabilityDeficit] = []

        for op in required_ops:
            matched: Optional[ConditionalCapability] = None
            for cap in self._registry.values():
                if cap.operator_type == op.operator:
                    if cap.is_applicable(environment_fingerprint, op.inputs):
                        matched = cap
                        break

            if matched:
                bound_caps.append(matched)
            else:
                deficits.append(CapabilityDeficit(
                    required_operation_id=op.operation_id,
                    missing_capability=f"Operator_{op.operator.value}_for_{op.semantic_responsibility}",
                    consequence=f"Cannot execute required transition: {op.semantic_responsibility}",
                    provisionable=True,
                    acquisition_route="PROVISION",
                ))

        return (bound_caps, deficits)

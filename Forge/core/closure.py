"""
forge/core/closure.py
Capability & Evidence Closure Engine for 10 SHADOWS Forge.

Enforces the mandatory pre-execution closure barrier and the permanent Anti-Cheating Invariant:
Output correctness does NOT establish execution legitimacy.
"""

from typing import Any, Dict, List, Optional, Set

from forge.core.registry import CapabilityRegistry
from forge.core.substrate import (
    CapabilityDeficit,
    ClosureReport,
    EvidenceClass,
    EvidenceDeficit,
    EvidenceRequirement,
    RequiredOperation,
)


class AntiCheatingViolation(Exception):
    """Raised when an execution result is submitted while closure is incomplete."""
    pass


class ClosureGate:
    """
    Evaluates physical capability and evidence closure before ExecutionGraph execution.
    """

    def __init__(self, registry: CapabilityRegistry):
        self.registry = registry

    def evaluate_closure(
        self,
        operations: List[RequiredOperation],
        verified_evidence_pool: Dict[str, Any],
    ) -> ClosureReport:
        satisfied_ops: List[str] = []
        satisfied_ev: List[str] = []
        cap_deficits: List[CapabilityDeficit] = []
        ev_deficits: List[EvidenceDeficit] = []

        # 1. Evaluate Capability Closure
        for op in operations:
            matching_caps = self.registry.find_capabilities_for_operator(op.operator)
            if matching_caps:
                satisfied_ops.append(op.operation_id)
            else:
                cap_deficits.append(CapabilityDeficit(
                    required_operation_id=op.operation_id,
                    missing_capability=f"capability_for_{op.operator.value}",
                    consequence=f"Cannot execute {op.semantic_responsibility}",
                    provisionable=True,
                    acquisition_route="PROVISION",
                ))

        # 2. Evaluate Evidence Closure
        for op in operations:
            for ev_req in op.evidence_requirements:
                ev_id = ev_req.evidence_id
                if ev_id in verified_evidence_pool:
                    ev_item = verified_evidence_pool[ev_id]
                    ev_class = ev_item.get("evidence_class") if isinstance(ev_item, dict) else getattr(ev_item, "confidence", None)
                    # UNVERIFIED_MODEL_PRIOR has ZERO authority for verified closure
                    if ev_class == EvidenceClass.UNVERIFIED_MODEL_PRIOR.value or ev_class == "UNVERIFIED_MODEL_PRIOR":
                        ev_deficits.append(EvidenceDeficit(
                            evidence_id=ev_id,
                            claim=ev_req.claim_or_decision_supported,
                            missing_evidence_class=ev_req.required_evidence_class,
                            resolution_route="RETRIEVE",
                        ))
                    else:
                        satisfied_ev.append(ev_id)
                else:
                    ev_deficits.append(EvidenceDeficit(
                        evidence_id=ev_id,
                        claim=ev_req.claim_or_decision_supported,
                        missing_evidence_class=ev_req.required_evidence_class,
                        resolution_route="RETRIEVE",
                    ))

        is_closed = (len(cap_deficits) == 0 and len(ev_deficits) == 0)

        return ClosureReport(
            is_closed=is_closed,
            satisfied_operations=satisfied_ops,
            satisfied_evidence=satisfied_ev,
            capability_deficits=cap_deficits,
            evidence_deficits=ev_deficits,
            anti_cheating_violation=False,
            rejection_reason=None if is_closed else "Capability or evidence closure incomplete",
        )

    def validate_execution_legitimacy(
        self,
        closure_report: ClosureReport,
        candidate_output: Any,
    ) -> None:
        """
        Permanent Anti-Cheating Invariant:
        Rejects candidate answers when closure is open, even if output appears correct.
        """
        if not closure_report.is_closed:
            raise AntiCheatingViolation(
                "OUTPUT CORRECTNESS DOES NOT ESTABLISH EXECUTION LEGITIMACY: "
                f"Candidate result rejected because closure is open. Deficits: "
                f"{[d.missing_capability for d in closure_report.capability_deficits]} "
                f"{[d.claim for d in closure_report.evidence_deficits]}"
            )

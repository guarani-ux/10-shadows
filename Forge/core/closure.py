"""
forge/core/closure.py
Strict Epistemic & Capability Closure Gate for 10 SHADOWS Forge.

Enforces:
1. Exact bound capability authorization (NO operator-type fallback).
2. Strict evidence class and provenance compatibility (no unauthorized substitution).
3. Complete blocking obligation coverage.
4. Physical Anti-Cheating Law: OUTPUT CORRECTNESS DOES NOT ESTABLISH EXECUTION LEGITIMACY.
"""

from typing import Any, Dict, List, Optional

from forge.core.registry import CapabilityRegistry
from forge.core.substrate import (
    CapabilityDeficit,
    CapabilityKind,
    CapabilityLifecycleState,
    ClosureReport,
    EvidenceClass,
    EvidenceDeficit,
    EvidenceRequirement,
    OperatorType,
    RequiredOperation,
    SatisfactionObligation,
)


class AntiCheatingViolation(Exception):
    """Raised when an execution result is accepted despite open closure or missing proofs."""
    pass


class ClosureGate:
    """
    Evaluates whether an induced RequiredOperation DAG and its SatisfactionObligations
    possess 100% physically verified capability, evidence, and authority closure.
    """

    def __init__(self, registry: CapabilityRegistry):
        self.registry = registry

    def evaluate_closure(
        self,
        operations: List[RequiredOperation],
        verified_evidence_pool: Dict[str, Any],
        obligations: Optional[List[SatisfactionObligation]] = None,
    ) -> ClosureReport:
        satisfied_ops: List[str] = []
        satisfied_ev: List[str] = []
        cap_deficits: List[CapabilityDeficit] = []
        ev_deficits: List[EvidenceDeficit] = []

        # 1. Evaluate Exact Capability Bindings (NO operator-type fallback)
        for op in operations:
            bound_cap_id = op.bound_capability_id
            if not bound_cap_id:
                cap_deficits.append(
                    CapabilityDeficit(
                        required_operation_id=op.operation_id,
                        missing_capability=f"Unbound capability for operator {op.operator.value}",
                        consequence="Operation lacks sealed capability binding.",
                        provisionable=True,
                        acquisition_route="PROVISION",
                    )
                )
            else:
                manifest = self.registry.get_capability(bound_cap_id)
                if not manifest or not manifest.is_authorized_for_execution:
                    cap_deficits.append(
                        CapabilityDeficit(
                            required_operation_id=op.operation_id,
                            missing_capability=bound_cap_id,
                            consequence=f"Capability '{bound_cap_id}' is not authorized for execution.",
                            provisionable=True,
                            acquisition_route="PROVISION",
                        )
                    )
                elif not all(inp in op.inputs for inp in manifest.input_contracts.keys()):
                    cap_deficits.append(
                        CapabilityDeficit(
                            required_operation_id=op.operation_id,
                            missing_capability=bound_cap_id,
                            consequence=f"Input contract mismatch on '{bound_cap_id}'.",
                            provisionable=False,
                            acquisition_route="REFUSE",
                        )
                    )
                else:
                    satisfied_ops.append(op.operation_id)

            # 2. Strict Evidence Requirements Verification (Always evaluate evidence for every operation)
            for ev_req in op.evidence_requirements:
                if ev_req.evidence_id not in verified_evidence_pool:
                    ev_deficits.append(
                        EvidenceDeficit(
                            evidence_id=ev_req.evidence_id,
                            claim=ev_req.claim_or_decision_supported,
                            missing_evidence_class=ev_req.required_evidence_class,
                            resolution_route="RETRIEVE",
                        )
                    )
                else:
                    actual_ev = verified_evidence_pool[ev_req.evidence_id]
                    actual_class = (
                        actual_ev.get("evidence_class")
                        if isinstance(actual_ev, dict)
                        else getattr(actual_ev, "confidence", None)
                    )
                    if isinstance(actual_class, EvidenceClass):
                        actual_class_val = actual_class.value
                    else:
                        actual_class_val = str(actual_class)

                    req_class_val = (
                        ev_req.required_evidence_class.value
                        if isinstance(ev_req.required_evidence_class, EvidenceClass)
                        else str(ev_req.required_evidence_class)
                    )

                    # Strict evidence class comparison: no silent downgrades
                    if actual_class_val == "UNVERIFIED_MODEL_PRIOR" or actual_class_val != req_class_val:
                        ev_deficits.append(
                            EvidenceDeficit(
                                evidence_id=ev_req.evidence_id,
                                claim=f"{ev_req.claim_or_decision_supported} (Required {req_class_val}, got {actual_class_val})",
                                missing_evidence_class=ev_req.required_evidence_class,
                                resolution_route="RETRIEVE",
                            )
                        )
                    else:
                        satisfied_ev.append(ev_req.evidence_id)

        # 3. Obligation Accounting
        if obligations:
            for obl in obligations:
                if obl.is_blocking and not obl.has_closure_authority:
                    cap_deficits.append(
                        CapabilityDeficit(
                            required_operation_id=obl.obligation_id,
                            missing_capability="AUTHORITY_CLOSURE",
                            consequence=f"Obligation '{obl.obligation_id}' has non-authoritative status '{obl.authority.value}'.",
                            provisionable=False,
                            acquisition_route="REFUSE",
                        )
                    )

        is_closed = (len(cap_deficits) == 0 and len(ev_deficits) == 0)

        return ClosureReport(
            is_closed=is_closed,
            satisfied_operations=satisfied_ops,
            satisfied_evidence=satisfied_ev,
            capability_deficits=cap_deficits,
            evidence_deficits=ev_deficits,
        )

    def validate_execution_legitimacy(
        self,
        closure_report: ClosureReport,
        candidate_result: Dict[str, Any],
    ) -> None:
        """
        Enforces: OUTPUT CORRECTNESS DOES NOT ESTABLISH EXECUTION LEGITIMACY.
        If an oracle or model supplies a plausible answer while closure is open, raise AntiCheatingViolation.
        """
        if not closure_report.is_closed:
            raise AntiCheatingViolation(
                f"Physical Reality Violation: OUTPUT CORRECTNESS DOES NOT ESTABLISH EXECUTION LEGITIMACY. "
                f"Candidate execution was attempted with open closure deficits: "
                f"Cap deficits: {[d.missing_capability for d in closure_report.capability_deficits]}, "
                f"Evidence deficits: {[d.evidence_id for d in closure_report.evidence_deficits]}"
            )

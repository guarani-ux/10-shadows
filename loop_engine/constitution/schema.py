"""
loop_engine/constitution/schema.py
Constitutional Ontology, Obligation Semantics, and Law 6 Sufficiency for 10 SHADOWS.

Enforces:
- LAW 6 — SUFFICIENCY / OBJECTIVE SATISFACTION:
  No higher-order conclusion (such as objective accomplishment) may become authoritative
  solely from the local success of its components. An explicit, qualified sufficiency
  evaluation over verified satisfaction obligations must authorize that conclusion.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
import hashlib
import json
from typing import Any, Dict, List, Optional, Set, Tuple


def canonical_json(data: Any) -> str:
    """Computes deterministic canonical JSON string."""
    def _default(o: Any) -> Any:
        if isinstance(o, Enum):
            return o.value
        if hasattr(o, "__dict__"):
            return o.__dict__
        if isinstance(o, (set, tuple)):
            return list(o)
        return str(o)

    return json.dumps(data, sort_keys=True, separators=(",", ":"), default=_default)


def compute_digest(data: Any) -> str:
    """Computes deterministic SHA256 hex digest."""
    return hashlib.sha256(canonical_json(data).encode("utf-8")).hexdigest()


class ObligationStatus(str, Enum):
    UNRESOLVED = "UNRESOLVED"
    SATISFIED = "SATISFIED"
    FALSIFIED = "FALSIFIED"
    INAPPLICABLE = "INAPPLICABLE"
    CONTESTED = "CONTESTED"


class SufficiencyRuleKind(str, Enum):
    ALL_MANDATORY = "ALL_MANDATORY"
    ANY_OF = "ANY_OF"
    CUSTOM = "CUSTOM"


@dataclass
class Obligation:
    obligation_id: str
    description: str
    required_effect: str
    is_mandatory: bool = True
    satisfaction_status: ObligationStatus = ObligationStatus.UNRESOLVED
    bound_evidence_digest: Optional[str] = None
    rationale: Optional[str] = None

    def satisfy(self, evidence_digest: str, rationale: str) -> None:
        self.satisfaction_status = ObligationStatus.SATISFIED
        self.bound_evidence_digest = evidence_digest
        self.rationale = rationale

    def falsify(self, reason: str) -> None:
        self.satisfaction_status = ObligationStatus.FALSIFIED
        self.rationale = reason


@dataclass
class SufficiencyRule:
    kind: SufficiencyRuleKind = SufficiencyRuleKind.ALL_MANDATORY
    details: Optional[List[str]] = None


@dataclass
class ObjectiveSufficiencyProof:
    objective_id: str
    is_satisfied: bool
    satisfied_obligations: List[str]
    unresolved_mandatory: List[str]
    falsified_mandatory: List[str]
    proof_digest: str


@dataclass
class EvidenceEntailment:
    evidence_digest: str
    target_obligation_id: str
    tested_effect: str
    is_applicable: bool
    justification: str

    @classmethod
    def verify_entailment(
        cls,
        evidence_digest: str,
        obligation: Obligation,
        tested_effect: str,
    ) -> EvidenceEntailment:
        is_applicable = (
            tested_effect.strip().lower() == obligation.required_effect.strip().lower()
        )
        if is_applicable:
            justification = f"Evidence '{evidence_digest}' directly tests required effect '{obligation.required_effect}'"
        else:
            justification = f"Irrelevant Evidence: Tested effect '{tested_effect}' does not fulfill required obligation effect '{obligation.required_effect}'"

        return cls(
            evidence_digest=evidence_digest,
            target_obligation_id=obligation.obligation_id,
            tested_effect=tested_effect,
            is_applicable=is_applicable,
            justification=justification,
        )


@dataclass
class ObjectiveContract:
    objective_id: str
    canonical_intent: str
    obligations: List[Obligation]
    sufficiency_rule: SufficiencyRule = field(default_factory=SufficiencyRule)
    intent_hash: str = ""

    def __post_init__(self) -> None:
        if not self.intent_hash:
            self.intent_hash = compute_digest(self.canonical_intent)

    def evaluate_sufficiency(self) -> ObjectiveSufficiencyProof:
        satisfied_ids: Set[str] = set()
        unresolved_mandatory: List[str] = []
        falsified_mandatory: List[str] = []

        for ob in self.obligations:
            if ob.satisfaction_status == ObligationStatus.SATISFIED:
                satisfied_ids.add(ob.obligation_id)
            elif ob.satisfaction_status == ObligationStatus.FALSIFIED:
                if ob.is_mandatory:
                    falsified_mandatory.push(ob.obligation_id) if hasattr(falsified_mandatory, "push") else falsified_mandatory.append(ob.obligation_id)
            elif ob.satisfaction_status in (ObligationStatus.UNRESOLVED, ObligationStatus.CONTESTED):
                if ob.is_mandatory:
                    unresolved_mandatory.append(ob.obligation_id)

        if falsified_mandatory:
            is_sufficient = False
        else:
            if self.sufficiency_rule.kind == SufficiencyRuleKind.ALL_MANDATORY:
                is_sufficient = len(unresolved_mandatory) == 0
            elif self.sufficiency_rule.kind == SufficiencyRuleKind.ANY_OF:
                target_ids = set(self.sufficiency_rule.details or [])
                is_sufficient = bool(satisfied_ids.intersection(target_ids))
            else:
                is_sufficient = len(unresolved_mandatory) == 0

        proof_digest = compute_digest({
            "objective_id": self.objective_id,
            "is_satisfied": is_sufficient,
            "satisfied": list(satisfied_ids),
            "unresolved": unresolved_mandatory,
            "falsified": falsified_mandatory,
        })

        return ObjectiveSufficiencyProof(
            objective_id=self.objective_id,
            is_satisfied=is_sufficient,
            satisfied_obligations=sorted(list(satisfied_ids)),
            unresolved_mandatory=unresolved_mandatory,
            falsified_mandatory=falsified_mandatory,
            proof_digest=proof_digest,
        )

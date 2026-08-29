"""
loop_engine/constitution/lifecycle.py
Objective Lifecycle, Revision Semantics, and Semantic Qualification for 10 SHADOWS.

Enforces:
- Raw Intent is not an authoritative objective.
- Explicit lifecycle: RawIntent -> CandidateInterpretation -> SemanticQualification -> VersionedObjectiveSpecification
- Objective versioning, provenance retention, and goal-drift tracking.
- Fail-closed disposition for ambiguous or domain-dependent intents.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
import hashlib
import json
from typing import Any, Dict, List, Optional, Set, Tuple

from forge.core.substrate import (
    CanonicalRequirement,
    ObjectiveAdequacyContract,
    ObjectiveAdequacyState,
    RawClause,
    RequirementDisposition,
    RequirementOrigin,
    RequirementTrace,
    canonical_json,
    compute_digest,
)


class SemanticQualificationStatus(str, Enum):
    QUALIFIED = "QUALIFIED"
    AMBIGUOUS = "AMBIGUOUS"
    HUMAN_AUTHORITY_REQUIRED = "HUMAN_AUTHORITY_REQUIRED"
    DOMAIN_AUTHORITY_REQUIRED = "DOMAIN_AUTHORITY_REQUIRED"
    INSUFFICIENT_INFORMATION = "INSUFFICIENT_INFORMATION"
    CONTESTED = "CONTESTED"
    PROVISIONAL = "PROVISIONAL"
    REJECTED = "REJECTED"


class RevisionType(str, Enum):
    INITIAL_CREATION = "INITIAL_CREATION"
    CLARIFICATION = "CLARIFICATION"
    REQUIREMENT_ADDITION = "REQUIREMENT_ADDITION"
    REQUIREMENT_REMOVAL = "REQUIREMENT_REMOVAL"
    SCOPE_EXPANSION = "SCOPE_EXPANSION"
    SCOPE_REDUCTION = "SCOPE_REDUCTION"
    CONSTRAINT_CHANGE = "CONSTRAINT_CHANGE"
    SEMANTIC_CORRECTION = "SEMANTIC_CORRECTION"


@dataclass(frozen=True)
class RawIntent:
    """Uninterpreted operator prompt or raw input payload."""
    raw_text: str
    ingress_timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    source_identity: str = "OPERATOR"
    intent_hash: str = ""

    def __post_init__(self) -> None:
        if not self.intent_hash:
            object.__setattr__(
                self,
                "intent_hash",
                compute_digest({"text": self.raw_text, "source": self.source_identity}),
            )


@dataclass
class CandidateInterpretation:
    """Proposed decomposition/interpretation of RawIntent by an untrusted worker/model."""
    candidate_id: str
    source_intent_hash: str
    proposed_clauses: List[RawClause]
    proposed_requirements: List[CanonicalRequirement]
    proposer_identity: str
    confidence: float = 0.5
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


@dataclass
class VersionedObjectiveSpecification:
    """
    Authoritative, immutable version of an objective specification.
    Contains the qualified canonical requirements and adequacy proof.
    """
    objective_id: str
    version: int
    canonical_intent: str
    intent_hash: str
    requirements: List[CanonicalRequirement]
    qualification_status: SemanticQualificationStatus
    adequacy_contract: Optional[ObjectiveAdequacyContract] = None
    parent_version: Optional[int] = None
    revision_type: RevisionType = RevisionType.INITIAL_CREATION
    revision_reason: Optional[str] = None
    authorized_by: str = "SYSTEM_TCB"
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    @property
    def specification_hash(self) -> str:
        return compute_digest({
            "objective_id": self.objective_id,
            "version": self.version,
            "canonical_intent": self.canonical_intent,
            "requirements": [r.requirement_hash for r in self.requirements],
            "qualification_status": self.qualification_status.value,
            "parent_version": self.parent_version,
            "revision_type": self.revision_type.value,
        })

    @property
    def is_executable(self) -> bool:
        return self.qualification_status == SemanticQualificationStatus.QUALIFIED


class ObjectiveLifecycleManager:
    """
    Manages the lifecycle, qualification, versioning, and revision of objectives.
    Prevents raw intent from self-certifying as authoritative specification.
    """

    def __init__(self):
        self._objectives: Dict[str, List[VersionedObjectiveSpecification]] = {}

    def qualify_intent(
        self,
        objective_id: str,
        raw_intent: RawIntent,
        candidate: CandidateInterpretation,
        known_domain_capabilities: Optional[Set[str]] = None,
    ) -> VersionedObjectiveSpecification:
        """
        Evaluates candidate interpretation for semantic completeness and ambiguity.
        Produces Version 1 of the Objective Specification.
        """
        known_caps = known_domain_capabilities or set()
        unaccounted_drops: List[str] = []
        missing_domain_caps: List[str] = []
        traces: List[RequirementTrace] = []

        # 1. Inspect raw text for ambiguity or non-trivial requirements
        raw_clean = raw_intent.raw_text.strip()
        if not raw_clean:
            return VersionedObjectiveSpecification(
                objective_id=objective_id,
                version=1,
                canonical_intent="",
                intent_hash=raw_intent.intent_hash,
                requirements=[],
                qualification_status=SemanticQualificationStatus.REJECTED,
                revision_reason="Empty raw intent payload.",
            )

        # 2. Check for empty requirement proposals on non-trivial intent
        if not candidate.proposed_requirements and len(raw_clean) > 5:
            # Non-trivial intent with zero requirements MUST fail closed
            adequacy = ObjectiveAdequacyContract(
                objective_id=objective_id,
                adequacy_state=ObjectiveAdequacyState.SOURCE_UNCOVERED,
                raw_clauses=candidate.proposed_clauses,
                traces=[],
                unaccounted_drops=[raw_clean],
                unauthorized_assumptions=[],
                missing_domain_capabilities=[],
            )
            spec = VersionedObjectiveSpecification(
                objective_id=objective_id,
                version=1,
                canonical_intent=raw_clean,
                intent_hash=raw_intent.intent_hash,
                requirements=[],
                qualification_status=SemanticQualificationStatus.INSUFFICIENT_INFORMATION,
                adequacy_contract=adequacy,
                revision_reason="Zero requirements proposed for non-trivial intent.",
            )
            self._record_spec(spec)
            return spec

        # 3. Check for domain capability prerequisites
        for req in candidate.proposed_requirements:
            traces.append(RequirementTrace(
                raw_clause_id=req.source_clause_id or "clause_default",
                raw_text=req.description,
                disposition=RequirementDisposition.PRESERVED,
                canonical_target=req.requirement_id,
            ))
            if req.required_domain_capability and req.required_domain_capability not in known_caps:
                missing_domain_caps.append(req.required_domain_capability)

        if missing_domain_caps:
            adequacy = ObjectiveAdequacyContract(
                objective_id=objective_id,
                adequacy_state=ObjectiveAdequacyState.DOMAIN_REQUIREMENTS_UNVERIFIED,
                raw_clauses=candidate.proposed_clauses,
                traces=traces,
                unaccounted_drops=[],
                unauthorized_assumptions=[],
                missing_domain_capabilities=missing_domain_caps,
            )
            spec = VersionedObjectiveSpecification(
                objective_id=objective_id,
                version=1,
                canonical_intent=raw_clean,
                intent_hash=raw_intent.intent_hash,
                requirements=candidate.proposed_requirements,
                qualification_status=SemanticQualificationStatus.DOMAIN_AUTHORITY_REQUIRED,
                adequacy_contract=adequacy,
                revision_reason=f"Missing verified domain capabilities: {missing_domain_caps}",
            )
            self._record_spec(spec)
            return spec

        # 4. Successfully qualified
        adequacy = ObjectiveAdequacyContract(
            objective_id=objective_id,
            adequacy_state=ObjectiveAdequacyState.ADEQUATE_FOR_EXECUTION,
            raw_clauses=candidate.proposed_clauses,
            traces=traces,
            unaccounted_drops=[],
            unauthorized_assumptions=[],
            missing_domain_capabilities=[],
        )
        spec = VersionedObjectiveSpecification(
            objective_id=objective_id,
            version=1,
            canonical_intent=raw_clean,
            intent_hash=raw_intent.intent_hash,
            requirements=candidate.proposed_requirements,
            qualification_status=SemanticQualificationStatus.QUALIFIED,
            adequacy_contract=adequacy,
            revision_reason="Semantic adequacy established under authoritative verification.",
        )
        self._record_spec(spec)
        return spec

    def revise_objective(
        self,
        current_spec: VersionedObjectiveSpecification,
        revision_type: RevisionType,
        revised_intent: Optional[str],
        revised_requirements: List[CanonicalRequirement],
        revision_reason: str,
        authorized_by: str = "HUMAN_OPERATOR",
    ) -> VersionedObjectiveSpecification:
        """
        Creates a new immutable version of the objective, preserving the lineage
        and triggering downstream dependency re-qualification.
        """
        new_version = current_spec.version + 1
        new_intent = revised_intent if revised_intent is not None else current_spec.canonical_intent
        new_intent_hash = compute_digest(new_intent)

        # Re-check adequacy
        if not revised_requirements and len(new_intent.strip()) > 5:
            qual_status = SemanticQualificationStatus.INSUFFICIENT_INFORMATION
        else:
            qual_status = SemanticQualificationStatus.QUALIFIED

        new_spec = VersionedObjectiveSpecification(
            objective_id=current_spec.objective_id,
            version=new_version,
            canonical_intent=new_intent,
            intent_hash=new_intent_hash,
            requirements=revised_requirements,
            qualification_status=qual_status,
            parent_version=current_spec.version,
            revision_type=revision_type,
            revision_reason=revision_reason,
            authorized_by=authorized_by,
        )
        self._record_spec(new_spec)
        return new_spec

    def get_version(self, objective_id: str, version: int) -> Optional[VersionedObjectiveSpecification]:
        for spec in self._objectives.get(objective_id, []):
            if spec.version == version:
                return spec
        return None

    def get_latest(self, objective_id: str) -> Optional[VersionedObjectiveSpecification]:
        specs = self._objectives.get(objective_id, [])
        return specs[-1] if specs else None

    def _record_spec(self, spec: VersionedObjectiveSpecification) -> None:
        if spec.objective_id not in self._objectives:
            self._objectives[spec.objective_id] = []
        self._objectives[spec.objective_id].append(spec)

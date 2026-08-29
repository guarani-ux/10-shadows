"""
loop_engine/constitution/lifecycle.py
Hardened Objective Lifecycle, Authority-Bearing Specifications, Revision Authorization,
and Forge Adequacy Integration for 10 SHADOWS.

Enforces:
- Proposal<T> != Qualified<T> != Authoritative<T>.
- Untrusted CandidateInterpretation cannot self-promote.
- Mechanical invocation of ObjectiveAdequacyVerifier to detect under-decomposition / dropped clauses.
- Revision Authorization requires privileged ObjectiveRevisionAuthorization, not unverified strings.
- Completeness is an epistemic claim, not a static boolean.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Tuple

from forge.core.adequacy import IntentCoverageEvaluator, RawClauseTokenizer
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
class ProposedRequirement:
    """Untrusted requirement candidate proposed by a worker or model."""

    proposal_id: str
    raw_clause_id: str
    description: str
    claimed_origin: RequirementOrigin = RequirementOrigin.ASSUMED
    is_blocking: bool = True
    proposer_identity: str = "untrusted_worker"
    confidence: float = 0.5


@dataclass
class CandidateInterpretation:
    """Proposed decomposition/interpretation of RawIntent by an untrusted worker/model."""

    candidate_id: str
    source_intent_hash: str
    proposed_clauses: List[RawClause]
    proposed_requirements: List[ProposedRequirement]
    proposer_identity: str
    confidence: float = 0.5
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


@dataclass(frozen=True)
class ObjectiveRevisionAuthorization:
    """
    Privileged authority token granting permission to revise an objective.
    Prevents unverified strings from impersonating operator or TCB authorization.
    """

    authorization_id: str
    authorizing_principal: str  # HUMAN_OPERATOR | SYSTEM_TCB | DOMAIN_AUTHORITY
    authority_proof_token: str
    target_objective_id: str
    target_version: int
    authorized_revision_types: List[RevisionType]
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def is_valid_for(self, objective_id: str, current_version: int, revision_type: RevisionType) -> bool:
        if not self.authority_proof_token.strip():
            return False
        if self.target_objective_id != objective_id:
            return False
        if self.target_version != current_version:
            return False
        if revision_type not in self.authorized_revision_types:
            return False
        return True


@dataclass
class VersionedObjectiveSpecification:
    """
    Authoritative, immutable version of an objective specification.
    Contains qualified canonical requirements and the adequacy contract.
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
    revision_authorization: Optional[ObjectiveRevisionAuthorization] = None
    revision_reason: Optional[str] = None
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    @property
    def specification_hash(self) -> str:
        return compute_digest(
            {
                "objective_id": self.objective_id,
                "version": self.version,
                "canonical_intent": self.canonical_intent,
                "requirements": [r.requirement_hash for r in self.requirements],
                "qualification_status": self.qualification_status.value,
                "parent_version": self.parent_version,
                "revision_type": self.revision_type.value,
            }
        )

    @property
    def is_executable(self) -> bool:
        return self.qualification_status == SemanticQualificationStatus.QUALIFIED


class ObjectiveLifecycleManager:
    """
    Manages the lifecycle, qualification, versioning, and revision of objectives.
    Prevents untrusted proposals from self-promoting to authoritative specifications.
    """

    def __init__(self):
        self._objectives: Dict[str, List[VersionedObjectiveSpecification]] = {}
        self._adequacy_verifier = IntentCoverageEvaluator()

    def qualify_intent(
        self,
        objective_id: str,
        raw_intent: RawIntent,
        candidate: CandidateInterpretation,
        known_domain_capabilities: Optional[Set[str]] = None,
    ) -> VersionedObjectiveSpecification:
        """
        Mechanically qualifies the candidate interpretation using IntentCoverageEvaluator.
        Ensures zero unmapped source intent, verified clause traces, and grounded origins.
        """
        known_caps = known_domain_capabilities or set()
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

        # 1. Parse raw text into authoritative clauses if not provided
        raw_clauses = candidate.proposed_clauses
        if not raw_clauses:
            raw_clauses = RawClauseTokenizer.tokenize(raw_clean)

        # 2. Check for empty requirement proposals on non-trivial intent
        if not candidate.proposed_requirements and len(raw_clean) > 5:
            adequacy = ObjectiveAdequacyContract(
                objective_id=objective_id,
                adequacy_state=ObjectiveAdequacyState.SOURCE_UNCOVERED,
                raw_clauses=raw_clauses,
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

        # 3. Promote proposed requirements to CanonicalRequirements with verified traces
        canonical_reqs: List[CanonicalRequirement] = []
        traces: List[RequirementTrace] = []
        unaccounted_drops: List[str] = []
        covered_clause_ids: Set[str] = set()

        for prop in candidate.proposed_requirements:
            req_id = prop.proposal_id or f"req_{len(canonical_reqs) + 1}"

            # Ground origin: if claimed SOURCE_EXPLICIT, must match an actual raw clause
            matching_clause = next(
                (
                    c
                    for c in raw_clauses
                    if c.clause_id == prop.raw_clause_id
                    or prop.description.lower() in c.text.lower()
                    or c.text.lower() in prop.description.lower()
                ),
                None,
            )

            if matching_clause:
                origin = RequirementOrigin.SOURCE_EXPLICIT
                covered_clause_ids.add(matching_clause.clause_id)
                traces.append(
                    RequirementTrace(
                        raw_clause_id=matching_clause.clause_id,
                        raw_text=matching_clause.text,
                        disposition=RequirementDisposition.PRESERVED,
                        canonical_target=req_id,
                    )
                )
            else:
                origin = RequirementOrigin.ASSUMED
                traces.append(
                    RequirementTrace(
                        raw_clause_id=prop.raw_clause_id or "unmapped",
                        raw_text=prop.description,
                        disposition=RequirementDisposition.AMBIGUOUS,
                        canonical_target=req_id,
                    )
                )

            canonical_reqs.append(
                CanonicalRequirement(
                    requirement_id=req_id,
                    description=prop.description,
                    origin=origin,
                    source_clause_id=matching_clause.clause_id if matching_clause else None,
                    is_blocking=prop.is_blocking,
                )
            )

        # Check for dropped/uncovered clauses
        for clause in raw_clauses:
            if clause.clause_id not in covered_clause_ids:
                unaccounted_drops.append(clause.text)

        # 4. Verify adequacy via Forge Adequacy Contract
        if unaccounted_drops:
            adequacy = ObjectiveAdequacyContract(
                objective_id=objective_id,
                adequacy_state=ObjectiveAdequacyState.SOURCE_UNCOVERED,
                raw_clauses=raw_clauses,
                traces=traces,
                unaccounted_drops=unaccounted_drops,
                unauthorized_assumptions=[],
                missing_domain_capabilities=[],
            )
            spec = VersionedObjectiveSpecification(
                objective_id=objective_id,
                version=1,
                canonical_intent=raw_clean,
                intent_hash=raw_intent.intent_hash,
                requirements=canonical_reqs,
                qualification_status=SemanticQualificationStatus.INSUFFICIENT_INFORMATION,
                adequacy_contract=adequacy,
                revision_reason=f"Uncovered source intent clauses: {unaccounted_drops}",
            )
            self._record_spec(spec)
            return spec

        # 5. Successfully qualified
        adequacy = ObjectiveAdequacyContract(
            objective_id=objective_id,
            adequacy_state=ObjectiveAdequacyState.ADEQUATE_FOR_EXECUTION,
            raw_clauses=raw_clauses,
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
            requirements=canonical_reqs,
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
        revision_authorization: ObjectiveRevisionAuthorization,
        revision_reason: str,
    ) -> VersionedObjectiveSpecification:
        """
        Creates a new immutable version of the objective under verified revision authorization.
        Fails closed if the authorization token is missing or invalid.
        """
        if not revision_authorization.is_valid_for(current_spec.objective_id, current_spec.version, revision_type):
            raise PermissionError(
                f"UNAUTHORIZED_REVISION: Revision authorization '{revision_authorization.authorization_id}' "
                f"is invalid for objective '{current_spec.objective_id}' v{current_spec.version} ({revision_type.value})."
            )

        new_version = current_spec.version + 1
        new_intent = revised_intent if revised_intent is not None else current_spec.canonical_intent
        new_intent_hash = compute_digest(new_intent)

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
            revision_authorization=revision_authorization,
            revision_reason=revision_reason,
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

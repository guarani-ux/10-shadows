"""
loop_engine/constitution/evidence.py
Relational Epistemic Evidence, Bounded Verifier Contracts, and Claim Qualification for 10 SHADOWS.

Enforces:
- Evidence is relational: Observation O supports/contradicts Claim C under Conditions K
  using Qualification Rule Q within Scope S at Time T against Candidate V.
- Elimination of string-matching / keyword entailment heuristics.
- Orthogonal dimensions: Epistemic, Applicability, Reachability, Authority, Observation.
- Stale evidence, candidate mismatch, and duplicate inflation rejection.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
import hashlib
import json
from typing import Any, Dict, List, Optional, Set, Tuple

from forge.core.substrate import EvidenceClass, compute_digest


class EpistemicDimension(str, Enum):
    SUPPORTED = "SUPPORTED"
    UNSUPPORTED = "UNSUPPORTED"
    CONTESTED = "CONTESTED"
    UNKNOWN = "UNKNOWN"
    CONTRADICTED = "CONTRADICTED"


class ApplicabilityDimension(str, Enum):
    APPLICABLE = "APPLICABLE"
    INAPPLICABLE = "INAPPLICABLE"
    UNRESOLVED = "UNRESOLVED"


class ReachabilityDimension(str, Enum):
    REACHABLE = "REACHABLE"
    UNREACHABLE = "UNREACHABLE"
    UNKNOWN = "UNKNOWN"


class AuthorityDimension(str, Enum):
    AUTHORIZED = "AUTHORIZED"
    UNAUTHORIZED = "UNAUTHORIZED"
    AUTHORITY_REQUIRED = "AUTHORITY_REQUIRED"


class ObservationDimension(str, Enum):
    OBSERVED = "OBSERVED"
    UNOBSERVED = "UNOBSERVED"
    UNAVAILABLE = "UNAVAILABLE"


@dataclass(frozen=True)
class BoundedVerifierContract:
    """
    Explicit specification of what an independent verifier tests, observes,
    and explicitly DOES NOT establish.
    """
    contract_id: str
    target_claim_id: str
    verification_modality: str  # DETERMINISTIC_TEST | STATIC_AST | PROPERTY_ORACLE | ADVERSARIAL_MUTATION
    scope: str
    target_candidate_sha: Optional[str]
    explicit_non_claims: List[str] = field(default_factory=list)
    verifier_identity: str = "svris_independent_oracle"
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    @property
    def contract_hash(self) -> str:
        return compute_digest({
            "id": self.contract_id,
            "claim": self.target_claim_id,
            "modality": self.verification_modality,
            "scope": self.scope,
            "candidate": self.target_candidate_sha,
            "non_claims": self.explicit_non_claims,
            "verifier": self.verifier_identity,
        })


@dataclass
class QualifiedEvidence:
    """
    Relational observation bound to candidate, environment, verifier, and scope.
    """
    evidence_id: str
    verifier_contract: BoundedVerifierContract
    observation_data: Dict[str, Any]
    evidence_class: EvidenceClass
    candidate_sha: str
    environment_fingerprint: str
    observation_status: ObservationDimension = ObservationDimension.OBSERVED
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    is_falsified: bool = False
    falsification_reason: Optional[str] = None

    @property
    def evidence_digest(self) -> str:
        return compute_digest({
            "id": self.evidence_id,
            "contract_hash": self.verifier_contract.contract_hash,
            "obs": self.observation_data,
            "class": self.evidence_class.value,
            "candidate": self.candidate_sha,
            "env": self.environment_fingerprint,
            "status": self.observation_status.value,
        })


@dataclass
class EpistemicClaim:
    """
    First-class epistemic claim representing a discrete assertion of fact,
    behavior, or requirement satisfaction.
    """
    claim_id: str
    subject: str
    predicate: str
    required_scope: str
    target_candidate_sha: Optional[str] = None
    epistemic_status: EpistemicDimension = EpistemicDimension.UNKNOWN
    applicability: ApplicabilityDimension = ApplicabilityDimension.UNRESOLVED
    authority: AuthorityDimension = AuthorityDimension.AUTHORITY_REQUIRED
    bound_evidence_ids: List[str] = field(default_factory=list)
    contradicting_evidence_ids: List[str] = field(default_factory=list)
    qualification_notes: Optional[str] = None


class RelationalEvidenceEvaluator:
    """
    Evaluates evidence against claims using strict relational semantics.
    Eliminates string/keyword matching and rejects mismatched or stale evidence.
    """

    @staticmethod
    def evaluate_claim(
        claim: EpistemicClaim,
        evidence_list: List[QualifiedEvidence],
        active_candidate_sha: Optional[str] = None,
    ) -> Tuple[EpistemicDimension, ApplicabilityDimension, Optional[str]]:
        """
        Determines if evidence qualifies the claim.
        Enforces candidate match, verifier contract binding, and non-falsification.
        """
        if not evidence_list:
            return (EpistemicDimension.UNSUPPORTED, ApplicabilityDimension.UNRESOLVED, "No evidence provided.")

        valid_supports: List[QualifiedEvidence] = []
        contradictions: List[QualifiedEvidence] = []

        seen_digests: Set[str] = set()

        for ev in evidence_list:
            # Check for duplicate evidence injection
            if ev.evidence_digest in seen_digests:
                continue
            seen_digests.add(ev.evidence_digest)

            # Check if evidence was falsified or retracted
            if ev.is_falsified:
                contradictions.append(ev)
                continue

            # Check candidate binding (if claim is candidate-specific)
            if claim.target_candidate_sha:
                if ev.candidate_sha != claim.target_candidate_sha:
                    return (
                        EpistemicDimension.UNSUPPORTED,
                        ApplicabilityDimension.INAPPLICABLE,
                        f"Candidate mismatch: Claim requires {claim.target_candidate_sha}, evidence is for {ev.candidate_sha}",
                    )

            if active_candidate_sha and ev.candidate_sha != active_candidate_sha:
                return (
                    EpistemicDimension.UNSUPPORTED,
                    ApplicabilityDimension.INAPPLICABLE,
                    f"Stale evidence: Active candidate is {active_candidate_sha}, evidence is from {ev.candidate_sha}",
                )

            # Check verifier contract match
            if ev.verifier_contract.target_claim_id != claim.claim_id:
                return (
                    EpistemicDimension.UNSUPPORTED,
                    ApplicabilityDimension.INAPPLICABLE,
                    f"Contract mismatch: Evidence is for {ev.verifier_contract.target_claim_id}, not {claim.claim_id}",
                )

            # Check observation status
            if ev.observation_status == ObservationDimension.UNAVAILABLE:
                return (
                    EpistemicDimension.UNSUPPORTED,
                    ApplicabilityDimension.UNRESOLVED,
                    f"Observation unavailable: {ev.observation_data.get('error', 'Verifier unavailable')}",
                )

            # Check observation outcome
            exit_code = ev.observation_data.get("exit_code", 0)
            tests_passed = ev.observation_data.get("tests_passed", 0)
            tests_failed = ev.observation_data.get("tests_failed", 0)

            if exit_code == 0 and tests_failed == 0 and tests_passed > 0:
                valid_supports.append(ev)
            elif tests_failed > 0 or exit_code != 0:
                contradictions.append(ev)
            else:
                # 0 passed, 0 failed -> no observations
                pass

        if contradictions:
            return (
                EpistemicDimension.CONTRADICTED,
                ApplicabilityDimension.APPLICABLE,
                f"Contradictory evidence: {len(contradictions)} failing observation(s) recorded.",
            )

        if valid_supports:
            return (
                EpistemicDimension.SUPPORTED,
                ApplicabilityDimension.APPLICABLE,
                f"Qualified by {len(valid_supports)} independent verified observation(s).",
            )

        return (
            EpistemicDimension.UNSUPPORTED,
            ApplicabilityDimension.UNRESOLVED,
            "Evidence insufficient to qualify claim.",
        )

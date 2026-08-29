"""
loop_engine/constitution/evidence.py
Separation of Verifier Specification, Execution Observation, and Relational Evidence Qualification.

Enforces:
- VerifierSpecification != VerifierExecutionObservation != EvidenceQualification.
- Observations cannot self-describe semantic authority.
- Candidate, Environment, and Scope constraints are mechanically enforced.
- Rejection of duplicate digests, candidate mismatches, and environment leaks.
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
class VerifierSpecification:
    """
    Independent specification of what a verifier must test, what modality it uses,
    and what it explicitly DOES NOT establish.
    """
    spec_id: str
    target_claim_id: str
    verification_modality: str  # DETERMINISTIC_TEST | STATIC_AST | PROPERTY_ORACLE | ADVERSARIAL_MUTATION
    expected_scope: str
    target_candidate_sha: Optional[str]
    required_environment_pattern: Optional[str] = None
    min_coverage_percentage: float = 0.0
    explicit_non_claims: List[str] = field(default_factory=list)
    verifier_identity: str = "svris_independent_oracle"
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    @property
    def spec_digest(self) -> str:
        return compute_digest({
            "id": self.spec_id,
            "claim": self.target_claim_id,
            "modality": self.verification_modality,
            "scope": self.expected_scope,
            "candidate": self.target_candidate_sha,
            "env": self.required_environment_pattern,
            "non_claims": self.explicit_non_claims,
            "verifier": self.verifier_identity,
        })


@dataclass
class VerifierExecutionObservation:
    """
    Empirical observation recorded by executing a verifier adapter.
    Derived mechanically from the execution process; cannot self-declare semantic authority.
    """
    observation_id: str
    spec_digest: str
    executed_command: str
    collector_type: str
    exit_code: int
    tests_collected: int
    tests_passed: int
    tests_failed: int
    duration_seconds: float
    coverage_percentage: float
    candidate_sha: str
    environment_fingerprint: str
    observation_status: ObservationDimension = ObservationDimension.OBSERVED
    is_falsified: bool = False
    falsification_reason: Optional[str] = None
    raw_trace: Optional[str] = None
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    @property
    def observation_digest(self) -> str:
        return compute_digest({
            "id": self.observation_id,
            "spec_digest": self.spec_digest,
            "cmd": self.executed_command,
            "exit": self.exit_code,
            "passed": self.tests_passed,
            "failed": self.tests_failed,
            "coverage": self.coverage_percentage,
            "candidate": self.candidate_sha,
            "env": self.environment_fingerprint,
            "status": self.observation_status.value,
        })


@dataclass
class QualifiedEvidence:
    """
    Qualified evidence relationship binding an independent specification
    to an execution observation and evidence class.
    """
    evidence_id: str
    specification: VerifierSpecification
    observation: VerifierExecutionObservation
    evidence_class: EvidenceClass
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    @property
    def evidence_digest(self) -> str:
        return compute_digest({
            "id": self.evidence_id,
            "spec": self.specification.spec_digest,
            "obs": self.observation.observation_digest,
            "class": self.evidence_class.value,
        })


@dataclass
class EpistemicClaim:
    """
    Discrete epistemic assertion of fact, behavior, or requirement satisfaction.
    """
    claim_id: str
    subject: str
    predicate: str
    required_scope: str
    target_candidate_sha: Optional[str] = None
    required_environment: Optional[str] = None
    epistemic_status: EpistemicDimension = EpistemicDimension.UNKNOWN
    applicability: ApplicabilityDimension = ApplicabilityDimension.UNRESOLVED
    authority: AuthorityDimension = AuthorityDimension.AUTHORITY_REQUIRED
    bound_evidence_ids: List[str] = field(default_factory=list)
    contradicting_evidence_ids: List[str] = field(default_factory=list)
    qualification_notes: Optional[str] = None


class RelationalEvidenceEvaluator:
    """
    Evaluates evidence against claims using strict relational semantics.
    Eliminates string/keyword heuristics, verifies specification-observation integrity,
    and enforces candidate and environment scope constraints.
    """

    @staticmethod
    def evaluate_claim(
        claim: EpistemicClaim,
        evidence_list: List[QualifiedEvidence],
        active_candidate_sha: Optional[str] = None,
        active_environment_fingerprint: Optional[str] = None,
    ) -> Tuple[EpistemicDimension, ApplicabilityDimension, Optional[str]]:
        """
        Evaluates whether evidence qualifies the claim.
        """
        if not evidence_list:
            return (EpistemicDimension.UNSUPPORTED, ApplicabilityDimension.UNRESOLVED, "No evidence provided.")

        valid_supports: List[QualifiedEvidence] = []
        contradictions: List[QualifiedEvidence] = []
        seen_digests: Set[str] = set()

        for ev in evidence_list:
            # 1. Deduplicate identical observation/specification pairings
            obs_binding_digest = compute_digest({
                "spec": ev.specification.spec_digest,
                "obs": ev.observation.observation_digest,
            })
            if obs_binding_digest in seen_digests:
                continue
            seen_digests.add(obs_binding_digest)

            spec = ev.specification
            obs = ev.observation

            # 2. Check specification-observation binding integrity
            if obs.spec_digest != spec.spec_digest:
                return (
                    EpistemicDimension.UNSUPPORTED,
                    ApplicabilityDimension.INAPPLICABLE,
                    f"Digest mismatch: Observation spec '{obs.spec_digest}' != Spec '{spec.spec_digest}'",
                )

            # 3. Check claim ID binding
            if spec.target_claim_id != claim.claim_id:
                return (
                    EpistemicDimension.UNSUPPORTED,
                    ApplicabilityDimension.INAPPLICABLE,
                    f"Target claim mismatch: Spec is for '{spec.target_claim_id}', Claim is '{claim.claim_id}'",
                )

            # 4. Check candidate binding
            if claim.target_candidate_sha and obs.candidate_sha != claim.target_candidate_sha:
                return (
                    EpistemicDimension.UNSUPPORTED,
                    ApplicabilityDimension.INAPPLICABLE,
                    f"Candidate mismatch: Claim requires '{claim.target_candidate_sha}', observation is for '{obs.candidate_sha}'",
                )

            if active_candidate_sha and obs.candidate_sha != active_candidate_sha:
                return (
                    EpistemicDimension.UNSUPPORTED,
                    ApplicabilityDimension.INAPPLICABLE,
                    f"Stale candidate evidence: Active is '{active_candidate_sha}', observation is from '{obs.candidate_sha}'",
                )

            # 5. Check environment binding
            if claim.required_environment and obs.environment_fingerprint != claim.required_environment:
                return (
                    EpistemicDimension.UNSUPPORTED,
                    ApplicabilityDimension.INAPPLICABLE,
                    f"Environment mismatch: Claim requires '{claim.required_environment}', observed in '{obs.environment_fingerprint}'",
                )

            if active_environment_fingerprint and obs.environment_fingerprint != active_environment_fingerprint:
                return (
                    EpistemicDimension.UNSUPPORTED,
                    ApplicabilityDimension.INAPPLICABLE,
                    f"Stale environment evidence: Active is '{active_environment_fingerprint}', observed in '{obs.environment_fingerprint}'",
                )

            # 6. Check observation availability
            if obs.observation_status == ObservationDimension.UNAVAILABLE:
                return (
                    EpistemicDimension.UNSUPPORTED,
                    ApplicabilityDimension.UNRESOLVED,
                    "Verifier execution was unavailable or timed out.",
                )

            # 7. Check falsification flag
            if obs.is_falsified:
                contradictions.append(ev)
                continue

            # 8. Check coverage threshold
            if obs.coverage_percentage < spec.min_coverage_percentage:
                contradictions.append(ev)
                continue

            # 9. Evaluate physical execution outcome
            if obs.exit_code == 0 and obs.tests_failed == 0 and obs.tests_passed > 0:
                valid_supports.append(ev)
            elif obs.tests_failed > 0 or obs.exit_code != 0:
                contradictions.append(ev)
            else:
                # 0 tests executed -> no support
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

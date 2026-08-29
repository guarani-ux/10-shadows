"""
loop_engine/constitution — Unified Constitutional Ontology, Objective Lifecycle,
Relational Evidence, and Law 6 Sufficiency Engine for 10 SHADOWS.
"""

from .capability import (
    CapabilityDeficitEngine,
    CapabilityEpistemicStatus,
    ConditionalCapability,
    OperationalCondition,
)
from .evidence import (
    ApplicabilityDimension,
    AuthorityDimension,
    EpistemicClaim,
    EpistemicDimension,
    ObservationDimension,
    QualifiedEvidence,
    ReachabilityDimension,
    RelationalEvidenceEvaluator,
    VerifierExecutionObservation,
    VerifierSpecification,
)
from .lifecycle import (
    CandidateInterpretation,
    ObjectiveLifecycleManager,
    ObjectiveRevisionAuthorization,
    ProposedRequirement,
    RawIntent,
    RevisionType,
    SemanticQualificationStatus,
    VersionedObjectiveSpecification,
)
from .sufficiency import (
    CompositionRule,
    Law6SufficiencyEngine,
    ObjectiveSufficiencyProof,
)

__all__ = [
    "ApplicabilityDimension",
    "AuthorityDimension",
    "CandidateInterpretation",
    "CapabilityDeficitEngine",
    "CapabilityEpistemicStatus",
    "CompositionRule",
    "ConditionalCapability",
    "EpistemicClaim",
    "EpistemicDimension",
    "Law6SufficiencyEngine",
    "ObjectiveLifecycleManager",
    "ObjectiveRevisionAuthorization",
    "ObjectiveSufficiencyProof",
    "ObservationDimension",
    "OperationalCondition",
    "ProposedRequirement",
    "QualifiedEvidence",
    "RawIntent",
    "ReachabilityDimension",
    "RelationalEvidenceEvaluator",
    "RevisionType",
    "SemanticQualificationStatus",
    "VerifierExecutionObservation",
    "VerifierSpecification",
    "VersionedObjectiveSpecification",
]

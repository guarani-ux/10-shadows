"""
forge/core/substrate.py
Domain-Agnostic Substrate for 10 SHADOWS Forge.

Defines the mathematical primitives, atomic operator ontology, 7-stage capability
lifecycles, evidence classifications, objective adequacy states, and closure schemas.
"""

from dataclasses import dataclass, field
from enum import Enum
import hashlib
import json
from typing import Any, Callable, Dict, List, Optional, Set, Tuple


class OperatorType(str, Enum):
    """Initial atomic operator basis derived strictly from executable capabilities."""
    INGEST = "INGEST"
    EXTRACT = "EXTRACT"
    COMPARE = "COMPARE"
    TRANSFORM = "TRANSFORM"
    DECOMPOSE = "DECOMPOSE"
    COMPOSE = "COMPOSE"
    CALCULATE = "CALCULATE"
    RETRIEVE = "RETRIEVE"
    TEST = "TEST"
    VALIDATE = "VALIDATE"
    ACT = "ACT"
    DECIDE = "DECIDE"
    ESCALATE = "ESCALATE"


class EvidenceClass(str, Enum):
    """Rigorous epistemic evidence taxonomy."""
    VERIFIED_FACT = "VERIFIED_FACT"            # Physically established by verifier or root provenance
    DOCUMENTED_METRIC = "DOCUMENTED_METRIC"    # Empirical benchmark or telemetry measurement
    DIRECT_QUOTE = "DIRECT_QUOTE"              # Unaltered source quotation
    EMPIRICAL_TEST = "EMPIRICAL_TEST"          # Machine-signed test execution receipt
    UNVERIFIED_MODEL_PRIOR = "UNVERIFIED_MODEL_PRIOR"  # Latent LLM memory (ZERO authority for closure)


class CapabilityLifecycleState(str, Enum):
    """7-stage capability authorization lifecycle."""
    CANDIDATE = "CANDIDATE"                                  # Initial unverified code proposal
    SYNTACTICALLY_VALID = "SYNTACTICALLY_VALID"              # AST parsed, compile() passes
    ISOLATED_TESTED = "ISOLATED_TESTED"                      # Passes sterile sandbox test suite
    VERIFIED_FOR_TASK = "VERIFIED_FOR_TASK"                  # Authorized for single task execution
    PROVISIONALLY_AVAILABLE = "PROVISIONALLY_AVAILABLE"      # Staged for multi-task evaluation
    REUSE_VERIFIED = "REUSE_VERIFIED"                        # Successfully transferred to foreign task
    PROMOTED = "PROMOTED"                                    # Fully promoted persistent system capability


class ObjectiveAdequacyState(str, Enum):
    """Upstream intent coverage and epistemic validity state."""
    ADEQUATE_FOR_EXECUTION = "ADEQUATE_FOR_EXECUTION"
    SOURCE_UNCOVERED = "SOURCE_UNCOVERED"
    SOURCE_AMBIGUOUS = "SOURCE_AMBIGUOUS"
    DOMAIN_REQUIREMENTS_UNVERIFIED = "DOMAIN_REQUIREMENTS_UNVERIFIED"
    REQUIRES_CAPABILITY = "REQUIRES_CAPABILITY"


class RequirementDisposition(str, Enum):
    """Disposition of each raw intent clause."""
    PRESERVED = "PRESERVED"
    NORMALIZED = "NORMALIZED"
    DEFERRED = "DEFERRED"
    REJECTED = "REJECTED"
    AMBIGUOUS = "AMBIGUOUS"
    IRRELEVANT = "IRRELEVANT"


class RequirementOrigin(str, Enum):
    """Origin classification for requirements in CanonicalObjective."""
    SOURCE_EXPLICIT = "SOURCE_EXPLICIT"
    SYSTEM_INVARIANT = "SYSTEM_INVARIANT"
    DOMAIN_DERIVED = "DOMAIN_DERIVED"
    ASSUMED = "ASSUMED"


@dataclass
class RawClause:
    clause_id: str
    text: str
    is_constraint: bool
    is_deliverable: bool


@dataclass
class RequirementTrace:
    raw_clause_id: str
    raw_text: str
    disposition: RequirementDisposition
    canonical_target: Optional[str] = None
    justification: Optional[str] = None


@dataclass
class CanonicalRequirement:
    requirement_id: str
    description: str
    origin: RequirementOrigin
    source_clause_id: Optional[str] = None
    required_domain_capability: Optional[str] = None


@dataclass
class ObjectiveAdequacyContract:
    objective_id: str
    adequacy_state: ObjectiveAdequacyState
    raw_clauses: List[RawClause]
    traces: List[RequirementTrace]
    unaccounted_drops: List[str]
    unauthorized_assumptions: List[str]
    missing_domain_capabilities: List[str]
    details: Dict[str, Any] = field(default_factory=dict)

    @property
    def permits_execution(self) -> bool:
        return self.adequacy_state == ObjectiveAdequacyState.ADEQUATE_FOR_EXECUTION


@dataclass
class EvidenceRequirement:
    evidence_id: str
    claim_or_decision_supported: str
    required_evidence_class: EvidenceClass
    minimum_confidence: float = 1.0
    provenance_requirements: List[str] = field(default_factory=list)


@dataclass
class RequiredOperation:
    operation_id: str
    operator: OperatorType
    semantic_responsibility: str
    inputs: List[str]
    outputs: List[str]
    preconditions: List[str] = field(default_factory=list)
    postconditions: List[str] = field(default_factory=list)
    dependencies: List[str] = field(default_factory=list)
    evidence_requirements: List[EvidenceRequirement] = field(default_factory=list)
    uncertainty: float = 0.0
    failure_modes: List[str] = field(default_factory=list)


@dataclass
class CapabilityManifest:
    capability_id: str
    operations_supported: List[OperatorType]
    input_contracts: Dict[str, Any]
    output_contracts: Dict[str, Any]
    authority_requirements: List[str]
    evidence_requirements: List[str]
    execution_adapter: Callable[..., Any]
    verifier: Optional[Callable[..., bool]] = None
    lifecycle_state: CapabilityLifecycleState = CapabilityLifecycleState.CANDIDATE
    limitations: List[str] = field(default_factory=list)
    provenance: Dict[str, Any] = field(default_factory=dict)
    version: str = "1.0.0"
    times_reused: int = 0

    @property
    def is_authorized_for_execution(self) -> bool:
        return self.lifecycle_state in (
            CapabilityLifecycleState.VERIFIED_FOR_TASK,
            CapabilityLifecycleState.PROVISIONALLY_AVAILABLE,
            CapabilityLifecycleState.REUSE_VERIFIED,
            CapabilityLifecycleState.PROMOTED,
        )


@dataclass
class VerificationContract:
    contract_id: str
    observable_success_condition: str
    verification_method: str
    evidence_required: List[str]
    validator_fn: Optional[Callable[[Any], bool]] = None


@dataclass
class DecompositionProof:
    objective_hash: str
    mapped_operations: List[str]
    uncovered_requirements: List[str]
    introduced_assumptions: List[str]
    dependency_completeness: bool
    terminal_output_coverage: float
    verification_coverage: float
    closure_status: str  # SATISFIED | INSUFFICIENT | ONTOLOGY_INSUFFICIENT
    operation_deficits: List[str] = field(default_factory=list)


@dataclass
class CapabilityDeficit:
    required_operation_id: str
    missing_capability: str
    consequence: str
    provisionable: bool
    acquisition_route: str  # PROVISION | ACQUIRE | ESCALATE | REFUSE


@dataclass
class EvidenceDeficit:
    evidence_id: str
    claim: str
    missing_evidence_class: EvidenceClass
    resolution_route: str  # RETRIEVE | ESCALATE | REFUSE


@dataclass
class ClosureReport:
    is_closed: bool
    satisfied_operations: List[str]
    satisfied_evidence: List[str]
    capability_deficits: List[CapabilityDeficit]
    evidence_deficits: List[EvidenceDeficit]
    anti_cheating_violation: bool = False
    rejection_reason: Optional[str] = None


@dataclass
class ExecutionGraph:
    graph_id: str
    objective_hash: str
    operations: List[RequiredOperation]
    capability_bindings: Dict[str, str]  # operation_id -> capability_id
    evidence_dependencies: Dict[str, List[str]]
    verification_gates: List[VerificationContract]
    human_gates: List[str]
    stop_conditions: List[str]
    failure_routes: Dict[str, str]

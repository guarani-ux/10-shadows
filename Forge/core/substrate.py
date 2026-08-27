"""
forge/core/substrate.py
Domain-Agnostic Canonical Substrate for 10 SHADOWS Forge.

Defines the mathematical primitives, atomic operator ontology, 7-stage capability
lifecycles, obligation authorities, capability kinds, evidence classifications,
semantic contracts, candidate bindings, applicability proofs, and immutable provenance links.
"""

from dataclasses import dataclass, field
from enum import Enum
import hashlib
import json
from typing import Any, Callable, Dict, List, Optional, Set, Tuple, Union


def canonical_json(data: Any) -> str:
    """Computes deterministic canonical JSON string with sorted keys and compact separators."""
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
    """Computes deterministic SHA256 hex digest of canonical JSON serialization."""
    return hashlib.sha256(canonical_json(data).encode("utf-8")).hexdigest()


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
    SOURCE_PROVIDED = "SOURCE_PROVIDED"        # Explicitly supplied in input (NOT externally verified fact)
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


class CapabilityKind(str, Enum):
    """Classification of capability implementation authority."""
    REAL_PHYSICAL_ADAPTER = "REAL_PHYSICAL_ADAPTER"          # Bound to real physical subsystem / disk / kernel / DB
    VERIFIED_EXTERNAL_ADAPTER = "VERIFIED_EXTERNAL_ADAPTER"  # Bound to verified external tool / process
    NON_AUTHORITATIVE_TEST_DOUBLE = "NON_AUTHORITATIVE_TEST_DOUBLE"  # Test stub / mock (FORBIDDEN for production closure)
    UNAVAILABLE = "UNAVAILABLE"                              # Deficit marker


class ObligationAuthority(str, Enum):
    """Authority taxonomy for SatisfactionObligations."""
    SOURCE_GROUNDED = "SOURCE_GROUNDED"                      # Derived directly from raw human source intent
    SYSTEM_INVARIANT = "SYSTEM_INVARIANT"                    # Derived from architectural TCB invariants
    VERIFIED_DOMAIN_DERIVED = "VERIFIED_DOMAIN_DERIVED"      # Derived from a verified registered domain model
    MODEL_HYPOTHESIS = "MODEL_HYPOTHESIS"                    # Proposed by LLM (ZERO closure authority by itself)
    HUMAN_APPROVED = "HUMAN_APPROVED"                        # Explicitly gated and authorized by human


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


class SemanticBindingStatus(str, Enum):
    """Lifecycle status of candidate semantic interpretations."""
    PROPOSED = "PROPOSED"                                    # Unverified candidate interpretation
    GROUNDED = "GROUNDED"                                    # Verified by independent authority in KernelDatabase
    AMBIGUOUS = "AMBIGUOUS"                                  # Multiple conflicting interpretations with no deciding authority
    UNSUPPORTED = "UNSUPPORTED"                              # No authority grounds this interpretation
    DOMAIN_AUTHORITY_REQUIRED = "DOMAIN_AUTHORITY_REQUIRED"  # Requires kernel-registered domain authority
    HUMAN_AUTHORITY_REQUIRED = "HUMAN_AUTHORITY_REQUIRED"    # Requires explicit human decision receipt


class SemanticAuthoritySource(str, Enum):
    """Legal sources of semantic applicability authority."""
    SOURCE_EXPLICIT_CONTRACT = "SOURCE_EXPLICIT_CONTRACT"    # Explicit machine-readable contract at ingress
    VERIFIED_DOMAIN_AUTHORITY = "VERIFIED_DOMAIN_AUTHORITY"  # Registered in KernelDatabase with valid evidence
    SYSTEM_INVARIANT = "SYSTEM_INVARIANT"                    # Hardcoded architectural TCB invariant
    EXPLICIT_HUMAN_APPROVAL = "EXPLICIT_HUMAN_APPROVAL"      # Approved by human gate bound to exact hash
    AUTHORITATIVE_EXTERNAL_EVIDENCE = "AUTHORITATIVE_EXTERNAL_EVIDENCE" # Machine-signed evidence establishing R -> S
    UNVERIFIED_MODEL_PROPOSAL = "UNVERIFIED_MODEL_PROPOSAL"  # Zero closure authority


@dataclass(frozen=True)
class ContractField:
    """Typed schema definition for semantic input/output fields."""
    type_name: str
    required: bool = True
    unit: Optional[str] = None
    constraints: Dict[str, Any] = field(default_factory=dict)
    schema_ref: Optional[str] = None


@dataclass(frozen=True)
class SemanticContract:
    """Canonical representation of a semantic transformation contract."""
    effect_type: str
    inputs: Dict[str, ContractField]
    outputs: Dict[str, ContractField]
    transformation_rule: Optional[str] = None
    evidence_requirements: Tuple["EvidenceRequirement", ...] = ()
    authority_requirements: Tuple[str, ...] = ()
    verification_spec: Optional[Dict[str, Any]] = None
    schema_version: str = "1.0"

    @property
    def contract_hash(self) -> str:
        return compute_digest({
            "effect_type": self.effect_type,
            "inputs": {k: v.__dict__ for k, v in self.inputs.items()},
            "outputs": {k: v.__dict__ for k, v in self.outputs.items()},
            "transformation_rule": self.transformation_rule,
            "evidence": [e.evidence_id for e in self.evidence_requirements],
            "authority": list(self.authority_requirements),
            "verification_spec": self.verification_spec,
            "schema_version": self.schema_version,
        })


@dataclass(frozen=True)
class CandidateSemanticBinding:
    """Candidate interpretation of a requirement (ZERO authority by definition)."""
    binding_hash: str
    requirement_hash: str
    source_requirement_id: str
    semantic_contract: SemanticContract
    is_blocking: bool
    candidate_provenance: Dict[str, Any]


@dataclass(frozen=True)
class SemanticApplicabilityProof:
    """Proof of semantic applicability resolved from KernelDatabase custody."""
    proof_id: str
    binding_hash: str
    requirement_hash: str
    semantic_contract_hash: str
    authority_source: SemanticAuthoritySource
    authority_record_id: str
    verifier_version: str = "1.0.0"


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
    requirement_hash: str = ""
    is_blocking: bool = True
    blocking_authority: str = "SOURCE_DEFAULT"

    def __post_init__(self):
        if not self.requirement_hash:
            self.requirement_hash = compute_digest({
                "id": self.requirement_id,
                "desc": self.description,
                "origin": self.origin.value,
                "clause_id": self.source_clause_id,
                "domain_cap": self.required_domain_capability,
                "blocking": self.is_blocking,
                "blocking_auth": self.blocking_authority,
            })


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


@dataclass(frozen=True)
class EvidenceRequirement:
    evidence_id: str
    claim_or_decision_supported: str
    required_evidence_class: EvidenceClass
    minimum_confidence: float = 1.0
    provenance_requirements: List[str] = field(default_factory=list)


@dataclass
class VerificationContract:
    contract_id: str
    observable_success_condition: str
    verification_method: str
    evidence_required: List[str]
    validator_fn: Optional[Callable[[Any], bool]] = None
    bound_obligation_id: str = ""
    bound_operation_id: str = ""
    semantic_binding_hash: str = ""
    applicability_proof_id: str = ""
    verification_authority_id: str = ""
    verification_spec_hash: str = ""


@dataclass
class SatisfactionObligation:
    """
    Represents: WHAT MUST BECOME OBSERVABLY TRUE?
    Defines the physical effect, input/output contracts, and evidence boundaries.
    """
    obligation_id: str
    source_requirement_ids: List[str]
    authority: ObligationAuthority
    required_effect_type: str
    required_input_contract: Dict[str, Any]
    required_output_contract: Dict[str, Any]
    required_evidence: List[EvidenceRequirement] = field(default_factory=list)
    required_authority: List[str] = field(default_factory=list)
    required_verification: List[VerificationContract] = field(default_factory=list)
    is_blocking: bool = True
    provenance: Dict[str, Any] = field(default_factory=dict)
    requirement_hash: str = ""
    semantic_binding_hash: str = ""
    applicability_proof_id: str = ""
    applicability_proof_hash: str = ""

    @property
    def has_closure_authority(self) -> bool:
        return self.authority in (
            ObligationAuthority.SOURCE_GROUNDED,
            ObligationAuthority.SYSTEM_INVARIANT,
            ObligationAuthority.VERIFIED_DOMAIN_DERIVED,
            ObligationAuthority.HUMAN_APPROVED,
        )


@dataclass
class CapabilityManifest:
    """
    Truthful capability manifest representing physically verified adapters.
    """
    capability_id: str
    operations_supported: List[OperatorType]
    input_contracts: Dict[str, Any]
    output_contracts: Dict[str, Any]
    authority_requirements: List[str]
    evidence_requirements: List[str]
    execution_adapter: Callable[..., Any]
    verifier: Optional[Callable[..., bool]] = None
    kind: CapabilityKind = CapabilityKind.REAL_PHYSICAL_ADAPTER
    lifecycle_state: CapabilityLifecycleState = CapabilityLifecycleState.CANDIDATE
    limitations: List[str] = field(default_factory=list)
    provenance: Dict[str, Any] = field(default_factory=dict)
    version: str = "1.0.0"
    times_reused: int = 0

    @property
    def is_authorized_for_execution(self) -> bool:
        return (
            self.kind in (CapabilityKind.REAL_PHYSICAL_ADAPTER, CapabilityKind.VERIFIED_EXTERNAL_ADAPTER)
            and self.lifecycle_state in (
                CapabilityLifecycleState.VERIFIED_FOR_TASK,
                CapabilityLifecycleState.PROVISIONALLY_AVAILABLE,
                CapabilityLifecycleState.REUSE_VERIFIED,
                CapabilityLifecycleState.PROMOTED,
            )
        )


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
    bound_capability_id: Optional[str] = None
    source_obligation_id: str = ""
    source_obligation_hash: str = ""
    semantic_proof_id: str = ""
    semantic_binding_hash: str = ""
    capability_binding_hash: str = ""


@dataclass
class CapabilityBinding:
    obligation_id: str
    capability_id: str
    manifest: CapabilityManifest
    input_mapping: Dict[str, str] = field(default_factory=dict)
    output_mapping: Dict[str, str] = field(default_factory=dict)
    semantic_binding_hash: str = ""
    capability_manifest_hash: str = ""


@dataclass
class ResolutionDeficit:
    deficit_type: str  # SEMANTIC_BINDING_DEFICIT | AMBIGUOUS | DOMAIN_AUTHORITY_REQUIRED | HUMAN_AUTHORITY_REQUIRED | REPRESENTATION_DEFICIT | CAPABILITY_DEFICIT | CAPABILITY_SELECTION_DEFICIT | INPUT_DEFICIT | EVIDENCE_DEFICIT | VERIFIER_DEFICIT
    obligation_id: str
    reason: str
    missing_element: str
    acquisition_route: str = "PROVISION"  # PROVISION | ACQUIRE | ESCALATE | REFUSE


@dataclass
class ResolutionProof:
    is_resolved: bool
    satisfaction_obligations: List[SatisfactionObligation]
    capability_bindings: Dict[str, CapabilityBinding]
    induced_operations: List[RequiredOperation]
    resolution_deficits: List[ResolutionDeficit]
    deficit_type: Optional[str] = None
    cost_score: float = 0.0
    resolution_hash: str = ""
    semantic_proof_ids: Tuple[str, ...] = ()


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
    graph_hash: str = ""

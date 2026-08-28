"""
loop_engine/epistemic.py
Epistemic Disposition & Evidence Envelope Architecture for 10 SHADOWS.

Deep Module enforcing epistemic discipline across all data and artifact transformations.
Enforces Pirate King Negative Constraints:
1. No False Victory
4. No Silent Assumption Promotion
5. No Semantic Laundering
6. No Unverifiable Success Disguised as Verified Success
9. No Synthetic Evidence Masquerading as Reality
11. No Unknown-Domain Bluffing
29. No Degradation into Plausible Bullshit
30. No Inability to Know Its Own Boundary
"""

from dataclasses import asdict, dataclass, field
from enum import Enum
import hashlib
import json
import time
from typing import Any, Dict, Generic, List, Optional, TypeVar

T = TypeVar("T")


class EvidenceOrigin(str, Enum):
    PHYSICAL_OBSERVATION = "PHYSICAL_OBSERVATION"  # Empirical observation from real environment
    SYNTHETIC_FIXTURE = "SYNTHETIC_FIXTURE"        # Test fixture or simulated input
    MODEL_INFERENCE = "MODEL_INFERENCE"            # Unverified model generation or prior
    DERIVED_TRANSFORM = "DERIVED_TRANSFORM"        # Deterministic transformation of prior envelope
    DECLARED_SPEC = "DECLARED_SPEC"                # Intent / spec declaration


class EpistemicStatus(str, Enum):
    VERIFIED = "VERIFIED"          # Physically proven via independent verifier gate
    INFERRED = "INFERRED"          # Plausible deduction from established evidence
    HYPOTHESIS = "HYPOTHESIS"      # Working assumption or unverified proposal
    UNKNOWN = "UNKNOWN"            # Explicit lack of knowledge or capability
    CONTRADICTED = "CONTRADICTED"  # Falsified by physical evidence


class EpistemicDisposition(str, Enum):
    SATISFIED = "SATISFIED"                                     # Proven against requirement
    CONDITIONALLY_SUPPORTED = "CONDITIONALLY_SUPPORTED"         # Proven only against synthetic harness
    SEMANTIC_BINDING_DEFICIT = "SEMANTIC_BINDING_DEFICIT"       # Output produced but ungrounded in intent
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"             # Missing physical observations
    CAPABILITY_DEFICIT = "CAPABILITY_DEFICIT"                   # Required capability is missing
    EXTERNAL_AUTHORITY_REQUIRED = "EXTERNAL_AUTHORITY_REQUIRED" # Needs human / sovereign signoff
    UNRESOLVED = "UNRESOLVED"                                   # Explicit uncomputable or unknown


class SemanticLaunderingError(Exception):
    """Raised when an envelope transformation attempts to illegally upgrade epistemic status or origin."""
    pass


def canonical_json_digest(data: Any) -> str:
    """Computes deterministic SHA-256 digest of canonical JSON payload."""
    serialized = json.dumps(data, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class EvidenceEnvelope(Generic[T]):
    """
    Immutable, cryptographic container wrapping any artifact payload with its
    epistemic status, origin, provenance hash, and disposition.
    """
    payload: T
    origin: EvidenceOrigin
    status: EpistemicStatus
    source_id: str
    envelope_hash: str
    parent_hash: Optional[str] = None
    disposition: EpistemicDisposition = EpistemicDisposition.SATISFIED
    confidence: float = 1.0
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "payload": self.payload if isinstance(self.payload, (dict, list, str, int, float, bool, type(None))) else str(self.payload),
            "origin": self.origin.value,
            "status": self.status.value,
            "source_id": self.source_id,
            "envelope_hash": self.envelope_hash,
            "parent_hash": self.parent_hash,
            "disposition": self.disposition.value,
            "confidence": self.confidence,
            "timestamp": self.timestamp,
        }


def create_envelope(
    payload: T,
    origin: EvidenceOrigin,
    status: EpistemicStatus,
    source_id: str,
    disposition: EpistemicDisposition = EpistemicDisposition.SATISFIED,
    confidence: float = 1.0,
    parent_hash: Optional[str] = None,
) -> EvidenceEnvelope[T]:
    """
    Constructs a new deterministic, frozen EvidenceEnvelope.
    """
    payload_hash = canonical_json_digest(payload)
    envelope_data = {
        "payload_hash": payload_hash,
        "origin": origin.value,
        "status": status.value,
        "source_id": source_id,
        "disposition": disposition.value,
        "parent_hash": parent_hash,
    }
    envelope_hash = canonical_json_digest(envelope_data)

    return EvidenceEnvelope(
        payload=payload,
        origin=origin,
        status=status,
        source_id=source_id,
        envelope_hash=envelope_hash,
        parent_hash=parent_hash,
        disposition=disposition,
        confidence=confidence,
    )


def transform_envelope(
    parent_envelope: EvidenceEnvelope[Any],
    new_payload: T,
    new_source_id: str,
    new_origin: Optional[EvidenceOrigin] = None,
    new_status: Optional[EpistemicStatus] = None,
    new_disposition: Optional[EpistemicDisposition] = None,
    new_confidence: Optional[float] = None,
) -> EvidenceEnvelope[T]:
    """
    Transforms an envelope while strictly enforcing Anti-Semantic Laundering invariants:
    1. A synthetic origin CANNOT be transformed into a physical observation.
    2. An INFERRED or HYPOTHESIS status CANNOT be upgraded to VERIFIED without verified gate proof.
    3. The parent envelope's hash is permanently linked as parent_hash.
    """
    target_origin = new_origin or EvidenceOrigin.DERIVED_TRANSFORM
    target_status = new_status or parent_envelope.status
    target_disposition = new_disposition or parent_envelope.disposition
    target_confidence = new_confidence if new_confidence is not None else parent_envelope.confidence

    # Anti-Laundering Invariant 1: Synthetic cannot upgrade to Physical
    if parent_envelope.origin == EvidenceOrigin.SYNTHETIC_FIXTURE and target_origin == EvidenceOrigin.PHYSICAL_OBSERVATION:
        raise SemanticLaunderingError(
            f"Synthetic evidence cannot masquerade as physical observation in transformation at '{new_source_id}'."
        )

    # Anti-Laundering Invariant 2: Inferred/Hypothesis cannot upgrade to Verified without gate authority
    if parent_envelope.status in (EpistemicStatus.INFERRED, EpistemicStatus.HYPOTHESIS, EpistemicStatus.UNKNOWN):
        if target_status == EpistemicStatus.VERIFIED:
            raise SemanticLaunderingError(
                f"Semantic laundering detected: Cannot promote '{parent_envelope.status.value}' to 'VERIFIED' "
                f"at transform '{new_source_id}' without verified gate receipt."
            )

    return create_envelope(
        payload=new_payload,
        origin=target_origin,
        status=target_status,
        source_id=new_source_id,
        disposition=target_disposition,
        confidence=target_confidence,
        parent_hash=parent_envelope.envelope_hash,
    )

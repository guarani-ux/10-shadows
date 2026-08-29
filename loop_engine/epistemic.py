"""
loop_engine/epistemic.py
Epistemic Disposition & Evidence Envelope Architecture for 10 SHADOWS.

Deep Module enforcing epistemic discipline, proof-bearing minting, and DAG provenance.
Enforces Pirate King Negative Constraints:
1. No False Victory
2. No Self-Authored Proof
3. No Authority from Eloquence
4. No Silent Assumption Promotion
5. No Semantic Laundering
6. No Unverifiable Success Disguised as Verified Success
9. No Synthetic Evidence Masquerading as Reality
11. No Unknown-Domain Bluffing
29. No Degradation into Plausible Bullshit
30. No Inability to Know Its Own Boundary
"""

import hashlib
import json
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, Generic, List, Optional, Sequence, Tuple, TypeVar, Union

from loop_engine.authority import (
    InvalidWitnessError,
    PrivilegedMintingError,
    ProofWitness,
)

T = TypeVar("T")


class EvidenceOrigin(str, Enum):
    PHYSICAL_OBSERVATION = "PHYSICAL_OBSERVATION"  # Empirical observation from real environment
    SYNTHETIC_FIXTURE = "SYNTHETIC_FIXTURE"  # Test fixture or simulated input
    MODEL_INFERENCE = "MODEL_INFERENCE"  # Unverified model generation or prior
    DERIVED_TRANSFORM = "DERIVED_TRANSFORM"  # Deterministic transformation of prior envelope
    DECLARED_SPEC = "DECLARED_SPEC"  # Intent / spec declaration


class EpistemicStatus(str, Enum):
    VERIFIED = "VERIFIED"  # Physically proven via independent verifier gate with ProofWitness
    INFERRED = "INFERRED"  # Plausible deduction from established evidence
    HYPOTHESIS = "HYPOTHESIS"  # Working assumption or unverified proposal
    UNKNOWN = "UNKNOWN"  # Explicit lack of knowledge or capability
    CONTRADICTED = "CONTRADICTED"  # Falsified by physical evidence


class EpistemicDisposition(str, Enum):
    SATISFIED = "SATISFIED"  # Proven against requirement
    CONDITIONALLY_SUPPORTED = "CONDITIONALLY_SUPPORTED"  # Proven only against synthetic harness
    SEMANTIC_BINDING_DEFICIT = "SEMANTIC_BINDING_DEFICIT"  # Output produced but ungrounded in intent
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"  # Missing physical observations
    CAPABILITY_DEFICIT = "CAPABILITY_DEFICIT"  # Required capability is missing
    EXTERNAL_AUTHORITY_REQUIRED = "EXTERNAL_AUTHORITY_REQUIRED"  # Needs human / sovereign signoff
    UNRESOLVED = "UNRESOLVED"  # Explicit uncomputable or unknown


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
    epistemic status, origin, DAG parent hashes, and disposition.
    """

    payload: T
    origin: EvidenceOrigin
    status: EpistemicStatus
    source_id: str
    envelope_hash: str
    parent_hashes: Tuple[str, ...] = field(default_factory=tuple)
    disposition: EpistemicDisposition = EpistemicDisposition.SATISFIED
    confidence: float = 1.0
    timestamp: float = field(default_factory=time.time)

    @property
    def parent_hash(self) -> Optional[str]:
        """Backward compatibility helper returning the primary parent hash if present."""
        return self.parent_hashes[0] if self.parent_hashes else None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "payload": self.payload
            if isinstance(self.payload, (dict, list, str, int, float, bool, type(None)))
            else str(self.payload),
            "origin": self.origin.value,
            "status": self.status.value,
            "source_id": self.source_id,
            "envelope_hash": self.envelope_hash,
            "parent_hashes": list(self.parent_hashes),
            "parent_hash": self.parent_hash,
            "disposition": self.disposition.value,
            "confidence": self.confidence,
            "timestamp": self.timestamp,
        }


def _raw_create_envelope(
    payload: T,
    origin: EvidenceOrigin,
    status: EpistemicStatus,
    source_id: str,
    disposition: EpistemicDisposition,
    confidence: float,
    parent_hashes: Tuple[str, ...],
) -> EvidenceEnvelope[T]:
    """Internal constructor calculating cryptographic envelope digest."""
    payload_hash = canonical_json_digest(payload)
    envelope_data = {
        "payload_hash": payload_hash,
        "origin": origin.value,
        "status": status.value,
        "source_id": source_id,
        "disposition": disposition.value,
        "parent_hashes": list(parent_hashes),
    }
    envelope_hash = canonical_json_digest(envelope_data)

    return EvidenceEnvelope(
        payload=payload,
        origin=origin,
        status=status,
        source_id=source_id,
        envelope_hash=envelope_hash,
        parent_hashes=parent_hashes,
        disposition=disposition,
        confidence=confidence,
    )


def create_unverified_envelope(
    payload: T,
    origin: EvidenceOrigin,
    status: EpistemicStatus,
    source_id: str,
    disposition: EpistemicDisposition = EpistemicDisposition.UNRESOLVED,
    confidence: float = 1.0,
    parent_hashes: Sequence[str] = (),
) -> EvidenceEnvelope[T]:
    """
    Public constructor for non-privileged epistemic claims.
    Enforces Invariant: Privileged states (VERIFIED, PHYSICAL_OBSERVATION) CANNOT be minted here.
    """
    if status == EpistemicStatus.VERIFIED:
        raise PrivilegedMintingError(
            "Privileged status 'VERIFIED' cannot be created through unverified constructors. "
            "Use mint_verified_envelope() with an authentic ProofWitness."
        )

    if origin == EvidenceOrigin.PHYSICAL_OBSERVATION:
        raise PrivilegedMintingError(
            "Privileged origin 'PHYSICAL_OBSERVATION' cannot be asserted by caller without ProofWitness. "
            "Use mint_verified_envelope()."
        )

    return _raw_create_envelope(
        payload=payload,
        origin=origin,
        status=status,
        source_id=source_id,
        disposition=disposition,
        confidence=confidence,
        parent_hashes=tuple(parent_hashes),
    )


# Alias for backward-compatible call sites using unverified defaults
def create_envelope(
    payload: T,
    origin: EvidenceOrigin = EvidenceOrigin.DECLARED_SPEC,
    status: EpistemicStatus = EpistemicStatus.HYPOTHESIS,
    source_id: str = "caller",
    disposition: EpistemicDisposition = EpistemicDisposition.UNRESOLVED,
    confidence: float = 1.0,
    parent_hash: Optional[str] = None,
    parent_hashes: Sequence[str] = (),
) -> EvidenceEnvelope[T]:
    """
    Creates an unverified EvidenceEnvelope. Rejects caller assertions of privileged state.
    """
    parents = list(parent_hashes)
    if parent_hash and parent_hash not in parents:
        parents.append(parent_hash)

    return create_unverified_envelope(
        payload=payload,
        origin=origin,
        status=status,
        source_id=source_id,
        disposition=disposition,
        confidence=confidence,
        parent_hashes=parents,
    )


def mint_verified_envelope(
    payload: T,
    origin: EvidenceOrigin,
    source_id: str,
    witness: ProofWitness,
    disposition: EpistemicDisposition = EpistemicDisposition.SATISFIED,
    confidence: float = 1.0,
    parent_hashes: Sequence[str] = (),
) -> EvidenceEnvelope[T]:
    """
    Privileged Constructor: Mints a VERIFIED EvidenceEnvelope backed by an authentic ProofWitness.
    """
    payload_hash = canonical_json_digest(payload)
    if not witness.verify(expected_digest=payload_hash, expected_scope="EVIDENCE_VERIFICATION"):
        raise InvalidWitnessError(
            f"ProofWitness cryptographic verification failed for envelope payload at '{source_id}'."
        )

    return _raw_create_envelope(
        payload=payload,
        origin=origin,
        status=EpistemicStatus.VERIFIED,
        source_id=source_id,
        disposition=disposition,
        confidence=confidence,
        parent_hashes=tuple(parent_hashes),
    )


def transform_envelope(
    parent_envelope: Union[EvidenceEnvelope[Any], Sequence[EvidenceEnvelope[Any]]],
    new_payload: T,
    new_source_id: str,
    new_origin: Optional[EvidenceOrigin] = None,
    new_status: Optional[EpistemicStatus] = None,
    new_disposition: Optional[EpistemicDisposition] = None,
    new_confidence: Optional[float] = None,
    witness: Optional[ProofWitness] = None,
) -> EvidenceEnvelope[T]:
    """
    Transforms one or more parent envelopes into a derived envelope.
    Enforces DAG provenance and Epistemic Lattice invariants:
    1. Synthetic cannot upgrade to Physical.
    2. Inferred/Hypothesis cannot upgrade to Verified without ProofWitness.
    3. Any parent CONTRADICTED status propagates downward unless resolved.
    4. Confidence cannot exceed minimum parent confidence without a ProofWitness.
    """
    parents: List[EvidenceEnvelope[Any]] = (
        list(parent_envelope) if isinstance(parent_envelope, (list, tuple)) else [parent_envelope]
    )

    if not parents:
        raise ValueError("transform_envelope requires at least one parent envelope.")

    primary_parent = parents[0]
    all_parent_hashes = tuple(p.envelope_hash for p in parents)

    # Calculate bounded confidence
    min_parent_conf = min(p.confidence for p in parents)
    target_confidence = new_confidence if new_confidence is not None else min_parent_conf
    if witness is None and target_confidence > min_parent_conf:
        target_confidence = min_parent_conf  # Confidence cannot be inflated without witness

    target_origin = new_origin or EvidenceOrigin.DERIVED_TRANSFORM
    target_status = new_status or primary_parent.status
    target_disposition = new_disposition or primary_parent.disposition

    # Lattice Invariant 1: Any parent CONTRADICTED forces child to CONTRADICTED
    if any(p.status == EpistemicStatus.CONTRADICTED for p in parents):
        target_status = EpistemicStatus.CONTRADICTED
        target_disposition = EpistemicDisposition.UNRESOLVED

    # Lattice Invariant 2: Synthetic cannot upgrade to Physical
    if (
        any(p.origin == EvidenceOrigin.SYNTHETIC_FIXTURE for p in parents)
        and target_origin == EvidenceOrigin.PHYSICAL_OBSERVATION
    ):
        raise SemanticLaunderingError(
            f"Synthetic evidence cannot masquerade as physical observation in transformation at '{new_source_id}'."
        )

    # Lattice Invariant 3: Upgrading to VERIFIED requires authentic ProofWitness
    has_unverified_parent = any(
        p.status in (EpistemicStatus.INFERRED, EpistemicStatus.HYPOTHESIS, EpistemicStatus.UNKNOWN) for p in parents
    )
    if (
        has_unverified_parent or primary_parent.status != EpistemicStatus.VERIFIED
    ) and target_status == EpistemicStatus.VERIFIED:
        if witness is None:
            raise SemanticLaunderingError(
                f"Semantic laundering detected: Cannot promote unverified parent to 'VERIFIED' "
                f"at transform '{new_source_id}' without verified ProofWitness."
            )
        payload_hash = canonical_json_digest(new_payload)
        if not witness.verify(expected_digest=payload_hash, expected_scope="EVIDENCE_VERIFICATION"):
            raise InvalidWitnessError("ProofWitness signature validation failed during transform promotion.")

    return _raw_create_envelope(
        payload=new_payload,
        origin=target_origin,
        status=target_status,
        source_id=new_source_id,
        disposition=target_disposition,
        confidence=target_confidence,
        parent_hashes=all_parent_hashes,
    )

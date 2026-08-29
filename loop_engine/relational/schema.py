"""
loop_engine/relational/schema.py
Typed Relational Substrate Schemas & Epistemic Types for 10 SHADOWS.

Enforces:
1. Substrate Law 1: Authority (Edges cannot self-certify authority)
2. Substrate Law 2: Provenance (Unbroken causal chain on all consequential relationships)
3. Substrate Law 3: Independence (Builder != Verifier on relationship qualification)
4. Substrate Law 4: Evidence Monotonicity (Downgrade cascades, no silent upgrades)
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Tuple


class EpistemicStatus(str, Enum):
    """Epistemic status of relational nodes and edges."""

    PROPOSED = "PROPOSED"  # Model/worker proposal (hypothetical)
    INFERRED = "INFERRED"  # Inferred via heuristics or similarity
    OBSERVED = "OBSERVED"  # Directly observed physical event/artifact
    VERIFIED = "VERIFIED"  # Verified by independent test or oracle
    QUALIFIED = "QUALIFIED"  # Independently qualified for execution
    AUTHORITATIVE = "AUTHORITATIVE"  # Certified by Kernel authority
    CONTESTED = "CONTESTED"  # Under active adversarial challenge
    SUPERSEDED = "SUPERSEDED"  # Replaced by newer qualified version
    INVALIDATED = "INVALIDATED"  # Falsified or downgraded (JTMS retracted)


class NodeType(str, Enum):
    """Categorization of relational graph nodes."""

    OBJECTIVE = "OBJECTIVE"
    SUBPROBLEM = "SUBPROBLEM"
    REQUIREMENT = "REQUIREMENT"
    UNKNOWN = "UNKNOWN"
    CLAIM = "CLAIM"
    CAPABILITY = "CAPABILITY"
    SHADOW = "SHADOW"
    TOOL = "TOOL"
    MODEL = "MODEL"
    WORKER = "WORKER"
    CANDIDATE = "CANDIDATE"
    ARTIFACT = "ARTIFACT"
    EVIDENCE = "EVIDENCE"
    VERIFIER = "VERIFIER"
    ACQUISITION_TARGET = "ACQUISITION_TARGET"
    PROBLEM_PATTERN = "PROBLEM_PATTERN"


class RelationType(str, Enum):
    """Categorization of relational graph edges."""

    # Dependency / Decomposition
    REQUIRES = "REQUIRES"
    BLOCKS = "BLOCKS"
    DEPENDS_ON = "DEPENDS_ON"
    DECOMPOSES_INTO = "DECOMPOSES_INTO"
    CONTRADICTS = "CONTRADICTS"

    # Capability / Provisioning
    CAN_CONTRIBUTE_TO = "CAN_CONTRIBUTE_TO"
    PROVIDED_BY = "PROVIDED_BY"
    COMPATIBLE_WITH = "COMPATIBLE_WITH"
    PRODUCES = "PRODUCES"
    ACQUIRES = "ACQUIRES"

    # Evidence / Provenance
    SUPPORTED_BY = "SUPPORTED_BY"
    CHALLENGED_BY = "CHALLENGED_BY"
    PRODUCED_BY = "PRODUCED_BY"
    PERFORMED_BY = "PERFORMED_BY"
    DERIVED_FROM = "DERIVED_FROM"
    VERIFIED_BY = "VERIFIED_BY"
    AUTHORIZED_BY = "AUTHORIZED_BY"
    INVALIDATES = "INVALIDATES"

    # Experience / Transfer
    TRANSFERS_TO = "TRANSFERS_TO"
    REPAIRED_BY = "REPAIRED_BY"


@dataclass(frozen=True)
class RelationalNode:
    """
    Typed, immutable relational graph node representing a problem entity,
    capability, artifact, or claim.
    """

    node_id: str
    node_type: NodeType
    label: str
    properties: Dict[str, Any] = field(default_factory=dict)
    epistemic_status: EpistemicStatus = EpistemicStatus.PROPOSED
    provenance_digest: str = ""
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def with_status(self, new_status: EpistemicStatus) -> RelationalNode:
        """Returns a copy of the node with updated epistemic status."""
        return RelationalNode(
            node_id=self.node_id,
            node_type=self.node_type,
            label=self.label,
            properties=dict(self.properties),
            epistemic_status=new_status,
            provenance_digest=self.provenance_digest,
            created_at=self.created_at,
        )

    def compute_digest(self) -> str:
        payload = {
            "node_id": self.node_id,
            "node_type": self.node_type.value,
            "label": self.label,
            "properties": self.properties,
            "epistemic_status": self.epistemic_status.value,
        }
        return hashlib.sha256(json.dumps(payload, sort_keys=True).encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class RelationalEdge:
    """
    Typed, immutable directed relational graph edge with explicit epistemic
    status, evidence modality, and confidence score.
    """

    edge_id: str
    source_id: str
    target_id: str
    relation_type: RelationType
    epistemic_status: EpistemicStatus = EpistemicStatus.PROPOSED
    modality: str = "Structural"
    confidence: float = 1.0
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    metadata: Dict[str, Any] = field(default_factory=dict)

    def with_status(self, new_status: EpistemicStatus) -> RelationalEdge:
        """Returns a copy of the edge with updated epistemic status."""
        return RelationalEdge(
            edge_id=self.edge_id,
            source_id=self.source_id,
            target_id=self.target_id,
            relation_type=self.relation_type,
            epistemic_status=new_status,
            modality=self.modality,
            confidence=self.confidence,
            created_at=self.created_at,
            metadata=dict(self.metadata),
        )

    def compute_digest(self) -> str:
        payload = {
            "edge_id": self.edge_id,
            "source_id": self.source_id,
            "target_id": self.target_id,
            "relation_type": self.relation_type.value,
            "epistemic_status": self.epistemic_status.value,
            "modality": self.modality,
            "confidence": self.confidence,
        }
        return hashlib.sha256(json.dumps(payload, sort_keys=True).encode("utf-8")).hexdigest()

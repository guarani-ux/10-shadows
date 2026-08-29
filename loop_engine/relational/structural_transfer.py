"""
loop_engine/relational/structural_transfer.py
Structural Cross-Domain Strategy Transfer & Motif Matching for 10 SHADOWS.

Features:
- Encodes relational topologies of problem-solution motifs.
- Computes structural graph similarity without relying on surface vocabulary/keywords.
- Enforces Transfer Qualification: Structural transfer PROPOSES a strategy candidate,
  but cannot establish validity without independent verification.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
from typing import Any, Dict, List, Optional, Set, Tuple
import uuid

from loop_engine.relational.graph_db import RelationalGraphStore
from loop_engine.relational.schema import (
    EpistemicStatus,
    NodeType,
    RelationType,
    RelationalEdge,
    RelationalNode,
)


@dataclass(frozen=True)
class RelationalMotif:
    """A recurring topological pattern of nodes and relationships."""
    motif_id: str
    name: str
    source_domain: str
    node_types: Tuple[NodeType, ...]
    edge_relations: Tuple[RelationType, ...]
    success_rate: float
    epistemic_status: EpistemicStatus = EpistemicStatus.OBSERVED


@dataclass(frozen=True)
class TransferProposal:
    """A proposed cross-domain transfer candidate."""
    proposal_id: str
    matched_motif: RelationalMotif
    target_objective_id: str
    structural_similarity: float
    recommended_strategy: str
    transfer_status: EpistemicStatus = EpistemicStatus.PROPOSED


class StructuralTransferEngine:
    """
    Finds and transfers structural problem-solving motifs across domains.
    """

    def __init__(self, graph_store: RelationalGraphStore):
        self.store = graph_store
        self._registered_motifs: List[RelationalMotif] = []

    def register_motif(self, motif: RelationalMotif) -> None:
        """Registers a verified problem-solving motif in the store."""
        self._registered_motifs.append(motif)
        node = RelationalNode(
            node_id=f"motif_{motif.motif_id}",
            node_type=NodeType.PROBLEM_PATTERN,
            label=motif.name,
            properties={
                "source_domain": motif.source_domain,
                "node_types": [nt.value for nt in motif.node_types],
                "edge_relations": [er.value for er in motif.edge_relations],
                "success_rate": motif.success_rate,
            },
            epistemic_status=motif.epistemic_status,
        )
        self.store.upsert_node(node)

    def find_transferrable_strategies(
        self,
        target_objective_id: str,
        target_node_types: List[NodeType],
        target_relations: List[RelationType],
    ) -> List[TransferProposal]:
        """
        Compares relational topology of target objective against historical motifs.
        Returns ranked transfer proposals with structural similarity scores.
        """
        proposals: List[TransferProposal] = []
        target_nt_set = set(target_node_types)
        target_rel_set = set(target_relations)

        for motif in self._registered_motifs:
            # Jaccard similarity over node types and edge relations
            motif_nt_set = set(motif.node_types)
            motif_rel_set = set(motif.edge_relations)

            nt_intersection = len(target_nt_set.intersection(motif_nt_set))
            nt_union = len(target_nt_set.union(motif_nt_set)) or 1
            nt_sim = nt_intersection / nt_union

            rel_intersection = len(target_rel_set.intersection(motif_rel_set))
            rel_union = len(target_rel_set.union(motif_rel_set)) or 1
            rel_sim = rel_intersection / rel_union

            overall_sim = round(0.5 * nt_sim + 0.5 * rel_sim, 3)
            if overall_sim > 0.4:
                prop_id = f"trans_{uuid.uuid4().hex[:8]}"
                prop = TransferProposal(
                    proposal_id=prop_id,
                    matched_motif=motif,
                    target_objective_id=target_objective_id,
                    structural_similarity=overall_sim,
                    recommended_strategy=f"Apply {motif.name} composition structure from {motif.source_domain}",
                    transfer_status=EpistemicStatus.PROPOSED,
                )
                proposals.append(prop)

        # Sort by similarity descending
        proposals.sort(key=lambda p: p.structural_similarity, reverse=True)
        return proposals

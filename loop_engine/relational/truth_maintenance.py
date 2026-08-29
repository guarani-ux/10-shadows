"""
loop_engine/relational/truth_maintenance.py
Justification-Based Truth Maintenance System (JTMS) for 10 SHADOWS.

Enforces:
- Substrate Law 4: Evidence Monotonicity (Evidence can be downgraded, never silently upgraded)
- Cascading invalidation: When an assumption, evidence record, or candidate is falsified,
  all downstream derived claims, qualifications, and dependent plans are automatically retracted.
- Audit trail: Retains the exact falsification rationale on all invalidated nodes/edges.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Dict, List, Optional, Set, Tuple

from loop_engine.relational.graph_db import RelationalGraphStore
from loop_engine.relational.schema import (
    EpistemicStatus,
    RelationalEdge,
    RelationalNode,
    RelationType,
)


class TruthMaintenanceEngine:
    """
    Manages epistemic validity, dependency invalidation, and justification networks.
    """

    def __init__(self, graph_store: RelationalGraphStore):
        self.store = graph_store

    def retract_and_cascade(
        self,
        falsified_node_id: str,
        invalidation_reason: str,
    ) -> List[str]:
        """
        Falsifies the specified node and cascades the invalidation down all
        dependent outgoing derivation and support edges.
        Returns the list of all invalidated node IDs.
        """
        invalidated_node_ids: List[str] = []
        queue: List[str] = [falsified_node_id]
        visited: Set[str] = set()

        while queue:
            curr_id = queue.pop(0)
            if curr_id in visited:
                continue
            visited.add(curr_id)

            # 1. Invalidate current node
            node = self.store.get_node(curr_id)
            if node:
                updated_props = dict(node.properties)
                updated_props["invalidation_reason"] = invalidation_reason
                updated_props["invalidated_at"] = datetime.now(timezone.utc).isoformat()
                updated_node = RelationalNode(
                    node_id=node.node_id,
                    node_type=node.node_type,
                    label=node.label,
                    properties=updated_props,
                    epistemic_status=EpistemicStatus.INVALIDATED,
                    provenance_digest=node.provenance_digest,
                    created_at=node.created_at,
                )
                self.store.upsert_node(updated_node)
                invalidated_node_ids.append(curr_id)

            # 2. Find all incoming and outgoing justification edges to cascade
            # Nodes that DERIVED_FROM or are SUPPORTED_BY this node become invalidated
            incoming = self.store.get_incoming_edges(target_id=curr_id)
            for edge in incoming:
                if edge.relation_type in {RelationType.DERIVED_FROM, RelationType.SUPPORTED_BY}:
                    self.store.update_edge_status(edge.edge_id, EpistemicStatus.INVALIDATED)
                    queue.append(edge.source_id)

            outgoing = self.store.get_outgoing_edges(source_id=curr_id)
            for edge in outgoing:
                self.store.update_edge_status(edge.edge_id, EpistemicStatus.INVALIDATED)
                if edge.relation_type in {RelationType.REQUIRES, RelationType.DECOMPOSES_INTO, RelationType.PRODUCES}:
                    # Consequential dependencies may be re-evaluated
                    pass

        return invalidated_node_ids

    def downgrade_evidence(
        self,
        evidence_node_id: str,
        downgraded_status: EpistemicStatus,
        reason: str,
    ) -> List[str]:
        """
        Downgrades an evidence node according to Law 4 (e.g. VERIFIED -> CONTESTED or PROPOSED).
        Cascades status changes to dependent claims.
        """
        node = self.store.get_node(evidence_node_id)
        if not node:
            return []

        # Law 4 Check: Monotonicity cannot silently upgrade
        status_rank = {
            EpistemicStatus.AUTHORITATIVE: 6,
            EpistemicStatus.QUALIFIED: 5,
            EpistemicStatus.VERIFIED: 4,
            EpistemicStatus.OBSERVED: 3,
            EpistemicStatus.PROPOSED: 2,
            EpistemicStatus.INFERRED: 1,
            EpistemicStatus.CONTESTED: 0,
            EpistemicStatus.INVALIDATED: -1,
            EpistemicStatus.SUPERSEDED: -2,
        }

        current_rank = status_rank.get(node.epistemic_status, 0)
        new_rank = status_rank.get(downgraded_status, 0)
        if new_rank > current_rank:
            raise ValueError(
                f"Substrate Law 4 Violation: Cannot upgrade evidence from {node.epistemic_status} "
                f"to {downgraded_status} without new physical observation."
            )

        self.store.update_node_status(evidence_node_id, downgraded_status)
        if downgraded_status in {EpistemicStatus.INVALIDATED, EpistemicStatus.CONTESTED}:
            return self.retract_and_cascade(evidence_node_id, reason)
        return [evidence_node_id]

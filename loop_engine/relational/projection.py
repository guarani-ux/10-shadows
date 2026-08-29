"""
loop_engine/relational/projection.py
Authoritative Receipt to Relational Graph Projection Engine for 10 SHADOWS.

Enforces:
- Graph as Projection / Index over Authoritative State.
- Extracts unbroken causal provenance graphs from sealed TenShadowsReceipts.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from loop_engine.relational.graph_db import RelationalGraphStore
from loop_engine.relational.schema import (
    EpistemicStatus,
    NodeType,
    RelationType,
    RelationalEdge,
    RelationalNode,
)


class RelationalProjectionEngine:
    """
    Projects authoritative receipts into the relational graph substrate.
    """

    def __init__(self, graph_store: RelationalGraphStore):
        self.store = graph_store

    def project_receipt(self, receipt_dict: Dict[str, Any]) -> str:
        """
        Projects a sealed TenShadowsReceipt dictionary into nodes and provenance edges.
        Returns the root run_id.
        """
        run_id = receipt_dict.get("run_id", "unknown_run")
        task_id = receipt_dict.get("task_id", "unknown_task")
        objective = receipt_dict.get("objective", "")
        obj_hash = receipt_dict.get("objective_hash", "")
        final_status = receipt_dict.get("final_status", "UNKNOWN")

        # 1. Create Objective Node
        obj_node = RelationalNode(
            node_id=f"obj_{task_id}",
            node_type=NodeType.OBJECTIVE,
            label=objective[:60],
            properties={"objective": objective, "objective_hash": obj_hash},
            epistemic_status=EpistemicStatus.AUTHORITATIVE,
            provenance_digest=obj_hash,
        )
        self.store.upsert_node(obj_node)

        # 2. Create Candidate Node if present
        cand_data = receipt_dict.get("candidate_classification", {})
        cand_kind = cand_data.get("kind", "None")
        cand_sha = cand_data.get("details", {}).get("candidate_sha", receipt_dict.get("final_head", ""))

        if cand_sha:
            cand_status = EpistemicStatus.QUALIFIED if final_status == "VERIFIED_SUCCESS" else EpistemicStatus.OBSERVED
            cand_node = RelationalNode(
                node_id=f"cand_{cand_sha[:10]}",
                node_type=NodeType.CANDIDATE,
                label=f"Candidate {cand_sha[:8]}",
                properties={"sha": cand_sha, "kind": cand_kind},
                epistemic_status=cand_status,
                provenance_digest=cand_sha,
            )
            self.store.upsert_node(cand_node)

            # Edge: Candidate PRODUCED_BY Worker / Objective
            edge_cand = RelationalEdge(
                edge_id=f"edge_prod_{obj_node.node_id}_{cand_node.node_id}",
                source_id=cand_node.node_id,
                target_id=obj_node.node_id,
                relation_type=RelationType.DERIVED_FROM,
                epistemic_status=cand_status,
            )
            self.store.upsert_edge(edge_cand)

        # 3. Create Verification Node if present
        ver_data = receipt_dict.get("verification")
        if ver_data:
            ver_id = ver_data.get("verifier_id", f"ver_{task_id}")
            ver_status = EpistemicStatus.VERIFIED if ver_data.get("verified_status") == "PASS" else EpistemicStatus.INVALIDATED
            ver_node = RelationalNode(
                node_id=ver_id,
                node_type=NodeType.VERIFIER,
                label=f"Verifier {ver_data.get('tests_passed')}/{ver_data.get('tests_collected')}",
                properties=ver_data,
                epistemic_status=ver_status,
                provenance_digest=ver_data.get("test_digest", ""),
            )
            self.store.upsert_node(ver_node)

            if cand_sha:
                # Edge: Candidate VERIFIED_BY Verifier
                edge_ver = RelationalEdge(
                    edge_id=f"edge_ver_{cand_node.node_id}_{ver_id}",
                    source_id=cand_node.node_id,
                    target_id=ver_id,
                    relation_type=RelationType.VERIFIED_BY,
                    epistemic_status=ver_status,
                    modality=ver_data.get("modality", "DeterministicTest"),
                )
                self.store.upsert_edge(edge_ver)

        return run_id

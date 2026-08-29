"""
loop_engine/relational/gap_planner.py
Capability Gap Discovery, Acquisition Targeting, & Dynamic Replanning for 10 SHADOWS.

The Primary Graph Synergy:
1. Traverses objective requirements against qualified capability topology.
2. Detects missing capabilities as first-class Gap nodes.
3. Formulates structured AcquisitionTargets.
4. Invokes independent capability provisioning & qualification.
5. Dynamically links qualified capability into graph and replans previously blocked routes.
"""

from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

from loop_engine.relational.graph_db import RelationalGraphStore
from loop_engine.relational.schema import (
    EpistemicStatus,
    NodeType,
    RelationalEdge,
    RelationalNode,
    RelationType,
)


@dataclass(frozen=True)
class CapabilityRequirement:
    """Declared capability requirement for a subproblem or objective."""

    requirement_id: str
    capability_name: str
    required_domain: str
    input_contract: Dict[str, Any]
    output_contract: Dict[str, Any]


@dataclass(frozen=True)
class CapabilityGap:
    """Identified missing capability gap blocking an execution path."""

    gap_id: str
    objective_id: str
    requirement: CapabilityRequirement
    reason: str


@dataclass(frozen=True)
class TraversalPlan:
    """Result of a capability graph traversal."""

    is_traversable: bool
    objective_id: str
    execution_path: List[RelationalNode]
    unresolved_gaps: List[CapabilityGap]
    plan_digest: str


class CapabilityGapPlanner:
    """
    Finds routes through capability space, discovers missing capability gaps,
    and coordinates independent acquisition and dynamic replanning.
    """

    def __init__(self, graph_store: RelationalGraphStore):
        self.store = graph_store

    def plan_traversal(
        self,
        objective_id: str,
        requirements: List[CapabilityRequirement],
    ) -> TraversalPlan:
        """
        Traverses available qualified capabilities to find an executable route for the objective.
        If any required capability is missing or not qualified, returns an untraversable plan
        with explicit CapabilityGaps.
        """
        execution_path: List[RelationalNode] = []
        unresolved_gaps: List[CapabilityGap] = []

        # 1. Fetch Objective Node
        obj_node = self.store.get_node(objective_id)
        if not obj_node:
            obj_node = RelationalNode(
                node_id=objective_id,
                node_type=NodeType.OBJECTIVE,
                label=f"Objective {objective_id}",
                epistemic_status=EpistemicStatus.OBSERVED,
            )
            self.store.upsert_node(obj_node)

        # 2. Check each requirement against qualified capabilities in store
        for req in requirements:
            # Query graph for matching capability nodes with QUALIFIED or AUTHORITATIVE status
            cap_nodes = self._find_matching_capabilities(req)

            if cap_nodes:
                best_cap = cap_nodes[0]
                execution_path.append(best_cap)

                # Link edge: Objective REQUIRES Capability (epistemic_status: QUALIFIED)
                edge_id = f"edge_{objective_id}_{best_cap.node_id}_{req.capability_name}"
                edge = RelationalEdge(
                    edge_id=edge_id,
                    source_id=objective_id,
                    target_id=best_cap.node_id,
                    relation_type=RelationType.REQUIRES,
                    epistemic_status=EpistemicStatus.QUALIFIED,
                    modality="DeterministicTest",
                    confidence=1.0,
                    metadata={"requirement_id": req.requirement_id},
                )
                self.store.upsert_edge(edge)
            else:
                # Gap discovered!
                gap_id = f"gap_{req.requirement_id}_{uuid.uuid4().hex[:6]}"
                gap = CapabilityGap(
                    gap_id=gap_id,
                    objective_id=objective_id,
                    requirement=req,
                    reason=f"No qualified capability registered for '{req.capability_name}' in domain '{req.required_domain}'",
                )
                unresolved_gaps.append(gap)

                # Record AcquisitionTarget node in graph
                target_node = RelationalNode(
                    node_id=gap_id,
                    node_type=NodeType.ACQUISITION_TARGET,
                    label=f"Acquire {req.capability_name}",
                    properties={
                        "capability_name": req.capability_name,
                        "domain": req.required_domain,
                        "input_contract": req.input_contract,
                        "output_contract": req.output_contract,
                    },
                    epistemic_status=EpistemicStatus.PROPOSED,
                )
                self.store.upsert_node(target_node)

                # Edge: Objective BLOCKED_BY AcquisitionTarget
                edge_block = RelationalEdge(
                    edge_id=f"edge_block_{objective_id}_{gap_id}",
                    source_id=objective_id,
                    target_id=gap_id,
                    relation_type=RelationType.BLOCKS,
                    epistemic_status=EpistemicStatus.PROPOSED,
                    metadata={"gap_id": gap_id},
                )
                self.store.upsert_edge(edge_block)

        is_traversable = len(unresolved_gaps) == 0

        plan_payload = {
            "objective_id": objective_id,
            "is_traversable": is_traversable,
            "path_ids": [n.node_id for n in execution_path],
            "gap_ids": [g.gap_id for g in unresolved_gaps],
        }
        plan_digest = hashlib.sha256(json.dumps(plan_payload, sort_keys=True).encode("utf-8")).hexdigest()

        return TraversalPlan(
            is_traversable=is_traversable,
            objective_id=objective_id,
            execution_path=execution_path,
            unresolved_gaps=unresolved_gaps,
            plan_digest=plan_digest,
        )

    def resolve_gap_and_replan(
        self,
        objective_id: str,
        gap: CapabilityGap,
        candidate_code: str,
        qualifier_fn: Callable[[str, Dict[str, Any]], Tuple[bool, str]],
        requirements: List[CapabilityRequirement],
    ) -> Tuple[bool, TraversalPlan, Optional[str]]:
        """
        Synthesizes/provisions the missing capability, qualifies it independently via qualifier_fn,
        links the newly qualified capability into the graph, and replans the traversal.
        """
        # 1. Execute Independent Qualification (Builder != Verifier)
        is_qualified, verifier_trace = qualifier_fn(
            candidate_code,
            {
                "input_contract": gap.requirement.input_contract,
                "output_contract": gap.requirement.output_contract,
            },
        )

        if not is_qualified:
            # Retract / Mark Acquisition Target as INVALIDATED
            self.store.update_node_status(gap.gap_id, EpistemicStatus.INVALIDATED)
            # Replan will still show gap
            plan = self.plan_traversal(objective_id, requirements)
            return False, plan, f"Qualification rejected: {verifier_trace}"

        # 2. Provision Qualified Capability Node
        cap_id = f"cap_{gap.requirement.capability_name}_{uuid.uuid4().hex[:6]}"
        code_digest = hashlib.sha256(candidate_code.encode("utf-8")).hexdigest()

        cap_node = RelationalNode(
            node_id=cap_id,
            node_type=NodeType.CAPABILITY,
            label=f"Qualified {gap.requirement.capability_name}",
            properties={
                "capability_name": gap.requirement.capability_name,
                "domain": gap.requirement.required_domain,
                "code_digest": code_digest,
                "input_contract": gap.requirement.input_contract,
                "output_contract": gap.requirement.output_contract,
                "verifier_trace": verifier_trace,
            },
            epistemic_status=EpistemicStatus.QUALIFIED,
            provenance_digest=code_digest,
        )
        self.store.upsert_node(cap_node)

        # 3. Retract Acquisition Target (SUPERSEDED by Qualified Capability)
        self.store.update_node_status(gap.gap_id, EpistemicStatus.SUPERSEDED)

        # 4. Replan traversal across the updated graph topology
        new_plan = self.plan_traversal(objective_id, requirements)
        return new_plan.is_traversable, new_plan, None

    def _find_matching_capabilities(self, req: CapabilityRequirement) -> List[RelationalNode]:
        """Finds qualified capabilities matching domain and name."""
        with self.store.get_connection() as conn:
            rows = conn.execute(
                """
                SELECT * FROM graph_nodes 
                WHERE node_type = 'CAPABILITY'
                  AND epistemic_status IN ('QUALIFIED', 'AUTHORITATIVE', 'VERIFIED')
                """
            ).fetchall()

            matched: List[RelationalNode] = []
            for r in rows:
                props = json.loads(r["properties_json"])
                if props.get("capability_name") == req.capability_name and props.get("domain") in {
                    req.required_domain,
                    "general",
                }:
                    matched.append(
                        RelationalNode(
                            node_id=r["node_id"],
                            node_type=NodeType(r["node_type"]),
                            label=r["label"],
                            properties=props,
                            epistemic_status=EpistemicStatus(r["epistemic_status"]),
                            provenance_digest=r["provenance_digest"],
                            created_at=r["created_at"],
                        )
                    )
            return matched

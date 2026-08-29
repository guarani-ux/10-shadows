"""
loop_engine/relational/dependency_scheduler.py
Topological Dependency Graph Scheduler & Parallel Frontier Engine for 10 SHADOWS.

Borrowing principles from Bazel & Content-Addressed Build DAGs:
- Computes topological order of subproblems and requirements.
- Detects circular dependencies before execution.
- Exposes independent parallelizable execution frontiers.
"""

from __future__ import annotations

from collections import defaultdict, deque
from typing import Dict, List, Optional, Set, Tuple

from loop_engine.relational.graph_db import RelationalGraphStore
from loop_engine.relational.schema import (
    EpistemicStatus,
    NodeType,
    RelationalEdge,
    RelationalNode,
    RelationType,
)


class CyclicDependencyError(Exception):
    """Raised when a dependency cycle is detected in the problem/task graph."""

    pass


class DependencyScheduler:
    """
    Schedules objective execution based on explicit topological dependencies.
    """

    def __init__(self, graph_store: RelationalGraphStore):
        self.store = graph_store

    def get_ready_frontier(
        self,
        root_node_id: str,
        completed_nodes: Set[str],
        allowed_statuses: Optional[Set[EpistemicStatus]] = None,
    ) -> List[RelationalNode]:
        """
        Returns all nodes reachable from root whose dependencies are 100% satisfied
        (in completed_nodes) and have not yet completed.
        """
        # Find all nodes in the subproblem tree
        dep_tuples = self.store.find_transitive_dependencies(
            start_node_id=root_node_id,
            relation_types={RelationType.REQUIRES, RelationType.DEPENDS_ON, RelationType.DECOMPOSES_INTO},
            allowed_statuses=allowed_statuses,
        )
        sub_node_ids = {node_id for node_id, _ in dep_tuples}
        sub_node_ids.add(root_node_id)

        ready: List[RelationalNode] = []
        for nid in sub_node_ids:
            if nid in completed_nodes:
                continue

            # Check if all prerequisite dependencies (outgoing DEPENDS_ON / REQUIRES edges) are satisfied
            outgoing = self.store.get_outgoing_edges(
                source_id=nid,
                relation_type=RelationType.DEPENDS_ON,
                min_status=allowed_statuses,
            )
            # A node is blocked if any prerequisite node is not in completed_nodes
            is_blocked = False
            for edge in outgoing:
                if edge.target_id in sub_node_ids and edge.target_id not in completed_nodes:
                    is_blocked = True
                    break

            if not is_blocked:
                node = self.store.get_node(nid)
                if node and node.epistemic_status != EpistemicStatus.INVALIDATED:
                    ready.append(node)

        return ready

    def compute_topological_order(
        self,
        nodes: List[RelationalNode],
        edges: List[RelationalEdge],
    ) -> List[RelationalNode]:
        """
        Computes strict topological ordering of nodes.
        Raises CyclicDependencyError if circular references exist.
        """
        in_degree: Dict[str, int] = {n.node_id: 0 for n in nodes}
        adj_list: Dict[str, List[str]] = defaultdict(list)
        node_map: Dict[str, RelationalNode] = {n.node_id: n for n in nodes}

        for edge in edges:
            if edge.relation_type in {RelationType.REQUIRES, RelationType.DEPENDS_ON}:
                # source depends on target, so target must be executed before source
                adj_list[edge.target_id].append(edge.source_id)
                in_degree[edge.source_id] = in_degree.get(edge.source_id, 0) + 1

        queue = deque([nid for nid, deg in in_degree.items() if deg == 0])
        ordered: List[RelationalNode] = []

        while queue:
            curr_id = queue.popleft()
            if curr_id in node_map:
                ordered.append(node_map[curr_id])

            for neighbor_id in adj_list[curr_id]:
                in_degree[neighbor_id] -= 1
                if in_degree[neighbor_id] == 0:
                    queue.append(neighbor_id)

        if len(ordered) != len(nodes):
            raise CyclicDependencyError(f"Cyclic dependency detected: scheduled {len(ordered)} of {len(nodes)} nodes.")

        return ordered

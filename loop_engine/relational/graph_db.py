"""
loop_engine/relational/graph_db.py
Transactional SQLite Relational Graph Store with Recursive CTE Traversal.

Features:
- Full WAL mode persistence with foreign key constraints.
- Sub-millisecond recursive path discovery and transitive closure queries.
- Zero external database dependencies (100% native SQLite).
- Epistemic status filtering (e.g., traverse only QUALIFIED/AUTHORITATIVE edges).
"""

from __future__ import annotations

import json
from pathlib import Path
import sqlite3
from typing import Any, Dict, List, Optional, Set, Tuple, Union

from loop_engine.relational.schema import (
    EpistemicStatus,
    NodeType,
    RelationType,
    RelationalEdge,
    RelationalNode,
)


class RelationalGraphStore:
    """
    Transactional SQLite-backed graph store for relational intelligence.
    """

    def __init__(self, db_path: Optional[Union[str, Path]] = None):
        if db_path == ":memory:":
            self.db_path = ":memory:"
        else:
            self.db_path = Path(db_path) if db_path else Path("scratch/relational_graph.db")
            self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def get_connection(self) -> sqlite3.Connection:
        """Returns a configured SQLite connection."""
        if self.db_path == ":memory:":
            # For in-memory, we can maintain an active connection
            if not hasattr(self, "_mem_conn") or self._mem_conn is None:
                self._mem_conn = sqlite3.connect(":memory:", timeout=15.0)
                self._mem_conn.execute("PRAGMA foreign_keys = ON;")
                self._mem_conn.row_factory = sqlite3.Row
            return self._mem_conn

        conn = sqlite3.connect(str(self.db_path), timeout=15.0)
        conn.execute("PRAGMA journal_mode = WAL;")
        conn.execute("PRAGMA synchronous = NORMAL;")
        conn.execute("PRAGMA foreign_keys = ON;")
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        """Initializes tables and indexes for relational nodes and edges."""
        with self.get_connection() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS graph_nodes (
                    node_id TEXT PRIMARY KEY,
                    node_type TEXT NOT NULL,
                    label TEXT NOT NULL,
                    properties_json TEXT NOT NULL,
                    epistemic_status TEXT NOT NULL,
                    provenance_digest TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS graph_edges (
                    edge_id TEXT PRIMARY KEY,
                    source_id TEXT NOT NULL,
                    target_id TEXT NOT NULL,
                    relation_type TEXT NOT NULL,
                    epistemic_status TEXT NOT NULL,
                    modality TEXT NOT NULL,
                    confidence REAL NOT NULL,
                    metadata_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY(source_id) REFERENCES graph_nodes(node_id) ON DELETE CASCADE,
                    FOREIGN KEY(target_id) REFERENCES graph_nodes(node_id) ON DELETE CASCADE
                );

                CREATE INDEX IF NOT EXISTS idx_nodes_type ON graph_nodes(node_type);
                CREATE INDEX IF NOT EXISTS idx_nodes_status ON graph_nodes(epistemic_status);
                CREATE INDEX IF NOT EXISTS idx_edges_source ON graph_edges(source_id, relation_type);
                CREATE INDEX IF NOT EXISTS idx_edges_target ON graph_edges(target_id, relation_type);
                CREATE INDEX IF NOT EXISTS idx_edges_status ON graph_edges(epistemic_status);
                """
            )

    def upsert_node(self, node: RelationalNode) -> None:
        """Inserts or updates a graph node."""
        with self.get_connection() as conn:
            conn.execute(
                """
                INSERT INTO graph_nodes (
                    node_id, node_type, label, properties_json, epistemic_status,
                    provenance_digest, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(node_id) DO UPDATE SET
                    node_type=excluded.node_type,
                    label=excluded.label,
                    properties_json=excluded.properties_json,
                    epistemic_status=excluded.epistemic_status,
                    provenance_digest=excluded.provenance_digest;
                """,
                (
                    node.node_id,
                    node.node_type.value,
                    node.label,
                    json.dumps(node.properties),
                    node.epistemic_status.value,
                    node.provenance_digest,
                    node.created_at,
                ),
            )

    def upsert_edge(self, edge: RelationalEdge) -> None:
        """Inserts or updates a graph edge."""
        with self.get_connection() as conn:
            conn.execute(
                """
                INSERT INTO graph_edges (
                    edge_id, source_id, target_id, relation_type, epistemic_status,
                    modality, confidence, metadata_json, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(edge_id) DO UPDATE SET
                    source_id=excluded.source_id,
                    target_id=excluded.target_id,
                    relation_type=excluded.relation_type,
                    epistemic_status=excluded.epistemic_status,
                    modality=excluded.modality,
                    confidence=excluded.confidence,
                    metadata_json=excluded.metadata_json;
                """,
                (
                    edge.edge_id,
                    edge.source_id,
                    edge.target_id,
                    edge.relation_type.value,
                    edge.epistemic_status.value,
                    edge.modality,
                    edge.confidence,
                    json.dumps(edge.metadata),
                    edge.created_at,
                ),
            )

    def get_node(self, node_id: str) -> Optional[RelationalNode]:
        """Fetches a node by ID."""
        with self.get_connection() as conn:
            row = conn.execute("SELECT * FROM graph_nodes WHERE node_id = ?", (node_id,)).fetchone()
            if not row:
                return None
            return RelationalNode(
                node_id=row["node_id"],
                node_type=NodeType(row["node_type"]),
                label=row["label"],
                properties=json.loads(row["properties_json"]),
                epistemic_status=EpistemicStatus(row["epistemic_status"]),
                provenance_digest=row["provenance_digest"],
                created_at=row["created_at"],
            )

    def get_outgoing_edges(
        self,
        source_id: str,
        relation_type: Optional[RelationType] = None,
        min_status: Optional[Set[EpistemicStatus]] = None,
    ) -> List[RelationalEdge]:
        """Gets all outgoing edges from source_id."""
        query = "SELECT * FROM graph_edges WHERE source_id = ?"
        params: List[Any] = [source_id]
        if relation_type:
            query += " AND relation_type = ?"
            params.append(relation_type.value)

        with self.get_connection() as conn:
            rows = conn.execute(query, params).fetchall()
            edges = []
            for r in rows:
                status = EpistemicStatus(r["epistemic_status"])
                if min_status and status not in min_status:
                    continue
                edges.append(
                    RelationalEdge(
                        edge_id=r["edge_id"],
                        source_id=r["source_id"],
                        target_id=r["target_id"],
                        relation_type=RelationType(r["relation_type"]),
                        epistemic_status=status,
                        modality=r["modality"],
                        confidence=r["confidence"],
                        metadata=json.loads(r["metadata_json"]),
                        created_at=r["created_at"],
                    )
                )
            return edges

    def get_incoming_edges(
        self,
        target_id: str,
        relation_type: Optional[RelationType] = None,
        min_status: Optional[Set[EpistemicStatus]] = None,
    ) -> List[RelationalEdge]:
        """Gets all incoming edges pointing to target_id."""
        query = "SELECT * FROM graph_edges WHERE target_id = ?"
        params: List[Any] = [target_id]
        if relation_type:
            query += " AND relation_type = ?"
            params.append(relation_type.value)

        with self.get_connection() as conn:
            rows = conn.execute(query, params).fetchall()
            edges = []
            for r in rows:
                status = EpistemicStatus(r["epistemic_status"])
                if min_status and status not in min_status:
                    continue
                edges.append(
                    RelationalEdge(
                        edge_id=r["edge_id"],
                        source_id=r["source_id"],
                        target_id=r["target_id"],
                        relation_type=RelationType(r["relation_type"]),
                        epistemic_status=status,
                        modality=r["modality"],
                        confidence=r["confidence"],
                        metadata=json.loads(r["metadata_json"]),
                        created_at=r["created_at"],
                    )
                )
            return edges

    def find_transitive_dependencies(
        self,
        start_node_id: str,
        relation_types: Set[RelationType],
        allowed_statuses: Optional[Set[EpistemicStatus]] = None,
    ) -> List[Tuple[str, int]]:
        """
        Executes a recursive SQLite CTE to find all transitively reachable nodes and depths.
        """
        rel_placeholders = ",".join(["?"] * len(relation_types))
        params: List[Any] = [start_node_id] + [r.value for r in relation_types]

        status_clause = ""
        if allowed_statuses:
            stat_placeholders = ",".join(["?"] * len(allowed_statuses))
            status_clause = f"AND epistemic_status IN ({stat_placeholders})"
            params.extend([s.value for s in allowed_statuses])

        cte_query = f"""
        WITH RECURSIVE dependency_tree(node_id, depth) AS (
            SELECT target_id, 1
            FROM graph_edges
            WHERE source_id = ? AND relation_type IN ({rel_placeholders}) {status_clause}
            UNION
            SELECT e.target_id, dt.depth + 1
            FROM graph_edges e
            JOIN dependency_tree dt ON e.source_id = dt.node_id
            WHERE e.relation_type IN ({rel_placeholders}) {status_clause} AND dt.depth < 50
        )
        SELECT DISTINCT node_id, MIN(depth) as min_depth
        FROM dependency_tree
        GROUP BY node_id
        ORDER BY min_depth ASC;
        """

        # Duplicate parameters for recursive UNION clause if needed
        union_params: List[Any] = [start_node_id]
        union_params.extend([r.value for r in relation_types])
        if allowed_statuses:
            union_params.extend([s.value for s in allowed_statuses])
        union_params.extend([r.value for r in relation_types])
        if allowed_statuses:
            union_params.extend([s.value for s in allowed_statuses])

        with self.get_connection() as conn:
            rows = conn.execute(cte_query, union_params).fetchall()
            return [(r["node_id"], r["min_depth"]) for r in rows]

    def update_node_status(self, node_id: str, new_status: EpistemicStatus) -> None:
        """Updates epistemic status of a node."""
        with self.get_connection() as conn:
            conn.execute(
                "UPDATE graph_nodes SET epistemic_status = ? WHERE node_id = ?",
                (new_status.value, node_id),
            )

    def update_edge_status(self, edge_id: str, new_status: EpistemicStatus) -> None:
        """Updates epistemic status of an edge."""
        with self.get_connection() as conn:
            conn.execute(
                "UPDATE graph_edges SET epistemic_status = ? WHERE edge_id = ?",
                (new_status.value, edge_id),
            )

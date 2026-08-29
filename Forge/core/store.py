"""
forge/core/store.py
Persistent transactional SQLite store for Forge with WAL mode and CAS revisions.
"""

import contextlib
import hashlib
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def canonical_json(data: Any) -> str:
    return json.dumps(data, sort_keys=True, separators=(",", ":"))


def compute_record_hash(parent_hash: Optional[str], record_data: Dict[str, Any]) -> str:
    base = f"{parent_hash or 'GENESIS'}:{canonical_json(record_data)}"
    return hashlib.sha256(base.encode("utf-8")).hexdigest()


from loop_engine.config import FORGE_DB_PATH, SCRATCH_DIR


class ForgeStore:
    def __init__(self, db_path: Optional[str | Path] = None):
        if db_path is None:
            SCRATCH_DIR.mkdir(parents=True, exist_ok=True)
            self.db_path = str(FORGE_DB_PATH)
        else:
            self.db_path = str(db_path)
        self._init_db()

    @contextlib.contextmanager
    def _get_connection(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON;")
        conn.execute("PRAGMA journal_mode = WAL;")
        try:
            with conn:
                yield conn
        finally:
            conn.close()

    def _init_db(self) -> None:
        with self._get_connection() as conn:
            conn.executescript("""
            CREATE TABLE IF NOT EXISTS runs (
                run_id TEXT PRIMARY KEY,
                created_at TEXT NOT NULL,
                request_json TEXT NOT NULL,
                task_spec_json TEXT,
                route_json TEXT,
                status TEXT NOT NULL,
                parent_hash TEXT,
                record_hash TEXT
            );

            CREATE TABLE IF NOT EXISTS artifacts (
                artifact_id TEXT PRIMARY KEY,
                task_id TEXT NOT NULL,
                artifact_type TEXT NOT NULL,
                version TEXT NOT NULL,
                spec_json TEXT NOT NULL,
                content_path TEXT,
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS transactions (
                transaction_id TEXT PRIMARY KEY,
                task_id TEXT NOT NULL,
                state TEXT NOT NULL,
                revision INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                parent_hash TEXT,
                record_hash TEXT
            );

            CREATE TABLE IF NOT EXISTS attempts (
                attempt_id TEXT PRIMARY KEY,
                transaction_id TEXT NOT NULL,
                state TEXT NOT NULL,
                proposal_json TEXT,
                created_at TEXT NOT NULL,
                FOREIGN KEY(transaction_id) REFERENCES transactions(transaction_id)
            );

            CREATE TABLE IF NOT EXISTS authorizations (
                authorization_id TEXT PRIMARY KEY,
                transaction_id TEXT NOT NULL,
                attempt_id TEXT NOT NULL,
                operation_hash TEXT NOT NULL,
                idempotency_key TEXT NOT NULL UNIQUE,
                state TEXT NOT NULL,
                issued_at TEXT NOT NULL,
                consumed_at TEXT,
                FOREIGN KEY(transaction_id) REFERENCES transactions(transaction_id)
            );

            CREATE TABLE IF NOT EXISTS learnings (
                learning_id TEXT PRIMARY KEY,
                task_id TEXT NOT NULL,
                execution_id TEXT,
                promotion TEXT NOT NULL,
                record_json TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            """)

    # --- Runs ---
    def record_run(
        self,
        run_id: str,
        request: Dict[str, Any],
        status: str = "PENDING",
        task_spec: Optional[Dict[str, Any]] = None,
        route: Optional[Dict[str, Any]] = None,
    ) -> None:
        record_payload = {
            "run_id": run_id,
            "request": request,
            "status": status,
            "task_spec": task_spec,
            "route": route,
        }
        rec_hash = compute_record_hash(None, record_payload)
        with self._get_connection() as conn:
            conn.execute(
                """
                INSERT INTO runs (run_id, created_at, request_json, task_spec_json, route_json, status, record_hash)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(run_id) DO UPDATE SET
                    status=excluded.status,
                    task_spec_json=coalesce(excluded.task_spec_json, runs.task_spec_json),
                    route_json=coalesce(excluded.route_json, runs.route_json),
                    record_hash=excluded.record_hash
                """,
                (
                    run_id,
                    utc_now_iso(),
                    json.dumps(request),
                    json.dumps(task_spec) if task_spec else None,
                    json.dumps(route) if route else None,
                    status,
                    rec_hash,
                ),
            )

    def get_run(self, run_id: str) -> Optional[Dict[str, Any]]:
        with self._get_connection() as conn:
            row = conn.execute("SELECT * FROM runs WHERE run_id = ?", (run_id,)).fetchone()
            if row:
                return {
                    "run_id": row["run_id"],
                    "created_at": row["created_at"],
                    "request": json.loads(row["request_json"]),
                    "task_spec": json.loads(row["task_spec_json"]) if row["task_spec_json"] else None,
                    "route": json.loads(row["route_json"]) if row["route_json"] else None,
                    "status": row["status"],
                    "record_hash": row["record_hash"],
                }
            return None

    # --- Artifacts ---
    def record_artifact(
        self,
        artifact_id: str,
        task_id: str,
        artifact_type: str,
        version: str,
        spec: Dict[str, Any],
        content_path: Optional[str] = None,
    ) -> None:
        with self._get_connection() as conn:
            conn.execute(
                """
                INSERT INTO artifacts (artifact_id, task_id, artifact_type, version, spec_json, content_path, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (artifact_id, task_id, artifact_type, version, json.dumps(spec), content_path, utc_now_iso()),
            )

    def get_artifact(self, artifact_id: str) -> Optional[Dict[str, Any]]:
        with self._get_connection() as conn:
            row = conn.execute("SELECT * FROM artifacts WHERE artifact_id = ?", (artifact_id,)).fetchone()
            if row:
                return {
                    "artifact_id": row["artifact_id"],
                    "task_id": row["task_id"],
                    "artifact_type": row["artifact_type"],
                    "version": row["version"],
                    "spec": json.loads(row["spec_json"]),
                    "content_path": row["content_path"],
                    "created_at": row["created_at"],
                }
            return None

    # --- Transactions & Attempts with Optimistic CAS & Hash Chaining ---
    def record_transaction(self, transaction_id: str, task_id: str, state: str = "OPEN") -> None:
        now = utc_now_iso()
        rec_hash = compute_record_hash(
            None, {"transaction_id": transaction_id, "task_id": task_id, "state": state, "revision": 1}
        )
        with self._get_connection() as conn:
            conn.execute(
                """
                INSERT INTO transactions (transaction_id, task_id, state, revision, created_at, updated_at, record_hash)
                VALUES (?, ?, ?, 1, ?, ?, ?)
                ON CONFLICT(transaction_id) DO UPDATE SET
                    state=excluded.state,
                    updated_at=excluded.updated_at,
                    revision=transactions.revision + 1,
                    record_hash=excluded.record_hash
                """,
                (transaction_id, task_id, state, now, now, rec_hash),
            )

    def update_transaction_cas(self, transaction_id: str, expected_revision: int, new_state: str) -> bool:
        now = utc_now_iso()
        with self._get_connection() as conn:
            row = conn.execute("SELECT * FROM transactions WHERE transaction_id = ?", (transaction_id,)).fetchone()
            if not row or row["revision"] != expected_revision:
                return False

            parent_hash = row["record_hash"]
            new_hash = compute_record_hash(
                parent_hash, {"transaction_id": transaction_id, "state": new_state, "revision": expected_revision + 1}
            )

            cursor = conn.execute(
                """
                UPDATE transactions
                SET state = ?, updated_at = ?, revision = revision + 1, parent_hash = ?, record_hash = ?
                WHERE transaction_id = ? AND revision = ?
                """,
                (new_state, now, parent_hash, new_hash, transaction_id, expected_revision),
            )
            return cursor.rowcount > 0

    def get_transaction(self, transaction_id: str) -> Optional[Dict[str, Any]]:
        with self._get_connection() as conn:
            row = conn.execute("SELECT * FROM transactions WHERE transaction_id = ?", (transaction_id,)).fetchone()
            if row:
                return dict(row)
            return None

    def record_attempt(
        self, attempt_id: str, transaction_id: str, state: str, proposal: Optional[Dict[str, Any]] = None
    ) -> None:
        with self._get_connection() as conn:
            conn.execute(
                """
                INSERT INTO attempts (attempt_id, transaction_id, state, proposal_json, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (attempt_id, transaction_id, state, json.dumps(proposal) if proposal else None, utc_now_iso()),
            )

    # --- Authorizations ---
    def record_authorization(
        self,
        authorization_id: str,
        transaction_id: str,
        attempt_id: str,
        operation_hash: str,
        idempotency_key: str,
        state: str = "AUTHORIZED",
    ) -> None:
        with self._get_connection() as conn:
            conn.execute(
                """
                INSERT INTO authorizations (authorization_id, transaction_id, attempt_id, operation_hash, idempotency_key, state, issued_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (authorization_id, transaction_id, attempt_id, operation_hash, idempotency_key, state, utc_now_iso()),
            )

    def get_authorization_by_idempotency_key(self, idempotency_key: str) -> Optional[Dict[str, Any]]:
        with self._get_connection() as conn:
            row = conn.execute("SELECT * FROM authorizations WHERE idempotency_key = ?", (idempotency_key,)).fetchone()
            if row:
                return dict(row)
            return None

    def consume_authorization(self, authorization_id: str) -> bool:
        with self._get_connection() as conn:
            cursor = conn.execute(
                """
                UPDATE authorizations
                SET state = 'CONSUMED', consumed_at = ?
                WHERE authorization_id = ? AND state = 'AUTHORIZED'
                """,
                (utc_now_iso(), authorization_id),
            )
            return cursor.rowcount > 0

    # --- Learnings ---
    def record_learning(
        self, learning_id: str, task_id: str, promotion: str, record: Dict[str, Any], execution_id: Optional[str] = None
    ) -> None:
        with self._get_connection() as conn:
            conn.execute(
                """
                INSERT INTO learnings (learning_id, task_id, execution_id, promotion, record_json, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (learning_id, task_id, execution_id, promotion, json.dumps(record), utc_now_iso()),
            )

    def get_learnings_for_task(self, task_id: str) -> List[Dict[str, Any]]:
        with self._get_connection() as conn:
            rows = conn.execute("SELECT * FROM learnings WHERE task_id = ?", (task_id,)).fetchall()
            return [
                {
                    "learning_id": r["learning_id"],
                    "task_id": r["task_id"],
                    "execution_id": r["execution_id"],
                    "promotion": r["promotion"],
                    "record": json.loads(r["record_json"]),
                    "created_at": r["created_at"],
                }
                for r in rows
            ]

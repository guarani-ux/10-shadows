import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from loop_engine.base import PROJECT_ROOT

KERNEL_DB_PATH = PROJECT_ROOT / "scratch" / "kernel.db"


class KernelDatabase:
    """
    Unified Single-Database Transactional Boundary for 10 SHADOWS.
    
    Prevents split-brain persistence by managing runs, artifacts, artifact_events,
    receipts, escalations, and approvals within one SQLite database in WAL mode.
    """

    SCHEMA_VERSION = 1

    def __init__(self, db_path: Optional[Path] = None):
        self.db_path = db_path or KERNEL_DB_PATH
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def get_connection(self) -> sqlite3.Connection:
        """Returns a configured SQLite connection in WAL mode."""
        conn = sqlite3.connect(str(self.db_path), timeout=15.0)
        conn.execute("PRAGMA journal_mode = WAL;")
        conn.execute("PRAGMA synchronous = NORMAL;")
        conn.execute("PRAGMA foreign_keys = ON;")
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        """Initializes database schema with PRAGMA user_version tracking."""
        with self.get_connection() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS runs (
                    run_id TEXT PRIMARY KEY,
                    parent_run_id TEXT,
                    task_id TEXT NOT NULL,
                    shadow_id INTEGER NOT NULL,
                    domain_code TEXT NOT NULL,
                    source_commit TEXT NOT NULL,
                    objective_hash TEXT NOT NULL,
                    canonical_input_hash TEXT NOT NULL,
                    status TEXT NOT NULL,
                    authority_level TEXT NOT NULL,
                    current_attempt INTEGER DEFAULT 1,
                    current_strike INTEGER DEFAULT 0,
                    status_history TEXT NOT NULL,
                    started_at TEXT NOT NULL,
                    ended_at TEXT
                );

                CREATE TABLE IF NOT EXISTS artifacts (
                    artifact_id TEXT PRIMARY KEY,
                    idempotency_key TEXT UNIQUE NOT NULL,
                    run_id TEXT NOT NULL,
                    parent_run_id TEXT NOT NULL,
                    producing_shadow_id INTEGER NOT NULL,
                    domain_code TEXT NOT NULL,
                    step_id TEXT NOT NULL,
                    artifact_type TEXT NOT NULL,
                    schema_version TEXT NOT NULL,
                    content_sha256 TEXT NOT NULL,
                    storage_path TEXT NOT NULL,
                    current_state TEXT NOT NULL,
                    source_artifact_hash TEXT NOT NULL,
                    source_commit TEXT NOT NULL,
                    producer_version TEXT NOT NULL,
                    validator_policy_fingerprint TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS artifact_events (
                    event_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    artifact_id TEXT NOT NULL,
                    idempotency_key TEXT NOT NULL,
                    from_state TEXT,
                    to_state TEXT NOT NULL,
                    event_reason TEXT NOT NULL,
                    validator_results TEXT,
                    actor_domain TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    FOREIGN KEY(artifact_id) REFERENCES artifacts(artifact_id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS receipts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    task_id TEXT NOT NULL,
                    run_id TEXT NOT NULL,
                    parent_run_id TEXT,
                    shadow_id INTEGER NOT NULL,
                    domain_code TEXT NOT NULL,
                    stage TEXT NOT NULL,
                    attempt INTEGER NOT NULL,
                    strikes_used INTEGER NOT NULL,
                    candidate_hash TEXT,
                    source_commit TEXT NOT NULL,
                    spec_hash TEXT NOT NULL,
                    status TEXT NOT NULL,
                    target_file TEXT,
                    artifact_sha256 TEXT,
                    failure_code TEXT,
                    repair_strategy TEXT,
                    promotion_decision TEXT NOT NULL,
                    receipt_json TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS escalations (
                    escalation_id TEXT PRIMARY KEY,
                    run_id TEXT NOT NULL,
                    parent_run_id TEXT NOT NULL,
                    task_id TEXT NOT NULL,
                    shadow_id INTEGER NOT NULL,
                    category TEXT NOT NULL,
                    reason TEXT NOT NULL,
                    details_json TEXT NOT NULL,
                    remediation_options_json TEXT NOT NULL,
                    status TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS approvals (
                    approval_id TEXT PRIMARY KEY,
                    escalation_id TEXT NOT NULL,
                    parent_run_id TEXT NOT NULL,
                    human_authority TEXT NOT NULL,
                    decision TEXT NOT NULL,
                    decision_payload_json TEXT NOT NULL,
                    resulting_plan_hash TEXT NOT NULL,
                    resumed_step_id TEXT NOT NULL,
                    timestamp TEXT NOT NULL
                );

                CREATE INDEX IF NOT EXISTS idx_runs_parent ON runs(parent_run_id);
                CREATE INDEX IF NOT EXISTS idx_artifacts_idempotency ON artifacts(idempotency_key);
                CREATE INDEX IF NOT EXISTS idx_artifacts_parent ON artifacts(parent_run_id);
                CREATE INDEX IF NOT EXISTS idx_artifacts_type ON artifacts(artifact_type);
                CREATE INDEX IF NOT EXISTS idx_artifact_events_id ON artifact_events(artifact_id);
                CREATE INDEX IF NOT EXISTS idx_receipts_parent_run ON receipts(parent_run_id);
                CREATE INDEX IF NOT EXISTS idx_receipts_run ON receipts(run_id);
                CREATE INDEX IF NOT EXISTS idx_escalations_parent ON escalations(parent_run_id);
                """
            )
            conn.execute(f"PRAGMA user_version = {self.SCHEMA_VERSION};")

    # ----------------------------------------------------
    # Run State Transactions
    # ----------------------------------------------------
    def record_run_state(
        self,
        run_id: str,
        task_id: str,
        shadow_id: int,
        domain_code: str,
        source_commit: str,
        objective_hash: str,
        canonical_input_hash: str,
        status: str,
        authority_level: str,
        status_history: List[str],
        parent_run_id: Optional[str] = None,
        current_attempt: int = 1,
        current_strike: int = 0,
        started_at: Optional[str] = None,
        ended_at: Optional[str] = None,
    ) -> None:
        """Upserts a run state record atomically."""
        now_str = started_at or datetime.now(timezone.utc).isoformat()
        with self.get_connection() as conn:
            conn.execute(
                """
                INSERT INTO runs (
                    run_id, parent_run_id, task_id, shadow_id, domain_code,
                    source_commit, objective_hash, canonical_input_hash,
                    status, authority_level, current_attempt, current_strike,
                    status_history, started_at, ended_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(run_id) DO UPDATE SET
                    status=excluded.status,
                    current_attempt=excluded.current_attempt,
                    current_strike=excluded.current_strike,
                    status_history=excluded.status_history,
                    ended_at=excluded.ended_at;
                """,
                (
                    run_id,
                    parent_run_id,
                    task_id,
                    shadow_id,
                    domain_code,
                    source_commit,
                    objective_hash,
                    canonical_input_hash,
                    status,
                    authority_level,
                    current_attempt,
                    current_strike,
                    json.dumps(status_history),
                    now_str,
                    ended_at,
                ),
            )

    def get_run(self, run_id: str) -> Optional[Dict[str, Any]]:
        """Queries single run by ID."""
        with self.get_connection() as conn:
            row = conn.execute("SELECT * FROM runs WHERE run_id = ?", (run_id,)).fetchone()
            if row:
                d = dict(row)
                d["status_history"] = json.loads(d["status_history"])
                return d
            return None

    # ----------------------------------------------------
    # Escalation & Approval Transactions
    # ----------------------------------------------------
    def record_escalation(
        self,
        escalation_id: str,
        run_id: str,
        parent_run_id: str,
        task_id: str,
        shadow_id: int,
        category: str,
        reason: str,
        details: Dict[str, Any],
        remediation_options: List[str],
    ) -> None:
        """Records a human escalation record."""
        now_str = datetime.now(timezone.utc).isoformat()
        with self.get_connection() as conn:
            conn.execute(
                """
                INSERT INTO escalations (
                    escalation_id, run_id, parent_run_id, task_id, shadow_id,
                    category, reason, details_json, remediation_options_json,
                    status, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'AWAITING_APPROVAL', ?);
                """,
                (
                    escalation_id,
                    run_id,
                    parent_run_id,
                    task_id,
                    shadow_id,
                    category,
                    reason,
                    json.dumps(details, default=str),
                    json.dumps(remediation_options),
                    now_str,
                ),
            )

    def record_approval(
        self,
        approval_id: str,
        escalation_id: str,
        parent_run_id: str,
        human_authority: str,
        decision: str,
        decision_payload: Dict[str, Any],
        resulting_plan_hash: str,
        resumed_step_id: str,
    ) -> None:
        """Records human decision and updates escalation status transactionally."""
        now_str = datetime.now(timezone.utc).isoformat()
        with self.get_connection() as conn:
            conn.execute(
                """
                INSERT INTO approvals (
                    approval_id, escalation_id, parent_run_id, human_authority,
                    decision, decision_payload_json, resulting_plan_hash,
                    resumed_step_id, timestamp
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?);
                """,
                (
                    approval_id,
                    escalation_id,
                    parent_run_id,
                    human_authority,
                    decision,
                    json.dumps(decision_payload, default=str),
                    resulting_plan_hash,
                    resumed_step_id,
                    now_str,
                ),
            )
            conn.execute(
                "UPDATE escalations SET status = ? WHERE escalation_id = ?;",
                (f"RESOLVED_{decision}", escalation_id),
            )

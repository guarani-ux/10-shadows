"""
loop_engine/kernel_db.py
Unified Single-Database Transactional Boundary for 10 SHADOWS.

Prevents split-brain persistence by managing runs, artifacts, artifact_events,
receipts, proposals, verified receipts, quarantine logs, strikes, and promotion WAL
within one SQLite database in WAL mode.
"""

import json
import sqlite3
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from loop_engine.base import PROJECT_ROOT
from loop_engine.schema import (
    LEGAL_STATE_TRANSITIONS,
    EnvironmentFingerprint,
    FailureClassification,
    ProposalManifest,
    QuarantineRecord,
    State,
    VerificationReceipt,
)

KERNEL_DB_PATH = PROJECT_ROOT / "scratch" / "kernel.db"


class ProposalAlreadySealedError(Exception):
    """Raised when attempting to overwrite an already sealed proposal manifest."""

    pass


class IllegalStateTransitionError(Exception):
    """Raised when attempting an illegal or unverified state transition."""

    pass


class ReceiptNotFoundError(Exception):
    """Raised when a promotion references a receipt_id that does not exist in KernelDatabase."""

    pass


class ReceiptMismatchError(Exception):
    """Raised when a receipt does not match the sealed proposal manifest."""

    pass


PRIVILEGED_STATES = {
    State.VERIFIED,
    State.PROMOTION_PENDING,
    State.PROMOTED,
    State.POST_PROMOTION_VERIFIED,
}


class PrivilegedStateMutationProhibitedError(Exception):
    """Raised when an unauthenticated caller attempts direct privileged state mutation in KernelDatabase."""

    pass


class KernelDatabase:
    """
    Unified Single-Database Transactional Boundary for 10 SHADOWS.
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

                CREATE TABLE IF NOT EXISTS proposals (
                    task_id TEXT PRIMARY KEY,
                    spec_hash TEXT NOT NULL,
                    base_commit_sha TEXT NOT NULL,
                    candidate_commit_sha TEXT NOT NULL,
                    candidate_tree_sha TEXT NOT NULL,
                    verifier_version TEXT NOT NULL,
                    acceptance_test_digest TEXT NOT NULL,
                    env_fingerprint TEXT NOT NULL,
                    state TEXT NOT NULL,
                    created_at REAL NOT NULL,
                    updated_at REAL NOT NULL
                );

                CREATE TABLE IF NOT EXISTS verified_receipts (
                    receipt_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    task_id TEXT NOT NULL,
                    spec_hash TEXT NOT NULL,
                    candidate_commit_sha TEXT NOT NULL,
                    candidate_tree_sha TEXT NOT NULL,
                    physical_tree_hash TEXT NOT NULL,
                    verifier_version TEXT NOT NULL,
                    acceptance_test_digest TEXT NOT NULL,
                    env_fingerprint TEXT NOT NULL,
                    status TEXT NOT NULL,
                    failure_classification TEXT,
                    failure_signature TEXT,
                    execution_trace TEXT,
                    created_at REAL NOT NULL,
                    FOREIGN KEY(task_id) REFERENCES proposals(task_id)
                );

                CREATE TABLE IF NOT EXISTS quarantine_log (
                    quarantine_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    task_id TEXT NOT NULL,
                    quarantine_dir TEXT NOT NULL,
                    candidate_commit_sha TEXT NOT NULL,
                    failure_classification TEXT NOT NULL,
                    failure_signature TEXT NOT NULL,
                    execution_trace TEXT NOT NULL,
                    created_at REAL NOT NULL
                );

                CREATE TABLE IF NOT EXISTS strike_log (
                    strike_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    task_id TEXT NOT NULL,
                    failure_classification TEXT NOT NULL,
                    failure_signature TEXT NOT NULL,
                    created_at REAL NOT NULL
                );

                CREATE TABLE IF NOT EXISTS promotion_wal (
                    wal_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    task_id TEXT NOT NULL,
                    target_branch TEXT NOT NULL,
                    candidate_commit_sha TEXT NOT NULL,
                    state TEXT NOT NULL,
                    created_at REAL NOT NULL
                );

                CREATE TABLE IF NOT EXISTS semantic_proofs (
                    proof_id TEXT PRIMARY KEY,
                    binding_hash TEXT NOT NULL,
                    requirement_hash TEXT NOT NULL,
                    semantic_contract_hash TEXT NOT NULL,
                    authority_source TEXT NOT NULL,
                    authority_record_id TEXT NOT NULL,
                    verifier_version TEXT NOT NULL,
                    status TEXT NOT NULL,
                    created_at REAL NOT NULL,
                    superseded_by TEXT
                );

                CREATE TABLE IF NOT EXISTS domain_authorities (
                    authority_id TEXT PRIMARY KEY,
                    namespace TEXT NOT NULL,
                    version TEXT NOT NULL,
                    scope_json TEXT NOT NULL,
                    mapping_json TEXT NOT NULL,
                    content_hash TEXT NOT NULL,
                    source_evidence_refs_json TEXT NOT NULL,
                    registration_authority_ref TEXT NOT NULL,
                    status TEXT NOT NULL,
                    created_at REAL NOT NULL,
                    superseded_by TEXT
                );

                CREATE TABLE IF NOT EXISTS authority_evidence (
                    evidence_id TEXT PRIMARY KEY,
                    evidence_class TEXT NOT NULL,
                    claim_scope TEXT NOT NULL,
                    content_hash TEXT NOT NULL,
                    provenance_json TEXT NOT NULL,
                    verification_receipt_ref TEXT,
                    status TEXT NOT NULL,
                    created_at REAL NOT NULL
                );

                CREATE INDEX IF NOT EXISTS idx_runs_parent ON runs(parent_run_id);
                CREATE INDEX IF NOT EXISTS idx_artifacts_idempotency ON artifacts(idempotency_key);
                CREATE INDEX IF NOT EXISTS idx_artifacts_parent ON artifacts(parent_run_id);
                CREATE INDEX IF NOT EXISTS idx_artifacts_type ON artifacts(artifact_type);
                CREATE INDEX IF NOT EXISTS idx_artifact_events_id ON artifact_events(artifact_id);
                CREATE INDEX IF NOT EXISTS idx_receipts_parent_run ON receipts(parent_run_id);
                CREATE INDEX IF NOT EXISTS idx_receipts_run ON receipts(run_id);
                CREATE INDEX IF NOT EXISTS idx_escalations_parent ON escalations(parent_run_id);
                CREATE INDEX IF NOT EXISTS idx_proposals_state ON proposals(state);
                CREATE INDEX IF NOT EXISTS idx_verified_receipts_task ON verified_receipts(task_id);
                """
            )
            conn.execute(f"PRAGMA user_version = {self.SCHEMA_VERSION};")

    # ----------------------------------------------------
    # Proposal & Zero-Trust State Transactions
    # ----------------------------------------------------
    def record_proposal(self, manifest: ProposalManifest) -> None:
        """
        Records a sealed proposal manifest. Immutable: fails if proposal already exists.
        """
        now = time.time()
        with self.get_connection() as conn:
            try:
                conn.execute(
                    """
                    INSERT INTO proposals (
                        task_id, spec_hash, base_commit_sha, candidate_commit_sha,
                        candidate_tree_sha, verifier_version, acceptance_test_digest,
                        env_fingerprint, state, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        manifest.task_id,
                        manifest.spec_hash,
                        manifest.base_commit_sha,
                        manifest.candidate_commit_sha,
                        manifest.candidate_tree_sha,
                        manifest.verifier_version,
                        manifest.acceptance_test_digest,
                        json.dumps(manifest.env_fingerprint.to_dict()),
                        manifest.state.value,
                        now,
                        now,
                    ),
                )
            except sqlite3.IntegrityError:
                raise ProposalAlreadySealedError(f"Proposal for task_id '{manifest.task_id}' is already sealed.")

    def get_proposal(self, task_id: str) -> Optional[ProposalManifest]:
        """Retrieves sealed proposal by task_id."""
        with self.get_connection() as conn:
            row = conn.execute("SELECT * FROM proposals WHERE task_id = ?", (task_id,)).fetchone()
            if not row:
                return None
            return ProposalManifest(
                task_id=row["task_id"],
                spec_hash=row["spec_hash"],
                base_commit_sha=row["base_commit_sha"],
                candidate_commit_sha=row["candidate_commit_sha"],
                candidate_tree_sha=row["candidate_tree_sha"],
                verifier_version=row["verifier_version"],
                acceptance_test_digest=row["acceptance_test_digest"],
                env_fingerprint=EnvironmentFingerprint.from_dict(json.loads(row["env_fingerprint"])),
                state=State(row["state"]),
                timestamp=row["created_at"],
            )

    def get_proposal_state(self, task_id: str) -> Optional[State]:

        with self.get_connection() as conn:
            row = conn.execute("SELECT state FROM proposals WHERE task_id = ?", (task_id,)).fetchone()
            return State(row["state"]) if row else None

    def _execute_privileged_state_transition(
        self, auth_token: str, task_id: str, from_state: State, to_state: State
    ) -> None:
        """Internal custody transition method callable exclusively by PrivilegedTransitionEngine."""
        from loop_engine.transition import _INTERNAL_TRANSITION_TOKEN

        if auth_token != _INTERNAL_TRANSITION_TOKEN:
            raise PrivilegedStateMutationProhibitedError(
                "Invalid authority token: direct privileged state mutation is prohibited."
            )
        self._raw_transition_proposal_state(task_id, from_state, to_state)

    def _raw_transition_proposal_state(self, task_id: str, from_state: State, to_state: State) -> None:
        allowed = LEGAL_STATE_TRANSITIONS.get(from_state, [])
        if to_state not in allowed:
            raise IllegalStateTransitionError(
                f"Illegal transition from '{from_state.value}' to '{to_state.value}'. Allowed: {[s.value for s in allowed]}"
            )

        now = time.time()
        with self.get_connection() as conn:
            cursor = conn.execute(
                "UPDATE proposals SET state = ?, updated_at = ? WHERE task_id = ? AND state = ?",
                (to_state.value, now, task_id, from_state.value),
            )
            if cursor.rowcount == 0:
                cur_row = conn.execute("SELECT state FROM proposals WHERE task_id = ?", (task_id,)).fetchone()
                cur_state = cur_row["state"] if cur_row else "NON_EXISTENT"
                raise IllegalStateTransitionError(
                    f"CAS transition failed for task '{task_id}': expected state '{from_state.value}', but found '{cur_state}'"
                )

    def transition_proposal_state(self, task_id: str, from_state: State, to_state: State) -> None:
        """
        Public transition method. Privileged states (VERIFIED, PROMOTION_PENDING, PROMOTED,
        POST_PROMOTION_VERIFIED) are restricted and cannot be mutated directly through this API.
        """
        if to_state in PRIVILEGED_STATES:
            raise PrivilegedStateMutationProhibitedError(
                f"Direct database mutation to privileged state '{to_state.value}' is prohibited. "
                "Privileged state transitions must be executed through PrivilegedTransitionEngine."
            )
        self._raw_transition_proposal_state(task_id, from_state, to_state)

    def update_state(self, task_id: str, to_state: State) -> None:
        """Convenience method for updating proposal state via transition_proposal_state."""
        cur_state = self.get_proposal_state(task_id)
        if cur_state is None:
            raise IllegalStateTransitionError(f"Proposal '{task_id}' does not exist.")
        self.transition_proposal_state(task_id, cur_state, to_state)

    def record_receipt(self, receipt: VerificationReceipt) -> int:
        """Alias for record_verified_receipt."""
        return self.record_verified_receipt(receipt)

    def record_verified_receipt(self, receipt: VerificationReceipt) -> int:
        """
        Persists a verifier receipt directly into KernelDatabase and returns receipt_id.
        """
        now = time.time()
        with self.get_connection() as conn:
            cursor = conn.execute(
                """
                INSERT INTO verified_receipts (
                    task_id, spec_hash, candidate_commit_sha, candidate_tree_sha,
                    physical_tree_hash, verifier_version, acceptance_test_digest,
                    env_fingerprint, status, failure_classification, failure_signature,
                    execution_trace, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    receipt.task_id,
                    receipt.spec_hash,
                    receipt.candidate_commit_sha,
                    receipt.candidate_tree_sha,
                    receipt.physical_tree_hash,
                    receipt.verifier_version,
                    receipt.acceptance_test_digest,
                    json.dumps(receipt.env_fingerprint.to_dict()),
                    receipt.status.value,
                    receipt.failure_classification.value if receipt.failure_classification else None,
                    receipt.failure_signature,
                    receipt.execution_trace,
                    now,
                ),
            )
            return cursor.lastrowid

    def get_verified_receipt(self, receipt_id: Any) -> Optional[VerificationReceipt]:
        if hasattr(receipt_id, "receipt_id") and isinstance(receipt_id.receipt_id, int):
            receipt_id = receipt_id.receipt_id
        elif isinstance(receipt_id, tuple) and len(receipt_id) > 0 and isinstance(receipt_id[0], int):
            receipt_id = receipt_id[0]

        with self.get_connection() as conn:
            row = conn.execute("SELECT * FROM verified_receipts WHERE receipt_id = ?", (receipt_id,)).fetchone()
            if not row:
                return None
            return VerificationReceipt(
                receipt_id=row["receipt_id"],
                task_id=row["task_id"],
                spec_hash=row["spec_hash"],
                base_commit_sha="",
                candidate_commit_sha=row["candidate_commit_sha"],
                candidate_tree_sha=row["candidate_tree_sha"],
                physical_tree_hash=row["physical_tree_hash"],
                verifier_version=row["verifier_version"],
                acceptance_test_digest=row["acceptance_test_digest"],
                env_fingerprint=EnvironmentFingerprint.from_dict(json.loads(row["env_fingerprint"])),
                status=State(row["status"]),
                failure_classification=FailureClassification(row["failure_classification"])
                if row["failure_classification"]
                else None,
                failure_signature=row["failure_signature"],
                execution_trace=row["execution_trace"],
                timestamp=row["created_at"],
            )

    def record_strike(self, task_id: str, classification: FailureClassification, signature: str) -> None:
        with self.get_connection() as conn:
            conn.execute(
                """
                INSERT INTO strike_log (task_id, failure_classification, failure_signature, created_at)
                VALUES (?, ?, ?, ?)
                """,
                (task_id, classification.value, signature, time.time()),
            )

    def get_strikes(self, task_id: str) -> int:
        with self.get_connection() as conn:
            row = conn.execute("SELECT COUNT(*) as count FROM strike_log WHERE task_id = ?", (task_id,)).fetchone()
            return row["count"] if row else 0

    def get_failure_signatures(self, task_id: str) -> List[str]:
        with self.get_connection() as conn:
            rows = conn.execute("SELECT failure_signature FROM strike_log WHERE task_id = ?", (task_id,)).fetchall()
            return [r["failure_signature"] for r in rows]

    def record_quarantine_entry(self, record: QuarantineRecord) -> int:
        with self.get_connection() as conn:
            cursor = conn.execute(
                """
                INSERT INTO quarantine_log (
                    task_id, quarantine_dir, candidate_commit_sha, failure_classification,
                    failure_signature, execution_trace, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    record.task_id,
                    record.quarantine_dir,
                    record.candidate_commit_sha,
                    record.failure_classification.value,
                    record.failure_signature,
                    record.execution_trace,
                    record.timestamp,
                ),
            )
            return cursor.lastrowid

    def record_promotion_wal_step(
        self, task_id: str, target_branch: str, candidate_commit_sha: str, state: State
    ) -> int:
        with self.get_connection() as conn:
            cursor = conn.execute(
                """
                INSERT INTO promotion_wal (task_id, target_branch, candidate_commit_sha, state, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (task_id, target_branch, candidate_commit_sha, state.value, time.time()),
            )
            return cursor.lastrowid

    def get_pending_promotions(self) -> List[Dict[str, Any]]:
        with self.get_connection() as conn:
            rows = conn.execute(
                "SELECT * FROM proposals WHERE state = ?",
                (State.PROMOTION_PENDING.value,),
            ).fetchall()
            return [dict(r) for r in rows]

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

    # ----------------------------------------------------
    # Semantic Authority Custody
    # ----------------------------------------------------
    def record_semantic_proof(
        self,
        proof_id: str,
        binding_hash: str,
        requirement_hash: str,
        semantic_contract_hash: str,
        authority_source: str,
        authority_record_id: str,
        verifier_version: str = "1.0.0",
        status: str = "VERIFIED",
    ) -> None:
        """Persists a verified semantic applicability proof."""
        with self.get_connection() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO semantic_proofs (
                    proof_id, binding_hash, requirement_hash, semantic_contract_hash,
                    authority_source, authority_record_id, verifier_version, status, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?);
                """,
                (
                    proof_id,
                    binding_hash,
                    requirement_hash,
                    semantic_contract_hash,
                    authority_source,
                    authority_record_id,
                    verifier_version,
                    status,
                    time.time(),
                ),
            )

    def get_semantic_proof(self, proof_id: str) -> Optional[Dict[str, Any]]:
        """Retrieves a semantic proof by proof_id."""
        with self.get_connection() as conn:
            row = conn.execute("SELECT * FROM semantic_proofs WHERE proof_id = ?", (proof_id,)).fetchone()
            return dict(row) if row else None

    def get_semantic_proof_by_binding_hash(self, binding_hash: str) -> Optional[Dict[str, Any]]:
        """Retrieves a verified semantic proof by binding_hash."""
        with self.get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM semantic_proofs WHERE binding_hash = ? AND status = 'VERIFIED' ORDER BY created_at DESC LIMIT 1",
                (binding_hash,),
            ).fetchone()
            return dict(row) if row else None

    def register_domain_authority(
        self,
        authority_id: str,
        namespace: str,
        version: str,
        scope: Dict[str, Any],
        mapping: Dict[str, Any],
        content_hash: str,
        source_evidence_refs: List[str],
        registration_authority_ref: str,
        status: str = "VERIFIED",
    ) -> None:
        """Registers an authorized domain ontology / semantic mapping."""
        with self.get_connection() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO domain_authorities (
                    authority_id, namespace, version, scope_json, mapping_json,
                    content_hash, source_evidence_refs_json, registration_authority_ref,
                    status, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
                """,
                (
                    authority_id,
                    namespace,
                    version,
                    json.dumps(scope, default=str),
                    json.dumps(mapping, default=str),
                    content_hash,
                    json.dumps(source_evidence_refs),
                    registration_authority_ref,
                    status,
                    time.time(),
                ),
            )

    def get_domain_authority(self, authority_id: str) -> Optional[Dict[str, Any]]:
        """Retrieves a domain authority by authority_id."""
        with self.get_connection() as conn:
            row = conn.execute("SELECT * FROM domain_authorities WHERE authority_id = ?", (authority_id,)).fetchone()
            if row:
                d = dict(row)
                d["scope"] = json.loads(d["scope_json"])
                d["mapping"] = json.loads(d["mapping_json"])
                d["source_evidence_refs"] = json.loads(d["source_evidence_refs_json"])
                return d
            return None

    def find_domain_authorities(
        self, namespace: Optional[str] = None, status: str = "VERIFIED"
    ) -> List[Dict[str, Any]]:
        """Finds all domain authorities for a namespace."""
        with self.get_connection() as conn:
            if namespace:
                rows = conn.execute(
                    "SELECT * FROM domain_authorities WHERE namespace = ? AND status = ?",
                    (namespace, status),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM domain_authorities WHERE status = ?",
                    (status,),
                ).fetchall()
            results = []
            for r in rows:
                d = dict(r)
                d["scope"] = json.loads(d["scope_json"])
                d["mapping"] = json.loads(d["mapping_json"])
                d["source_evidence_refs"] = json.loads(d["source_evidence_refs_json"])
                results.append(d)
            return results

    def record_authority_evidence(
        self,
        evidence_id: str,
        evidence_class: str,
        claim_scope: str,
        content_hash: str,
        provenance: Dict[str, Any],
        verification_receipt_ref: Optional[str] = None,
        status: str = "VERIFIED",
    ) -> None:
        """Records a trusted authority evidence record."""
        with self.get_connection() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO authority_evidence (
                    evidence_id, evidence_class, claim_scope, content_hash,
                    provenance_json, verification_receipt_ref, status, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?);
                """,
                (
                    evidence_id,
                    evidence_class,
                    claim_scope,
                    content_hash,
                    json.dumps(provenance, default=str),
                    verification_receipt_ref,
                    status,
                    time.time(),
                ),
            )

    def get_authority_evidence(self, evidence_id: str) -> Optional[Dict[str, Any]]:
        """Retrieves a trusted authority evidence record."""
        with self.get_connection() as conn:
            row = conn.execute("SELECT * FROM authority_evidence WHERE evidence_id = ?", (evidence_id,)).fetchone()
            if row:
                d = dict(row)
                d["provenance"] = json.loads(d["provenance_json"])
                return d
            return None

    def get_approval_for_subject(self, subject_type: str, subject_hash: str) -> Optional[Dict[str, Any]]:
        """Retrieves an approval decision for a specific subject hash (e.g. binding_hash)."""
        with self.get_connection() as conn:
            # Check resulting_plan_hash or search decision_payload_json for subject_hash
            row = conn.execute(
                "SELECT * FROM approvals WHERE resulting_plan_hash = ? AND decision = 'APPROVE' ORDER BY timestamp DESC LIMIT 1",
                (subject_hash,),
            ).fetchone()
            if not row:
                # Also check if subject_hash is in decision_payload_json
                rows = conn.execute(
                    "SELECT * FROM approvals WHERE decision = 'APPROVE' ORDER BY timestamp DESC"
                ).fetchall()
                for r in rows:
                    try:
                        payload = json.loads(r["decision_payload_json"])
                        if payload.get("binding_hash") == subject_hash or payload.get("subject_hash") == subject_hash:
                            row = r
                            break
                    except Exception:
                        pass
            return dict(row) if row else None

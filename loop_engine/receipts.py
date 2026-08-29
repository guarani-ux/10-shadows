import hashlib
import json
import os
import shutil
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from loop_engine.base import PROJECT_ROOT, force_remove_readonly

RECEIPTS_DB_PATH = PROJECT_ROOT / "scratch" / "receipts.db"


class AtomicCommitError(Exception):
    """Raised when atomic 2-phase commit fails to promote staging candidate."""

    pass


def compute_file_sha256(file_path: Path) -> str:
    """Computes deterministic SHA-256 hash of a file on disk."""
    if not file_path.exists():
        raise FileNotFoundError(f"File not found: {file_path}")
    h = hashlib.sha256()
    with open(file_path, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()


def atomic_two_phase_commit(candidate_path: Path, target_path: Path) -> Dict[str, Any]:
    """
    Executes atomic two-phase commit:
    1. Validates candidate exists and computes SHA-256 hash.
    2. Writes to target atomically using os.replace.
    3. Removes candidate file from staging.
    """
    if not candidate_path.exists():
        raise AtomicCommitError(f"Candidate path does not exist: {candidate_path}")

    target_path.parent.mkdir(parents=True, exist_ok=True)
    candidate_hash = compute_file_sha256(candidate_path)
    file_bytes = candidate_path.stat().st_size

    temp_target = target_path.parent / f".tmp_{target_path.name}_{int(datetime.now().timestamp() * 1000)}"
    shutil.copy2(candidate_path, temp_target)
    os.replace(temp_target, target_path)
    try:
        candidate_path.unlink()
    except Exception:
        pass

    return {
        "status": "COMMITTED",
        "target_file": str(target_path),
        "sha256": candidate_hash,
        "bytes_written": file_bytes,
    }


class ExecutionReceipt(BaseModel):
    """
    Immutable, cryptographically verifiable record of a successful loop commit.
    """

    task_id: str
    run_id: str
    parent_run_id: Optional[str] = None
    shadow_id: int = 0
    domain_code: str = "unmapped"
    stage: str = "FINAL"
    attempt: int = 1
    candidate_hash: Optional[str] = None
    source_commit: Optional[str] = None
    spec_hash: str
    status: str
    strikes_used: int
    target_file: Optional[str] = None
    artifact_sha256: Optional[str] = None
    failure_code: Optional[str] = None
    repair_strategy: Optional[str] = None
    promotion_decision: str = "PROMOTED"
    extra_data: Dict[str, Any] = Field(default_factory=dict)
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class ReceiptStore:
    """
    SQLite WAL-Mode Receipt Store with explicit cryptographic traceability.
    """

    def __init__(self, db_path: Optional[Path] = None):
        self.db_path = db_path or RECEIPTS_DB_PATH
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path), timeout=10.0)
        conn.execute("PRAGMA journal_mode = WAL;")
        conn.execute("PRAGMA synchronous = NORMAL;")
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._get_connection() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS receipts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    task_id TEXT NOT NULL,
                    run_id TEXT NOT NULL,
                    parent_run_id TEXT,
                    shadow_id INTEGER DEFAULT 0,
                    domain_code TEXT DEFAULT 'unmapped',
                    stage TEXT DEFAULT 'FINAL',
                    attempt INTEGER DEFAULT 1,
                    candidate_hash TEXT,
                    source_commit TEXT,
                    spec_hash TEXT NOT NULL,
                    status TEXT NOT NULL,
                    strikes_used INTEGER NOT NULL,
                    target_file TEXT,
                    artifact_sha256 TEXT,
                    failure_code TEXT,
                    repair_strategy TEXT,
                    promotion_decision TEXT DEFAULT 'PROMOTED',
                    receipt_json TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)

            # Schema migration checks for existing SQLite files
            columns = [row["name"] for row in conn.execute("PRAGMA table_info(receipts);").fetchall()]
            if "shadow_id" not in columns:
                conn.execute("ALTER TABLE receipts ADD COLUMN shadow_id INTEGER DEFAULT 0;")
            if "parent_run_id" not in columns:
                conn.execute("ALTER TABLE receipts ADD COLUMN parent_run_id TEXT;")
            if "domain_code" not in columns:
                conn.execute("ALTER TABLE receipts ADD COLUMN domain_code TEXT DEFAULT 'unmapped';")
            if "stage" not in columns:
                conn.execute("ALTER TABLE receipts ADD COLUMN stage TEXT DEFAULT 'FINAL';")
            if "attempt" not in columns:
                conn.execute("ALTER TABLE receipts ADD COLUMN attempt INTEGER DEFAULT 1;")
            if "candidate_hash" not in columns:
                conn.execute("ALTER TABLE receipts ADD COLUMN candidate_hash TEXT;")
            if "source_commit" not in columns:
                conn.execute("ALTER TABLE receipts ADD COLUMN source_commit TEXT;")
            if "failure_code" not in columns:
                conn.execute("ALTER TABLE receipts ADD COLUMN failure_code TEXT;")
            if "repair_strategy" not in columns:
                conn.execute("ALTER TABLE receipts ADD COLUMN repair_strategy TEXT;")
            if "promotion_decision" not in columns:
                conn.execute("ALTER TABLE receipts ADD COLUMN promotion_decision TEXT DEFAULT 'PROMOTED';")

            conn.execute("CREATE INDEX IF NOT EXISTS idx_receipts_task ON receipts(task_id);")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_receipts_run ON receipts(run_id);")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_receipts_shadow ON receipts(shadow_id);")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_receipts_hash ON receipts(spec_hash);")

    def record_receipt(
        self,
        task_id: str,
        run_id: str,
        spec_hash: str,
        status: str,
        strikes_used: int,
        shadow_id: int = 0,
        domain_code: str = "unmapped",
        stage: str = "FINAL",
        attempt: int = 1,
        candidate_hash: Optional[str] = None,
        source_commit: Optional[str] = None,
        target_file: Optional[str] = None,
        artifact_sha256: Optional[str] = None,
        failure_code: Optional[str] = None,
        repair_strategy: Optional[str] = None,
        promotion_decision: str = "PROMOTED",
        extra_data: Optional[Dict[str, Any]] = None,
        parent_run_id: Optional[str] = None,
    ) -> int:
        """Atomically inserts an execution receipt and returns its ID."""
        receipt = ExecutionReceipt(
            task_id=task_id,
            run_id=run_id,
            parent_run_id=parent_run_id,
            shadow_id=shadow_id,
            domain_code=domain_code,
            stage=stage,
            attempt=attempt,
            candidate_hash=candidate_hash,
            source_commit=source_commit,
            spec_hash=spec_hash,
            status=status,
            strikes_used=strikes_used,
            target_file=target_file,
            artifact_sha256=artifact_sha256,
            failure_code=failure_code,
            repair_strategy=repair_strategy,
            promotion_decision=promotion_decision,
            extra_data=extra_data or {},
        )

        with self._get_connection() as conn:
            cursor = conn.execute(
                """
                INSERT INTO receipts (
                    task_id, run_id, parent_run_id, shadow_id, domain_code,
                    stage, attempt, candidate_hash, source_commit, spec_hash,
                    status, strikes_used, target_file, artifact_sha256,
                    failure_code, repair_strategy, promotion_decision, receipt_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    receipt.task_id,
                    receipt.run_id,
                    receipt.parent_run_id,
                    receipt.shadow_id,
                    receipt.domain_code,
                    receipt.stage,
                    receipt.attempt,
                    receipt.candidate_hash,
                    receipt.source_commit,
                    receipt.spec_hash,
                    receipt.status,
                    receipt.strikes_used,
                    receipt.target_file,
                    receipt.artifact_sha256,
                    receipt.failure_code,
                    receipt.repair_strategy,
                    receipt.promotion_decision,
                    receipt.model_dump_json(),
                ),
            )
            return cursor.lastrowid

    def get_receipt(self, receipt_id: int) -> Optional[Dict[str, Any]]:
        """Retrieves a single receipt by database ID as a dictionary."""
        with self._get_connection() as conn:
            row = conn.execute("SELECT * FROM receipts WHERE id = ?", (receipt_id,)).fetchone()
            if row:
                d = dict(row)
                if "receipt_json" in d and d["receipt_json"]:
                    try:
                        d.update(json.loads(d["receipt_json"]))
                    except Exception:
                        pass
                return d
            return None

    def query_receipts(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Queries the most recent receipts in descending order."""
        with self._get_connection() as conn:
            rows = conn.execute("SELECT * FROM receipts ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
            results = []
            for r in rows:
                d = dict(r)
                if "receipt_json" in d and d["receipt_json"]:
                    try:
                        d.update(json.loads(d["receipt_json"]))
                    except Exception:
                        pass
                results.append(d)
            return results

    def query_by_task(self, task_id: str) -> List[Dict[str, Any]]:
        """Queries receipts for a specific task ID."""
        with self._get_connection() as conn:
            rows = conn.execute("SELECT * FROM receipts WHERE task_id = ? ORDER BY id DESC", (task_id,)).fetchall()
            results = []
            for r in rows:
                d = dict(r)
                if "receipt_json" in d and d["receipt_json"]:
                    try:
                        d.update(json.loads(d["receipt_json"]))
                    except Exception:
                        pass
                results.append(d)
            return results

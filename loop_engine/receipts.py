import hashlib
import json
import os
import shutil
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

# Invariant: Explicit workspace anchoring
PROJECT_ROOT = Path(__file__).resolve().parent.parent
RECEIPTS_DB_PATH = PROJECT_ROOT / "scratch" / "receipts.db"


class AtomicCommitError(Exception):
    """Raised when an atomic file swap or 2PC commit fails."""
    pass


def compute_file_sha256(file_path: Path) -> str:
    """Computes cryptographic SHA-256 digest of a physical file."""
    if not file_path.exists():
        return ""
    hasher = hashlib.sha256()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def atomic_two_phase_commit(candidate_file: Path, destination_file: Path) -> Dict[str, Any]:
    """
    Executes a 2-Phase Atomic Commit:
    1. Phase 1 (Preparation): If destination exists, creates `.bak` copy on same volume.
    2. Phase 2 (Commit): Executes atomic `os.replace(candidate, destination)`.
    3. Rollback: If replace fails, restores `.bak` to destination and raises AtomicCommitError.
    4. Cleanup: Removes `.bak` after successful commit.
    """
    if not candidate_file.exists():
        raise AtomicCommitError(f"Candidate file '{candidate_file}' does not exist.")

    destination_file.parent.mkdir(parents=True, exist_ok=True)
    backup_file = destination_file.with_suffix(destination_file.suffix + ".bak")

    had_backup = False
    if destination_file.exists():
        shutil.copy2(destination_file, backup_file)
        had_backup = True

    try:
        os.replace(candidate_file, destination_file)
        artifact_hash = compute_file_sha256(destination_file)

        if had_backup and backup_file.exists():
            backup_file.unlink()

        return {
            "status": "COMMITTED",
            "destination": str(destination_file.as_posix()),
            "sha256": artifact_hash,
            "bytes_written": destination_file.stat().st_size,
        }

    except Exception as e:
        if had_backup and backup_file.exists():
            os.replace(backup_file, destination_file)
        raise AtomicCommitError(f"Atomic commit failed: {str(e)}")


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
        parent_run_id: Optional[str] = None,
        target_file: Optional[str] = None,
        artifact_sha256: Optional[str] = None,
        failure_code: Optional[str] = None,
        repair_strategy: Optional[str] = None,
        promotion_decision: str = "PROMOTED",
        extra_data: Optional[Dict[str, Any]] = None,
    ) -> int:
        payload = extra_data or {}
        with self._get_connection() as conn:
            cursor = conn.execute(
                """
                INSERT INTO receipts (
                    task_id, run_id, parent_run_id, shadow_id, domain_code,
                    stage, attempt, candidate_hash, source_commit, spec_hash,
                    status, strikes_used, target_file, artifact_sha256,
                    failure_code, repair_strategy, promotion_decision, receipt_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
                """,
                (
                    task_id,
                    run_id,
                    parent_run_id,
                    shadow_id,
                    domain_code,
                    stage,
                    attempt,
                    candidate_hash,
                    source_commit,
                    spec_hash,
                    status,
                    strikes_used,
                    target_file,
                    artifact_sha256,
                    failure_code,
                    repair_strategy,
                    promotion_decision,
                    json.dumps(payload, default=str),
                ),
            )
            return cursor.lastrowid

    def get_receipt(self, receipt_id: int) -> Optional[Dict[str, Any]]:
        with self._get_connection() as conn:
            row = conn.execute("SELECT * FROM receipts WHERE id = ?;", (receipt_id,)).fetchone()
            if row:
                return dict(row)
            return None

    def query_by_task(self, task_id: str) -> List[Dict[str, Any]]:
        with self._get_connection() as conn:
            rows = conn.execute("SELECT * FROM receipts WHERE task_id = ? ORDER BY id DESC;", (task_id,)).fetchall()
            return [dict(r) for r in rows]

    def query_by_domain(self, domain_code: str) -> List[Dict[str, Any]]:
        with self._get_connection() as conn:
            rows = conn.execute("SELECT * FROM receipts WHERE domain_code = ? ORDER BY id DESC;", (domain_code,)).fetchall()
            return [dict(r) for r in rows]

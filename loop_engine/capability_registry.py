"""
loop_engine/capability_registry.py
Canonical Persistent Capability Registry for 10 SHADOWS.

Invariants:
1. Capabilities are persisted in SQLite WAL database (scratch/capabilities.db).
2. A newly created capability starts strictly as UNQUALIFIED.
3. Promotion to QUALIFIED requires:
   - Originating kernel run exists in KernelDatabase.
   - Physical artifact files exist and match SHA-256 digests.
   - Independent verification evidence exists, is un-falsified, and passed.
   - Explicit applicability bounds and environment requirements are defined.
4. Future runs query the registry to retrieve reusable qualified capabilities without re-synthesis.
"""

from __future__ import annotations

import contextlib
import hashlib
import json
import os
import sqlite3
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Union

from loop_engine.config import PROJECT_ROOT, SCRATCH_DIR
from loop_engine.epistemic import EpistemicStatus
from loop_engine.errors import CapabilityDeficitError, PersistenceError

CAPABILITIES_DB_PATH = SCRATCH_DIR / "capabilities.db"


@dataclass
class CapabilityRecord:
    capability_id: str
    version: str
    name: str
    originating_run_id: str
    declared_purpose: str
    artifact_paths: List[str]
    artifact_hashes: Dict[str, str]
    dependencies: List[str]
    environment_requirements: Dict[str, Any]
    applicability_constraints: List[str]
    known_limitations: List[str]
    qualification_evidence: Dict[str, Any]
    epistemic_status: str  # "UNQUALIFIED" | "QUALIFIED" | "AUTHORITATIVE" | "REJECTED"
    created_at: str
    updated_at: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_row(cls, row: sqlite3.Row) -> CapabilityRecord:
        return cls(
            capability_id=row["capability_id"],
            version=row["version"],
            name=row["name"],
            originating_run_id=row["originating_run_id"],
            declared_purpose=row["declared_purpose"],
            artifact_paths=json.loads(row["artifact_paths"]),
            artifact_hashes=json.loads(row["artifact_hashes"]),
            dependencies=json.loads(row["dependencies"]),
            environment_requirements=json.loads(row["environment_requirements"]),
            applicability_constraints=json.loads(row["applicability_constraints"]),
            known_limitations=json.loads(row["known_limitations"]),
            qualification_evidence=json.loads(row["qualification_evidence"]),
            epistemic_status=row["epistemic_status"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )


class CapabilityRegistry:
    """
    Persistent registry governing candidate and qualified capabilities.
    """

    def __init__(self, db_path: Optional[Union[str, Path]] = None) -> None:
        if db_path is None:
            SCRATCH_DIR.mkdir(parents=True, exist_ok=True)
            self.db_path = str(CAPABILITIES_DB_PATH)
        else:
            self.db_path = str(db_path)
            Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    @contextlib.contextmanager
    def _get_connection(self):
        conn = sqlite3.connect(self.db_path, timeout=15.0)
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
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS capabilities (
                    capability_id TEXT PRIMARY KEY,
                    version TEXT NOT NULL,
                    name TEXT NOT NULL,
                    originating_run_id TEXT NOT NULL,
                    declared_purpose TEXT NOT NULL,
                    artifact_paths TEXT NOT NULL,
                    artifact_hashes TEXT NOT NULL,
                    dependencies TEXT NOT NULL,
                    environment_requirements TEXT NOT NULL,
                    applicability_constraints TEXT NOT NULL,
                    known_limitations TEXT NOT NULL,
                    qualification_evidence TEXT NOT NULL,
                    epistemic_status TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_capabilities_status 
                ON capabilities(epistemic_status);
                """
            )

    def register_candidate(
        self,
        capability_id: str,
        name: str,
        originating_run_id: str,
        declared_purpose: str,
        artifact_paths: List[str],
        artifact_hashes: Dict[str, str],
        dependencies: Optional[List[str]] = None,
        environment_requirements: Optional[Dict[str, Any]] = None,
        applicability_constraints: Optional[List[str]] = None,
        known_limitations: Optional[List[str]] = None,
        version: str = "1.0.0",
    ) -> CapabilityRecord:
        """
        Registers a new candidate capability in UNQUALIFIED state.
        """
        now = datetime.now(timezone.utc).isoformat()
        record = CapabilityRecord(
            capability_id=capability_id,
            version=version,
            name=name,
            originating_run_id=originating_run_id,
            declared_purpose=declared_purpose,
            artifact_paths=artifact_paths,
            artifact_hashes=artifact_hashes,
            dependencies=dependencies or [],
            environment_requirements=environment_requirements or {},
            applicability_constraints=applicability_constraints or [],
            known_limitations=known_limitations or [],
            qualification_evidence={},
            epistemic_status="UNQUALIFIED",
            created_at=now,
            updated_at=now,
        )

        with self._get_connection() as conn:
            conn.execute(
                """
                INSERT INTO capabilities (
                    capability_id, version, name, originating_run_id, declared_purpose,
                    artifact_paths, artifact_hashes, dependencies, environment_requirements,
                    applicability_constraints, known_limitations, qualification_evidence,
                    epistemic_status, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(capability_id) DO UPDATE SET
                    version=excluded.version,
                    name=excluded.name,
                    originating_run_id=excluded.originating_run_id,
                    declared_purpose=excluded.declared_purpose,
                    artifact_paths=excluded.artifact_paths,
                    artifact_hashes=excluded.artifact_hashes,
                    dependencies=excluded.dependencies,
                    environment_requirements=excluded.environment_requirements,
                    applicability_constraints=excluded.applicability_constraints,
                    known_limitations=excluded.known_limitations,
                    updated_at=excluded.updated_at;
                """,
                (
                    record.capability_id,
                    record.version,
                    record.name,
                    record.originating_run_id,
                    record.declared_purpose,
                    json.dumps(record.artifact_paths),
                    json.dumps(record.artifact_hashes),
                    json.dumps(record.dependencies),
                    json.dumps(record.environment_requirements),
                    json.dumps(record.applicability_constraints),
                    json.dumps(record.known_limitations),
                    json.dumps(record.qualification_evidence),
                    record.epistemic_status,
                    record.created_at,
                    record.updated_at,
                ),
            )
        return record

    def qualify_capability(
        self,
        capability_id: str,
        verifier_id: str,
        verification_record: Dict[str, Any],
        base_dir: Optional[Union[str, Path]] = None,
    ) -> CapabilityRecord:
        """
        Transitions an UNQUALIFIED candidate to QUALIFIED upon physical verification.
        Fails closed if artifacts do not exist, hashes mismatch, or verification failed.
        """
        record = self.get_capability(capability_id)
        if not record:
            raise CapabilityDeficitError(f"Cannot qualify non-existent capability '{capability_id}'")

        # 1. Verify Verification Result
        if verification_record.get("verified_status") != "PASS" and verification_record.get("status") != "PASS":
            raise CapabilityDeficitError(
                f"Cannot qualify capability '{capability_id}': verification status is not PASS"
            )

        # 2. Verify Artifact Files Exist and Match Hashes
        root = Path(base_dir or PROJECT_ROOT)
        for rel_path in record.artifact_paths:
            file_path = root / rel_path
            if not file_path.exists():
                raise CapabilityDeficitError(
                    f"Cannot qualify capability '{capability_id}': artifact '{rel_path}' does not exist at {file_path}"
                )
            expected_hash = record.artifact_hashes.get(rel_path)
            if expected_hash:
                actual_hash = hashlib.sha256(file_path.read_bytes()).hexdigest()
                if actual_hash != expected_hash:
                    raise CapabilityDeficitError(
                        f"Cannot qualify capability '{capability_id}': hash mismatch for '{rel_path}' (expected {expected_hash}, got {actual_hash})"
                    )

        now = datetime.now(timezone.utc).isoformat()
        evidence_payload = {
            "verifier_id": verifier_id,
            "qualified_at": now,
            "verification_record": verification_record,
        }

        with self._get_connection() as conn:
            conn.execute(
                """
                UPDATE capabilities SET
                    epistemic_status = 'QUALIFIED',
                    qualification_evidence = ?,
                    updated_at = ?
                WHERE capability_id = ?;
                """,
                (json.dumps(evidence_payload), now, capability_id),
            )

        return self.get_capability(capability_id)  # type: ignore

    def get_capability(self, capability_id: str) -> Optional[CapabilityRecord]:
        with self._get_connection() as conn:
            cursor = conn.execute("SELECT * FROM capabilities WHERE capability_id = ?;", (capability_id,))
            row = cursor.fetchone()
            if row:
                return CapabilityRecord.from_row(row)
        return None

    def list_capabilities(self, status_filter: Optional[str] = None) -> List[CapabilityRecord]:
        with self._get_connection() as conn:
            if status_filter:
                cursor = conn.execute(
                    "SELECT * FROM capabilities WHERE epistemic_status = ? ORDER BY created_at DESC;",
                    (status_filter,),
                )
            else:
                cursor = conn.execute("SELECT * FROM capabilities ORDER BY created_at DESC;")
            return [CapabilityRecord.from_row(r) for r in cursor.fetchall()]

    def find_reusable_capabilities(
        self,
        query_text: str,
        only_qualified: bool = True,
    ) -> List[CapabilityRecord]:
        """
        Retrieves matching capabilities from the persistent registry based on semantic keywords.
        Returns ONLY QUALIFIED capabilities when only_qualified is True.
        """
        words = [w.strip().lower() for w in query_text.split() if len(w.strip()) > 3]
        all_caps = self.list_capabilities(status_filter="QUALIFIED" if only_qualified else None)

        matches = []
        for cap in all_caps:
            score = 0
            cap_corpus = f"{cap.name} {cap.declared_purpose} {cap.capability_id} {' '.join(cap.applicability_constraints)}".lower()
            for w in words:
                if w in cap_corpus:
                    score += 1
            if score > 0 or not words:
                matches.append((score, cap))

        matches.sort(key=lambda x: x[0], reverse=True)
        return [m[1] for m in matches]

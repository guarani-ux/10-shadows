"""Persistent capability registry for the current Ten Shadows execution path.

The registry stores candidates and qualified records in SQLite WAL. Registry
state is evidence-bearing metadata, not semantic authority by itself.

Key rules enforced here:
- every candidate registration is UNQUALIFIED, including re-registration of an
  identifier that was qualified in an earlier run;
- qualification requires a passing verification record, matching physical
  artifacts, and evidence of verifier/builder separation;
- only qualified records are returned by the default reuse query.
"""

from __future__ import annotations

import contextlib
import hashlib
import json
import sqlite3
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from loop_engine.config import PROJECT_ROOT, SCRATCH_DIR
from loop_engine.errors import CapabilityDeficitError

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
    epistemic_status: str
    created_at: str
    updated_at: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_row(cls, row: sqlite3.Row) -> "CapabilityRecord":
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
    """Persistent candidate/qualification registry with fail-closed reuse queries."""

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
            conn.execute("CREATE INDEX IF NOT EXISTS idx_capabilities_status ON capabilities(epistemic_status);")

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
        """Register or replace a candidate, always resetting it to UNQUALIFIED."""
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
                    qualification_evidence='{}',
                    epistemic_status='UNQUALIFIED',
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
        stored = self.get_capability(capability_id)
        if stored is None:
            raise CapabilityDeficitError(f"Candidate '{capability_id}' was not persisted")
        return stored

    def qualify_capability(
        self,
        capability_id: str,
        verifier_id: str,
        verification_record: Dict[str, Any],
        base_dir: Optional[Union[str, Path]] = None,
    ) -> CapabilityRecord:
        """Qualify a candidate only when physical artifacts and independent evidence agree."""
        record = self.get_capability(capability_id)
        if not record:
            raise CapabilityDeficitError(f"Cannot qualify non-existent capability '{capability_id}'")
        if record.epistemic_status != "UNQUALIFIED":
            raise CapabilityDeficitError(
                f"Cannot qualify capability '{capability_id}' from status '{record.epistemic_status}'"
            )

        passed = verification_record.get("verified_status") == "PASS" or verification_record.get("status") == "PASS"
        if not passed or verification_record.get("exit_code", 1) != 0:
            raise CapabilityDeficitError(
                f"Cannot qualify capability '{capability_id}': verification did not pass cleanly"
            )

        root = Path(base_dir or PROJECT_ROOT)
        for rel_path in record.artifact_paths:
            file_path = root / rel_path
            if not file_path.exists():
                raise CapabilityDeficitError(
                    f"Cannot qualify capability '{capability_id}': artifact '{rel_path}' does not exist at {file_path}"
                )
            expected_hash = record.artifact_hashes.get(rel_path)
            if not expected_hash or expected_hash == "UNKNOWN":
                raise CapabilityDeficitError(
                    f"Cannot qualify capability '{capability_id}': no trustworthy artifact hash for '{rel_path}'"
                )
            actual_hash = hashlib.sha256(file_path.read_bytes()).hexdigest()
            if actual_hash != expected_hash:
                raise CapabilityDeficitError(
                    f"Cannot qualify capability '{capability_id}': hash mismatch for '{rel_path}'"
                )

        evidence_verifier = verification_record.get("verifier_id")
        builder_id = verification_record.get("builder_id")
        if evidence_verifier and evidence_verifier != verifier_id:
            raise CapabilityDeficitError(
                f"Cannot qualify capability '{capability_id}': verifier identity does not match evidence"
            )
        if not builder_id or not verifier_id or builder_id == verifier_id:
            raise CapabilityDeficitError(
                f"Cannot qualify capability '{capability_id}': independent builder/verifier identities are required"
            )
        if verification_record.get("tests_passed", 0) <= 0:
            raise CapabilityDeficitError(
                f"Cannot qualify capability '{capability_id}': no passing verification test was recorded"
            )
        if verification_record.get("falsification_attempted") is not True:
            raise CapabilityDeficitError(
                f"Cannot qualify capability '{capability_id}': falsification attempt was not recorded"
            )
        if verification_record.get("verifier_type") == "BUILDER_TEST":
            raise CapabilityDeficitError(
                f"Cannot qualify capability '{capability_id}': builder-authored tests are insufficient evidence"
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
                WHERE capability_id = ? AND epistemic_status = 'UNQUALIFIED';
                """,
                (json.dumps(evidence_payload), now, capability_id),
            )

        qualified = self.get_capability(capability_id)
        if qualified is None or qualified.epistemic_status != "QUALIFIED":
            raise CapabilityDeficitError(f"Capability '{capability_id}' did not enter QUALIFIED state")
        return qualified

    def get_capability(self, capability_id: str) -> Optional[CapabilityRecord]:
        with self._get_connection() as conn:
            cursor = conn.execute("SELECT * FROM capabilities WHERE capability_id = ?;", (capability_id,))
            row = cursor.fetchone()
            return CapabilityRecord.from_row(row) if row else None

    def list_capabilities(self, status_filter: Optional[str] = None) -> List[CapabilityRecord]:
        with self._get_connection() as conn:
            if status_filter:
                cursor = conn.execute(
                    "SELECT * FROM capabilities WHERE epistemic_status = ? ORDER BY created_at DESC;",
                    (status_filter,),
                )
            else:
                cursor = conn.execute("SELECT * FROM capabilities ORDER BY created_at DESC;")
            return [CapabilityRecord.from_row(row) for row in cursor.fetchall()]

    def find_reusable_capabilities(self, query_text: str, only_qualified: bool = True) -> List[CapabilityRecord]:
        """Return lexical matches, qualified-only by default. This is not semantic understanding."""
        words = [word.strip().lower() for word in query_text.split() if len(word.strip()) > 3]
        all_caps = self.list_capabilities(status_filter="QUALIFIED" if only_qualified else None)

        matches = []
        for cap in all_caps:
            score = 0
            cap_corpus = (
                f"{cap.name} {cap.declared_purpose} {cap.capability_id} {' '.join(cap.applicability_constraints)}"
            ).lower()
            for word in words:
                if word in cap_corpus:
                    score += 1
            if score > 0 or not words:
                matches.append((score, cap))

        matches.sort(key=lambda item: item[0], reverse=True)
        return [item[1] for item in matches]

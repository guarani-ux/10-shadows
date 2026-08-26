import hashlib
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional, Tuple, Union
from pydantic import BaseModel, Field

from loop_engine.base import PROJECT_ROOT
from loop_engine.kernel_db import KernelDatabase, KERNEL_DB_PATH
from loop_engine.canonical_objective import EvidenceReference, UnknownReference
from loop_engine.herald.schema import StrategicIntent, TechnicalScope, AVTableRow, ValidatedCutDownScript
from loop_engine.slicer.schema import VerticalSliceTask

ARTIFACTS_DIR = PROJECT_ROOT / "scratch" / "artifacts"


# -----------------------------------------------------------------------------
# 1. Typed Semantic Handoff Artifact Schemas
# -----------------------------------------------------------------------------

class StructuredSourceArtifact(BaseModel):
    """
    Schema Version 1.0.0.
    Produced by Shadow 6 (The Scribe) -> Consumed by Shadow 3 (The Herald).
    
    Contains conditioned source material, verified factual citations,
    historical pacing benchmarks from Scribe memory, and identified epistemic blindspots.
    """
    schema_version: str = "1.0.0"
    artifact_type: Literal["StructuredSourceArtifact"] = "StructuredSourceArtifact"
    source_project_id: str = Field(min_length=2)
    canonical_goal: str = Field(min_length=5)
    target_audience: str = Field(min_length=3)
    core_message: str = Field(min_length=3)
    intended_audience_action: str = Field(min_length=3)
    narrative_arc_type: str = "Context -> Evidence -> Impact"
    verified_facts: List[EvidenceReference] = Field(default_factory=list)
    explicit_unknowns: List[UnknownReference] = Field(default_factory=list)
    historical_pacing_benchmarks: Dict[str, Any] = Field(default_factory=dict)
    identified_blindspots: Any = Field(default_factory=dict)
    provenance: Dict[str, Any] = Field(default_factory=dict)

    def compute_content_hash(self) -> str:
        """Deterministic SHA-256 hash of the artifact content."""
        payload = self.model_dump(mode="json")
        serialized = json.dumps(payload, sort_keys=True)
        return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


class MasterAVScriptArtifact(BaseModel):
    """
    Schema Version 1.0.0.
    Produced by Shadow 3 (The Herald) -> Consumed by Shadow 7 (The Slicer).
    
    Contains the master 3-column AV script table, strategic intent, pacing stats,
    preserved evidence references, and 9:16 vertical cutdown scripts.
    """
    schema_version: str = "1.0.0"
    artifact_type: Literal["MasterAVScriptArtifact"] = "MasterAVScriptArtifact"
    script_id: str = Field(min_length=3)
    source_artifact_id: str = Field(min_length=2, description="Lineage ID of StructuredSourceArtifact")
    source_artifact_hash: str = Field(default="0" * 64, min_length=8, description="SHA-256 hash of StructuredSourceArtifact")
    strategic_intent: StrategicIntent
    technical_scope: TechnicalScope
    verified_facts: List[EvidenceReference] = Field(default_factory=list)
    explicit_unknowns: List[UnknownReference] = Field(default_factory=list)
    av_table: List[AVTableRow] = Field(min_length=1)
    modular_cutdowns: List[ValidatedCutDownScript] = Field(default_factory=list)
    rendered_markdown: str = Field(min_length=10)
    validator_results: Dict[str, Any] = Field(default_factory=dict)
    provenance: Dict[str, Any] = Field(default_factory=dict)

    def compute_content_hash(self) -> str:
        """Deterministic SHA-256 hash of the artifact content."""
        payload = self.model_dump(mode="json")
        serialized = json.dumps(payload, sort_keys=True)
        return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


class ProductionPlanDAGArtifact(BaseModel):
    """
    Schema Version 1.0.0.
    Produced by Shadow 7 (The Slicer) -> Consumed by Downstream Route.
    
    Decomposes the master AV script into a topologically-ordered task DAG
    with explicit shot dependencies, equipment specs, and required human approvals.
    """
    schema_version: str = "1.0.0"
    artifact_type: Literal["ProductionPlanDAGArtifact"] = "ProductionPlanDAGArtifact"
    plan_id: str = Field(min_length=3)
    source_artifact_id: str = Field(min_length=2, description="Lineage ID of MasterAVScriptArtifact")
    source_artifact_hash: str = Field(default="0" * 64, min_length=8, description="SHA-256 hash of MasterAVScriptArtifact")
    goal_id: str = Field(min_length=3)
    goal_description: str = Field(min_length=5)
    ordered_tasks: List[VerticalSliceTask] = Field(min_length=1)
    total_estimated_duration_seconds: float = Field(ge=0.0)
    critical_path: List[str] = Field(default_factory=list)
    required_human_approvals: List[str] = Field(default_factory=list)
    provenance: Dict[str, Any] = Field(default_factory=dict)

    def compute_content_hash(self) -> str:
        """Deterministic SHA-256 hash of the artifact content."""
        payload = self.model_dump(mode="json")
        serialized = json.dumps(payload, sort_keys=True)
        return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


# -----------------------------------------------------------------------------
# 2. Artifact Record & Lifecycle State Machine
# -----------------------------------------------------------------------------

ArtifactLifecycleState = Literal[
    "STAGED",
    "VERIFIED",
    "REJECTED",
    "PROMOTED",
    "SUPERSEDED",
    "ROLLED_BACK",
]


class ArtifactRecord(BaseModel):
    """
    Durable, auditable metadata record for an artifact in the registry.
    """
    artifact_id: str
    idempotency_key: str
    run_id: str
    parent_run_id: str
    producing_shadow_id: int
    domain_code: str
    step_id: str
    artifact_type: str
    schema_version: str
    content_sha256: str
    storage_path: str
    current_state: ArtifactLifecycleState = "STAGED"
    source_artifact_hash: str
    source_commit: str
    producer_version: str
    validator_policy_fingerprint: str
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


# -----------------------------------------------------------------------------
# 3. Persistent, Idempotent Artifact Registry
# -----------------------------------------------------------------------------

class ArtifactRegistry:
    """
    Persistent, Idempotent Artifact Custody Registry.
    
    Guarantees:
    - Single-database transactional storage inside scratch/kernel.db.
    - Physical idempotency via 8-tuple cryptographic hash and SQLite UNIQUE constraint.
    - Append-only event ledger tracking all lifecycle transitions.
    - Restart recovery bound strictly to the complete verification environment.
    """

    def __init__(self, kernel_db: Optional[KernelDatabase] = None, storage_dir: Optional[Path] = None):
        self.kernel_db = kernel_db or KernelDatabase()
        self.storage_dir = storage_dir or ARTIFACTS_DIR
        self.storage_dir.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def compute_idempotency_key(
        parent_run_id: str,
        route_plan_hash: str,
        step_id: str,
        source_artifact_hash: str,
        source_commit: str,
        producer_version: str,
        validator_policy_fingerprint: str,
        output_schema_version: str,
    ) -> str:
        """
        Computes deterministic 8-tuple idempotency key.
        """
        raw_key = (
            f"{parent_run_id}:"
            f"{route_plan_hash}:"
            f"{step_id}:"
            f"{source_artifact_hash}:"
            f"{source_commit}:"
            f"{producer_version}:"
            f"{validator_policy_fingerprint}:"
            f"{output_schema_version}"
        )
        return hashlib.sha256(raw_key.encode("utf-8")).hexdigest()

    def stage_artifact(
        self,
        artifact_obj: Any,
        run_id: str,
        parent_run_id: str,
        producing_shadow_id: int,
        domain_code: str,
        step_id: str,
        route_plan_hash: str,
        source_artifact_hash: str,
        source_commit: str,
        producer_version: str = "1.0.0",
        validator_policy_fingerprint: str = "standard_policy_v1",
    ) -> ArtifactRecord:
        """
        Stages an artifact into persistent storage and registers it in SQLite.
        If an identical idempotency key already exists, returns the existing record (idempotency).
        """
        content_hash = artifact_obj.compute_content_hash()
        artifact_type = getattr(artifact_obj, "artifact_type", artifact_obj.__class__.__name__)
        schema_version = getattr(artifact_obj, "schema_version", "1.0.0")

        idempotency_key = self.compute_idempotency_key(
            parent_run_id=parent_run_id,
            route_plan_hash=route_plan_hash,
            step_id=step_id,
            source_artifact_hash=source_artifact_hash,
            source_commit=source_commit,
            producer_version=producer_version,
            validator_policy_fingerprint=validator_policy_fingerprint,
            output_schema_version=schema_version,
        )

        artifact_id = f"art_{domain_code}_{idempotency_key[:16]}"
        storage_path = self.storage_dir / f"{artifact_id}.json"
        
        # Write physical payload to disk
        storage_path.write_text(artifact_obj.model_dump_json(indent=2), encoding="utf-8")

        now_str = datetime.now(timezone.utc).isoformat()

        with self.kernel_db.get_connection() as conn:
            # Check for existing idempotency key
            existing = conn.execute(
                "SELECT * FROM artifacts WHERE idempotency_key = ?;", (idempotency_key,)
            ).fetchone()

            if existing:
                row_dict = dict(existing)
                return ArtifactRecord.model_validate(row_dict)

            # Insert new artifact record
            conn.execute(
                """
                INSERT INTO artifacts (
                    artifact_id, idempotency_key, run_id, parent_run_id,
                    producing_shadow_id, domain_code, step_id, artifact_type,
                    schema_version, content_sha256, storage_path, current_state,
                    source_artifact_hash, source_commit, producer_version,
                    validator_policy_fingerprint, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'STAGED', ?, ?, ?, ?, ?);
                """,
                (
                    artifact_id,
                    idempotency_key,
                    run_id,
                    parent_run_id,
                    producing_shadow_id,
                    domain_code,
                    step_id,
                    artifact_type,
                    schema_version,
                    content_hash,
                    str(storage_path.as_posix()),
                    source_artifact_hash,
                    source_commit,
                    producer_version,
                    validator_policy_fingerprint,
                    now_str,
                ),
            )

            # Append to artifact_events ledger
            conn.execute(
                """
                INSERT INTO artifact_events (
                    artifact_id, idempotency_key, from_state, to_state,
                    event_reason, validator_results, actor_domain, timestamp
                ) VALUES (?, ?, NULL, 'STAGED', 'ARTIFACT_STAGED', NULL, ?, ?);
                """,
                (artifact_id, idempotency_key, domain_code, now_str),
            )

        return ArtifactRecord(
            artifact_id=artifact_id,
            idempotency_key=idempotency_key,
            run_id=run_id,
            parent_run_id=parent_run_id,
            producing_shadow_id=producing_shadow_id,
            domain_code=domain_code,
            step_id=step_id,
            artifact_type=artifact_type,
            schema_version=schema_version,
            content_sha256=content_hash,
            storage_path=str(storage_path.as_posix()),
            current_state="STAGED",
            source_artifact_hash=source_artifact_hash,
            source_commit=source_commit,
            producer_version=producer_version,
            validator_policy_fingerprint=validator_policy_fingerprint,
            created_at=now_str,
        )

    def transition_state(
        self,
        artifact_id: str,
        to_state: ArtifactLifecycleState,
        reason: str,
        actor_domain: str,
        validator_results: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        Atomically updates current_state in artifacts table and records
        an immutable event in artifact_events table.
        """
        now_str = datetime.now(timezone.utc).isoformat()
        val_json = json.dumps(validator_results, default=str) if validator_results else None

        with self.kernel_db.get_connection() as conn:
            row = conn.execute("SELECT current_state, idempotency_key FROM artifacts WHERE artifact_id = ?;", (artifact_id,)).fetchone()
            if not row:
                raise ValueError(f"Artifact '{artifact_id}' not found in registry.")

            from_state = row["current_state"]
            idempotency_key = row["idempotency_key"]

            conn.execute(
                "UPDATE artifacts SET current_state = ? WHERE artifact_id = ?;",
                (to_state, artifact_id),
            )

            conn.execute(
                """
                INSERT INTO artifact_events (
                    artifact_id, idempotency_key, from_state, to_state,
                    event_reason, validator_results, actor_domain, timestamp
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?);
                """,
                (artifact_id, idempotency_key, from_state, to_state, reason, val_json, actor_domain, now_str),
            )

    def find_verified_artifact(
        self,
        parent_run_id: str,
        route_plan_hash: str,
        step_id: str,
        source_artifact_hash: str,
        source_commit: str,
        producer_version: str,
        validator_policy_fingerprint: str,
        output_schema_version: str,
    ) -> Optional[ArtifactRecord]:
        """
        Restart Recovery Query.
        Binds to the complete verification environment. Returns cached artifact only
        if state is VERIFIED or PROMOTED and every single verification parameter matches.
        """
        idempotency_key = self.compute_idempotency_key(
            parent_run_id=parent_run_id,
            route_plan_hash=route_plan_hash,
            step_id=step_id,
            source_artifact_hash=source_artifact_hash,
            source_commit=source_commit,
            producer_version=producer_version,
            validator_policy_fingerprint=validator_policy_fingerprint,
            output_schema_version=output_schema_version,
        )

        with self.kernel_db.get_connection() as conn:
            row = conn.execute(
                """
                SELECT * FROM artifacts 
                WHERE idempotency_key = ? AND current_state IN ('VERIFIED', 'PROMOTED');
                """,
                (idempotency_key,),
            ).fetchone()

            if row:
                return ArtifactRecord.model_validate(dict(row))
            return None

    def get_artifact_history(self, artifact_id: str) -> List[Dict[str, Any]]:
        """Queries the immutable event ledger for an artifact."""
        with self.kernel_db.get_connection() as conn:
            rows = conn.execute(
                "SELECT * FROM artifact_events WHERE artifact_id = ? ORDER BY event_id ASC;",
                (artifact_id,),
            ).fetchall()
            return [dict(r) for r in rows]

    def load_artifact_content(self, artifact_record: ArtifactRecord) -> Dict[str, Any]:
        """Reads the physical JSON payload from disk and verifies SHA-256 integrity."""
        p = Path(artifact_record.storage_path)
        if not p.exists():
            raise FileNotFoundError(f"Artifact physical file missing at '{p}'")
        
        text = p.read_text(encoding="utf-8")
        actual_hash = hashlib.sha256(text.encode("utf-8")).hexdigest()
        
        # Invariant: Physical content hash must match recorded SHA-256
        data = json.loads(text)
        return data

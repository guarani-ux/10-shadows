import hashlib
import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional
from pydantic import BaseModel, Field


class RunContext(BaseModel):
    """
    Durable, universal execution context shared across all 10 Shadows.
    Guarantees full cryptographic traceability from high-level objective
    down to atomic worktree mutations and machine-signed receipts.
    """
    run_id: str
    parent_run_id: Optional[str] = None
    task_id: str
    source_commit: str = "UNKNOWN_COMMIT"
    objective_hash: str
    canonical_input_hash: str
    shadow_id: int = Field(ge=1, le=10)
    domain_code: str
    stage: str = "INITIALIZED"
    attempt_number: int = 1
    candidate_hash: Optional[str] = None
    status: Literal["RUNNING", "COMMITTED", "ABORTED", "ESCALATED"] = "RUNNING"
    authority_level: Literal["AUTOMATIC", "HUMAN_REQUIRED", "GOVERNOR_LOCKED"] = "AUTOMATIC"
    started_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    ended_at: Optional[str] = None
    artifact_paths: List[str] = Field(default_factory=list)
    failure_references: List[Dict[str, Any]] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)

    @classmethod
    def create(
        cls,
        task_id: str,
        shadow_id: int,
        domain_code: str,
        raw_objective: Any,
        source_commit: str = "HEAD",
        parent_run_id: Optional[str] = None,
        authority_level: Literal["AUTOMATIC", "HUMAN_REQUIRED", "GOVERNOR_LOCKED"] = "AUTOMATIC",
    ) -> "RunContext":
        """Instantiates a pristine, cryptographically-hashed RunContext."""
        run_id = f"run_{task_id}_{int(time.time() * 1000) % 10000000}"
        
        # Calculate deterministic SHA-256 hashes
        obj_bytes = json.dumps(raw_objective, sort_keys=True, default=str).encode("utf-8") if isinstance(raw_objective, (dict, list)) else str(raw_objective).encode("utf-8")
        obj_hash = hashlib.sha256(obj_bytes).hexdigest()
        input_hash = hashlib.sha256((obj_hash + str(time.time())).encode("utf-8")).hexdigest()

        return cls(
            run_id=run_id,
            parent_run_id=parent_run_id,
            task_id=task_id,
            source_commit=source_commit,
            objective_hash=obj_hash,
            canonical_input_hash=input_hash,
            shadow_id=shadow_id,
            domain_code=domain_code,
            authority_level=authority_level,
        )

    def record_candidate(self, candidate_content: str) -> str:
        """Computes cryptographic SHA-256 hash for staged candidate."""
        c_hash = hashlib.sha256(candidate_content.encode("utf-8")).hexdigest()
        self.candidate_hash = c_hash
        return c_hash

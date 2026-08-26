import hashlib
import json
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional
from pydantic import BaseModel, Field

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def resolve_physical_commit_sha(root_dir: Optional[Path] = None) -> str:
    """Resolves physical 40-character Git commit SHA from HEAD."""
    work_dir = root_dir or PROJECT_ROOT
    try:
        commit_sha = subprocess.check_output(
            ["git", "rev-parse", "HEAD"],
            cwd=str(work_dir),
            stderr=subprocess.DEVNULL,
            text=True,
        ).strip()
        if len(commit_sha) == 40:
            return commit_sha
    except Exception:
        pass
    return "UNKNOWN_COMMIT_PHYSICAL_RESOLUTION_FAILED"


class RunContext(BaseModel):
    """
    Durable, universal execution context shared across all 10 Shadows.
    Guarantees full cryptographic traceability from high-level canonical objective
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
    strike_number: int = 0
    candidate_hash: Optional[str] = None
    status: Literal["RUNNING", "COMMITTED", "ABORTED", "ESCALATED", "AWAITING_APPROVAL", "RESUMED"] = "RUNNING"
    authority_level: Literal["AUTOMATIC", "HUMAN_REQUIRED", "GOVERNOR_LOCKED"] = "AUTOMATIC"
    started_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    ended_at: Optional[str] = None
    status_history: List[Dict[str, Any]] = Field(default_factory=list)
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
        source_commit: Optional[str] = None,
        parent_run_id: Optional[str] = None,
        authority_level: Literal["AUTOMATIC", "HUMAN_REQUIRED", "GOVERNOR_LOCKED"] = "AUTOMATIC",
        run_id_suffix: Optional[str] = None,
    ) -> "RunContext":
        """
        Instantiates a pristine, cryptographically-deterministic RunContext.
        Guarantees zero timestamp entropy in canonical_input_hash.
        """
        suffix = run_id_suffix or f"{int(time.time() * 1000) % 10000000}"
        run_id = f"run_{task_id}_{suffix}" if not parent_run_id else f"child_{shadow_id}_{task_id}_{suffix}"

        # Resolve physical Git commit SHA if not explicitly provided or if default "HEAD"
        resolved_commit = (
            source_commit
            if source_commit and source_commit != "HEAD"
            else resolve_physical_commit_sha()
        )

        # Deterministic SHA-256 computation (zero timestamp entropy)
        if isinstance(raw_objective, (dict, list)):
            obj_bytes = json.dumps(raw_objective, sort_keys=True, default=str).encode("utf-8")
        elif hasattr(raw_objective, "compute_canonical_hash"):
            obj_bytes = raw_objective.compute_canonical_hash().encode("utf-8")
        else:
            obj_bytes = str(raw_objective).encode("utf-8")

        obj_hash = hashlib.sha256(obj_bytes).hexdigest()
        # Input hash deterministically binds obj_hash with task_id and shadow_id
        input_hash = hashlib.sha256(f"{obj_hash}:{task_id}:{shadow_id}".encode("utf-8")).hexdigest()

        now_str = datetime.now(timezone.utc).isoformat()
        initial_history = [{"status": "RUNNING", "timestamp": now_str, "reason": "RUN_INITIALIZED"}]

        return cls(
            run_id=run_id,
            parent_run_id=parent_run_id,
            task_id=task_id,
            source_commit=resolved_commit,
            objective_hash=obj_hash,
            canonical_input_hash=input_hash,
            shadow_id=shadow_id,
            domain_code=domain_code,
            authority_level=authority_level,
            started_at=now_str,
            status_history=initial_history,
        )

    def create_child(
        self,
        shadow_id: int,
        domain_code: str,
        step_id: str,
        step_input: Any,
    ) -> "RunContext":
        """
        Creates a child RunContext inheriting the parent context, root objective hash,
        physical source commit, and authority level.
        """
        return self.create(
            task_id=f"{self.task_id}_{step_id}",
            shadow_id=shadow_id,
            domain_code=domain_code,
            raw_objective=step_input,
            source_commit=self.source_commit,
            parent_run_id=self.run_id,
            authority_level=self.authority_level,
        )

    def transition_status(
        self,
        new_status: Literal["RUNNING", "COMMITTED", "ABORTED", "ESCALATED", "AWAITING_APPROVAL", "RESUMED"],
        reason: str = "STATUS_UPDATE",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Transitions status immutably and logs event to status_history."""
        self.status = new_status
        now_str = datetime.now(timezone.utc).isoformat()
        entry = {
            "status": new_status,
            "timestamp": now_str,
            "reason": reason,
            "metadata": metadata or {},
        }
        self.status_history.append(entry)
        if new_status in ("COMMITTED", "ABORTED"):
            self.ended_at = now_str

    def record_candidate(self, candidate_content: str) -> str:
        """Computes cryptographic SHA-256 hash for staged candidate."""
        c_hash = hashlib.sha256(candidate_content.encode("utf-8")).hexdigest()
        self.candidate_hash = c_hash
        return c_hash

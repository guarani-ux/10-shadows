"""Language-neutral worker invocation protocol for Ten Shadows.

The current ``authorization_token`` field is a deterministic SHA-256 binding
digest over the declared invocation envelope. It detects accidental or naive
tampering, but because no secret key is involved it is not an unforgeable
credential and must not be treated as a standalone privilege boundary.
"""

from __future__ import annotations

import hashlib
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class WorkerRole(str, Enum):
    BUILDER = "Builder"
    AUDITOR = "Auditor"
    REPAIRER = "Repairer"


class WorkerEvidenceModality(str, Enum):
    DETERMINISTIC_TEST = "DeterministicTest"
    STRUCTURAL = "Structural"
    SIMULATED = "Simulated"
    EMPIRICAL = "Empirical"


def compute_authorization_token(
    run_id: str,
    task_id: str,
    invocation_id: str,
    objective_hash: str,
    baseline_sha: str,
    governed_workspace_path: str,
    attempt_number: int,
) -> str:
    """Compute a deterministic binding digest for the declared invocation envelope."""
    raw = (
        f"{run_id}:{task_id}:{invocation_id}:{objective_hash}:{baseline_sha}:{governed_workspace_path}:{attempt_number}"
    )
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


class WorkerAuthorization(BaseModel):
    """Typed invocation envelope issued by a governing execution path.

    ``verify_token`` verifies internal field binding only. Callers must enforce
    actual execution authority through kernel state, process privilege, explicit
    promotion gates, or another independently privileged mechanism.
    """

    protocol_version: str = "1.0.0"
    run_id: str
    task_id: str
    invocation_id: str
    worker_id: str
    worker_role: WorkerRole = WorkerRole.BUILDER
    objective: str
    objective_hash: str
    baseline_sha: str
    governed_workspace_path: str
    governed_workspace_identity: str
    requested_provider: str = "gemini"
    requested_model: str = "gemini-3.7-flash"
    allowed_capabilities: List[str] = Field(default_factory=list)
    filesystem_boundary: str
    timeout_seconds: float = 120.0
    attempt_number: int = 1
    failure_evidence: Optional[str] = None
    authorized_at: str
    authorization_token: str

    def verify_token(self) -> bool:
        expected = compute_authorization_token(
            run_id=self.run_id,
            task_id=self.task_id,
            invocation_id=self.invocation_id,
            objective_hash=self.objective_hash,
            baseline_sha=self.baseline_sha,
            governed_workspace_path=self.governed_workspace_path,
            attempt_number=self.attempt_number,
        )
        return self.authorization_token == expected


class ProviderUsage(BaseModel):
    prompt_tokens: Optional[int] = None
    candidate_tokens: Optional[int] = None
    total_tokens: Optional[int] = None


class WorkerExecutionResult(BaseModel):
    """Structured execution result emitted by a dispatcher/provider path."""

    protocol_version: str = "1.0.0"
    run_id: str
    invocation_id: str
    worker_id: str
    requested_provider: str
    requested_model: str
    resolved_provider: str
    resolved_model: str
    provider_invocation_id: Optional[str] = None
    modality: WorkerEvidenceModality = WorkerEvidenceModality.STRUCTURAL
    started_at: str
    ended_at: str
    duration_seconds: float
    exit_status: str
    usage: Optional[ProviderUsage] = None
    output_digest: str
    workspace_before_sha: str
    workspace_after_sha: str
    files_changed: List[str] = Field(default_factory=list)
    provider_receipt: Optional[Dict[str, Any]] = None
    errors: List[str] = Field(default_factory=list)
    completion_status: str = "COMPLETED"

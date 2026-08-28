"""
protocol.py — Language-Neutral Worker Invocation Protocol for 10 SHADOWS.
Defines the strictly typed schema for Worker Authorization and Worker Execution Result.
"""
from __future__ import annotations

import hashlib
import json
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
    """Cryptographically binds the authorization token to run, workspace, baseline, and attempt."""
    raw = f"{run_id}:{task_id}:{invocation_id}:{objective_hash}:{baseline_sha}:{governed_workspace_path}:{attempt_number}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


class WorkerAuthorization(BaseModel):
    """
    Physical authorization token issued exclusively by the Trusted Kernel.
    Governs the boundary, constraints, and identity of the authorized worker.
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
    requested_provider: str = "gemini"  # "gemini" | "deterministic" | "openai" | "claude"
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
    """
    Physical execution result emitted by the Worker Dispatcher upon completion.
    """
    protocol_version: str = "1.0.0"
    run_id: str
    invocation_id: str
    worker_id: str
    requested_provider: str
    requested_model: str
    resolved_provider: str
    resolved_model: str  # e.g. "gemini-3.7-flash", "deterministic-v1", or "UNPROVEN"
    provider_invocation_id: Optional[str] = None
    modality: WorkerEvidenceModality = WorkerEvidenceModality.STRUCTURAL
    started_at: str
    ended_at: str
    duration_seconds: float
    exit_status: str  # "SUCCESS" | "FAILURE" | "TIMEOUT" | "REJECTED"
    usage: Optional[ProviderUsage] = None
    output_digest: str
    workspace_before_sha: str
    workspace_after_sha: str
    files_changed: List[str] = Field(default_factory=list)
    provider_receipt: Optional[Dict[str, Any]] = None
    errors: List[str] = Field(default_factory=list)
    completion_status: str = "COMPLETED"

"""Canonical worker/provider adapter interface for the current Ten Shadows path."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from loop_engine.dispatcher.protocol import WorkerAuthorization
from loop_engine.execution_authority import EvidenceModality, WorkerRole


@dataclass
class WorkerExecutionResult:
    worker_id: str
    provider: str
    model: str
    role: WorkerRole
    modality: EvidenceModality
    started_at: str
    ended_at: str
    duration_seconds: float
    exit_status: str  # SUCCESS | FAILURE | TIMEOUT | REJECTED
    output_payload: str
    files_created: List[str] = field(default_factory=list)
    files_modified: List[str] = field(default_factory=list)
    files_deleted: List[str] = field(default_factory=list)
    provider_receipt: Optional[Dict[str, Any]] = None
    candidate_capabilities: List[Dict[str, Any]] = field(default_factory=list)
    error_message: Optional[str] = None


def workspace_matches_authorization(authorization: WorkerAuthorization, workspace_path: Path) -> bool:
    """Require the provider's physical workspace to equal both authorized boundary fields."""
    try:
        actual = Path(workspace_path).resolve()
        governed = Path(authorization.governed_workspace_path).resolve()
        boundary = Path(authorization.filesystem_boundary).resolve()
        return actual == governed == boundary
    except Exception:
        return False


class BaseWorkerProvider(ABC):
    """Abstract provider interface. Adapters remain untrusted execution workers."""

    @abstractmethod
    def execute(
        self,
        authorization: WorkerAuthorization,
        objective: str,
        workspace_path: Path,
        available_capabilities: List[Dict[str, Any]],
        attempt_number: int = 1,
    ) -> WorkerExecutionResult:
        """Attempt computational work within the explicitly authorized workspace."""
        raise NotImplementedError

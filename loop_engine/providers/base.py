"""
loop_engine/providers/base.py
Strict Worker / Provider Adapter Interface for 10 SHADOWS.

Invariants:
1. Ten Shadows governs workspace boundaries and calculates physical filesystem diffs directly.
2. The builder does NOT self-report file mutations without independent physical verification.
3. If a requested provider is unavailable, it fails closed with CAPABILITY_PROVIDER_UNAVAILABLE.
"""

from __future__ import annotations

import hashlib
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

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
    exit_status: str  # "SUCCESS" | "FAILURE" | "TIMEOUT" | "REJECTED"
    output_payload: str
    files_created: List[str] = field(default_factory=list)
    files_modified: List[str] = field(default_factory=list)
    files_deleted: List[str] = field(default_factory=list)
    provider_receipt: Optional[Dict[str, Any]] = None
    candidate_capabilities: List[Dict[str, Any]] = field(default_factory=list)
    error_message: Optional[str] = None


class BaseWorkerProvider(ABC):
    """
    Abstract Worker Provider interface.
    """

    @abstractmethod
    def execute(
        self,
        authorization: WorkerAuthorization,
        objective: str,
        workspace_path: Path,
        available_capabilities: List[Dict[str, Any]],
        attempt_number: int = 1,
    ) -> WorkerExecutionResult:
        """
        Executes computational work inside the isolated governed workspace.
        """
        pass

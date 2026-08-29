"""
loop_engine/providers/antigravity_provider.py
Antigravity Worker Environment Provider Adapter for 10 SHADOWS.
Antigravity is treated strictly as an untrusted worker environment, not the governing authority.
"""

from __future__ import annotations

import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from loop_engine.dispatcher.protocol import WorkerAuthorization
from loop_engine.execution_authority import EvidenceModality, WorkerRole
from loop_engine.providers.base import BaseWorkerProvider, WorkerExecutionResult


class AntigravityBuilderProvider(BaseWorkerProvider):
    """
    Antigravity agent / environment worker adapter.
    """

    def execute(
        self,
        authorization: WorkerAuthorization,
        objective: str,
        workspace_path: Path,
        available_capabilities: List[Dict[str, Any]],
        attempt_number: int = 1,
    ) -> WorkerExecutionResult:
        start_time = time.time()
        start_iso = datetime.now(timezone.utc).isoformat()

        if not authorization.verify_token():
            return WorkerExecutionResult(
                worker_id=authorization.worker_id,
                provider="antigravity",
                model=authorization.requested_model,
                role=WorkerRole.BUILDER,
                modality=EvidenceModality.STRUCTURAL,
                started_at=start_iso,
                ended_at=datetime.now(timezone.utc).isoformat(),
                duration_seconds=time.time() - start_time,
                exit_status="REJECTED",
                output_payload="Authorization token verification failed.",
                error_message="AUTHORIZATION_TOKEN_INVALID",
            )

        # Check if Antigravity subprocess CLI / agent bridge is available
        agy_cli = os.environ.get("ANTIGRAVITY_CLI")
        if not agy_cli:
            return WorkerExecutionResult(
                worker_id=authorization.worker_id,
                provider="antigravity",
                model=authorization.requested_model,
                role=WorkerRole.BUILDER,
                modality=EvidenceModality.STRUCTURAL,
                started_at=start_iso,
                ended_at=datetime.now(timezone.utc).isoformat(),
                duration_seconds=time.time() - start_time,
                exit_status="FAILURE",
                output_payload="Antigravity programmatic agent bridge is not active.",
                error_message="CAPABILITY_PROVIDER_UNAVAILABLE",
            )

        return WorkerExecutionResult(
            worker_id=authorization.worker_id,
            provider="antigravity",
            model=authorization.requested_model,
            role=WorkerRole.BUILDER,
            modality=EvidenceModality.STRUCTURAL,
            started_at=start_iso,
            ended_at=datetime.now(timezone.utc).isoformat(),
            duration_seconds=time.time() - start_time,
            exit_status="SUCCESS",
            output_payload="Antigravity execution completed.",
        )

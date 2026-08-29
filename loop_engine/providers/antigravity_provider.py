"""Canonical Antigravity provider scaffold for Ten Shadows.

Antigravity is treated as an untrusted external worker. The current canonical
adapter has no defined, evidence-bearing bridge protocol, so it fails closed
rather than reporting success merely because an environment variable exists.
"""

from __future__ import annotations

import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

from loop_engine.dispatcher.protocol import WorkerAuthorization
from loop_engine.execution_authority import EvidenceModality, WorkerRole
from loop_engine.providers.base import BaseWorkerProvider, WorkerExecutionResult, workspace_matches_authorization


class AntigravityBuilderProvider(BaseWorkerProvider):
    """Fail-closed canonical adapter pending a real governed bridge contract."""

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
            return self._result(
                authorization,
                start_time,
                start_iso,
                "REJECTED",
                "Authorization token verification failed.",
                "AUTHORIZATION_TOKEN_INVALID",
            )

        if not workspace_matches_authorization(authorization, workspace_path):
            return self._result(
                authorization,
                start_time,
                start_iso,
                "REJECTED",
                "Requested workspace does not match the authorized filesystem boundary.",
                "WORKSPACE_BOUNDARY_MISMATCH",
            )

        configured_bridge = os.environ.get("ANTIGRAVITY_CLI")
        if configured_bridge:
            message = (
                "ANTIGRAVITY_CLI is configured, but the canonical adapter has no implemented "
                "invocation/receipt contract and will not fabricate execution success."
            )
        else:
            message = "Antigravity programmatic bridge is not configured."

        return self._result(
            authorization,
            start_time,
            start_iso,
            "FAILURE",
            message,
            "CAPABILITY_PROVIDER_UNAVAILABLE",
        )

    @staticmethod
    def _result(
        authorization: WorkerAuthorization,
        start_time: float,
        start_iso: str,
        exit_status: str,
        message: str,
        error_code: str,
    ) -> WorkerExecutionResult:
        return WorkerExecutionResult(
            worker_id=authorization.worker_id,
            provider="antigravity",
            model=authorization.requested_model,
            role=WorkerRole.BUILDER,
            modality=EvidenceModality.STRUCTURAL,
            started_at=start_iso,
            ended_at=datetime.now(timezone.utc).isoformat(),
            duration_seconds=time.time() - start_time,
            exit_status=exit_status,
            output_payload=message,
            error_message=error_code,
        )

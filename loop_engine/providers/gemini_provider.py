"""Canonical Gemini provider scaffold for Ten Shadows.

This adapter currently performs authorization/configuration checks and fails
closed. It does not perform a live Gemini generation call, so it must not report
empirical execution success.
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


class GeminiBuilderProvider(BaseWorkerProvider):
    """Fail-closed canonical adapter until a governed live invocation is implemented."""

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
            return self._failure(
                authorization,
                start_time,
                start_iso,
                "REJECTED",
                "Authorization token verification failed.",
                "AUTHORIZATION_TOKEN_INVALID",
            )

        if not workspace_matches_authorization(authorization, workspace_path):
            return self._failure(
                authorization,
                start_time,
                start_iso,
                "REJECTED",
                "Requested workspace does not match the authorized filesystem boundary.",
                "WORKSPACE_BOUNDARY_MISMATCH",
            )

        api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
        if not api_key:
            message = "Gemini API credentials are not configured."
        else:
            message = "Canonical Gemini live generation is not implemented in this provider path."

        return self._failure(
            authorization,
            start_time,
            start_iso,
            "FAILURE",
            message,
            "CAPABILITY_PROVIDER_UNAVAILABLE",
        )

    @staticmethod
    def _failure(
        authorization: WorkerAuthorization,
        start_time: float,
        start_iso: str,
        exit_status: str,
        message: str,
        error_code: str,
    ) -> WorkerExecutionResult:
        return WorkerExecutionResult(
            worker_id=authorization.worker_id,
            provider="gemini",
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

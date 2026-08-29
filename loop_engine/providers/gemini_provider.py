"""
loop_engine/providers/gemini_provider.py
Gemini Model Provider Adapter for 10 SHADOWS.
Fails closed with CAPABILITY_PROVIDER_UNAVAILABLE if API key is not configured.
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


class GeminiBuilderProvider(BaseWorkerProvider):
    """
    Gemini API builder adapter.
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
                provider="gemini",
                model=authorization.requested_model,
                role=WorkerRole.BUILDER,
                modality=EvidenceModality.EMPIRICAL,
                started_at=start_iso,
                ended_at=datetime.now(timezone.utc).isoformat(),
                duration_seconds=time.time() - start_time,
                exit_status="REJECTED",
                output_payload="Authorization token verification failed.",
                error_message="AUTHORIZATION_TOKEN_INVALID",
            )

        api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
        if not api_key:
            return WorkerExecutionResult(
                worker_id=authorization.worker_id,
                provider="gemini",
                model=authorization.requested_model,
                role=WorkerRole.BUILDER,
                modality=EvidenceModality.EMPIRICAL,
                started_at=start_iso,
                ended_at=datetime.now(timezone.utc).isoformat(),
                duration_seconds=time.time() - start_time,
                exit_status="FAILURE",
                output_payload="Gemini API key is not configured in environment.",
                error_message="CAPABILITY_PROVIDER_UNAVAILABLE",
            )

        # When API key exists, this executes empirical model generation
        # For current sandbox without live network credentials, fail closed cleanly
        return WorkerExecutionResult(
            worker_id=authorization.worker_id,
            provider="gemini",
            model=authorization.requested_model,
            role=WorkerRole.BUILDER,
            modality=EvidenceModality.EMPIRICAL,
            started_at=start_iso,
            ended_at=datetime.now(timezone.utc).isoformat(),
            duration_seconds=time.time() - start_time,
            exit_status="FAILURE",
            output_payload="Gemini API network call not enabled in sterile sandbox.",
            error_message="CAPABILITY_PROVIDER_UNAVAILABLE",
        )

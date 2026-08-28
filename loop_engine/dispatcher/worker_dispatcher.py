"""
worker_dispatcher.py — Autonomous Worker Dispatcher for 10 SHADOWS.
Bridges the Trusted Kernel and Model Providers across a language-neutral protocol boundary.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Optional, Type

# Ensure PROJECT_ROOT is on sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from loop_engine.dispatcher.protocol import (
    WorkerAuthorization,
    WorkerExecutionResult,
    WorkerEvidenceModality,
)
from loop_engine.dispatcher.providers.base import WorkerProviderAdapter
from loop_engine.dispatcher.providers.deterministic_provider import DeterministicWorkerAdapter
from loop_engine.dispatcher.providers.gemini_provider import GeminiWorkerAdapter
from loop_engine.harness.git_worktree import assert_not_authoritative_source


PROVIDER_REGISTRY: Dict[str, Type[WorkerProviderAdapter]] = {
    "deterministic": DeterministicWorkerAdapter,
    "gemini": GeminiWorkerAdapter,
}


def dispatch_worker(auth: WorkerAuthorization) -> WorkerExecutionResult:
    """
    Validates authorization, enforces workspace containment, and invokes provider adapter.
    """
    workspace_path = Path(auth.governed_workspace_path).resolve()
    
    # 1. Authoritative Source Protection Guard
    assert_not_authoritative_source(workspace_path, "worker_dispatch")

    # 2. Workspace Existence
    if not workspace_path.exists():
        now = datetime.now(timezone.utc).isoformat()
        return WorkerExecutionResult(
            protocol_version="1.0.0",
            run_id=auth.run_id,
            invocation_id=auth.invocation_id,
            worker_id=auth.worker_id,
            requested_provider=auth.requested_provider,
            requested_model=auth.requested_model,
            resolved_provider="dispatcher",
            resolved_model="UNPROVEN",
            started_at=now,
            ended_at=now,
            duration_seconds=0.001,
            exit_status="FAILURE",
            output_digest=hashlib.sha256(b"workspace_missing").hexdigest(),
            workspace_before_sha=auth.baseline_sha,
            workspace_after_sha=auth.baseline_sha,
            errors=[f"Governed workspace path does not exist: {workspace_path}"],
            completion_status="FAILED",
        )

    # 3. Token Verification
    if not auth.verify_token():
        now = datetime.now(timezone.utc).isoformat()
        return WorkerExecutionResult(
            protocol_version="1.0.0",
            run_id=auth.run_id,
            invocation_id=auth.invocation_id,
            worker_id=auth.worker_id,
            requested_provider=auth.requested_provider,
            requested_model=auth.requested_model,
            resolved_provider="dispatcher",
            resolved_model="UNPROVEN",
            started_at=now,
            ended_at=now,
            duration_seconds=0.001,
            exit_status="REJECTED",
            output_digest=hashlib.sha256(b"forged_authorization").hexdigest(),
            workspace_before_sha=auth.baseline_sha,
            workspace_after_sha=auth.baseline_sha,
            errors=["Security violation: Worker authorization token verification failed (forged or tampered authorization)."],
            completion_status="REJECTED",
        )

    # 4. Resolve Provider Adapter
    provider_cls = PROVIDER_REGISTRY.get(auth.requested_provider.lower())
    if not provider_cls:
        now = datetime.now(timezone.utc).isoformat()
        return WorkerExecutionResult(
            protocol_version="1.0.0",
            run_id=auth.run_id,
            invocation_id=auth.invocation_id,
            worker_id=auth.worker_id,
            requested_provider=auth.requested_provider,
            requested_model=auth.requested_model,
            resolved_provider="dispatcher",
            resolved_model="UNPROVEN",
            started_at=now,
            ended_at=now,
            duration_seconds=0.001,
            exit_status="FAILURE",
            output_digest=hashlib.sha256(b"unsupported_provider").hexdigest(),
            workspace_before_sha=auth.baseline_sha,
            workspace_after_sha=auth.baseline_sha,
            errors=[f"Requested provider '{auth.requested_provider}' is not registered with dispatcher."],
            completion_status="FAILED",
        )

    adapter = provider_cls()
    return adapter.execute(auth, workspace_path)


def main() -> int:
    parser = argparse.ArgumentParser(description="Ten Shadows Worker Dispatcher")
    parser.add_argument("--auth", required=True, help="Path to WorkerAuthorization JSON file")
    parser.add_argument("--output", required=True, help="Path to write WorkerExecutionResult JSON file")
    args = parser.parse_args()

    auth_path = Path(args.auth)
    out_path = Path(args.output)

    if not auth_path.exists():
        print(f"[DISPATCHER ERROR] Authorization file not found: {auth_path}", file=sys.stderr)
        return 1

    try:
        raw_auth = auth_path.read_text(encoding="utf-8")
        auth = WorkerAuthorization.model_validate_json(raw_auth)
    except Exception as e:
        print(f"[DISPATCHER ERROR] Invalid authorization JSON: {e}", file=sys.stderr)
        return 1

    result = dispatch_worker(auth)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(result.model_dump_json(indent=2), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())

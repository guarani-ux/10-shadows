"""Worker dispatcher for the Rust/Python protocol path.

The dispatcher validates the protocol binding digest, refuses the authoritative
repository as a worker workspace, requires the two declared workspace boundary
fields to resolve to the same location, and then invokes a provider adapter.

The current SHA-256 ``authorization_token`` is a tamper-detection binding digest,
not an unforgeable credential: all inputs needed to recompute it are present in
the authorization object. Do not treat token verification alone as a security
or privilege boundary.
"""

from __future__ import annotations

import argparse
import hashlib
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Type

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from loop_engine.dispatcher.protocol import WorkerAuthorization, WorkerExecutionResult
from loop_engine.dispatcher.providers.base import WorkerProviderAdapter
from loop_engine.dispatcher.providers.deterministic_provider import DeterministicWorkerAdapter
from loop_engine.dispatcher.providers.gemini_provider import GeminiWorkerAdapter
from loop_engine.dispatcher.providers.shadow_provider import ShadowDomainWorkerAdapter
from loop_engine.harness.git_worktree import assert_not_authoritative_source

PROVIDER_REGISTRY: Dict[str, Type[WorkerProviderAdapter]] = {
    "deterministic": DeterministicWorkerAdapter,
    "gemini": GeminiWorkerAdapter,
    "shadow": ShadowDomainWorkerAdapter,
    "forge": ShadowDomainWorkerAdapter,
    "alchemist": ShadowDomainWorkerAdapter,
    "svris": ShadowDomainWorkerAdapter,
    "scribe": ShadowDomainWorkerAdapter,
    "herald": ShadowDomainWorkerAdapter,
    "gamemaster": ShadowDomainWorkerAdapter,
}


def _failure(auth: WorkerAuthorization, message: str, *, rejected: bool = False) -> WorkerExecutionResult:
    now = datetime.now(timezone.utc).isoformat()
    marker = message.encode("utf-8", errors="replace")
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
        exit_status="REJECTED" if rejected else "FAILURE",
        output_digest=hashlib.sha256(marker).hexdigest(),
        workspace_before_sha=auth.baseline_sha,
        workspace_after_sha=auth.baseline_sha,
        errors=[message],
        completion_status="REJECTED" if rejected else "FAILED",
    )


def dispatch_worker(auth: WorkerAuthorization) -> WorkerExecutionResult:
    """Validate the declared execution envelope and invoke the requested adapter."""
    workspace_path = Path(auth.governed_workspace_path).resolve()
    filesystem_boundary = Path(auth.filesystem_boundary).resolve()

    if workspace_path != filesystem_boundary:
        return _failure(
            auth,
            "Workspace boundary mismatch: governed_workspace_path and filesystem_boundary resolve differently.",
            rejected=True,
        )

    try:
        assert_not_authoritative_source(workspace_path, "worker_dispatch")
    except Exception as exc:
        return _failure(auth, f"Authoritative source protection rejected workspace: {exc}", rejected=True)

    if not workspace_path.exists() or not workspace_path.is_dir():
        return _failure(auth, f"Governed workspace path does not exist: {workspace_path}")

    if not auth.verify_token():
        return _failure(
            auth,
            "Worker authorization binding digest does not match the declared invocation envelope.",
            rejected=True,
        )

    requested_provider = auth.requested_provider.lower()
    if requested_provider.startswith("shadow:"):
        provider_cls = ShadowDomainWorkerAdapter
    else:
        provider_cls = PROVIDER_REGISTRY.get(requested_provider)
    if not provider_cls:
        return _failure(auth, f"Requested provider '{auth.requested_provider}' is not registered with dispatcher.")

    adapter = provider_cls()
    return adapter.execute(auth, workspace_path)


def main() -> int:
    parser = argparse.ArgumentParser(description="Ten Shadows worker dispatcher")
    parser.add_argument("--auth", required=True, help="Path to WorkerAuthorization JSON file")
    parser.add_argument("--output", required=True, help="Path to write WorkerExecutionResult JSON file")
    args = parser.parse_args()

    auth_path = Path(args.auth)
    out_path = Path(args.output)

    if not auth_path.exists():
        print(f"[DISPATCHER ERROR] Authorization file not found: {auth_path}", file=sys.stderr)
        return 1

    try:
        auth = WorkerAuthorization.model_validate_json(auth_path.read_text(encoding="utf-8"))
    except Exception as exc:
        print(f"[DISPATCHER ERROR] Invalid authorization JSON: {exc}", file=sys.stderr)
        return 1

    result = dispatch_worker(auth)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(result.model_dump_json(indent=2), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())

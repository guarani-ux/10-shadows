"""
test_worker_dispatcher.py — Physical Unit & Adversarial Tests for Worker Dispatcher.
"""
from __future__ import annotations

import os
import subprocess
import tempfile
from datetime import datetime, timezone
from pathlib import Path
import pytest

from loop_engine.dispatcher.protocol import (
    WorkerAuthorization,
    WorkerExecutionResult,
    compute_authorization_token,
)
from loop_engine.dispatcher.worker_dispatcher import dispatch_worker
from loop_engine.harness.git_worktree import AuthoritativeSourceProtectionError, PROJECT_ROOT


@pytest.fixture
def disposable_workspace():
    """Creates a disposable git repository to serve as a governed workspace."""
    with tempfile.TemporaryDirectory() as tmpdir:
        ws_path = Path(tmpdir).resolve()
        subprocess.run(["git", "init"], cwd=str(ws_path), check=True, capture_output=True)
        subprocess.run(["git", "config", "user.name", "Test Worker"], cwd=str(ws_path), check=True, capture_output=True)
        subprocess.run(["git", "config", "user.email", "worker@ten-shadows.local"], cwd=str(ws_path), check=True, capture_output=True)

        readme = ws_path / "README.md"
        readme.write_text("# Initial Workspace\n", encoding="utf-8")
        subprocess.run(["git", "add", "README.md"], cwd=str(ws_path), check=True, capture_output=True)
        subprocess.run(["git", "commit", "-m", "chore: initial commit"], cwd=str(ws_path), check=True, capture_output=True)

        proc = subprocess.run(["git", "rev-parse", "HEAD"], cwd=str(ws_path), check=True, capture_output=True, text=True)
        baseline_sha = proc.stdout.strip()

        yield ws_path, baseline_sha


def test_deterministic_worker_dispatch_success(disposable_workspace):
    """Verifies that the deterministic provider successfully modifies the governed workspace."""
    ws_path, baseline_sha = disposable_workspace
    
    run_id = "run_test_001"
    task_id = "task_001"
    inv_id = "inv_001"
    obj = "Implement standard feature"
    obj_hash = "hash_001"
    now = datetime.now(timezone.utc).isoformat()
    
    token = compute_authorization_token(
        run_id=run_id,
        task_id=task_id,
        invocation_id=inv_id,
        objective_hash=obj_hash,
        baseline_sha=baseline_sha,
        governed_workspace_path=str(ws_path),
        attempt_number=1,
    )

    auth = WorkerAuthorization(
        run_id=run_id,
        task_id=task_id,
        invocation_id=inv_id,
        worker_id="forge_builder_001",
        objective=obj,
        objective_hash=obj_hash,
        baseline_sha=baseline_sha,
        governed_workspace_path=str(ws_path),
        governed_workspace_identity="ws_001",
        requested_provider="deterministic",
        requested_model="deterministic-v1",
        filesystem_boundary=str(ws_path),
        authorized_at=now,
        authorization_token=token,
    )

    result = dispatch_worker(auth)

    assert result.exit_status == "SUCCESS"
    assert result.resolved_provider == "deterministic_test_harness"
    assert result.resolved_model == "deterministic-v1"
    assert result.workspace_after_sha != baseline_sha
    assert (ws_path / "src" / "deterministic_feature.py").exists()
    assert len(result.files_changed) == 1


def test_tampered_authorization_token_rejected(disposable_workspace):
    """Verifies that forged or tampered authorization tokens are rejected by the dispatcher."""
    ws_path, baseline_sha = disposable_workspace
    now = datetime.now(timezone.utc).isoformat()

    auth = WorkerAuthorization(
        run_id="run_forged",
        task_id="task_forged",
        invocation_id="inv_forged",
        worker_id="forge_builder",
        objective="Tampered objective",
        objective_hash="hash_forged",
        baseline_sha=baseline_sha,
        governed_workspace_path=str(ws_path),
        governed_workspace_identity="ws_forged",
        requested_provider="deterministic",
        requested_model="deterministic-v1",
        filesystem_boundary=str(ws_path),
        authorized_at=now,
        authorization_token="FORGED_INVALID_TOKEN_123456",
    )

    result = dispatch_worker(auth)

    assert result.exit_status == "REJECTED"
    assert result.completion_status == "REJECTED"
    assert "Worker authorization token verification failed" in result.errors[0]
    assert result.workspace_after_sha == baseline_sha


def test_authoritative_root_as_workspace_rejected():
    """Verifies that attempting to target the authoritative root fails with AuthoritativeSourceProtectionError."""
    now = datetime.now(timezone.utc).isoformat()
    token = compute_authorization_token(
        run_id="run_root",
        task_id="task_root",
        invocation_id="inv_root",
        objective_hash="hash_root",
        baseline_sha="base_root",
        governed_workspace_path=str(PROJECT_ROOT),
        attempt_number=1,
    )

    auth = WorkerAuthorization(
        run_id="run_root",
        task_id="task_root",
        invocation_id="inv_root",
        worker_id="forge_builder",
        objective="Illegal root mutation",
        objective_hash="hash_root",
        baseline_sha="base_root",
        governed_workspace_path=str(PROJECT_ROOT),
        governed_workspace_identity="ws_root",
        requested_provider="deterministic",
        requested_model="deterministic-v1",
        filesystem_boundary=str(PROJECT_ROOT),
        authorized_at=now,
        authorization_token=token,
    )

    with pytest.raises(AuthoritativeSourceProtectionError):
        dispatch_worker(auth)


def test_gemini_missing_credentials_fails_closed(disposable_workspace, monkeypatch):
    """Verifies that missing GEMINI_API_KEY causes clean failure without model inference."""
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    
    ws_path, baseline_sha = disposable_workspace
    now = datetime.now(timezone.utc).isoformat()
    
    token = compute_authorization_token(
        run_id="run_gemini",
        task_id="task_gemini",
        invocation_id="inv_gemini",
        objective_hash="hash_gemini",
        baseline_sha=baseline_sha,
        governed_workspace_path=str(ws_path),
        attempt_number=1,
    )

    auth = WorkerAuthorization(
        run_id="run_gemini",
        task_id="task_gemini",
        invocation_id="inv_gemini",
        worker_id="forge_builder_gemini",
        objective="Perform Gemini task",
        objective_hash="hash_gemini",
        baseline_sha=baseline_sha,
        governed_workspace_path=str(ws_path),
        governed_workspace_identity="ws_gemini",
        requested_provider="gemini",
        requested_model="gemini-3.7-flash",
        filesystem_boundary=str(ws_path),
        authorized_at=now,
        authorization_token=token,
    )

    result = dispatch_worker(auth)

    assert result.exit_status == "FAILURE"
    assert result.resolved_model == "UNPROVEN"
    assert "GEMINI_API_KEY not configured in environment." in result.errors[0]
    assert result.workspace_after_sha == baseline_sha


def test_deterministic_repair_loop(disposable_workspace):
    """Verifies multi-attempt repair capability in deterministic provider."""
    ws_path, baseline_sha = disposable_workspace
    now = datetime.now(timezone.utc).isoformat()

    # Attempt 1: Deliberate failure
    token1 = compute_authorization_token("run_rep", "task_rep", "inv_rep_1", "hash_rep", baseline_sha, str(ws_path), 1)
    auth1 = WorkerAuthorization(
        run_id="run_rep",
        task_id="task_rep",
        invocation_id="inv_rep_1",
        worker_id="builder",
        objective="fail_attempt_1 and repair",
        objective_hash="hash_rep",
        baseline_sha=baseline_sha,
        governed_workspace_path=str(ws_path),
        governed_workspace_identity="ws_rep",
        requested_provider="deterministic",
        requested_model="deterministic-v1",
        filesystem_boundary=str(ws_path),
        attempt_number=1,
        authorized_at=now,
        authorization_token=token1,
    )
    res1 = dispatch_worker(auth1)
    assert "tests/test_deliberate_fail.py" in res1.files_changed

    # Attempt 2: Repaired!
    token2 = compute_authorization_token("run_rep", "task_rep", "inv_rep_2", "hash_rep", baseline_sha, str(ws_path), 2)
    auth2 = WorkerAuthorization(
        run_id="run_rep",
        task_id="task_rep",
        invocation_id="inv_rep_2",
        worker_id="builder",
        objective="fail_attempt_1 and repair",
        objective_hash="hash_rep",
        baseline_sha=baseline_sha,
        governed_workspace_path=str(ws_path),
        governed_workspace_identity="ws_rep",
        requested_provider="deterministic",
        requested_model="deterministic-v1",
        filesystem_boundary=str(ws_path),
        attempt_number=2,
        failure_evidence="pytest failure in tests/test_deliberate_fail.py",
        authorized_at=now,
        authorization_token=token2,
    )
    res2 = dispatch_worker(auth2)
    assert "src/repaired_module.py" in res2.files_changed
    assert not (ws_path / "tests" / "test_deliberate_fail.py").exists()

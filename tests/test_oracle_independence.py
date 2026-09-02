from __future__ import annotations

from pathlib import Path

from loop_engine.dispatcher.protocol import WorkerAuthorization, compute_authorization_token
from loop_engine.providers.deterministic_provider import DeterministicBuilderProvider


def _authorization(workspace: Path) -> WorkerAuthorization:
    token = compute_authorization_token(
        run_id="run_oracle_independence",
        task_id="task_oracle_independence",
        invocation_id="inv_oracle_independence",
        objective_hash="0" * 64,
        baseline_sha="UNKNOWN",
        governed_workspace_path=str(workspace),
        attempt_number=1,
    )
    return WorkerAuthorization(
        run_id="run_oracle_independence",
        task_id="task_oracle_independence",
        invocation_id="inv_oracle_independence",
        worker_id="builder_oracle_independence",
        worker_role="Builder",
        objective="Create a Python function that converts Celsius to Fahrenheit",
        objective_hash="0" * 64,
        baseline_sha="UNKNOWN",
        governed_workspace_path=str(workspace),
        governed_workspace_identity="oracle_independence_ws",
        requested_provider="deterministic",
        requested_model="standard",
        allowed_capabilities=[],
        filesystem_boundary=str(workspace),
        attempt_number=1,
        authorized_at="2026-08-29T00:00:00Z",
        authorization_token=token,
    )


def test_builder_cannot_supply_its_own_verification_oracle(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()

    result = DeterministicBuilderProvider().execute(
        _authorization(workspace),
        "Create a Python function that converts Celsius to Fahrenheit",
        workspace,
        [],
    )

    assert result.exit_status == "SUCCESS"
    assert (workspace / "temperature.py").is_file()
    assert not (workspace / "tests").exists()

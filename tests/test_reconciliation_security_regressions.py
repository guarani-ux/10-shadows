from __future__ import annotations

import hashlib
import inspect
from pathlib import Path

from loop_engine.capability_registry import CapabilityRegistry
from loop_engine.dispatcher.protocol import WorkerAuthorization, compute_authorization_token
from loop_engine.execution_authority import EvidenceModality
from loop_engine.orchestrator import TenShadowsOrchestrator
from loop_engine.providers.antigravity_provider import AntigravityBuilderProvider
from loop_engine.providers.deterministic_provider import DeterministicBuilderProvider


def _authorization(workspace: Path, *, provider: str = "deterministic") -> WorkerAuthorization:
    token = compute_authorization_token(
        run_id="run_reconcile",
        task_id="task_reconcile",
        invocation_id="inv_reconcile",
        objective_hash="0" * 64,
        baseline_sha="UNKNOWN",
        governed_workspace_path=str(workspace),
        attempt_number=1,
    )
    return WorkerAuthorization(
        run_id="run_reconcile",
        task_id="task_reconcile",
        invocation_id="inv_reconcile",
        worker_id="builder_reconcile",
        worker_role="Builder",
        objective="Create a Python function that converts Celsius to Fahrenheit",
        objective_hash="0" * 64,
        baseline_sha="UNKNOWN",
        governed_workspace_path=str(workspace),
        governed_workspace_identity="reconcile_ws",
        requested_provider=provider,
        requested_model="standard",
        allowed_capabilities=[],
        filesystem_boundary=str(workspace),
        attempt_number=1,
        authorized_at="2026-08-29T00:00:00Z",
        authorization_token=token,
    )


def test_provider_rejects_valid_token_replayed_against_different_workspace(tmp_path: Path) -> None:
    authorized = tmp_path / "authorized"
    unauthorized = tmp_path / "outside"
    authorized.mkdir()
    unauthorized.mkdir()

    result = DeterministicBuilderProvider().execute(
        _authorization(authorized),
        "Create a Python function that converts Celsius to Fahrenheit",
        unauthorized,
        [],
    )

    assert result.exit_status == "REJECTED"
    assert result.error_message == "WORKSPACE_BOUNDARY_MISMATCH"
    assert not (unauthorized / "temperature.py").exists()


def test_antigravity_configuration_alone_cannot_fabricate_success(tmp_path: Path, monkeypatch) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    monkeypatch.setenv("ANTIGRAVITY_CLI", "configured-but-not-invoked")

    result = AntigravityBuilderProvider().execute(
        _authorization(workspace, provider="antigravity"),
        "Do arbitrary work",
        workspace,
        [],
    )

    assert result.exit_status == "FAILURE"
    assert result.error_message == "CAPABILITY_PROVIDER_UNAVAILABLE"
    assert result.modality == EvidenceModality.STRUCTURAL


def test_reregistering_qualified_identifier_resets_authority(tmp_path: Path) -> None:
    registry = CapabilityRegistry(db_path=tmp_path / "caps.db")
    artifact = tmp_path / "cap.py"
    artifact.write_text("VALUE = 1\n", encoding="utf-8")
    digest = hashlib.sha256(artifact.read_bytes()).hexdigest()

    registry.register_candidate(
        capability_id="cap_reuse",
        name="Reusable",
        originating_run_id="run_one",
        declared_purpose="test reuse",
        artifact_paths=["cap.py"],
        artifact_hashes={"cap.py": digest},
        applicability_constraints=["reuse"],
    )
    registry.qualify_capability(
        capability_id="cap_reuse",
        verifier_id="verifier_one",
        verification_record={
            "verified_status": "PASS",
            "exit_code": 0,
            "tests_passed": 1,
            "tests_failed": 0,
            "falsification_attempted": True,
            "verifier_id": "verifier_one",
            "builder_id": "builder_one",
            "verifier_type": "INDEPENDENT_BEHAVIORAL_ORACLE",
        },
        base_dir=tmp_path,
    )
    assert registry.get_capability("cap_reuse").epistemic_status == "QUALIFIED"

    artifact.write_text("VALUE = 2\n", encoding="utf-8")
    new_digest = hashlib.sha256(artifact.read_bytes()).hexdigest()
    registry.register_candidate(
        capability_id="cap_reuse",
        name="Reusable changed",
        originating_run_id="run_two",
        declared_purpose="changed candidate",
        artifact_paths=["cap.py"],
        artifact_hashes={"cap.py": new_digest},
        applicability_constraints=["reuse"],
    )

    stored = registry.get_capability("cap_reuse")
    assert stored is not None
    assert stored.epistemic_status == "UNQUALIFIED"
    assert stored.qualification_evidence == {}


def test_programmatic_orchestrator_is_non_promoting_by_default() -> None:
    parameter = inspect.signature(TenShadowsOrchestrator.run_objective).parameters["no_promote"]
    assert parameter.default is True

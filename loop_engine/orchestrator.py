"""Current canonical Ten Shadows governed-execution orchestrator.

This module coordinates a kernel-established run, an authorized worker adapter,
physical workspace observation, independent deterministic verification, optional
capability qualification, optional target promotion, and receipt sealing.

Scope limits are deliberate:
- the governed workspace is a Ten Shadows staging boundary, not an OS sandbox;
- only the deterministic verifier path is implemented here;
- target promotion is opt-in and is not described as atomic Git promotion;
- behavioral verification is not semantic proof that an open-ended objective was
  fully satisfied.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from loop_engine.capability_registry import CapabilityRecord, CapabilityRegistry
from loop_engine.config import PROJECT_ROOT, RECEIPTS_DIR, SCRATCH_DIR
from loop_engine.context import resolve_physical_commit_sha
from loop_engine.dispatcher.protocol import WorkerAuthorization, compute_authorization_token
from loop_engine.dispatcher.protocol import WorkerRole as ProtocolWorkerRole
from loop_engine.errors import ConfigurationError
from loop_engine.execution_authority import (
    EvidenceModality,
    EvidencePurpose,
    ExecutionAttemptRecord,
    IndependentVerificationRecord,
    RunStatus,
    TenShadowsKernel,
    VerificationType,
    WorkerInvocationRecord,
    verify_execution_receipt,
)
from loop_engine.kernel_db import KernelDatabase
from loop_engine.observability import get_logger
from loop_engine.providers.antigravity_provider import AntigravityBuilderProvider
from loop_engine.providers.base import BaseWorkerProvider, WorkerExecutionResult
from loop_engine.providers.deterministic_provider import DeterministicBuilderProvider
from loop_engine.providers.gemini_provider import GeminiBuilderProvider

logger = get_logger("Orchestrator")


@dataclass
class OrchestratorExecutionReport:
    run_id: str
    task_id: str
    status: str
    objective_status: str
    routing_strategy: str
    capabilities_used: List[str]
    capabilities_created: List[str]
    capabilities_qualified: List[str]
    verification_status: str
    receipt_path: Optional[str]
    receipt_valid: bool
    final_head: Optional[str]
    error_message: Optional[str] = None
    details: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    def print_summary(self) -> None:
        print("=" * 60)
        print("10 SHADOWS - GOVERNED EXECUTION RECEIPT SUMMARY")
        print("=" * 60)
        print(f"RUN_ID:                 {self.run_id}")
        print(f"STATUS:                 {self.status}")
        print(f"OBJECTIVE_STATUS:       {self.objective_status}")
        print(f"CAPABILITIES_USED:      {', '.join(self.capabilities_used) or 'NONE'}")
        print(f"CAPABILITIES_CREATED:   {', '.join(self.capabilities_created) or 'NONE'}")
        print(f"CAPABILITIES_QUALIFIED: {', '.join(self.capabilities_qualified) or 'NONE'}")
        print(f"VERIFICATION_STATUS:    {self.verification_status}")
        print(f"RECEIPT_PATH:           {self.receipt_path or 'NONE'}")
        print(f"RECEIPT_VALID:          {'TRUE' if self.receipt_valid else 'FALSE'}")
        if self.error_message:
            print(f"ERROR:                  {self.error_message}")
        print("=" * 60)


class TenShadowsOrchestrator:
    """Coordinate the currently implemented governed execution path."""

    def __init__(
        self,
        kernel: Optional[TenShadowsKernel] = None,
        registry: Optional[CapabilityRegistry] = None,
        kernel_db: Optional[KernelDatabase] = None,
        receipts_dir: Optional[Path] = None,
    ) -> None:
        self.db = kernel_db or KernelDatabase()
        self.receipts_dir = receipts_dir or RECEIPTS_DIR
        self.kernel = kernel or TenShadowsKernel(kernel_db=self.db, receipts_dir=self.receipts_dir)
        self.registry = registry or CapabilityRegistry()

    def _resolve_provider(self, provider_name: str) -> BaseWorkerProvider:
        normalized = provider_name.strip().lower()
        if normalized in {"deterministic", "local"}:
            return DeterministicBuilderProvider()
        if normalized in {"gemini", "google"}:
            return GeminiBuilderProvider()
        if normalized in {"antigravity", "agy"}:
            return AntigravityBuilderProvider()
        raise ConfigurationError(f"Unknown provider '{provider_name}'")

    @staticmethod
    def _take_fs_snapshot(directory: Path) -> Dict[str, str]:
        """Map observed workspace-relative files to SHA-256 hashes."""
        snapshot: Dict[str, str] = {}
        if not directory.exists():
            return snapshot
        for root, dirs, files in os.walk(directory):
            dirs[:] = [
                name
                for name in dirs
                if name not in {".git", "__pycache__", ".pytest_cache", "scratch", "sandbox"}
            ]
            for filename in files:
                if filename.endswith((".pyc", ".tmp")):
                    continue
                file_path = Path(root) / filename
                try:
                    rel_path = str(file_path.relative_to(directory)).replace("\\", "/")
                    snapshot[rel_path] = hashlib.sha256(file_path.read_bytes()).hexdigest()
                except OSError:
                    continue
        return snapshot

    @staticmethod
    def _capability_materializable(capability: CapabilityRecord, target: Path) -> bool:
        """Require every registered artifact to exist at the target with its qualified hash."""
        if not capability.artifact_paths:
            return False
        for rel_path in capability.artifact_paths:
            source = target / rel_path
            expected_hash = capability.artifact_hashes.get(rel_path)
            if not source.is_file() or not expected_hash or expected_hash == "UNKNOWN":
                return False
            try:
                actual_hash = hashlib.sha256(source.read_bytes()).hexdigest()
            except OSError:
                return False
            if actual_hash != expected_hash:
                return False
        return True

    def run_objective(
        self,
        objective: str,
        target_path: Optional[Union[str, Path]] = None,
        task_id: Optional[str] = None,
        domain_code: str = "general_engineering",
        builder_provider: str = "deterministic",
        verifier_provider: str = "deterministic",
        max_attempts: int = 3,
        no_promote: bool = True,
    ) -> OrchestratorExecutionReport:
        """Execute one objective. Target mutation is disabled unless explicitly requested."""
        target = Path(target_path or PROJECT_ROOT).resolve()
        start_time = time.time()

        if not objective or not objective.strip():
            raise ConfigurationError("Objective string cannot be empty.")
        if not 1 <= max_attempts <= 3:
            raise ConfigurationError("max_attempts must be between 1 and 3")
        if verifier_provider.strip().lower() not in {"deterministic", "local"}:
            raise ConfigurationError(
                "Only the deterministic verifier path is implemented in the canonical orchestrator."
            )
        if not target.exists() or not target.is_dir():
            raise ConfigurationError(f"Target directory does not exist: {target}")

        clean_objective = objective.strip()
        run_ctx = self.kernel.establish_run(
            objective=clean_objective,
            target_path=target,
            task_id=task_id,
            domain_code=domain_code,
        )
        logger.emit("RUN_ESTABLISHED", run_id=run_ctx.run_id, task_id=run_ctx.task_id)

        registry_matches = self.registry.find_reusable_capabilities(clean_objective, only_qualified=True)
        available_caps = [cap for cap in registry_matches if self._capability_materializable(cap, target)]
        caps_used_ids = [cap.capability_id for cap in available_caps]
        if len(available_caps) != len(registry_matches):
            logger.emit(
                "STALE_CAPABILITIES_EXCLUDED",
                run_id=run_ctx.run_id,
                count=len(registry_matches) - len(available_caps),
            )

        routing_strategy, required_caps, route_digest = self.kernel.determine_route(
            run_ctx=run_ctx,
            objective=clean_objective,
        )

        starting_head = resolve_physical_commit_sha(target)
        workspace_root = (SCRATCH_DIR / "workspaces").resolve()
        workspace_root.mkdir(parents=True, exist_ok=True)
        workspace_dir = (workspace_root / run_ctx.run_id).resolve()
        if workspace_dir.parent != workspace_root:
            raise ConfigurationError("Governed workspace escaped configured workspace root")
        workspace_dir.mkdir(parents=False, exist_ok=False)

        for cap in available_caps:
            for rel_path in cap.artifact_paths:
                source = target / rel_path
                destination = workspace_dir / rel_path
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source, destination)

        lease_file = SCRATCH_DIR / "active_run_lease.json"
        lease_payload = {
            "run_id": run_ctx.run_id,
            "task_id": run_ctx.task_id,
            "workspace_path": str(workspace_dir),
            "token": compute_authorization_token(
                run_id=run_ctx.run_id,
                task_id=run_ctx.task_id,
                invocation_id="master_lease",
                objective_hash=run_ctx.objective_hash,
                baseline_sha=starting_head or "UNKNOWN_NON_GIT_TARGET",
                governed_workspace_path=str(workspace_dir),
                attempt_number=0,
            ),
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        lease_file.write_text(json.dumps(lease_payload, indent=2), encoding="utf-8")

        builder = self._resolve_provider(builder_provider)
        attempt_records: List[ExecutionAttemptRecord] = []
        invocation_records: List[WorkerInvocationRecord] = []
        all_created_caps: List[str] = []
        all_qualified_caps: List[str] = []
        last_verification: Optional[IndependentVerificationRecord] = None
        last_worker_error: Optional[str] = None
        is_success = False
        snapshot_after: Dict[str, str] = self._take_fs_snapshot(workspace_dir)
        files_deleted: List[str] = []

        try:
            for attempt_number in range(1, max_attempts + 1):
                snapshot_before = self._take_fs_snapshot(workspace_dir)
                worker_id = f"{builder_provider}_builder_{run_ctx.task_id}_{attempt_number}"
                invocation_id = f"inv_{run_ctx.task_id}_{attempt_number}"
                auth_token = compute_authorization_token(
                    run_id=run_ctx.run_id,
                    task_id=run_ctx.task_id,
                    invocation_id=invocation_id,
                    objective_hash=run_ctx.objective_hash,
                    baseline_sha=starting_head or "UNKNOWN",
                    governed_workspace_path=str(workspace_dir),
                    attempt_number=attempt_number,
                )
                authorization = WorkerAuthorization(
                    run_id=run_ctx.run_id,
                    task_id=run_ctx.task_id,
                    invocation_id=invocation_id,
                    worker_id=worker_id,
                    worker_role=ProtocolWorkerRole.BUILDER,
                    objective=clean_objective,
                    objective_hash=run_ctx.objective_hash,
                    baseline_sha=starting_head or "UNKNOWN",
                    governed_workspace_path=str(workspace_dir),
                    governed_workspace_identity=run_ctx.run_id,
                    requested_provider=builder_provider,
                    requested_model="standard",
                    allowed_capabilities=required_caps,
                    filesystem_boundary=str(workspace_dir),
                    attempt_number=attempt_number,
                    authorized_at=datetime.now(timezone.utc).isoformat(),
                    authorization_token=auth_token,
                )

                worker_result: WorkerExecutionResult = builder.execute(
                    authorization=authorization,
                    objective=clean_objective,
                    workspace_path=workspace_dir,
                    available_capabilities=[cap.to_dict() for cap in available_caps],
                    attempt_number=attempt_number,
                )
                last_worker_error = worker_result.error_message
                snapshot_after = self._take_fs_snapshot(workspace_dir)
                files_deleted = [path for path in snapshot_before if path not in snapshot_after]

                invocation = self.kernel.record_worker_invocation(
                    run_ctx=run_ctx,
                    worker_id=worker_id,
                    provider=worker_result.provider,
                    model=worker_result.model,
                    role=worker_result.role,
                    input_payload=clean_objective,
                    output_payload=worker_result.output_payload,
                    duration_seconds=worker_result.duration_seconds,
                    modality=worker_result.modality,
                    provider_receipt=worker_result.provider_receipt,
                )
                invocation_records.append(invocation)

                attempt_candidate_ids: List[str] = []
                for candidate in worker_result.candidate_capabilities:
                    candidate_id = candidate["capability_id"]
                    attempt_candidate_ids.append(candidate_id)
                    all_created_caps.append(candidate_id)
                    artifact_hashes = {
                        path: snapshot_after.get(path, "UNKNOWN")
                        for path in candidate.get("artifact_paths", [])
                    }
                    self.registry.register_candidate(
                        capability_id=candidate_id,
                        name=candidate.get("name", candidate_id),
                        originating_run_id=run_ctx.run_id,
                        declared_purpose=candidate.get("declared_purpose", clean_objective),
                        artifact_paths=candidate.get("artifact_paths", []),
                        artifact_hashes=artifact_hashes,
                        dependencies=candidate.get("dependencies", []),
                        applicability_constraints=candidate.get("applicability_constraints", []),
                    )

                verifier_id = f"independent_verifier_{run_ctx.task_id}_{attempt_number}"
                if worker_result.exit_status != "SUCCESS":
                    verification = IndependentVerificationRecord(
                        verifier_id=verifier_id,
                        verifier_type=VerificationType.INDEPENDENT_BEHAVIORAL_ORACLE,
                        builder_id=worker_id,
                        modality=EvidenceModality.DETERMINISTIC_TEST,
                        purpose=EvidencePurpose.BEHAVIORAL_VERIFICATION,
                        test_digest=hashlib.sha256(worker_result.output_payload.encode("utf-8")).hexdigest(),
                        tests_collected=0,
                        tests_passed=0,
                        tests_failed=1,
                        exit_code=1,
                        duration_seconds=0.001,
                        falsification_attempted=True,
                        verified_status="FAIL",
                        execution_trace=worker_result.output_payload,
                    )
                else:
                    verification = self.kernel.execute_independent_verification(
                        run_ctx=run_ctx,
                        target_path=workspace_dir,
                        builder_id=worker_id,
                        test_cwd=workspace_dir,
                        verifier_type=VerificationType.INDEPENDENT_BEHAVIORAL_ORACLE,
                    )
                last_verification = verification

                passed = verification.verified_status == "PASS" and verification.exit_code == 0
                if passed and files_deleted and not no_promote:
                    passed = False
                    verification = IndependentVerificationRecord(
                        verifier_id=verifier_id,
                        verifier_type=VerificationType.INDEPENDENT_BEHAVIORAL_ORACLE,
                        builder_id=worker_id,
                        modality=EvidenceModality.DETERMINISTIC_TEST,
                        purpose=EvidencePurpose.BEHAVIORAL_VERIFICATION,
                        test_digest=verification.test_digest,
                        tests_collected=verification.tests_collected,
                        tests_passed=verification.tests_passed,
                        tests_failed=max(1, verification.tests_failed),
                        exit_code=1,
                        duration_seconds=verification.duration_seconds,
                        falsification_attempted=True,
                        verified_status="FAIL",
                        execution_trace="Promotion rejected: canonical copy promotion does not support deletion semantics.",
                    )
                    last_verification = verification

                attempt_records.append(
                    ExecutionAttemptRecord(
                        attempt_number=attempt_number,
                        started_at=worker_result.started_at,
                        ended_at=worker_result.ended_at,
                        duration_seconds=worker_result.duration_seconds,
                        worker_invocations=[invocation],
                        artifacts_staged=[{"path": path, "sha256": digest} for path, digest in snapshot_after.items()],
                        verification=verification,
                        promotion_decision=(
                            "PROMOTION_ELIGIBLE"
                            if passed and not no_promote
                            else ("SKIPPED_NO_PROMOTE" if passed else "REJECTED")
                        ),
                        status="COMPLETED" if passed else "FAILED",
                        rejection_reason=None if passed else verification.execution_trace,
                    )
                )

                if passed:
                    is_success = True
                    for candidate_id in attempt_candidate_ids:
                        try:
                            self.registry.qualify_capability(
                                capability_id=candidate_id,
                                verifier_id=verifier_id,
                                verification_record=verification.model_dump(),
                                base_dir=workspace_dir,
                            )
                            all_qualified_caps.append(candidate_id)
                        except Exception as exc:
                            logger.emit(
                                "CAPABILITY_QUALIFICATION_FAILED",
                                capability_id=candidate_id,
                                error=str(exc),
                            )
                    break
        finally:
            if lease_file.exists():
                try:
                    lease_file.unlink()
                except OSError:
                    pass

        final_head = starting_head
        if is_success and not no_promote:
            for rel_path in snapshot_after:
                source = workspace_dir / rel_path
                destination = target / rel_path
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source, destination)
            final_head = resolve_physical_commit_sha(target)
            promotion_payload: Dict[str, Any] = {
                "status": "PROMOTED",
                "promotion_type": "VERIFIED_COPY",
                "promoted_at": datetime.now(timezone.utc).isoformat(),
                "files_promoted": list(snapshot_after.keys()),
                "deletions_supported": False,
            }
        elif is_success:
            promotion_payload = {"status": "SKIPPED_NO_PROMOTE", "promoted_at": None}
        else:
            promotion_payload = {"status": "REJECTED", "promoted_at": None}

        if is_success:
            final_status = RunStatus.VERIFIED_SUCCESS
            objective_status = "BEHAVIORALLY_VERIFIED"
        elif last_worker_error == "CAPABILITY_DEFICIT":
            final_status = RunStatus.BLOCKED
            objective_status = "CAPABILITY_DEFICIT"
        elif last_worker_error == "CAPABILITY_PROVIDER_UNAVAILABLE":
            final_status = RunStatus.BLOCKED
            objective_status = "PROVIDER_UNAVAILABLE"
        else:
            final_status = RunStatus.FAILED
            objective_status = "OBJECTIVE_UNRESOLVED"

        artifacts_produced = [{"path": path, "sha256": digest} for path, digest in snapshot_after.items()]
        self.kernel.seal_and_persist_receipt(
            run_ctx=run_ctx,
            objective=clean_objective,
            target_path=target,
            starting_head=starting_head,
            final_head=final_head,
            routing_strategy=routing_strategy,
            routing_decision_digest=route_digest,
            capabilities_selected=required_caps,
            attempts=attempt_records,
            worker_invocations=invocation_records,
            artifacts_produced=artifacts_produced,
            verification=last_verification,
            promotion=promotion_payload,
            final_status=final_status,
        )

        receipt_path = self.receipts_dir / f"{run_ctx.run_id}_receipt.json"
        receipt_valid = False
        if receipt_path.exists():
            valid, errors = verify_execution_receipt(receipt_path, kernel_db=self.db)
            receipt_valid = valid and not errors

        return OrchestratorExecutionReport(
            run_id=run_ctx.run_id,
            task_id=run_ctx.task_id,
            status=final_status.value,
            objective_status=objective_status,
            routing_strategy=routing_strategy.value,
            capabilities_used=caps_used_ids,
            capabilities_created=list(dict.fromkeys(all_created_caps)),
            capabilities_qualified=list(dict.fromkeys(all_qualified_caps)),
            verification_status="PASS" if is_success else "FAIL",
            receipt_path=str(receipt_path) if receipt_path.exists() else None,
            receipt_valid=receipt_valid,
            final_head=final_head,
            error_message=(
                None
                if is_success
                else (last_verification.execution_trace if last_verification else last_worker_error or "Execution failed")
            ),
            details={
                "attempts": len(attempt_records),
                "artifacts_produced": len(artifacts_produced),
                "promotion": promotion_payload["status"],
                "duration_seconds": round(time.time() - start_time, 3),
            },
        )

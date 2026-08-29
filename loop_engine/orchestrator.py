"""
loop_engine/orchestrator.py
Deterministic Master Orchestrator for 10 SHADOWS.

Invariants:
1. The AI model / agent is NEVER responsible for deciding whether Ten Shadows is used.
2. The model NEVER receives raw objectives before kernel.establish_run has succeeded.
3. Success, qualification, capability registration, and promotion are determined exclusively by kernel state.
4. If no valid kernel receipt is sealed and verified, the execution is declared FAILED.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple, Union

from loop_engine.capability_registry import CapabilityRecord, CapabilityRegistry
from loop_engine.config import PROJECT_ROOT, RECEIPTS_DIR, SCRATCH_DIR
from loop_engine.context import RunContext, resolve_physical_commit_sha
from loop_engine.dispatcher.protocol import (
    WorkerAuthorization,
    compute_authorization_token,
)
from loop_engine.dispatcher.protocol import (
    WorkerRole as ProtocolWorkerRole,
)
from loop_engine.errors import (
    AuthorityError,
    CapabilityDeficitError,
    ConfigurationError,
    ExecutionError,
    PreflightCheckError,
    TenShadowsError,
)
from loop_engine.execution_authority import (
    DisaggregatedEpistemicClaims,
    EvidenceModality,
    EvidencePurpose,
    ExecutionAttemptRecord,
    IndependentVerificationRecord,
    RoutingStrategy,
    RunStatus,
    TenShadowsKernel,
    TenShadowsReceipt,
    VerificationType,
    WorkerInvocationRecord,
    WorkerRole,
    verify_execution_receipt,
)
from loop_engine.harness.git_worktree import GitWorktreeHarness
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
        print("10 SHADOWS — CANONICAL EXECUTION RECEIPT SUMMARY")
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
    """
    The Single Invertible Master Orchestrator for 10 SHADOWS.
    """

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
        p_name = provider_name.strip().lower()
        if p_name in ["deterministic", "local"]:
            return DeterministicBuilderProvider()
        elif p_name in ["gemini", "google"]:
            return GeminiBuilderProvider()
        elif p_name in ["antigravity", "agy"]:
            return AntigravityBuilderProvider()
        else:
            raise ConfigurationError(f"Unknown provider '{provider_name}'")

    def _take_fs_snapshot(self, directory: Path) -> Dict[str, str]:
        """Scans directory and maps relative path to SHA-256 content hash."""
        snapshot = {}
        if not directory.exists():
            return snapshot
        for root, dirs, files in os.walk(directory):
            # Ignore git internals, pycache, temporary dirs
            dirs[:] = [d for d in dirs if d not in [".git", "__pycache__", ".pytest_cache", "scratch", "sandbox"]]
            for file in files:
                if file.endswith(".pyc") or file.endswith(".tmp"):
                    continue
                file_path = Path(root) / file
                try:
                    rel_path = str(file_path.relative_to(directory)).replace("\\", "/")
                    snapshot[rel_path] = hashlib.sha256(file_path.read_bytes()).hexdigest()
                except Exception:
                    pass
        return snapshot

    def run_objective(
        self,
        objective: str,
        target_path: Optional[Union[str, Path]] = None,
        task_id: Optional[str] = None,
        domain_code: str = "general_engineering",
        builder_provider: str = "deterministic",
        verifier_provider: str = "deterministic",
        max_attempts: int = 3,
        no_promote: bool = False,
    ) -> OrchestratorExecutionReport:
        """
        Executes an objective through the mandatory 20-step Ten Shadows Kernel sequence.
        """
        target = Path(target_path or PROJECT_ROOT).resolve()
        start_time = time.time()

        # Step 1: Accept Objective
        if not objective or not objective.strip():
            raise ConfigurationError("Objective string cannot be empty.")
        clean_objective = objective.strip()

        # Step 2: Establish Kernel Run (MANDATORY BEFORE ANY WORKER IS CALLED)
        run_ctx = self.kernel.establish_run(
            objective=clean_objective,
            target_path=target,
            task_id=task_id,
            domain_code=domain_code,
        )
        logger.emit("RUN_ESTABLISHED", run_id=run_ctx.run_id, task_id=run_ctx.task_id)

        # Step 3: Query Persistent Capability Registry for Reusable Matches
        available_caps = self.registry.find_reusable_capabilities(clean_objective, only_qualified=True)
        caps_used_ids = [c.capability_id for c in available_caps]
        if available_caps:
            logger.emit(
                "CAPABILITIES_RETRIEVED",
                run_id=run_ctx.run_id,
                count=len(available_caps),
                capabilities=caps_used_ids,
            )

        # Step 4: Determine Route & Strategy
        routing_strategy, required_caps, route_digest = self.kernel.determine_route(
            run_ctx=run_ctx, objective=clean_objective
        )
        logger.emit(
            "ROUTE_DETERMINED",
            run_id=run_ctx.run_id,
            strategy=routing_strategy.value,
            capabilities=required_caps,
        )

        # Step 5: Create Governed Workspace (Isolated Ephemeral Worktree or Temp Sandbox)
        starting_head = resolve_physical_commit_sha(target)
        workspace_dir = SCRATCH_DIR / "workspaces" / f"governed_{run_ctx.task_id}"
        workspace_dir.mkdir(parents=True, exist_ok=True)

        # If target has reusable capabilities, copy them into the workspace
        for cap in available_caps:
            for rel_path in cap.artifact_paths:
                source_file = target / rel_path
                if source_file.exists():
                    dest_file = workspace_dir / rel_path
                    dest_file.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(source_file, dest_file)

        # Step 6: Initialize Loop State
        builder = self._resolve_provider(builder_provider)
        attempts_records: List[ExecutionAttemptRecord] = []
        invocations_records: List[WorkerInvocationRecord] = []
        all_created_caps: List[str] = []
        all_qualified_caps: List[str] = []
        last_verification: Optional[IndependentVerificationRecord] = None
        is_success = False
        attempt_number = 1

        # Step 7: Attempt & Repair Loop (Up to max_attempts)
        while attempt_number <= max_attempts and not is_success:
            logger.emit(
                "ATTEMPT_STARTED",
                run_id=run_ctx.run_id,
                attempt=attempt_number,
                max_attempts=max_attempts,
            )

            # Issue Cryptographic Authorization Token
            worker_id = f"{builder_provider}_builder_{run_ctx.task_id}_{attempt_number}"
            auth_token = compute_authorization_token(
                run_id=run_ctx.run_id,
                task_id=run_ctx.task_id,
                invocation_id=f"inv_{run_ctx.task_id}_{attempt_number}",
                objective_hash=run_ctx.objective_hash,
                baseline_sha=starting_head or "UNKNOWN",
                governed_workspace_path=str(workspace_dir),
                attempt_number=attempt_number,
            )

            authorization = WorkerAuthorization(
                run_id=run_ctx.run_id,
                task_id=run_ctx.task_id,
                invocation_id=f"inv_{run_ctx.task_id}_{attempt_number}",
                worker_id=worker_id,
                worker_role=ProtocolWorkerRole.BUILDER,
                objective=clean_objective,
                objective_hash=run_ctx.objective_hash,
                baseline_sha=starting_head or "UNKNOWN",
                governed_workspace_path=str(workspace_dir),
                governed_workspace_identity=f"governed_{run_ctx.task_id}",
                requested_provider=builder_provider,
                requested_model="standard",
                allowed_capabilities=required_caps,
                filesystem_boundary=str(workspace_dir),
                attempt_number=attempt_number,
                authorized_at=datetime.now(timezone.utc).isoformat(),
                authorization_token=auth_token,
            )

            # Pre-execution physical snapshot
            snapshot_before = self._take_fs_snapshot(workspace_dir)

            # Invoke Builder Adapter
            worker_res: WorkerExecutionResult = builder.execute(
                authorization=authorization,
                objective=clean_objective,
                workspace_path=workspace_dir,
                available_capabilities=[c.to_dict() for c in available_caps],
                attempt_number=attempt_number,
            )

            # Post-execution physical snapshot & diff calculation
            snapshot_after = self._take_fs_snapshot(workspace_dir)
            files_created = [f for f in snapshot_after if f not in snapshot_before]
            files_modified = [
                f for f in snapshot_after if f in snapshot_before and snapshot_after[f] != snapshot_before[f]
            ]
            files_deleted = [f for f in snapshot_before if f not in snapshot_after]

            # Record Invocation Record
            inv_rec = self.kernel.record_worker_invocation(
                run_ctx=run_ctx,
                worker_id=worker_id,
                provider=worker_res.provider,
                model=worker_res.model,
                role=worker_res.role,
                input_payload=clean_objective,
                output_payload=worker_res.output_payload,
                duration_seconds=worker_res.duration_seconds,
                modality=worker_res.modality,
                provider_receipt=worker_res.provider_receipt,
            )
            invocations_records.append(inv_rec)

            # Register Candidate Capabilities (Strictly UNQUALIFIED initially)
            for cand in worker_res.candidate_capabilities:
                cand_id = cand["capability_id"]
                all_created_caps.append(cand_id)

                # Compute artifact hashes from physical snapshot
                art_hashes = {p: snapshot_after.get(p, "UNKNOWN") for p in cand.get("artifact_paths", [])}

                self.registry.register_candidate(
                    capability_id=cand_id,
                    name=cand.get("name", cand_id),
                    originating_run_id=run_ctx.run_id,
                    declared_purpose=cand.get("declared_purpose", clean_objective),
                    artifact_paths=cand.get("artifact_paths", []),
                    artifact_hashes=art_hashes,
                    dependencies=cand.get("dependencies", []),
                    applicability_constraints=cand.get("applicability_constraints", []),
                )
                logger.emit("CANDIDATE_CAPABILITY_REGISTERED", capability_id=cand_id, status="UNQUALIFIED")

            # Step 8: Execute Independent Verification Harness
            verifier_id = f"independent_verifier_{run_ctx.task_id}_{attempt_number}"
            verification_rec = self.kernel.execute_independent_verification(
                run_ctx=run_ctx,
                target_path=workspace_dir,
                builder_id=worker_id,
                test_cwd=workspace_dir,
                verifier_type=VerificationType.INDEPENDENT_BEHAVIORAL_ORACLE,
            )
            last_verification = verification_rec

            # Record Attempt Record
            att_rec = ExecutionAttemptRecord(
                attempt_number=attempt_number,
                started_at=worker_res.started_at,
                ended_at=worker_res.ended_at,
                duration_seconds=worker_res.duration_seconds,
                worker_invocations=[inv_rec],
                artifacts_staged=[{"path": p, "sha256": h} for p, h in snapshot_after.items()],
                verification=verification_rec,
                promotion_decision="PROMOTED"
                if (verification_rec.verified_status == "PASS" and not no_promote)
                else ("REJECTED" if verification_rec.verified_status != "PASS" else "SKIPPED_NO_PROMOTE"),
                status="COMPLETED" if verification_rec.verified_status == "PASS" else "FAILED",
                rejection_reason=None
                if verification_rec.verified_status == "PASS"
                else verification_rec.execution_trace,
            )
            attempts_records.append(att_rec)

            # Check if verification succeeded
            if verification_rec.verified_status == "PASS" and verification_rec.exit_code == 0:
                is_success = True
                logger.emit("VERIFICATION_PASSED", run_id=run_ctx.run_id, attempt=attempt_number)

                # Step 9: Qualify Candidate Capabilities
                for cand_id in all_created_caps:
                    try:
                        self.registry.qualify_capability(
                            capability_id=cand_id,
                            verifier_id=verifier_id,
                            verification_record=verification_rec.model_dump(),
                            base_dir=workspace_dir,
                        )
                        all_qualified_caps.append(cand_id)
                        logger.emit("CAPABILITY_QUALIFIED", capability_id=cand_id)
                    except Exception as e:
                        logger.emit("CAPABILITY_QUALIFICATION_FAILED", capability_id=cand_id, error=str(e))
                break
            else:
                logger.emit(
                    "VERIFICATION_FAILED",
                    run_id=run_ctx.run_id,
                    attempt=attempt_number,
                    reason=verification_rec.execution_trace,
                )
                attempt_number += 1

        # Step 10: Promotion or Rejection
        final_head = starting_head
        promotion_payload: Optional[Dict[str, Any]] = None

        if is_success and not no_promote:
            # Promote physical changes to target
            for file_rel, h in snapshot_after.items():
                src = workspace_dir / file_rel
                dst = target / file_rel
                dst.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src, dst)
            final_head = resolve_physical_commit_sha(target)
            promotion_payload = {
                "status": "PROMOTED",
                "promoted_at": datetime.now(timezone.utc).isoformat(),
                "files_promoted": list(snapshot_after.keys()),
            }
            logger.emit("CHANGES_PROMOTED", run_id=run_ctx.run_id, target=str(target))
        elif is_success and no_promote:
            promotion_payload = {
                "status": "SKIPPED_NO_PROMOTE",
                "promoted_at": None,
            }
        else:
            promotion_payload = {
                "status": "REJECTED",
                "promoted_at": None,
            }

        # Step 11: Seal and Persist Execution Receipt
        final_status = RunStatus.VERIFIED_SUCCESS if is_success else RunStatus.FAILED
        artifacts_produced = [{"path": p, "sha256": h} for p, h in snapshot_after.items()]

        receipt = self.kernel.seal_and_persist_receipt(
            run_ctx=run_ctx,
            objective=clean_objective,
            target_path=target,
            starting_head=starting_head,
            final_head=final_head,
            routing_strategy=routing_strategy,
            routing_decision_digest=route_digest,
            capabilities_selected=required_caps,
            attempts=attempts_records,
            worker_invocations=invocations_records,
            artifacts_produced=artifacts_produced,
            verification=last_verification,
            promotion=promotion_payload,
            final_status=final_status,
        )

        # Step 12: Verify Receipt Integrity Post-Sealing
        receipt_path = self.receipts_dir / f"{run_ctx.run_id}_receipt.json"
        is_receipt_valid = False
        if receipt_path.exists():
            is_valid, errs = verify_execution_receipt(receipt_path, kernel_db=self.db)
            is_receipt_valid = is_valid and len(errs) == 0

        # Step 13: Construct and Return Final Report
        report = OrchestratorExecutionReport(
            run_id=run_ctx.run_id,
            task_id=run_ctx.task_id,
            status=final_status.value,
            objective_status="SATISFIED" if is_success else "FAILED",
            routing_strategy=routing_strategy.value,
            capabilities_used=caps_used_ids,
            capabilities_created=all_created_caps,
            capabilities_qualified=all_qualified_caps,
            verification_status="PASS" if is_success else "FAIL",
            receipt_path=str(receipt_path) if receipt_path.exists() else None,
            receipt_valid=is_receipt_valid,
            final_head=final_head,
            error_message=None
            if is_success
            else (last_verification.execution_trace if last_verification else "Execution failed"),
            details={
                "attempts": len(attempts_records),
                "artifacts_produced": len(artifacts_produced),
                "duration_seconds": round(time.time() - start_time, 3),
            },
        )
        return report

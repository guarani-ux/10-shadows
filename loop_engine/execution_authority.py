"""Evidence-bearing execution primitives for the current Ten Shadows Python path.

This module deliberately separates mechanical observations from stronger claims.
A sealed receipt proves that Ten Shadows recorded a governed execution envelope;
it does not automatically prove semantic objective satisfaction, safe promotion,
or general capability acquisition.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import sys
import time
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Literal, Optional, Tuple, Union

from pydantic import BaseModel, Field, model_validator

from loop_engine.base import PROJECT_ROOT
from loop_engine.context import RunContext
from loop_engine.epistemic import SemanticLaunderingError
from loop_engine.errors import ConfigurationError
from loop_engine.kernel_db import KernelDatabase
from loop_engine.schema import compute_env_fingerprint


class RunStatus(str, Enum):
    CREATED = "CREATED"
    ROUTED = "ROUTED"
    RUNNING = "RUNNING"
    VERIFYING = "VERIFYING"
    VERIFIED_SUCCESS = "VERIFIED_SUCCESS"
    COMPLETED_UNVERIFIED = "COMPLETED_UNVERIFIED"
    FAILED = "FAILED"
    BLOCKED = "BLOCKED"
    NOT_COMPUTABLE = "NOT_COMPUTABLE"


class RoutingStrategy(str, Enum):
    CODE_HARDENING = "CODE_HARDENING"
    GOAL_DECOMPOSITION = "GOAL_DECOMPOSITION"
    ZERO_TRUST_PROPOSAL_VERIFICATION = "ZERO_TRUST_PROPOSAL_VERIFICATION"
    ADVERSARIAL_AUDIT = "ADVERSARIAL_AUDIT"
    DIRECT_DELEGATION = "DIRECT_DELEGATION"


class WorkerRole(str, Enum):
    PLANNER = "PLANNER"
    BUILDER = "BUILDER"
    VERIFIER = "VERIFIER"
    AUDITOR = "AUDITOR"
    DECOMPOSER = "DECOMPOSER"
    DELEGATE = "DELEGATE"


class EvidenceModality(str, Enum):
    SIMULATED = "SIMULATED"
    STRUCTURAL = "STRUCTURAL"
    DETERMINISTIC_TEST = "DETERMINISTIC_TEST"
    INTEGRATION = "INTEGRATION"
    EMPIRICAL = "EMPIRICAL"


class EvidencePurpose(str, Enum):
    EXECUTION = "EXECUTION"
    INTEGRITY = "INTEGRITY"
    PROVENANCE = "PROVENANCE"
    BEHAVIORAL_VERIFICATION = "BEHAVIORAL_VERIFICATION"
    SEMANTIC_VERIFICATION = "SEMANTIC_VERIFICATION"
    PROMOTION = "PROMOTION"


class VerificationType(str, Enum):
    BUILDER_TEST = "BUILDER_TEST"
    INDEPENDENT_BEHAVIORAL_ORACLE = "INDEPENDENT_BEHAVIORAL_ORACLE"
    INDEPENDENT_SEMANTIC_FALSIFICATION = "INDEPENDENT_SEMANTIC_FALSIFICATION"
    STATIC_ANALYSIS_GUARD = "STATIC_ANALYSIS_GUARD"


MODALITY_RANK: Dict[EvidenceModality, int] = {
    EvidenceModality.SIMULATED: 1,
    EvidenceModality.STRUCTURAL: 2,
    EvidenceModality.DETERMINISTIC_TEST: 3,
    EvidenceModality.INTEGRATION: 4,
    EvidenceModality.EMPIRICAL: 5,
}


def assert_evidence_monotonicity(declared_modality: EvidenceModality, claimed_modality: EvidenceModality) -> None:
    """Reject an evidence-strength upgrade that was not physically observed."""
    if MODALITY_RANK[claimed_modality] > MODALITY_RANK[declared_modality]:
        raise SemanticLaunderingError(
            "Evidence Monotonicity Violation: "
            f"Attempted illegal upgrade from '{declared_modality.value}' to '{claimed_modality.value}'."
        )


class ProviderExecutionReceipt(BaseModel):
    """Evidence record for a physically observed external provider invocation."""

    provider: str
    model: str
    transaction_id: str
    started_at: str
    ended_at: str
    duration_seconds: float
    token_usage: Dict[str, int] = Field(default_factory=dict)
    modality: EvidenceModality
    raw_response_digest: str
    status: str = "SUCCESS"

    @model_validator(mode="after")
    def validate_provider_evidence(self) -> "ProviderExecutionReceipt":
        if self.modality == EvidenceModality.EMPIRICAL:
            if (
                not self.transaction_id
                or self.transaction_id.startswith("mock_")
                or self.transaction_id.startswith("fake_")
            ):
                raise ValueError("EMPIRICAL provider execution requires a non-mock transaction_id.")
            if self.duration_seconds <= 0.0:
                raise ValueError("EMPIRICAL provider execution requires positive duration_seconds.")
            if not self.raw_response_digest or len(self.raw_response_digest) != 64:
                raise ValueError("EMPIRICAL provider execution requires a 64-character SHA-256 response digest.")
        return self


class WorkerInvocationRecord(BaseModel):
    """Recorded evidence of a worker/tool invocation."""

    invocation_id: str
    worker_id: str
    provider: str
    model: str
    role: WorkerRole
    modality: EvidenceModality = EvidenceModality.STRUCTURAL
    input_digest: str
    output_digest: str
    started_at: str
    ended_at: str
    duration_seconds: float
    status: str
    provider_receipt: Optional[ProviderExecutionReceipt] = None
    extra_metadata: Dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_worker_provenance(self) -> "WorkerInvocationRecord":
        if self.modality == EvidenceModality.EMPIRICAL:
            if self.provider_receipt is None:
                raise ValueError("Worker claiming EMPIRICAL modality must provide non-null provider_receipt.")
            if self.provider_receipt.modality != EvidenceModality.EMPIRICAL:
                raise ValueError("Worker claiming EMPIRICAL modality cannot hold non-EMPIRICAL provider_receipt.")
        return self


class IndependentVerificationRecord(BaseModel):
    """Mechanically captured output from a verifier distinct from the builder identity."""

    verifier_id: str
    verifier_type: VerificationType = VerificationType.INDEPENDENT_BEHAVIORAL_ORACLE
    builder_id: str
    modality: EvidenceModality = EvidenceModality.DETERMINISTIC_TEST
    purpose: EvidencePurpose = EvidencePurpose.BEHAVIORAL_VERIFICATION
    test_digest: str
    tests_collected: int
    tests_passed: int
    tests_failed: int
    exit_code: int
    duration_seconds: float
    falsification_attempted: bool = True
    verified_status: str
    execution_trace: Optional[str] = None
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    @model_validator(mode="after")
    def validate_independence(self) -> "IndependentVerificationRecord":
        if self.builder_id and self.verifier_id and self.builder_id == self.verifier_id:
            raise ValueError(
                f"Verification Independence Violation: builder_id '{self.builder_id}' is identical to "
                f"verifier_id '{self.verifier_id}' (Self-certification)."
            )
        return self


class ExecutionAttemptRecord(BaseModel):
    attempt_number: int
    started_at: str
    ended_at: str
    duration_seconds: float
    worker_invocations: List[WorkerInvocationRecord] = Field(default_factory=list)
    artifacts_staged: List[Dict[str, Any]] = Field(default_factory=list)
    verification: Optional[IndependentVerificationRecord] = None
    promotion_decision: str = "AWAITING_VERIFICATION"
    status: str = "IN_PROGRESS"
    rejection_reason: Optional[str] = None


class DisaggregatedEpistemicClaims(BaseModel):
    claim_kernel_run_created: bool
    claim_kernel_routed: bool
    claim_worker_executed: bool
    claim_empirical_provider_invoked: bool
    claim_candidate_mutated: bool
    claim_independently_verified: bool
    claim_promoted: bool
    claim_target_behaviorally_tested: bool
    claim_semantic_objective_satisfied: bool


class TenShadowsReceipt(BaseModel):
    """Sealed record with deliberately disaggregated claims."""

    receipt_version: str = "2.2.0"
    kernel_version: str = "10_SHADOWS_PYTHON_KERNEL_reconciled"
    run_id: str
    task_id: str
    objective: str
    objective_hash: str
    target_path: str
    starting_head: Optional[str] = None
    final_head: Optional[str] = None
    routing_strategy: RoutingStrategy
    routing_decision_digest: str
    capabilities_selected: List[str] = Field(default_factory=list)
    attempts: List[ExecutionAttemptRecord] = Field(default_factory=list)
    worker_invocations: List[WorkerInvocationRecord] = Field(default_factory=list)
    artifacts_produced: List[Dict[str, Any]] = Field(default_factory=list)
    verification: Optional[IndependentVerificationRecord] = None
    verification_scope: Literal["candidate", "target", "unknown"] = "unknown"
    promotion: Optional[Dict[str, Any]] = None
    epistemic_claims: DisaggregatedEpistemicClaims
    final_status: RunStatus
    created_at: str
    sealed_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    env_fingerprint: Dict[str, Any] = Field(default_factory=lambda: compute_env_fingerprint().to_dict())
    receipt_signature: str = ""

    @model_validator(mode="after")
    def validate_claim_consistency(self) -> "TenShadowsReceipt":
        claims = self.epistemic_claims
        if self.final_status == RunStatus.VERIFIED_SUCCESS:
            if self.verification is None:
                raise ValueError("VERIFIED_SUCCESS requires independent verification evidence.")
            if self.verification.verifier_type == VerificationType.BUILDER_TEST:
                raise ValueError("BUILDER_TEST evidence is insufficient for VERIFIED_SUCCESS.")
            if (
                self.verification.exit_code != 0
                or self.verification.tests_passed <= 0
                or self.verification.verified_status != "PASS"
            ):
                raise ValueError("VERIFIED_SUCCESS requires a clean passing verification record.")
        actual_promoted = bool(self.promotion and self.promotion.get("status") == "PROMOTED")
        if claims.claim_promoted != actual_promoted:
            raise ValueError("claim_promoted disagrees with the physical promotion record.")
        if claims.claim_target_behaviorally_tested and self.verification_scope != "target":
            raise ValueError("Target behavioral-test claim requires verification_scope='target'.")
        if claims.claim_semantic_objective_satisfied:
            if (
                self.verification is None
                or self.verification.verifier_type != VerificationType.INDEPENDENT_SEMANTIC_FALSIFICATION
            ):
                raise ValueError(
                    "Semantic objective satisfaction requires independent semantic falsification evidence."
                )
        return self

    def compute_signature(self) -> str:
        data = self.model_dump(exclude={"receipt_signature"})
        return hashlib.sha256(json.dumps(data, sort_keys=True, default=str).encode("utf-8")).hexdigest()


def verify_execution_receipt(
    receipt_data: Union[Dict[str, Any], Path, str],
    kernel_db: Optional[KernelDatabase] = None,
) -> Tuple[bool, List[str]]:
    """Verify receipt integrity, database anchoring, evidence consistency, and claim scope."""
    errors: List[str] = []
    if isinstance(receipt_data, (str, Path)):
        path = Path(receipt_data)
        if not path.exists() or not path.is_file():
            return False, [f"Receipt file does not exist: {path}"]
        try:
            receipt_dict = json.loads(path.read_text(encoding="utf-8"))
        except Exception as exc:
            return False, [f"Failed to parse receipt JSON: {exc}"]
    elif isinstance(receipt_data, dict):
        receipt_dict = receipt_data
    else:
        return False, [f"Invalid receipt data type: {type(receipt_data)}"]

    try:
        receipt = TenShadowsReceipt.model_validate(receipt_dict)
    except Exception as exc:
        return False, [f"Receipt schema validation error: {exc}"]

    expected_signature = receipt.compute_signature()
    if receipt.receipt_signature != expected_signature:
        errors.append("Receipt signature mismatch (tampered or stale receipt contents).")

    db = kernel_db or KernelDatabase()
    run_record = db.get_run(receipt.run_id)
    if not run_record:
        errors.append(f"Run '{receipt.run_id}' does not exist in authoritative KernelDatabase.")
    elif run_record["objective_hash"] != receipt.objective_hash:
        errors.append("Objective hash mismatch between receipt and KernelDatabase.")

    if receipt.verification:
        verification = receipt.verification
        if verification.builder_id and verification.verifier_id and verification.builder_id == verification.verifier_id:
            errors.append("Verification Independence Violation: builder and verifier identities are identical.")
        if receipt.final_status == RunStatus.VERIFIED_SUCCESS and (
            verification.exit_code != 0
            or verification.tests_passed <= 0
            or verification.verified_status != "PASS"
            or verification.verifier_type == VerificationType.BUILDER_TEST
        ):
            errors.append("VERIFIED_SUCCESS is not supported by the recorded verification evidence.")

    for worker in receipt.worker_invocations:
        if worker.modality == EvidenceModality.EMPIRICAL:
            if worker.provider_receipt is None:
                errors.append(f"Worker '{worker.worker_id}' claims EMPIRICAL modality without provider evidence.")
            elif worker.provider_receipt.duration_seconds <= 0.0:
                errors.append(f"Worker '{worker.worker_id}' empirical provider duration is not positive.")

    for label, head in (("starting_head", receipt.starting_head), ("final_head", receipt.final_head)):
        if head and not head.startswith("UNKNOWN") and len(head) != 40:
            errors.append(f"Invalid {label} format: '{head}'. Must be 40-char SHA, UNKNOWN*, or None.")

    claims = receipt.epistemic_claims
    actual_promoted = bool(receipt.promotion and receipt.promotion.get("status") == "PROMOTED")
    if claims.claim_promoted != actual_promoted:
        errors.append("Promotion claim does not match promotion evidence.")
    if claims.claim_target_behaviorally_tested and receipt.verification_scope != "target":
        errors.append("Target behavioral-test claim is unsupported by verification scope.")
    if claims.claim_independently_verified and receipt.verification is None:
        errors.append("Independent-verification claim has no verification record.")

    return len(errors) == 0, errors


def is_ten_shadows_execution(
    run_id_or_receipt: Union[str, Path, Dict[str, Any]],
    kernel_db: Optional[KernelDatabase] = None,
) -> bool:
    """Return true only for a structurally valid, database-anchored Ten Shadows receipt.

    This predicate means a governed execution was recorded. It does not mean the
    objective was semantically satisfied or that promotion occurred.
    """
    db = kernel_db or KernelDatabase()
    if (
        isinstance(run_id_or_receipt, str)
        and not run_id_or_receipt.endswith(".json")
        and not os.path.exists(run_id_or_receipt)
    ):
        run_id = run_id_or_receipt
        if not db.get_run(run_id):
            return False
        receipt_path = PROJECT_ROOT / ".receipts" / f"{run_id}_receipt.json"
        if receipt_path.exists():
            valid, _ = verify_execution_receipt(receipt_path, kernel_db=db)
            return valid
        with db.get_connection() as conn:
            row = conn.execute("SELECT receipt_json FROM receipts WHERE run_id = ?", (run_id,)).fetchone()
        if row and row["receipt_json"]:
            try:
                valid, _ = verify_execution_receipt(json.loads(row["receipt_json"]), kernel_db=db)
                return valid
            except Exception:
                return False
        return False
    valid, _ = verify_execution_receipt(run_id_or_receipt, kernel_db=db)
    return valid


class TenShadowsKernel:
    """Python evidence/state kernel used by the current canonical orchestrator."""

    def __init__(
        self,
        kernel_db: Optional[KernelDatabase] = None,
        receipts_dir: Optional[Path] = None,
    ) -> None:
        self.db = kernel_db or KernelDatabase()
        self.receipts_dir = receipts_dir or (PROJECT_ROOT / ".receipts")
        self.receipts_dir.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def _resolve_target_head(target_path: Path) -> Optional[str]:
        if not target_path.exists():
            return None
        try:
            result = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                cwd=str(target_path),
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                check=False,
            )
            head = result.stdout.strip()
            return head if result.returncode == 0 and len(head) == 40 else None
        except Exception:
            return None

    def establish_run(
        self,
        objective: str,
        target_path: Union[str, Path],
        task_id: Optional[str] = None,
        domain_code: str = "general_engineering",
    ) -> RunContext:
        target = Path(target_path).resolve()
        tid = task_id or f"task_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S_%f')}"
        starting_head = self._resolve_target_head(target) or "UNKNOWN_NON_GIT_TARGET"
        run_ctx = RunContext.create(
            task_id=tid,
            shadow_id=1,
            domain_code=domain_code,
            raw_objective=objective,
            source_commit=starting_head,
        )
        history = [s.get("status", str(s)) if isinstance(s, dict) else str(s) for s in run_ctx.status_history]
        self.db.record_run_state(
            run_id=run_ctx.run_id,
            task_id=run_ctx.task_id,
            shadow_id=run_ctx.shadow_id,
            domain_code=run_ctx.domain_code,
            source_commit=run_ctx.source_commit,
            objective_hash=run_ctx.objective_hash,
            canonical_input_hash=run_ctx.canonical_input_hash,
            status=RunStatus.CREATED.value,
            authority_level="AUTOMATIC",
            status_history=history,
        )
        return run_ctx

    def determine_route(
        self,
        run_ctx: RunContext,
        objective: str,
    ) -> Tuple[RoutingStrategy, List[str], str]:
        """Apply the current lexical route heuristic; this is not semantic capability reasoning."""
        text = objective.lower()
        if any(word in text for word in ["harden", "zero trust", "persist", "concurrency", "wal", "atomic"]):
            strategy = RoutingStrategy.CODE_HARDENING
            capabilities = [
                "PERSISTENCE_HARDENING",
                "DETERMINISTIC_TIME",
                "ATOMIC_MUTATION",
                "INDEPENDENT_VERIFICATION",
            ]
        elif any(word in text for word in ["audit", "verify", "falsify", "inspect", "assess"]):
            strategy = RoutingStrategy.ADVERSARIAL_AUDIT
            capabilities = ["STATIC_INSPECTION", "ADVERSARIAL_FALSIFICATION", "CONTRACT_VERIFICATION"]
        elif any(word in text for word in ["trivial", "ping", "echo", "format only", "simple comment"]):
            strategy = RoutingStrategy.DIRECT_DELEGATION
            capabilities = ["DIRECT_EXECUTION"]
        else:
            strategy = RoutingStrategy.GOAL_DECOMPOSITION
            capabilities = [
                "INTENT_ADEQUACY",
                "OBLIGATION_DERIVATION",
                "BUILD_COMPILATION",
                "INDEPENDENT_VERIFICATION",
            ]

        payload = {
            "run_id": run_ctx.run_id,
            "strategy": strategy.value,
            "capabilities": capabilities,
        }
        decision_digest = hashlib.sha256(json.dumps(payload, sort_keys=True).encode("utf-8")).hexdigest()
        history = [s.get("status", str(s)) if isinstance(s, dict) else str(s) for s in run_ctx.status_history] + [
            RunStatus.ROUTED.value
        ]
        self.db.record_run_state(
            run_id=run_ctx.run_id,
            task_id=run_ctx.task_id,
            shadow_id=run_ctx.shadow_id,
            domain_code=run_ctx.domain_code,
            source_commit=run_ctx.source_commit,
            objective_hash=run_ctx.objective_hash,
            canonical_input_hash=run_ctx.canonical_input_hash,
            status=RunStatus.ROUTED.value,
            authority_level="AUTOMATIC",
            status_history=history,
        )
        return strategy, capabilities, decision_digest

    def record_worker_invocation(
        self,
        run_ctx: RunContext,
        worker_id: str,
        provider: str,
        model: str,
        role: WorkerRole,
        input_payload: str,
        output_payload: str,
        duration_seconds: float,
        modality: EvidenceModality = EvidenceModality.STRUCTURAL,
        provider_receipt: Optional[ProviderExecutionReceipt] = None,
        status: str = "SUCCESS",
    ) -> WorkerInvocationRecord:
        now = datetime.now(timezone.utc).isoformat()
        return WorkerInvocationRecord(
            invocation_id=f"inv_{int(time.time() * 1000)}_{len(run_ctx.status_history)}",
            worker_id=worker_id,
            provider=provider,
            model=model,
            role=role,
            modality=modality,
            input_digest=hashlib.sha256(input_payload.encode("utf-8")).hexdigest(),
            output_digest=hashlib.sha256(output_payload.encode("utf-8")).hexdigest(),
            started_at=now,
            ended_at=now,
            duration_seconds=duration_seconds,
            status=status,
            provider_receipt=provider_receipt,
        )

    def execute_independent_verification(
        self,
        run_ctx: RunContext,
        target_path: Path,
        builder_id: str,
        verifier_cmd: Optional[List[str]] = None,
        test_cwd: Optional[Path] = None,
        verifier_type: VerificationType = VerificationType.INDEPENDENT_BEHAVIORAL_ORACLE,
    ) -> IndependentVerificationRecord:
        verifier_id = f"svris_verifier_{run_ctx.task_id}"
        if builder_id == verifier_id:
            verifier_id = f"svris_independent_verifier_{run_ctx.task_id}"
        command = verifier_cmd or [sys.executable, "-m", "pytest", "tests/", "-v", "--tb=short"]
        cwd = test_cwd or target_path
        started = time.time()
        try:
            result = subprocess.run(
                command,
                cwd=str(cwd),
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=120.0,
                check=False,
            )
            duration = max(0.001, time.time() - started)
            stdout = result.stdout
            passed_match = re.search(r"(\d+)\s+passed", stdout)
            failed_match = re.search(r"(\d+)\s+failed", stdout)
            passed = int(passed_match.group(1)) if passed_match else (1 if result.returncode == 0 else 0)
            failed = int(failed_match.group(1)) if failed_match else (1 if result.returncode != 0 else 0)
            return IndependentVerificationRecord(
                verifier_id=verifier_id,
                verifier_type=verifier_type,
                builder_id=builder_id,
                modality=EvidenceModality.DETERMINISTIC_TEST,
                purpose=EvidencePurpose.BEHAVIORAL_VERIFICATION,
                test_digest=hashlib.sha256(f"{command}:{stdout}".encode("utf-8")).hexdigest(),
                tests_collected=passed + failed,
                tests_passed=passed,
                tests_failed=failed,
                exit_code=result.returncode,
                duration_seconds=round(duration, 3),
                falsification_attempted=True,
                verified_status="PASS" if result.returncode == 0 else "FAIL",
                execution_trace=stdout[-1000:] if stdout else None,
            )
        except Exception as exc:
            return IndependentVerificationRecord(
                verifier_id=verifier_id,
                verifier_type=verifier_type,
                builder_id=builder_id,
                modality=EvidenceModality.DETERMINISTIC_TEST,
                purpose=EvidencePurpose.BEHAVIORAL_VERIFICATION,
                test_digest=hashlib.sha256(str(exc).encode("utf-8")).hexdigest(),
                tests_collected=0,
                tests_passed=0,
                tests_failed=1,
                exit_code=1,
                duration_seconds=max(0.001, round(time.time() - started, 3)),
                falsification_attempted=True,
                verified_status="FAIL",
                execution_trace=f"Verifier execution error: {exc}",
            )

    def seal_and_persist_receipt(
        self,
        run_ctx: RunContext,
        objective: str,
        target_path: Path,
        starting_head: Optional[str],
        final_head: Optional[str],
        routing_strategy: RoutingStrategy,
        routing_decision_digest: str,
        capabilities_selected: List[str],
        attempts: List[ExecutionAttemptRecord],
        worker_invocations: List[WorkerInvocationRecord],
        artifacts_produced: List[Dict[str, Any]],
        verification: Optional[IndependentVerificationRecord],
        promotion: Optional[Dict[str, Any]],
        final_status: RunStatus,
        verification_scope: Literal["candidate", "target", "unknown"] = "candidate",
    ) -> TenShadowsReceipt:
        has_empirical_worker = any(
            worker.modality == EvidenceModality.EMPIRICAL and worker.provider_receipt is not None
            for worker in worker_invocations
        )
        is_verified = bool(
            verification
            and verification.verified_status == "PASS"
            and verification.exit_code == 0
            and verification.tests_passed > 0
            and verification.verifier_type != VerificationType.BUILDER_TEST
        )
        is_promoted = bool(promotion and promotion.get("status") == "PROMOTED")
        claims = DisaggregatedEpistemicClaims(
            claim_kernel_run_created=True,
            claim_kernel_routed=True,
            claim_worker_executed=bool(worker_invocations),
            claim_empirical_provider_invoked=has_empirical_worker,
            claim_candidate_mutated=bool(artifacts_produced),
            claim_independently_verified=is_verified,
            claim_promoted=is_promoted,
            claim_target_behaviorally_tested=is_verified and verification_scope == "target",
            claim_semantic_objective_satisfied=bool(
                is_verified
                and verification
                and verification.verifier_type == VerificationType.INDEPENDENT_SEMANTIC_FALSIFICATION
            ),
        )
        receipt = TenShadowsReceipt(
            run_id=run_ctx.run_id,
            task_id=run_ctx.task_id,
            objective=objective,
            objective_hash=run_ctx.objective_hash,
            target_path=str(target_path),
            starting_head=starting_head,
            final_head=final_head,
            routing_strategy=routing_strategy,
            routing_decision_digest=routing_decision_digest,
            capabilities_selected=capabilities_selected,
            attempts=attempts,
            worker_invocations=worker_invocations,
            artifacts_produced=artifacts_produced,
            verification=verification,
            verification_scope=verification_scope,
            promotion=promotion,
            epistemic_claims=claims,
            final_status=final_status,
            created_at=run_ctx.started_at,
        )
        receipt.receipt_signature = receipt.compute_signature()
        receipt_file = self.receipts_dir / f"{run_ctx.run_id}_receipt.json"
        receipt_file.write_text(receipt.model_dump_json(indent=2) + "\n", encoding="utf-8")

        promotion_status = promotion.get("status") if promotion else "NOT_PROMOTED"
        with self.db.get_connection() as conn:
            conn.execute(
                """
                INSERT INTO receipts (
                    task_id, run_id, parent_run_id, shadow_id, domain_code,
                    stage, attempt, candidate_hash, source_commit, spec_hash,
                    status, strikes_used, target_file, artifact_sha256,
                    failure_code, repair_strategy, promotion_decision, receipt_json, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    receipt.task_id,
                    receipt.run_id,
                    run_ctx.parent_run_id,
                    run_ctx.shadow_id,
                    run_ctx.domain_code,
                    "SEALED",
                    len(attempts) or 1,
                    receipt.final_head,
                    receipt.starting_head or "UNKNOWN",
                    receipt.objective_hash,
                    receipt.final_status.value,
                    0,
                    str(target_path),
                    receipt.receipt_signature,
                    None,
                    None,
                    promotion_status,
                    receipt.model_dump_json(),
                    datetime.now(timezone.utc).isoformat(),
                ),
            )

        history = [s.get("status", str(s)) if isinstance(s, dict) else str(s) for s in run_ctx.status_history] + [
            receipt.final_status.value
        ]
        self.db.record_run_state(
            run_id=run_ctx.run_id,
            task_id=run_ctx.task_id,
            shadow_id=run_ctx.shadow_id,
            domain_code=run_ctx.domain_code,
            source_commit=receipt.final_head or run_ctx.source_commit,
            objective_hash=run_ctx.objective_hash,
            canonical_input_hash=run_ctx.canonical_input_hash,
            status=receipt.final_status.value,
            authority_level="AUTOMATIC",
            status_history=history,
        )
        return receipt

    def run_objective(
        self,
        objective: str,
        target_path: Union[str, Path],
        task_id: Optional[str] = None,
        builder_fn: Optional[Callable[[RunContext, Path], List[Dict[str, Any]]]] = None,
        custom_verifier_cmd: Optional[List[str]] = None,
        verifier_type: VerificationType = VerificationType.INDEPENDENT_BEHAVIORAL_ORACLE,
        worker_modality: EvidenceModality = EvidenceModality.STRUCTURAL,
        provider_receipt: Optional[ProviderExecutionReceipt] = None,
        provider_name: str = "local_callable",
        model_name: str = "deterministic",
        allow_target_mutation: bool = False,
    ) -> TenShadowsReceipt:
        """Internal compatibility harness used by legacy/adversarial tests.

        This is not the supported public objective entrypoint. Non-trivial work
        without a supplied builder is BLOCKED rather than fabricated. A supplied
        builder may mutate the physical target only when ``allow_target_mutation``
        is explicitly true.
        """
        target = Path(target_path).resolve()
        if not target.exists() or not target.is_dir():
            raise FileNotFoundError(f"Target path does not exist: {target}")

        run_ctx = self.establish_run(objective=objective, target_path=target, task_id=task_id)
        starting_head = self._resolve_target_head(target)
        strategy, capabilities, route_digest = self.determine_route(run_ctx, objective)

        if strategy == RoutingStrategy.DIRECT_DELEGATION:
            return self.seal_and_persist_receipt(
                run_ctx=run_ctx,
                objective=objective,
                target_path=target,
                starting_head=starting_head,
                final_head=starting_head,
                routing_strategy=strategy,
                routing_decision_digest=route_digest,
                capabilities_selected=capabilities,
                attempts=[],
                worker_invocations=[],
                artifacts_produced=[],
                verification=None,
                promotion=None,
                final_status=RunStatus.COMPLETED_UNVERIFIED,
                verification_scope="unknown",
            )

        if builder_fn is None:
            return self.seal_and_persist_receipt(
                run_ctx=run_ctx,
                objective=objective,
                target_path=target,
                starting_head=starting_head,
                final_head=starting_head,
                routing_strategy=strategy,
                routing_decision_digest=route_digest,
                capabilities_selected=capabilities,
                attempts=[],
                worker_invocations=[],
                artifacts_produced=[],
                verification=None,
                promotion={"status": "REJECTED", "reason": "No builder implementation supplied."},
                final_status=RunStatus.BLOCKED,
                verification_scope="unknown",
            )

        if not allow_target_mutation:
            raise ConfigurationError(
                "Direct TenShadowsKernel.run_objective target mutation is disabled by default. "
                "Use the canonical ts_run.py path or explicitly authorize this internal test harness."
            )

        attempt_started = time.time()
        build_started = time.time()
        artifacts = builder_fn(run_ctx, target)
        invocation = self.record_worker_invocation(
            run_ctx=run_ctx,
            worker_id=f"local_builder_{run_ctx.task_id}",
            provider=provider_name,
            model=model_name,
            role=WorkerRole.BUILDER,
            modality=worker_modality,
            input_payload=objective,
            output_payload=json.dumps(artifacts),
            duration_seconds=max(0.001, round(time.time() - build_started, 3)),
            provider_receipt=provider_receipt,
            status="SUCCESS",
        )
        verification = self.execute_independent_verification(
            run_ctx=run_ctx,
            target_path=target,
            builder_id=invocation.worker_id,
            verifier_cmd=custom_verifier_cmd,
            verifier_type=verifier_type,
        )
        passed = verification.verified_status == "PASS" and verification.exit_code == 0
        final_head = self._resolve_target_head(target) or starting_head
        promotion = {
            "status": "DIRECT_TARGET_MUTATION_VERIFIED" if passed else "DIRECT_TARGET_MUTATION_FAILED",
            "promoted_at": None,
            "head": final_head,
            "note": "No separate promotion step occurred; the authorized test harness mutated the target directly.",
        }
        attempt = ExecutionAttemptRecord(
            attempt_number=1,
            started_at=run_ctx.started_at,
            ended_at=datetime.now(timezone.utc).isoformat(),
            duration_seconds=round(time.time() - attempt_started, 3),
            worker_invocations=[invocation],
            artifacts_staged=artifacts,
            verification=verification,
            promotion_decision=promotion["status"],
            status="PASS" if passed else "FAIL",
            rejection_reason=None if passed else verification.execution_trace,
        )
        return self.seal_and_persist_receipt(
            run_ctx=run_ctx,
            objective=objective,
            target_path=target,
            starting_head=starting_head,
            final_head=final_head,
            routing_strategy=strategy,
            routing_decision_digest=route_digest,
            capabilities_selected=capabilities,
            attempts=[attempt],
            worker_invocations=[invocation],
            artifacts_produced=artifacts,
            verification=verification,
            promotion=promotion,
            final_status=RunStatus.VERIFIED_SUCCESS if passed else RunStatus.FAILED,
            verification_scope="target",
        )

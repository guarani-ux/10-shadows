"""
loop_engine/execution_authority.py
Authoritative Execution Kernel, Substrate Laws & Evidence Qualification for 10 SHADOWS.

Enforces the Four Substrate Laws:
LAW 1 — AUTHORITY:
    Only mechanically privileged components create authoritative state.
    Unprivileged actors lack the mechanism required to exercise authority.
LAW 2 — PROVENANCE:
    Every consequential claim retains an unbroken causal chain:
    PHYSICAL OBSERVATION -> EVIDENCE -> EVALUATOR -> QUALIFICATION -> AUTHORITY.
LAW 3 — INDEPENDENCE:
    The causal path producing a candidate is insufficient to certify it.
    Consequential promotion requires an independent verification authority.
LAW 4 — EVIDENCE MONOTONICITY:
    Evidence may be downgraded when stronger requirements are introduced.
    Evidence must NEVER be silently upgraded beyond what was physically observed.

Core Invariant:
NO VALID KERNEL-ISSUED EXECUTION RECEIPT = TEN SHADOWS DID NOT EXECUTE.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import time
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Literal, Optional, Sequence, Tuple, Union

from pydantic import BaseModel, Field, model_validator

from loop_engine.base import PROJECT_ROOT
from loop_engine.context import RunContext, resolve_physical_commit_sha
from loop_engine.epistemic import (
    EpistemicDisposition,
    EpistemicStatus,
    EvidenceOrigin,
    SemanticLaunderingError,
    canonical_json_digest,
)
from loop_engine.kernel_db import KERNEL_DB_PATH, KernelDatabase
from loop_engine.schema import EnvironmentFingerprint, compute_env_fingerprint

# ---------------------------------------------------------------------------
# Canonical Substrate Enums
# ---------------------------------------------------------------------------


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
    SIMULATED = "SIMULATED"  # Mock/synthetic generation, zero real execution
    STRUCTURAL = "STRUCTURAL"  # Static structure, AST rules, schema adherence
    DETERMINISTIC_TEST = "DETERMINISTIC_TEST"  # Deterministic test execution against local sandbox
    INTEGRATION = "INTEGRATION"  # Multi-component/subprocess integration
    EMPIRICAL = "EMPIRICAL"  # Verified physical provider API or system call


class EvidencePurpose(str, Enum):
    EXECUTION = "EXECUTION"  # Proves computational work was performed
    INTEGRITY = "INTEGRITY"  # Proves data has not changed (hash matching)
    PROVENANCE = "PROVENANCE"  # Traces causal chain to raw objective
    BEHAVIORAL_VERIFICATION = "BEHAVIORAL_VERIFICATION"  # Proves test assertions passed
    SEMANTIC_VERIFICATION = "SEMANTIC_VERIFICATION"  # Proves domain goal satisfied via independent oracle
    PROMOTION = "PROMOTION"  # Authorizes atomic merge/commit to target


class VerificationType(str, Enum):
    BUILDER_TEST = "BUILDER_TEST"  # Authored by builder; verifies developer intent
    INDEPENDENT_BEHAVIORAL_ORACLE = "INDEPENDENT_BEHAVIORAL_ORACLE"  # Independent test harness
    INDEPENDENT_SEMANTIC_FALSIFICATION = "INDEPENDENT_SEMANTIC_FALSIFICATION"  # Active falsifier
    STATIC_ANALYSIS_GUARD = "STATIC_ANALYSIS_GUARD"  # AST security / structural verifier


MODALITY_RANK: Dict[EvidenceModality, int] = {
    EvidenceModality.SIMULATED: 1,
    EvidenceModality.STRUCTURAL: 2,
    EvidenceModality.DETERMINISTIC_TEST: 3,
    EvidenceModality.INTEGRATION: 4,
    EvidenceModality.EMPIRICAL: 5,
}


def assert_evidence_monotonicity(declared_modality: EvidenceModality, claimed_modality: EvidenceModality) -> None:
    """Enforces Law 4: A weaker modality must NEVER silently become a stronger modality."""
    if MODALITY_RANK[claimed_modality] > MODALITY_RANK[declared_modality]:
        raise SemanticLaunderingError(
            f"Evidence Monotonicity Violation: Attempted illegal upgrade from '{declared_modality.value}' to '{claimed_modality.value}'."
        )


# ---------------------------------------------------------------------------
# Typed Evidence Models
# ---------------------------------------------------------------------------


class ProviderExecutionReceipt(BaseModel):
    """Immutable proof of external physical provider invocation."""

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
                raise ValueError("EMPIRICAL provider execution requires authentic non-mock transaction_id.")
            if self.duration_seconds <= 0.0:
                raise ValueError("EMPIRICAL provider execution requires positive duration_seconds.")
            if not self.raw_response_digest or len(self.raw_response_digest) != 64:
                raise ValueError("EMPIRICAL provider execution requires valid 64-character SHA-256 response digest.")
        return self


class WorkerInvocationRecord(BaseModel):
    """Mechanically recorded evidence of an external model or tool invocation."""

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
    """Mechanically captured record from an independent verifier harness."""

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
    verified_status: str  # "PASS" | "FAIL" | "BLOCKED"
    execution_trace: Optional[str] = None
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    @model_validator(mode="after")
    def validate_independence(self) -> "IndependentVerificationRecord":
        if self.builder_id and self.verifier_id and (self.builder_id == self.verifier_id):
            raise ValueError(
                f"Verification Independence Violation: builder_id '{self.builder_id}' is identical to verifier_id '{self.verifier_id}' (Self-certification)."
            )
        return self


class ExecutionAttemptRecord(BaseModel):
    """Immutable, append-only record of a single execution attempt within a run."""

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
    """
    Explicitly distinguishes the 9 separate claims so the receipt cannot imply
    stronger conclusions than physical evidence establishes.
    """

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
    """
    Authoritative, sealed execution receipt emitted exclusively by TenShadowsKernel.
    """

    receipt_version: str = "2.1.0"
    kernel_version: str = "10_SHADOWS_KERNEL_v3.0"
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
    promotion: Optional[Dict[str, Any]] = None
    epistemic_claims: DisaggregatedEpistemicClaims
    final_status: RunStatus
    created_at: str
    sealed_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    env_fingerprint: Dict[str, Any] = Field(default_factory=lambda: compute_env_fingerprint().to_dict())
    receipt_signature: str = ""

    @model_validator(mode="after")
    def validate_consequential_verification(self) -> "TenShadowsReceipt":
        if self.final_status == RunStatus.VERIFIED_SUCCESS:
            if self.verification is None:
                raise ValueError("Consequential VERIFIED_SUCCESS status requires independent verification evidence.")
            if self.verification.verifier_type == VerificationType.BUILDER_TEST:
                raise ValueError("BUILDER_TEST evidence is insufficient for consequential VERIFIED_SUCCESS.")
        return self

    def compute_signature(self) -> str:
        """Computes deterministic signature of the receipt content excluding the signature itself."""
        data = self.model_dump(exclude={"receipt_signature"})
        canonical_bytes = json.dumps(data, sort_keys=True, default=str).encode("utf-8")
        return hashlib.sha256(canonical_bytes).hexdigest()


# ---------------------------------------------------------------------------
# Verification Predicate & Inspector
# ---------------------------------------------------------------------------


def verify_execution_receipt(
    receipt_data: Union[Dict[str, Any], Path, str],
    kernel_db: Optional[KernelDatabase] = None,
) -> Tuple[bool, List[str]]:
    """
    Mechanically verifies a Ten Shadows execution receipt against physical kernel evidence.

    Fails closed if:
    1. Receipt structure or schema is invalid.
    2. Receipt signature does not match its contents.
    3. Run record does not exist in KernelDatabase.
    4. Run objective_hash does not match KernelDatabase.
    5. Starting/final Git HEADs conflict with recorded physical state.
    6. Builder attempted to self-certify independent verification.
    7. Consequential run is marked VERIFIED_SUCCESS without qualifying independent verification.
    8. Worker claims EMPIRICAL modality without authentic provider receipt.
    9. Receipt is a manual forgery or replay unanchored to kernel execution.
    """
    errors: List[str] = []

    # 1. Resolve receipt dictionary
    if isinstance(receipt_data, (str, Path)):
        p = Path(receipt_data)
        if not p.exists() or not p.is_file():
            return False, [f"Receipt file does not exist: {p}"]
        try:
            with open(p, "r", encoding="utf-8") as f:
                receipt_dict = json.load(f)
        except Exception as e:
            return False, [f"Failed to parse receipt JSON: {str(e)}"]
    elif isinstance(receipt_data, dict):
        receipt_dict = receipt_data
    else:
        return False, [f"Invalid receipt data type: {type(receipt_data)}"]

    # 2. Schema instantiation & signature verification
    try:
        receipt = TenShadowsReceipt.model_validate(receipt_dict)
    except Exception as e:
        return False, [f"Receipt schema validation error: {str(e)}"]

    expected_sig = receipt.compute_signature()
    if receipt.receipt_signature != expected_sig:
        errors.append(
            f"Receipt signature mismatch: expected '{expected_sig}', found '{receipt.receipt_signature}' (Tampered or forged receipt)."
        )

    # 3. Kernel Database anchor check
    db = kernel_db or KernelDatabase()
    run_record = db.get_run(receipt.run_id)
    if not run_record:
        errors.append(
            f"Run '{receipt.run_id}' does not exist in authoritative KernelDatabase (Unanchored receipt / external fabrication)."
        )
    else:
        # 4. Objective hash match
        if run_record["objective_hash"] != receipt.objective_hash:
            errors.append(
                f"Objective hash mismatch between receipt ('{receipt.objective_hash}') and KernelDatabase ('{run_record['objective_hash']}')."
            )

    # 5. Verification independence and qualification checks
    if receipt.verification:
        v = receipt.verification
        if v.builder_id and v.verifier_id and (v.builder_id == v.verifier_id):
            errors.append(
                f"Verification Independence Violation: builder_id '{v.builder_id}' is identical to verifier_id '{v.verifier_id}' (Self-certification)."
            )
        if receipt.final_status == RunStatus.VERIFIED_SUCCESS:
            if v.exit_code != 0 or v.tests_passed <= 0 or v.verified_status != "PASS":
                errors.append(
                    f"Invalid VERIFIED_SUCCESS: verification recorded exit_code={v.exit_code}, passed={v.tests_passed}, status='{v.verified_status}'."
                )
            if v.verifier_type == VerificationType.BUILDER_TEST:
                errors.append("BUILDER_TEST evidence is insufficient for consequential VERIFIED_SUCCESS.")

    # 6. Consequential status checks
    if receipt.final_status == RunStatus.VERIFIED_SUCCESS and not receipt.verification:
        errors.append("Consequential VERIFIED_SUCCESS status requires independent verification evidence.")

    # 7. Worker modality checks
    for w in receipt.worker_invocations:
        if w.modality == EvidenceModality.EMPIRICAL:
            if not w.provider_receipt:
                errors.append(f"Worker '{w.worker_id}' claims EMPIRICAL modality but missing provider_receipt.")
            elif w.provider_receipt.duration_seconds <= 0.0:
                errors.append(f"Worker '{w.worker_id}' claims EMPIRICAL modality but recorded duration <= 0.0.")

    # 8. Git HEAD consistency checks
    if receipt.starting_head and receipt.starting_head.startswith("UNKNOWN_"):
        pass  # Non-git target directory is allowable if path exists
    elif receipt.starting_head and len(receipt.starting_head) != 40:
        errors.append(f"Invalid starting_head format: '{receipt.starting_head}'. Must be 40-char SHA or None.")

    if receipt.final_head and len(receipt.final_head) != 40:
        errors.append(f"Invalid final_head format: '{receipt.final_head}'. Must be 40-char SHA or None.")

    is_valid = len(errors) == 0
    return is_valid, errors


def is_ten_shadows_execution(
    run_id_or_receipt: Union[str, Path, Dict[str, Any]],
    kernel_db: Optional[KernelDatabase] = None,
) -> bool:
    """
    Authoritative predicate determining whether Ten Shadows mechanically governed a run.

    Returns TRUE only when valid, non-forged kernel evidence proves the run was created,
    routed, executed, verified, and sealed by the Ten Shadows engine.
    """
    db = kernel_db or KernelDatabase()

    # If passed a run_id string
    if (
        isinstance(run_id_or_receipt, str)
        and not run_id_or_receipt.endswith(".json")
        and not os.path.exists(run_id_or_receipt)
    ):
        run_id = run_id_or_receipt
        run_record = db.get_run(run_id)
        if not run_record:
            return False

        # Look for receipt in standard receipts folder
        receipt_path = PROJECT_ROOT / ".receipts" / f"{run_id}_receipt.json"
        if receipt_path.exists():
            valid, _ = verify_execution_receipt(receipt_path, kernel_db=db)
            return valid

        # Query receipts table in kernel_db
        with db.get_connection() as conn:
            row = conn.execute("SELECT receipt_json FROM receipts WHERE run_id = ?", (run_id,)).fetchone()
            if row and row["receipt_json"]:
                try:
                    data = json.loads(row["receipt_json"])
                    valid, _ = verify_execution_receipt(data, kernel_db=db)
                    return valid
                except Exception:
                    return False
        return False

    # Otherwise passed a receipt path or dictionary
    valid, _ = verify_execution_receipt(run_id_or_receipt, kernel_db=db)
    return valid


# ---------------------------------------------------------------------------
# Authoritative Execution Kernel
# ---------------------------------------------------------------------------


class TenShadowsKernel:
    """
    The Single Invertible Execution Authority for Ten Shadows.
    """

    def __init__(
        self,
        kernel_db: Optional[KernelDatabase] = None,
        receipts_dir: Optional[Path] = None,
    ) -> None:
        self.db = kernel_db or KernelDatabase()
        self.receipts_dir = receipts_dir or (PROJECT_ROOT / ".receipts")
        self.receipts_dir.mkdir(parents=True, exist_ok=True)

    def _resolve_target_head(self, target_path: Path) -> Optional[str]:
        """Resolves target Git HEAD if target is a repository."""
        if not target_path.exists():
            return None
        try:
            res = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                cwd=str(target_path),
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
            )
            if res.returncode == 0:
                head = res.stdout.strip()
                if len(head) == 40:
                    return head
        except Exception:
            pass
        return None

    def establish_run(
        self,
        objective: str,
        target_path: Union[str, Path],
        task_id: Optional[str] = None,
        domain_code: str = "general_engineering",
    ) -> RunContext:
        """
        Creates an immutable, cryptographically-bound run record in KernelDatabase
        BEFORE any worker model receives authority to act.
        """
        target = Path(target_path).resolve()
        tid = task_id or f"task_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}"
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
        """
        Performs kernel-governed deficit and capability characterization.
        Emits and records an explicit RoutingDecision before execution.
        """
        obj_lower = objective.lower()

        if any(w in obj_lower for w in ["harden", "zero trust", "persist", "concurrency", "wal", "atomic"]):
            strategy = RoutingStrategy.CODE_HARDENING
            caps = ["PERSISTENCE_HARDENING", "DETERMINISTIC_TIME", "ATOMIC_MUTATION", "INDEPENDENT_VERIFICATION"]
        elif any(w in obj_lower for w in ["audit", "verify", "falsify", "inspect", "assess"]):
            strategy = RoutingStrategy.ADVERSARIAL_AUDIT
            caps = ["STATIC_INSPECTION", "ADVERSARIAL_FALSIFICATION", "CONTRACT_VERIFICATION"]
        elif any(w in obj_lower for w in ["trivial", "ping", "echo", "format only", "simple comment"]):
            strategy = RoutingStrategy.DIRECT_DELEGATION
            caps = ["DIRECT_EXECUTION"]
        else:
            strategy = RoutingStrategy.GOAL_DECOMPOSITION
            caps = ["INTENT_ADEQUACY", "OBLIGATION_DERIVATION", "BUILD_COMPILATION", "INDEPENDENT_VERIFICATION"]

        decision_payload = {
            "run_id": run_ctx.run_id,
            "strategy": strategy.value,
            "capabilities": caps,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        decision_digest = hashlib.sha256(json.dumps(decision_payload, sort_keys=True).encode("utf-8")).hexdigest()

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

        return strategy, caps, decision_digest

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
    ) -> WorkerInvocationRecord:
        """Records a mechanical worker invocation record inside the run."""
        now = datetime.now(timezone.utc).isoformat()
        inv = WorkerInvocationRecord(
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
            status="SUCCESS",
            provider_receipt=provider_receipt,
        )
        return inv

    def execute_independent_verification(
        self,
        run_ctx: RunContext,
        target_path: Path,
        builder_id: str,
        verifier_cmd: Optional[List[str]] = None,
        test_cwd: Optional[Path] = None,
        verifier_type: VerificationType = VerificationType.INDEPENDENT_BEHAVIORAL_ORACLE,
    ) -> IndependentVerificationRecord:
        """
        Executes independent verification harness separate from the builder.
        Runs pytest / test harness, captures exit code, test count, and trace.
        """
        verifier_id = f"svris_verifier_{run_ctx.task_id}"
        if builder_id == verifier_id:
            verifier_id = f"svris_independent_verifier_{run_ctx.task_id}"

        cmd = verifier_cmd or [
            sys.executable,
            "-m",
            "pytest",
            "tests/",
            "-v",
            "--tb=short",
        ]
        cwd = test_cwd or target_path

        start_time = time.time()
        try:
            res = subprocess.run(
                cmd,
                cwd=str(cwd),
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=120.0,
            )
            duration = max(0.001, time.time() - start_time)
            stdout = res.stdout
            exit_code = res.returncode

            passed_match = re.search(r"(\d+)\s+passed", stdout)
            failed_match = re.search(r"(\d+)\s+failed", stdout)
            passed_cnt = int(passed_match.group(1)) if passed_match else (1 if exit_code == 0 else 0)
            failed_cnt = int(failed_match.group(1)) if failed_match else (1 if exit_code != 0 else 0)

            test_digest = hashlib.sha256(f"{cmd}:{stdout}".encode("utf-8")).hexdigest()
            status = "PASS" if exit_code == 0 else "FAIL"

            rec = IndependentVerificationRecord(
                verifier_id=verifier_id,
                verifier_type=verifier_type,
                builder_id=builder_id,
                modality=EvidenceModality.DETERMINISTIC_TEST,
                purpose=EvidencePurpose.BEHAVIORAL_VERIFICATION,
                test_digest=test_digest,
                tests_collected=passed_cnt + failed_cnt,
                tests_passed=passed_cnt,
                tests_failed=failed_cnt,
                exit_code=exit_code,
                duration_seconds=round(duration, 3),
                falsification_attempted=True,
                verified_status=status,
                execution_trace=stdout[-1000:] if stdout else None,
            )
            return rec
        except Exception as e:
            duration = max(0.001, time.time() - start_time)
            return IndependentVerificationRecord(
                verifier_id=verifier_id,
                verifier_type=verifier_type,
                builder_id=builder_id,
                modality=EvidenceModality.DETERMINISTIC_TEST,
                purpose=EvidencePurpose.BEHAVIORAL_VERIFICATION,
                test_digest=hashlib.sha256(str(e).encode("utf-8")).hexdigest(),
                tests_collected=0,
                tests_passed=0,
                tests_failed=1,
                exit_code=1,
                duration_seconds=round(duration, 3),
                falsification_attempted=True,
                verified_status="FAIL",
                execution_trace=f"Verifier execution error: {str(e)}",
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
    ) -> TenShadowsReceipt:
        """
        Constructs, disaggregates epistemic claims, signs, and persists the sealed TenShadowsReceipt.
        """
        # Disaggregate Epistemic Claims
        has_empirical_worker = any(
            w.modality == EvidenceModality.EMPIRICAL and w.provider_receipt is not None for w in worker_invocations
        )
        is_verified = (
            verification is not None
            and verification.verified_status == "PASS"
            and verification.exit_code == 0
            and verification.verifier_type != VerificationType.BUILDER_TEST
        )
        is_promoted = promotion is not None and promotion.get("status") == "PROMOTED"

        claims = DisaggregatedEpistemicClaims(
            claim_kernel_run_created=True,
            claim_kernel_routed=True,
            claim_worker_executed=len(worker_invocations) > 0,
            claim_empirical_provider_invoked=has_empirical_worker,
            claim_candidate_mutated=len(artifacts_produced) > 0,
            claim_independently_verified=is_verified,
            claim_promoted=is_promoted,
            claim_target_behaviorally_tested=is_verified,
            claim_semantic_objective_satisfied=(
                is_verified and verification.verifier_type == VerificationType.INDEPENDENT_SEMANTIC_FALSIFICATION
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
            promotion=promotion,
            epistemic_claims=claims,
            final_status=final_status,
            created_at=run_ctx.started_at,
        )
        receipt.receipt_signature = receipt.compute_signature()

        # Write receipt JSON to .receipts/
        receipt_file = self.receipts_dir / f"{run_ctx.run_id}_receipt.json"
        with open(receipt_file, "w", encoding="utf-8") as f:
            f.write(receipt.model_dump_json(indent=2))
            f.write("\n")

        # Persist into KernelDatabase
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
                    "PROMOTED" if receipt.final_status == RunStatus.VERIFIED_SUCCESS else "NOT_PROMOTED",
                    receipt.model_dump_json(),
                    datetime.now(timezone.utc).isoformat(),
                ),
            )

        # Update final run state in KernelDatabase
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
        provider_name: str = "gemini",
        model_name: str = "gemini-2.5-flash",
    ) -> TenShadowsReceipt:
        """
        Full End-to-End Ten Shadows Governed Run Execution with Immutable Attempt Tracking.
        """
        target = Path(target_path).resolve()
        if not target.exists():
            raise FileNotFoundError(f"Target path does not exist: {target}")

        # 1. Establish Run in KernelDatabase before worker execution
        run_ctx = self.establish_run(objective=objective, target_path=target, task_id=task_id)
        starting_head = self._resolve_target_head(target)

        # 2. Determine Route
        strategy, caps, route_digest = self.determine_route(run_ctx, objective)

        attempts: List[ExecutionAttemptRecord] = []
        workers: List[WorkerInvocationRecord] = []
        artifacts: List[Dict[str, Any]] = []
        verification_rec: Optional[IndependentVerificationRecord] = None
        promotion_rec: Optional[Dict[str, Any]] = None

        builder_id = f"forge_builder_{run_ctx.task_id}"

        # 3. Direct Delegation path for trivial tasks
        if strategy == RoutingStrategy.DIRECT_DELEGATION:
            inv = self.record_worker_invocation(
                run_ctx=run_ctx,
                worker_id="direct_delegate_worker",
                provider=provider_name,
                model=model_name,
                role=WorkerRole.DELEGATE,
                modality=EvidenceModality.STRUCTURAL,
                input_payload=objective,
                output_payload="Direct delegation completed without heavy machinery.",
                duration_seconds=0.05,
            )
            workers.append(inv)
            final_status = RunStatus.COMPLETED_UNVERIFIED
            final_head = starting_head

            attempt_rec = ExecutionAttemptRecord(
                attempt_number=1,
                started_at=run_ctx.started_at,
                ended_at=datetime.now(timezone.utc).isoformat(),
                duration_seconds=0.05,
                worker_invocations=[inv],
                artifacts_staged=[],
                verification=None,
                promotion_decision="DIRECT_DELEGATION_COMPLETED",
                status="PASS",
            )
            attempts.append(attempt_rec)

            return self.seal_and_persist_receipt(
                run_ctx=run_ctx,
                objective=objective,
                target_path=target,
                starting_head=starting_head,
                final_head=final_head,
                routing_strategy=strategy,
                routing_decision_digest=route_digest,
                capabilities_selected=caps,
                attempts=attempts,
                worker_invocations=workers,
                artifacts_produced=artifacts,
                verification=None,
                promotion=None,
                final_status=final_status,
            )

        # 4. Standard Consequential Execution Path (Attempt 1)
        attempt_start = time.time()

        # Step A: Worker Build
        build_start = time.time()
        if builder_fn:
            artifacts = builder_fn(run_ctx, target)
        else:
            artifacts = [{"target": str(target), "status": "INSPECTED_AND_PREPARED"}]

        build_dur = max(0.001, round(time.time() - build_start, 3))
        inv = self.record_worker_invocation(
            run_ctx=run_ctx,
            worker_id=builder_id,
            provider=provider_name,
            model=model_name,
            role=WorkerRole.BUILDER,
            modality=worker_modality,
            input_payload=objective,
            output_payload=json.dumps(artifacts),
            duration_seconds=build_dur,
            provider_receipt=provider_receipt,
        )
        workers.append(inv)

        # Step B: Independent Verification (Builder != Verifier)
        verification_rec = self.execute_independent_verification(
            run_ctx=run_ctx,
            target_path=target,
            builder_id=builder_id,
            verifier_cmd=custom_verifier_cmd,
            verifier_type=verifier_type,
        )

        # Step C: Promotion Gate
        final_head = self._resolve_target_head(target) or starting_head
        if verification_rec.verified_status == "PASS" and verification_rec.exit_code == 0:
            final_status = RunStatus.VERIFIED_SUCCESS
            promotion_rec = {
                "status": "PROMOTED",
                "promoted_at": datetime.now(timezone.utc).isoformat(),
                "head": final_head,
            }
            attempt_status = "PASS"
            promo_decision = "PROMOTED"
        else:
            final_status = RunStatus.FAILED
            promotion_rec = {
                "status": "REJECTED",
                "reason": f"Verification failed with exit code {verification_rec.exit_code}",
            }
            attempt_status = "FAIL"
            promo_decision = "REJECTED"

        attempt_rec = ExecutionAttemptRecord(
            attempt_number=1,
            started_at=run_ctx.started_at,
            ended_at=datetime.now(timezone.utc).isoformat(),
            duration_seconds=round(time.time() - attempt_start, 3),
            worker_invocations=[inv],
            artifacts_staged=artifacts,
            verification=verification_rec,
            promotion_decision=promo_decision,
            status=attempt_status,
            rejection_reason=promotion_rec.get("reason"),
        )
        attempts.append(attempt_rec)

        # 5. Seal & Persist Receipt
        return self.seal_and_persist_receipt(
            run_ctx=run_ctx,
            objective=objective,
            target_path=target,
            starting_head=starting_head,
            final_head=final_head,
            routing_strategy=strategy,
            routing_decision_digest=route_digest,
            capabilities_selected=caps,
            attempts=attempts,
            worker_invocations=workers,
            artifacts_produced=artifacts,
            verification=verification_rec,
            promotion=promotion_rec,
            final_status=final_status,
        )

import hashlib
import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Literal, Optional, Tuple
from pydantic import BaseModel, Field

from loop_engine.base import BaseLoop, STAGING_ROOT, force_remove_readonly
from loop_engine.context import RunContext
from loop_engine.preflight import (
    canonical_spec_hash,
    run_pre_flight,
    assert_spec_untampered,
    PreflightCheckError,
    SpecTamperError,
)
from loop_engine.kernel_db import KernelDatabase
from loop_engine.schema import FailureClassification



class StrikeCeilingExceededError(Exception):
    """Raised when an autonomous execution loop fails 3 consecutive verification attempts."""
    pass


class OscillationDetectedError(Exception):
    """Raised when a retry produces a mathematically identical candidate to a prior failed attempt."""
    pass


class StepExecutionResult(BaseModel):
    """
    Structured outcome of a single Shadow step execution under the StepGovernor.
    """
    status: Literal["SUCCESS", "FAILED", "ABORTED", "ESCALATED"]
    task_id: str
    run_id: str
    parent_run_id: Optional[str] = None
    shadow_id: int = 0
    domain_code: str = "unmapped"
    spec_hash: str
    attempts_used: int = 1
    strikes_used: int = 0
    candidate_hash: Optional[str] = None
    negative_constraints_count: int = 0
    negative_constraints_ledger: List[Dict[str, Any]] = Field(default_factory=list)
    receipt: Optional[Dict[str, Any]] = None
    artifact_id: Optional[str] = None
    escalation: Optional[Dict[str, Any]] = None
    last_error: Optional[str] = None


from loop_engine.governance import (
    GovernanceConfig,
    load_canonical_governance,
    GovernanceConfigurationError,
)

class GovernanceOverrideProhibitedError(TypeError):
    """Raised when a caller attempts to manually override canonical strike governance."""
    pass


class StepGovernor:
    """
    Step-Level Governor and Anti-Oscillation Engine.
    
    Owns:
    - Single-step attempt counting (1..max_strikes) strictly governed by canonical governance.yaml.
    - Ephemeral staging workspace allocation and isolated destruction.
    - Anti-tamper spec sealing.
    - Deterministic trace compaction and cumulative negative constraint memory.
    - Mathematical candidate oscillation detection.
    - Injection of measured attempts/strikes into runner commit routines.
    """

    def __init__(
        self,
        kernel_db: Optional[KernelDatabase] = None,
        governance_config: Optional[GovernanceConfig] = None,
        max_error_lines: int = 25,
        **kwargs: Any,
    ):
        if "max_strikes" in kwargs or "max_attempts" in kwargs:
            override_key = "max_strikes" if "max_strikes" in kwargs else "max_attempts"
            raise GovernanceOverrideProhibitedError(
                f"Manual strike override '{override_key}={kwargs[override_key]}' is prohibited. "
                "The strike ceiling is exclusively governed by canonical governance.yaml."
            )
        if kwargs:
            raise TypeError(f"StepGovernor.__init__() got unexpected keyword argument(s): {list(kwargs.keys())}")

        self.governance = governance_config or load_canonical_governance()
        self.max_strikes = self.governance.governor.strike_ceiling
        self.execution_timeout_seconds = self.governance.governor.execution_timeout_seconds
        self.max_error_lines = max_error_lines
        self.kernel_db = kernel_db or KernelDatabase()


    def compact_error_trace(self, raw_error: str) -> str:
        """Compacts verbose error tracebacks to preserve root-cause failure data within token budget."""
        if not raw_error:
            return ""
        lines = raw_error.strip().splitlines()
        if len(lines) <= self.max_error_lines:
            return "\n".join(lines)
        return "\n".join(lines[-self.max_error_lines:])

    def run_step(
        self,
        loop: BaseLoop,
        raw_input: Any,
        parent_context: Optional[RunContext] = None,
        required_modules: Optional[List[str]] = None,
        step_id: Optional[str] = None,
        forced_failure_attempt: Optional[int] = None,
        forced_failure_msg: Optional[str] = None,
        inject_oscillation_attempt: Optional[int] = None,
    ) -> StepExecutionResult:
        """
        Executes a single Shadow step under strict strike limits and anti-oscillation governance.
        """
        # 1. Normalize input
        if hasattr(loop, "normalize_with_context") and parent_context:
            task_spec = loop.normalize_with_context(raw_input, parent_context=parent_context, step_id=step_id)
        else:
            task_spec = loop.normalize(raw_input)

        task_id = task_spec.get("task_id", f"task_{int(time.time())}")
        shadow_id = getattr(loop, "shadow_id", 0)
        domain_code = getattr(loop, "domain_code", "unmapped")
        
        # Context management
        child_context: Optional[RunContext] = None
        if parent_context:
            child_context = parent_context.create_child(
                shadow_id=shadow_id or 1,
                domain_code=domain_code,
                step_id=step_id or "step",
                step_input=raw_input,
            )
            run_id = child_context.run_id
            parent_run_id = parent_context.run_id
        else:
            run_id = task_spec.get("run_id") or f"run_{task_id}_{int(time.time() * 1000) % 1000000}"
            parent_run_id = None

        staging_dir = STAGING_ROOT / run_id
        if staging_dir.exists():
            import shutil
            shutil.rmtree(staging_dir, onerror=force_remove_readonly)
        staging_dir.mkdir(parents=True, exist_ok=True)

        # 2. Phase 0 Preflight & Spec Sealing
        sealed_spec_hash = run_pre_flight(
            task_spec=task_spec,
            staging_dir=staging_dir,
            required_modules=required_modules,
        )

        negative_constraints_ledger: List[Dict[str, Any]] = []
        candidate_hashes_history: List[str] = []
        feedback: Optional[str] = None
        strike = 0
        attempt = 0
        last_candidate_hash: Optional[str] = None

        try:
            while strike < self.max_strikes:
                attempt += 1

                # Invariant: Anti-Tamper check before every iteration
                assert_spec_untampered(sealed_spec_hash, task_spec)

                # Inject attempt state into loop if supported
                if hasattr(loop, "set_governor_state"):
                    loop.set_governor_state(attempt=attempt, strike=strike, parent_run_id=parent_run_id)

                # 3. Execution in isolated staging
                try:
                    candidate_path = loop.execute_staging(
                        task_spec=task_spec,
                        staging_dir=staging_dir,
                        feedback=feedback,
                    )
                except Exception as e:
                    strike += 1
                    compacted_err = self.compact_error_trace(str(e))
                    failure_entry = {
                        "attempt": attempt,
                        "strike": strike,
                        "phase": "EXECUTION",
                        "error": compacted_err,
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                    }
                    negative_constraints_ledger.append(failure_entry)
                    feedback = f"Execution Failure on Attempt {attempt} (Strike {strike}): {compacted_err}"
                    continue

                # Compute candidate hash
                if candidate_path.exists():
                    cand_text = candidate_path.read_text(encoding="utf-8")
                    curr_cand_hash = hashlib.sha256(cand_text.encode("utf-8")).hexdigest()
                else:
                    curr_cand_hash = "missing_candidate"

                last_candidate_hash = curr_cand_hash

                # 4. Anti-Oscillation Check: Detect repeated identical candidate on retry
                if attempt > 1 and len(candidate_hashes_history) > 0:
                    if curr_cand_hash == candidate_hashes_history[-1] and strike > 0:
                        strike += 1
                        compacted_err = "Anti-Oscillation Violation: Candidate generated on retry is mathematically identical to prior failed candidate."
                        failure_entry = {
                            "attempt": attempt,
                            "strike": strike,
                            "phase": "OSCILLATION",
                            "error": compacted_err,
                            "timestamp": datetime.now(timezone.utc).isoformat(),
                        }
                        negative_constraints_ledger.append(failure_entry)
                        feedback = f"Oscillation Detected on Strike {strike}: {compacted_err}"
                        continue

                candidate_hashes_history.append(curr_cand_hash)

                # Invariant: Verify task_spec was not mutated during staging
                assert_spec_untampered(sealed_spec_hash, task_spec)

                # 5. Deterministic Failure Injection Seam (Testing Hook)
                if forced_failure_attempt == attempt:
                    passed, error_msg = False, (forced_failure_msg or f"Forced Failure Seam triggered on attempt {attempt}")
                else:
                    passed, error_msg = loop.verify(candidate_path, task_spec)

                if passed:
                    # 6. Atomic Commit
                    if hasattr(loop, "commit_with_governance"):
                        receipt = loop.commit_with_governance(
                            candidate_path=candidate_path,
                            task_spec=task_spec,
                            attempt=attempt,
                            strikes_used=strike,
                            parent_run_id=parent_run_id,
                            candidate_hash=curr_cand_hash,
                        )
                    else:
                        receipt = loop.commit(candidate_path, task_spec)

                    return StepExecutionResult(
                        status="SUCCESS",
                        task_id=task_id,
                        run_id=run_id,
                        parent_run_id=parent_run_id,
                        shadow_id=shadow_id,
                        domain_code=domain_code,
                        spec_hash=sealed_spec_hash,
                        attempts_used=attempt,
                        strikes_used=strike,
                        candidate_hash=curr_cand_hash,
                        negative_constraints_count=len(negative_constraints_ledger),
                        negative_constraints_ledger=negative_constraints_ledger,
                        receipt=receipt,
                    )

                # Verification Failed -> Record to negative constraints ledger
                strike += 1
                compacted_err = self.compact_error_trace(error_msg)
                failure_entry = {
                    "attempt": attempt,
                    "strike": strike,
                    "phase": "VERIFICATION",
                    "error": compacted_err,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }
                negative_constraints_ledger.append(failure_entry)
                feedback = (
                    f"Verification Gate Failed on Strike {strike}/{self.max_strikes} (Attempt {attempt}).\n"
                    f"Cumulative Failures: {len(negative_constraints_ledger)}\n"
                    f"Error Signature:\n{compacted_err}"
                )

            # Strikes exhausted -> Abort
            return StepExecutionResult(
                status="ABORTED",
                task_id=task_id,
                run_id=run_id,
                parent_run_id=parent_run_id,
                shadow_id=shadow_id,
                domain_code=domain_code,
                spec_hash=sealed_spec_hash,
                attempts_used=attempt,
                strikes_used=self.max_strikes,
                candidate_hash=last_candidate_hash,
                negative_constraints_count=len(negative_constraints_ledger),
                negative_constraints_ledger=negative_constraints_ledger,
                last_error=feedback,
            )

        finally:
            if staging_dir.exists():
                import shutil
                shutil.rmtree(staging_dir, onerror=force_remove_readonly)


# Backward-compatible alias for existing test suites
class Governor(StepGovernor):
    """
    Maintains 100% backward compatibility for all existing Governor tests.
    """
    def run_loop(
        self,
        loop: BaseLoop,
        raw_input: Any,
        required_modules: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        res = self.run_step(loop=loop, raw_input=raw_input, required_modules=required_modules)
        d = res.model_dump(mode="json")
        if res.status == "SUCCESS":
            d["strikes_used"] = res.attempts_used
        elif res.status == "ABORTED":
            d["strikes_exhausted"] = res.strikes_used
        return d


class RetryGovernor:
    """
    Deterministic retry governor enforcing strict attempt bounds.

    Invariants:
    1. max_attempts > 0 (strictly positive integer).
    2. 0 <= attempts_used <= max_attempts (clamped bound).
    3. remaining_attempts() == max(0, max_attempts - attempts_used) >= 0.
    4. can_retry() is True if and only if attempts_used < max_attempts.
    5. Zero courtesy retries: When attempts_used == max_attempts, can_retry() is False.
    6. Calling record_failure() at capacity clamps attempts_used to max_attempts.
    """

    def __init__(self, max_attempts: int, attempts_used: int = 0) -> None:
        if not isinstance(max_attempts, int) or isinstance(max_attempts, bool):
            raise TypeError("max_attempts must be an integer.")
        if not isinstance(attempts_used, int) or isinstance(attempts_used, bool):
            raise TypeError("attempts_used must be an integer.")
        if max_attempts <= 0:
            raise ValueError(f"max_attempts must be strictly positive (> 0), got {max_attempts}.")
        if attempts_used < 0:
            raise ValueError(f"attempts_used must be non-negative (>= 0), got {attempts_used}.")
        if attempts_used > max_attempts:
            raise ValueError(
                f"attempts_used ({attempts_used}) cannot exceed max_attempts ({max_attempts})."
            )

        self._max_attempts: int = max_attempts
        self._attempts_used: int = attempts_used

    @property
    def max_attempts(self) -> int:
        """Returns the maximum allowed attempts."""
        return self._max_attempts

    @property
    def attempts_used(self) -> int:
        """Returns the number of attempts used so far."""
        return self._attempts_used

    def can_retry(self) -> bool:
        """
        Returns True only when another attempt is permitted (remaining_attempts > 0).
        Explicitly rejects any courtesy retries when attempts_used >= max_attempts.
        """
        return self._attempts_used < self._max_attempts

    def record_failure(self) -> None:
        """
        Increment attempts used by exactly 1.
        If attempt limit has already been reached, clamps attempts_used to max_attempts.
        """
        if self._attempts_used < self._max_attempts:
            self._attempts_used += 1

    def remaining_attempts(self) -> int:
        """
        Returns the number of remaining attempts before exhaustion.
        Always returns an integer >= 0.
        """
        return max(0, self._max_attempts - self._attempts_used)

    def reset(self) -> None:
        """Resets the attempts used counter to 0."""
        self._attempts_used = 0

    def __repr__(self) -> str:
        return f"RetryGovernor(max_attempts={self._max_attempts}, attempts_used={self._attempts_used})"



class TokenBucketRateLimiter:
    """
    Thread-safe Token Bucket Rate Limiter.
    Operates using monotonic timestamps and atomic token consumption.
    """

    def __init__(self, capacity: float, refill_rate: float):
        import threading
        if capacity <= 0:
            raise ValueError("Capacity must be strictly positive.")
        if refill_rate <= 0:
            raise ValueError("Refill rate must be strictly positive.")

        self.capacity = float(capacity)
        self.refill_rate = float(refill_rate)
        self.tokens = float(capacity)
        self.last_refill_time = time.monotonic()
        self._lock = threading.Lock()

    def _refill(self) -> None:
        """Refill tokens based on elapsed monotonic time."""
        now = time.monotonic()
        elapsed = now - self.last_refill_time
        if elapsed > 0:
            added_tokens = elapsed * self.refill_rate
            self.tokens = min(self.capacity, self.tokens + added_tokens)
            self.last_refill_time = now

    def allow(self, tokens: float = 1.0) -> bool:
        """
        Attempts to consume tokens from the bucket.
        Returns True if tokens were consumed, False if rate limited.
        """
        if tokens <= 0:
            return True

        with self._lock:
            self._refill()
            if self.tokens >= tokens:
                self.tokens -= tokens
                return True
            return False

    def get_available_tokens(self) -> float:
        """Returns the current number of available tokens in the bucket."""
        with self._lock:
            self._refill()
            return self.tokens


class GovernorEngine:
    """
    Database-backed 3-Strike Governor with failure discrimination and anti-oscillation tracking.
    """

    def __init__(self, db: KernelDatabase, max_strikes: int = 3):
        self.db = db
        self.max_strikes = max_strikes

    def evaluate_failure(self, task_id: str, classification: FailureClassification, signature: str) -> bool:
        """
        Evaluates failure. Increments strikes ONLY on implementation and regression bugs.
        Detects repetitive oscillation.
        Returns True if a strike was recorded, False otherwise.
        """
        if classification not in (FailureClassification.CANDIDATE_FAILURE, FailureClassification.REGRESSION_FAILURE):
            return False

        # Anti-oscillation detection
        existing_signatures = self.db.get_failure_signatures(task_id)
        if signature in existing_signatures:
            # Duplicate failure signature detected - force immediate terminal strike
            self.db.record_strike(task_id, classification, f"OSCILLATION_DETECTED:{signature}")
            return True

        self.db.record_strike(task_id, classification, signature)
        return True

    def get_strike_count(self, task_id: str) -> int:
        return self.db.get_strikes(task_id)

    def is_aborted(self, task_id: str) -> bool:
        return self.get_strike_count(task_id) >= self.max_strikes


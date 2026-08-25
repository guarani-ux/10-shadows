import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

from loop_engine.base import BaseLoop, STAGING_ROOT, force_remove_readonly
from loop_engine.preflight import (
    canonical_spec_hash,
    run_pre_flight,
    assert_spec_untampered,
    PreflightCheckError,
    SpecTamperError,
)


class StrikeCeilingExceededError(Exception):
    """Raised when an autonomous execution loop fails 3 consecutive verification attempts."""
    pass


class Governor:
    """
    3-Strike Governor and Anti-Oscillation Engine.
    Orchestrates execution loops with deterministic strike limits, cumulative
    negative constraint memory, and token-bounded error compaction.
    """

    def __init__(self, max_strikes: int = 3, max_error_lines: int = 25):
        self.max_strikes = max_strikes
        self.max_error_lines = max_error_lines

    def compact_error_trace(self, raw_error: str) -> str:
        """
        Compacts verbose error tracebacks to preserve root-cause failure data
        while staying strictly within token budget (last N lines).
        """
        if not raw_error:
            return ""
        lines = raw_error.strip().splitlines()
        if len(lines) <= self.max_error_lines:
            return "\n".join(lines)
        return "\n".join(lines[-self.max_error_lines:])

    def run_loop(
        self,
        loop: BaseLoop,
        raw_input: Any,
        required_modules: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        Executes a BaseLoop under the 3-Strike Governor.
        Enforces Phase 0 preflight, anti-tamper spec sealing, and cumulative
        negative constraint memory across retries.
        """
        task_spec = loop.normalize(raw_input)
        task_id = task_spec.get("task_id", f"task_{int(time.time())}")
        run_id = f"run_{task_id}_{int(time.time() * 1000) % 1000000}"

        staging_dir = STAGING_ROOT / run_id
        if staging_dir.exists():
            import shutil
            shutil.rmtree(staging_dir, onerror=force_remove_readonly)
        staging_dir.mkdir(parents=True, exist_ok=True)

        # 1. Phase 0: Preflight Admission & Spec Sealing
        sealed_spec_hash = run_pre_flight(
            task_spec=task_spec,
            staging_dir=staging_dir,
            required_modules=required_modules,
        )

        negative_constraints_ledger: List[Dict[str, Any]] = []
        feedback: Optional[str] = None
        strike = 0

        try:
            while strike < self.max_strikes:
                strike += 1

                # Invariant: Anti-Tamper check before every iteration
                assert_spec_untampered(sealed_spec_hash, task_spec)

                # 2. Execution in Staging
                try:
                    candidate_path = loop.execute_staging(
                        task_spec=task_spec,
                        staging_dir=staging_dir,
                        feedback=feedback,
                    )
                except Exception as e:
                    compacted_err = self.compact_error_trace(str(e))
                    failure_entry = {
                        "strike": strike,
                        "phase": "EXECUTION",
                        "error": compacted_err,
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                    }
                    negative_constraints_ledger.append(failure_entry)
                    feedback = f"Execution Failure on Strike {strike}: {compacted_err}"
                    continue

                # Invariant: Verify task_spec was not mutated during staging execution
                assert_spec_untampered(sealed_spec_hash, task_spec)


                # 3. Verification Gate
                passed, error_msg = loop.verify(candidate_path, task_spec)

                if passed:
                    # 4. Atomic Commit
                    receipt = loop.commit(candidate_path, task_spec)
                    return {
                        "status": "SUCCESS",
                        "task_id": task_id,
                        "run_id": run_id,
                        "spec_hash": sealed_spec_hash,
                        "strikes_used": strike,
                        "negative_constraints_count": len(negative_constraints_ledger),
                        "receipt": receipt,
                    }

                # Verification Failed -> Record to negative constraints ledger
                compacted_err = self.compact_error_trace(error_msg)
                failure_entry = {
                    "strike": strike,
                    "phase": "VERIFICATION",
                    "error": compacted_err,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }
                negative_constraints_ledger.append(failure_entry)
                feedback = (
                    f"Verification Gate Failed on Strike {strike}/{self.max_strikes}.\n"
                    f"Cumulative Failures: {len(negative_constraints_ledger)}\n"
                    f"Error Signature:\n{compacted_err}"
                )

            # 3-Strike Hard Abort
            forensic_report = {
                "status": "ABORTED",
                "task_id": task_id,
                "run_id": run_id,
                "spec_hash": sealed_spec_hash,
                "strikes_exhausted": self.max_strikes,
                "negative_constraints_ledger": negative_constraints_ledger,
                "last_error": feedback,
            }
            return forensic_report

        finally:
            if staging_dir.exists():
                import shutil
                shutil.rmtree(staging_dir, onerror=force_remove_readonly)

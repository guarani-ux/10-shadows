"""
zero_trust_engine/governor.py
3-Strike Governor with failure discrimination, anti-oscillation tracking, and KernelDatabase persistence.
"""

from loop_engine.kernel_db import KernelDatabase
from loop_engine.schema import FailureClassification


class GovernorEngine:
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

"""
loop_engine/promoter.py
6-State Idempotent Promotion Coordinator with transactional CAS transitions,
database-retrieved receipts only, ancestry-based reconciliation, and post-promotion test execution.
"""

import subprocess
import sys
from pathlib import Path
from typing import Any, Optional

from loop_engine.kernel_db import (
    KernelDatabase,
    ReceiptNotFoundError,
    ReceiptMismatchError,
    IllegalStateTransitionError,
)
from loop_engine.schema import State, VerificationReceipt
from loop_engine.verifier_gate import PhysicalVerifierGate


class PromotionCoordinator:
    def __init__(
        self,
        repo_dir: Path,
        target_branch: str,
        kernel_db: KernelDatabase,
        verifier_gate: PhysicalVerifierGate,
    ):
        self.repo_dir = repo_dir
        self.target_branch = target_branch
        self.kernel_db = kernel_db
        self.verifier_gate = verifier_gate

    def promote(self, task_id: str, receipt_id: Any) -> bool:
        """
        Promotes a candidate strictly from a persisted receipt in KernelDatabase.
        Accepts receipt_id (int) or VerificationReceipt / VerificationResult.
        """
        if isinstance(receipt_id, int):
            rid = receipt_id
        elif hasattr(receipt_id, "receipt_id") and isinstance(receipt_id.receipt_id, int):
            rid = receipt_id.receipt_id
        elif isinstance(receipt_id, tuple) and len(receipt_id) > 0 and isinstance(receipt_id[0], int):
            rid = receipt_id[0]
        else:
            raise ReceiptMismatchError(f"Invalid receipt identifier: {receipt_id}")

        # 1. Fetch and validate receipt from KernelDatabase
        receipt = self.kernel_db.get_verified_receipt(rid)
        if not receipt:
            raise ReceiptNotFoundError(f"No receipt found with receipt_id={receipt_id}")

        if receipt.task_id != task_id:
            raise ReceiptMismatchError(f"Receipt task_id '{receipt.task_id}' does not match '{task_id}'")

        if receipt.status != State.VERIFIED:
            return False

        proposal = self.kernel_db.get_proposal(task_id)
        if not proposal:
            raise ReceiptMismatchError(f"No proposal manifest found for task_id '{task_id}'")

        if (
            receipt.spec_hash != proposal.spec_hash
            or receipt.candidate_commit_sha != proposal.candidate_commit_sha
            or receipt.candidate_tree_sha != proposal.candidate_tree_sha
        ):
            raise ReceiptMismatchError("Receipt cryptographic properties do not match sealed proposal manifest.")

        # 2. Pre-Promotion Workspace Integrity Checks
        status_res = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=self.repo_dir,
            capture_output=True,
            text=True,
        )
        if status_res.returncode != 0 or status_res.stdout.strip():
            # Dirty worktree: cannot promote safely
            return False

        target_head_res = subprocess.run(
            ["git", "rev-parse", self.target_branch],
            cwd=self.repo_dir,
            capture_output=True,
            text=True,
        )
        if target_head_res.returncode != 0:
            return False
        current_target_head = target_head_res.stdout.strip()

        # Verify target branch has not moved away from verified base
        if current_target_head != proposal.base_commit_sha:
            # Check if base_commit_sha is ancestor of current target
            base_check = subprocess.run(
                ["git", "merge-base", "--is-ancestor", proposal.base_commit_sha, current_target_head],
                cwd=self.repo_dir,
            )
            if base_check.returncode != 0:
                # Target branch diverged; requires re-verification
                return False

        # 3. Transactional Transition: VERIFIED -> PROMOTION_PENDING
        self.kernel_db.transition_proposal_state(task_id, State.VERIFIED, State.PROMOTION_PENDING)
        self.kernel_db.record_promotion_wal_step(
            task_id, self.target_branch, receipt.candidate_commit_sha, State.PROMOTION_PENDING
        )

        # 4. Git Merge Fast-Forward
        checkout_res = subprocess.run(
            ["git", "checkout", self.target_branch],
            cwd=self.repo_dir,
            capture_output=True,
            text=True,
        )
        if checkout_res.returncode != 0:
            self.kernel_db.transition_proposal_state(task_id, State.PROMOTION_PENDING, State.VERIFIED)
            return False

        merge_res = subprocess.run(
            ["git", "merge", "--ff-only", receipt.candidate_commit_sha],
            cwd=self.repo_dir,
            capture_output=True,
            text=True,
        )
        if merge_res.returncode != 0:
            self.kernel_db.transition_proposal_state(task_id, State.PROMOTION_PENDING, State.VERIFIED)
            return False

        # 5. Transactional Transition: PROMOTION_PENDING -> PROMOTED
        self.kernel_db.transition_proposal_state(task_id, State.PROMOTION_PENDING, State.PROMOTED)
        self.kernel_db.record_promotion_wal_step(
            task_id, self.target_branch, receipt.candidate_commit_sha, State.PROMOTED
        )

        # 6. Physical Post-Promotion Execution on Target Branch
        post_verify_success = self._run_post_promotion_verification()
        if not post_verify_success:
            return False

        # 7. Final Transition: PROMOTED -> POST_PROMOTION_VERIFIED
        self.kernel_db.transition_proposal_state(task_id, State.PROMOTED, State.POST_PROMOTION_VERIFIED)
        self.kernel_db.record_promotion_wal_step(
            task_id, self.target_branch, receipt.candidate_commit_sha, State.POST_PROMOTION_VERIFIED
        )
        return True

    def _run_post_promotion_verification(self) -> bool:
        """Runs the test suite directly on the promoted target branch."""
        test_file = self.verifier_gate.canonical_fixtures_dir / "test_app.py"
        if not test_file.exists():
            return True

        res = subprocess.run(
            [
                sys.executable,
                "-m",
                "pytest",
                str(test_file),
                "-v",
                "-p",
                "no:logfire",
                "-p",
                "no:ddtrace",
                "-p",
                "no:langsmith",
            ],
            cwd=self.repo_dir,
            capture_output=True,
            text=True,
            timeout=60,
        )
        return res.returncode == 0

    def reconcile_interrupted_promotions(self) -> None:
        """
        Startup reconciliation: Reconciles interrupted PROMOTION_PENDING states
        using Git commit ancestry and post-promotion verification.
        """
        pending_rows = self.kernel_db.get_pending_promotions()
        for row in pending_rows:
            task_id = row["task_id"]
            cand_sha = row["candidate_commit_sha"]

            # Check if candidate commit is an ancestor of target branch HEAD
            ancestry_check = subprocess.run(
                ["git", "merge-base", "--is-ancestor", cand_sha, self.target_branch],
                cwd=self.repo_dir,
            )

            if ancestry_check.returncode == 0:
                # Commit is already merged into target branch; run post-promotion test
                if self._run_post_promotion_verification():
                    # CAS update to POST_PROMOTION_VERIFIED
                    self.kernel_db.transition_proposal_state(task_id, State.PROMOTION_PENDING, State.PROMOTED)
                    self.kernel_db.transition_proposal_state(task_id, State.PROMOTED, State.POST_PROMOTION_VERIFIED)
                    continue

            # If commit is not in target branch, roll back state to VERIFIED
            self.kernel_db.transition_proposal_state(task_id, State.PROMOTION_PENDING, State.VERIFIED)

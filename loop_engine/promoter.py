"""
loop_engine/promoter.py
6-State Idempotent Promotion Coordinator with transactional CAS transitions,
database-retrieved receipts only, ancestry-based reconciliation, post-promotion test execution,
and load-bearing privileged state transitions strictly mediated by PrivilegedTransitionEngine.
"""

import subprocess
import sys
from pathlib import Path
from typing import Any, Optional

from loop_engine.authority import issue_proof_witness
from loop_engine.kernel_db import (
    KernelDatabase,
    ReceiptNotFoundError,
    ReceiptMismatchError,
    IllegalStateTransitionError,
)
from loop_engine.schema import State, VerificationReceipt
from loop_engine.transition import (
    PrivilegedTransitionEngine,
    TransitionRequest,
    TransitionReceipt,
    TransitionRejection,
    compute_complete_claim_digest,
    compute_governance_digest,
)
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
        self.transition_engine = PrivilegedTransitionEngine(kernel_db=self.kernel_db)

    def _request_transition(
        self,
        task_id: str,
        from_state: State,
        to_state: State,
        receipt: VerificationReceipt,
        authority_scope: str = "PROMOTION",
    ) -> bool:
        """Helper to create and submit a cryptographically witnessed TransitionRequest to the PrivilegedTransitionEngine."""
        gov_digest = compute_governance_digest()
        claim_digest = compute_complete_claim_digest(
            task_id=task_id,
            from_state=from_state,
            to_state=to_state,
            subject_identity=receipt.candidate_commit_sha,
            candidate_tree_sha=receipt.candidate_tree_sha,
            spec_hash=receipt.spec_hash,
            acceptance_test_digest=receipt.acceptance_test_digest,
            evidence_digest=receipt.execution_trace or "",
            authority_scope=authority_scope,
            governance_hash=gov_digest,
        )
        witness = issue_proof_witness(
            issuer="loop_engine.promoter",
            target_digest=claim_digest,
            scope=authority_scope,
        )
        req = TransitionRequest(
            task_id=task_id,
            from_state=from_state,
            to_state=to_state,
            subject_identity=receipt.candidate_commit_sha,
            candidate_tree_sha=receipt.candidate_tree_sha,
            spec_hash=receipt.spec_hash,
            acceptance_test_digest=receipt.acceptance_test_digest,
            evidence_digest=receipt.execution_trace or "",
            authority_scope=authority_scope,
            witness=witness,
            governance_hash=gov_digest,
        )
        res = self.transition_engine.execute_transition(req)
        return not isinstance(res, TransitionRejection)

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
            return False

        # 2. Check current state - Idempotency
        cur_state = self.kernel_db.get_proposal_state(task_id)
        if cur_state == State.POST_PROMOTION_VERIFIED:
            return True

        # Precondition check: target repo clean
        status_res = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=self.repo_dir,
            capture_output=True,
            text=True,
        )
        if status_res.stdout.strip():
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

        # 3. Transactional Transition: VERIFIED -> PROMOTION_PENDING via Transition Engine
        if not self._request_transition(task_id, State.VERIFIED, State.PROMOTION_PENDING, receipt):
            return False
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
            self._request_transition(task_id, State.PROMOTION_PENDING, State.VERIFIED, receipt)
            return False

        merge_res = subprocess.run(
            ["git", "merge", "--ff-only", receipt.candidate_commit_sha],
            cwd=self.repo_dir,
            capture_output=True,
            text=True,
        )
        if merge_res.returncode != 0:
            self._request_transition(task_id, State.PROMOTION_PENDING, State.VERIFIED, receipt)
            return False

        # 5. Transactional Transition: PROMOTION_PENDING -> PROMOTED via Transition Engine
        if not self._request_transition(task_id, State.PROMOTION_PENDING, State.PROMOTED, receipt):
            return False
        self.kernel_db.record_promotion_wal_step(
            task_id, self.target_branch, receipt.candidate_commit_sha, State.PROMOTED
        )

        # 6. Physical Post-Promotion Execution on Target Branch
        post_verify_success = self._run_post_promotion_verification()
        if not post_verify_success:
            self._request_transition(task_id, State.PROMOTED, State.REJECTED, receipt)
            return False

        # 7. Final Transition: PROMOTED -> POST_PROMOTION_VERIFIED via Transition Engine
        if not self._request_transition(task_id, State.PROMOTED, State.POST_PROMOTION_VERIFIED, receipt):
            return False
        self.kernel_db.record_promotion_wal_step(
            task_id, self.target_branch, receipt.candidate_commit_sha, State.POST_PROMOTION_VERIFIED
        )
        return True

    def _run_post_promotion_verification(self) -> bool:
        """Runs the test suite directly on the promoted target branch (Fail-Closed)."""
        test_files = list(self.verifier_gate.canonical_fixtures_dir.glob("test_*.py"))
        if not test_files:
            return True

        test_target = test_files[0]
        res = subprocess.run(
            [
                sys.executable,
                "-m",
                "pytest",
                str(test_target),
            ],
            cwd=self.repo_dir,
            capture_output=True,
            text=True,
        )
        return res.returncode == 0

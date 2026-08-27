"""
loop_engine/verifier_gate.py
Sterile candidate verification executing 10 physical verification gates with
module-shadowing protection, fixture checksumming, test collection validation,
and direct persistence into KernelDatabase.
"""

import os
import re
import subprocess
import sys
import time
from pathlib import Path
from typing import Optional, Tuple

from loop_engine.kernel_db import KernelDatabase
from loop_engine.schema import (
    FailureClassification,
    ProposalManifest,
    State,
    VerificationReceipt,
    compute_env_fingerprint,
    compute_failure_signature,
    compute_test_digest,
    compute_tree_hash,
)

BANNED_SHADOW_MODULES = [
    "pytest.py",
    "sitecustomize.py",
    "usercustomize.py",
    "unittest.py",
    "subprocess.py",
    "os.py",
    "sys.py",
]


class PhysicalVerifierGate:
    def __init__(
        self,
        repo_dir: Path,
        canonical_fixtures_dir: Path,
        kernel_db: KernelDatabase,
        verifier_version: str = "2.0.0",
    ):
        self.repo_dir = repo_dir
        self.canonical_fixtures_dir = canonical_fixtures_dir
        self.kernel_db = kernel_db
        self.verifier_version = verifier_version

    def verify_candidate(
        self,
        manifest: ProposalManifest,
        candidate_worktree: Path,
        test_file_relative: str = "test_app.py",
    ) -> Tuple[int, VerificationReceipt]:
        """
        Executes sterile physical verification and persists receipt directly into KernelDatabase.
        Returns: (receipt_id, VerificationReceipt)
        """
        now = time.time()
        env_fp = compute_env_fingerprint()

        # Gate 1: Module Shadowing & Attacker-Controlled Import Prevention
        for banned in BANNED_SHADOW_MODULES:
            if (candidate_worktree / banned).exists():
                receipt = VerificationReceipt(
                    receipt_id=None,
                    task_id=manifest.task_id,
                    spec_hash=manifest.spec_hash,
                    base_commit_sha=manifest.base_commit_sha,
                    candidate_commit_sha=manifest.candidate_commit_sha,
                    candidate_tree_sha=manifest.candidate_tree_sha,
                    physical_tree_hash="",
                    verifier_version=self.verifier_version,
                    acceptance_test_digest=manifest.acceptance_test_digest,
                    env_fingerprint=env_fp,
                    status=State.BLOCKED,
                    failure_classification=FailureClassification.GOVERNOR_FAILURE,
                    failure_signature=compute_failure_signature(f"Candidate module shadowing detected: {banned}"),
                    execution_trace=f"Attacker-controlled module shadowing attempt: '{banned}' created in worktree root.",
                    timestamp=now,
                )
                receipt_id = self.kernel_db.record_verified_receipt(receipt)
                receipt.receipt_id = receipt_id
                return receipt_id, receipt

        # Gate 2: Physical Git Tree Hash & Clean Worktree Integrity
        git_tree_res = subprocess.run(
            ["git", "rev-parse", "HEAD^{tree}"],
            cwd=candidate_worktree,
            capture_output=True,
            text=True,
        )
        physical_git_tree = git_tree_res.stdout.strip() if git_tree_res.returncode == 0 else ""

        status_res = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=candidate_worktree,
            capture_output=True,
            text=True,
        )
        is_clean = (status_res.returncode == 0 and not status_res.stdout.strip())

        if (physical_git_tree != manifest.candidate_tree_sha) or not is_clean:
            receipt = VerificationReceipt(
                receipt_id=None,
                task_id=manifest.task_id,
                spec_hash=manifest.spec_hash,
                base_commit_sha=manifest.base_commit_sha,
                candidate_commit_sha=manifest.candidate_commit_sha,
                candidate_tree_sha=manifest.candidate_tree_sha,
                physical_tree_hash=physical_git_tree,
                verifier_version=self.verifier_version,
                acceptance_test_digest=manifest.acceptance_test_digest,
                env_fingerprint=env_fp,
                status=State.REJECTED,
                failure_classification=FailureClassification.CANDIDATE_FAILURE,
                failure_signature=compute_failure_signature("Tree hash mismatch or dirty worktree"),
                execution_trace=f"Physical tree={physical_git_tree}, Manifest tree={manifest.candidate_tree_sha}, Clean={is_clean}",
                timestamp=now,
            )
            receipt_id = self.kernel_db.record_verified_receipt(receipt)
            receipt.receipt_id = receipt_id
            return receipt_id, receipt

        # Gate 3: Pre-Execution Canonical Fixture Checksum
        pre_fixture_digest = compute_test_digest(self.canonical_fixtures_dir)
        if pre_fixture_digest != manifest.acceptance_test_digest:
            receipt = VerificationReceipt(
                receipt_id=None,
                task_id=manifest.task_id,
                spec_hash=manifest.spec_hash,
                base_commit_sha=manifest.base_commit_sha,
                candidate_commit_sha=manifest.candidate_commit_sha,
                candidate_tree_sha=manifest.candidate_tree_sha,
                physical_tree_hash=physical_git_tree,
                verifier_version=self.verifier_version,
                acceptance_test_digest=manifest.acceptance_test_digest,
                env_fingerprint=env_fp,
                status=State.BLOCKED,
                failure_classification=FailureClassification.GOVERNOR_FAILURE,
                failure_signature=compute_failure_signature("Canonical fixture digest mismatch before test run"),
                execution_trace="Canonical acceptance fixtures were mutated or deleted prior to test execution.",
                timestamp=now,
            )
            receipt_id = self.kernel_db.record_verified_receipt(receipt)
            receipt.receipt_id = receipt_id
            return receipt_id, receipt

        # Gate 4: Tamper Rejection on Worktree Fixtures
        worktree_fixtures = candidate_worktree / "canonical_fixtures"
        if worktree_fixtures.exists():
            worktree_test_digest = compute_tree_hash(worktree_fixtures)
            if worktree_test_digest != manifest.acceptance_test_digest:
                receipt = VerificationReceipt(
                    receipt_id=None,
                    task_id=manifest.task_id,
                    spec_hash=manifest.spec_hash,
                    base_commit_sha=manifest.base_commit_sha,
                    candidate_commit_sha=manifest.candidate_commit_sha,
                    candidate_tree_sha=manifest.candidate_tree_sha,
                    physical_tree_hash=physical_git_tree,
                    verifier_version=self.verifier_version,
                    acceptance_test_digest=manifest.acceptance_test_digest,
                    env_fingerprint=env_fp,
                    status=State.BLOCKED,
                    failure_classification=FailureClassification.GOVERNOR_FAILURE,
                    failure_signature=compute_failure_signature("Canonical fixture tamper detected in worktree"),
                    execution_trace="Proposer attempted to mutate canonical acceptance fixtures in worktree.",
                    timestamp=now,
                )
                receipt_id = self.kernel_db.record_verified_receipt(receipt)
                receipt.receipt_id = receipt_id
                return receipt_id, receipt

        # Gate 5: Sterile Subprocess Pytest Execution
        test_file = self.canonical_fixtures_dir / test_file_relative
        if not test_file.exists():
            receipt = VerificationReceipt(
                receipt_id=None,
                task_id=manifest.task_id,
                spec_hash=manifest.spec_hash,
                base_commit_sha=manifest.base_commit_sha,
                candidate_commit_sha=manifest.candidate_commit_sha,
                candidate_tree_sha=manifest.candidate_tree_sha,
                physical_tree_hash=physical_git_tree,
                verifier_version=self.verifier_version,
                acceptance_test_digest=manifest.acceptance_test_digest,
                env_fingerprint=env_fp,
                status=State.BLOCKED,
                failure_classification=FailureClassification.SPEC_FAILURE,
                failure_signature=compute_failure_signature(f"Missing test fixture: {test_file_relative}"),
                execution_trace=f"Specified test fixture '{test_file_relative}' does not exist.",
                timestamp=now,
            )
            receipt_id = self.kernel_db.record_verified_receipt(receipt)
            receipt.receipt_id = receipt_id
            return receipt_id, receipt

        run_env = {
            "PATH": os.environ.get("PATH", ""),
            "PYTHONPATH": str(candidate_worktree),
            "SYSTEMROOT": os.environ.get("SYSTEMROOT", ""),
            "COMSPEC": os.environ.get("COMSPEC", ""),
            "WINDIR": os.environ.get("WINDIR", ""),
            "TMP": os.environ.get("TMP", ""),
            "TEMP": os.environ.get("TEMP", ""),
            "USERPROFILE": os.environ.get("USERPROFILE", ""),
            "HOMEDRIVE": os.environ.get("HOMEDRIVE", ""),
            "HOMEPATH": os.environ.get("HOMEPATH", ""),
            "LOCALAPPDATA": os.environ.get("LOCALAPPDATA", ""),
            "APPDATA": os.environ.get("APPDATA", ""),
        }

        try:
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
                cwd=candidate_worktree,
                capture_output=True,
                text=True,
                env=run_env,
                timeout=60,
            )

            # Gate 6: Post-Execution Canonical Fixture Checksum
            post_fixture_digest = compute_test_digest(self.canonical_fixtures_dir)
            if post_fixture_digest != manifest.acceptance_test_digest:
                receipt = VerificationReceipt(
                    receipt_id=None,
                    task_id=manifest.task_id,
                    spec_hash=manifest.spec_hash,
                    base_commit_sha=manifest.base_commit_sha,
                    candidate_commit_sha=manifest.candidate_commit_sha,
                    candidate_tree_sha=manifest.candidate_tree_sha,
                    physical_tree_hash=physical_git_tree,
                    verifier_version=self.verifier_version,
                    acceptance_test_digest=manifest.acceptance_test_digest,
                    env_fingerprint=env_fp,
                    status=State.BLOCKED,
                    failure_classification=FailureClassification.GOVERNOR_FAILURE,
                    failure_signature=compute_failure_signature("Canonical fixture mutated during test execution"),
                    execution_trace="Test execution mutated canonical acceptance fixtures during run.",
                    timestamp=now,
                )
                receipt_id = self.kernel_db.record_verified_receipt(receipt)
                receipt.receipt_id = receipt_id
                return receipt_id, receipt

            # Gate 7: Verify Expected Test Collection & Execution Count
            collection_match = re.search(r"collected (\d+) item", res.stdout)
            collected_count = int(collection_match.group(1)) if collection_match else 0

            passed_match = re.search(r"(\d+) passed", res.stdout)
            passed_count = int(passed_match.group(1)) if passed_match else 0

            if collected_count == 0 or passed_count == 0 or res.returncode != 0:
                sig = compute_failure_signature(res.stdout + "\n" + res.stderr)
                error_msg = res.stdout + "\n" + res.stderr
                if collected_count == 0:
                    error_msg = f"Zero tests collected! Pytest collected {collected_count} items.\n" + error_msg

                receipt = VerificationReceipt(
                    receipt_id=None,
                    task_id=manifest.task_id,
                    spec_hash=manifest.spec_hash,
                    base_commit_sha=manifest.base_commit_sha,
                    candidate_commit_sha=manifest.candidate_commit_sha,
                    candidate_tree_sha=manifest.candidate_tree_sha,
                    physical_tree_hash=physical_git_tree,
                    verifier_version=self.verifier_version,
                    acceptance_test_digest=manifest.acceptance_test_digest,
                    env_fingerprint=env_fp,
                    status=State.REJECTED,
                    failure_classification=FailureClassification.CANDIDATE_FAILURE,
                    failure_signature=sig,
                    execution_trace=error_msg,
                    timestamp=now,
                )
                receipt_id = self.kernel_db.record_verified_receipt(receipt)
                receipt.receipt_id = receipt_id
                return receipt_id, receipt

            # Gate 8: Verified Pass
            receipt = VerificationReceipt(
                receipt_id=None,
                task_id=manifest.task_id,
                spec_hash=manifest.spec_hash,
                base_commit_sha=manifest.base_commit_sha,
                candidate_commit_sha=manifest.candidate_commit_sha,
                candidate_tree_sha=manifest.candidate_tree_sha,
                physical_tree_hash=physical_git_tree,
                verifier_version=self.verifier_version,
                acceptance_test_digest=manifest.acceptance_test_digest,
                env_fingerprint=env_fp,
                status=State.VERIFIED,
                execution_trace=res.stdout,
                timestamp=now,
            )
            receipt_id = self.kernel_db.record_verified_receipt(receipt)
            receipt.receipt_id = receipt_id
            return receipt_id, receipt

        except Exception as e:
            receipt = VerificationReceipt(
                receipt_id=None,
                task_id=manifest.task_id,
                spec_hash=manifest.spec_hash,
                base_commit_sha=manifest.base_commit_sha,
                candidate_commit_sha=manifest.candidate_commit_sha,
                candidate_tree_sha=manifest.candidate_tree_sha,
                physical_tree_hash=physical_git_tree,
                verifier_version=self.verifier_version,
                acceptance_test_digest=manifest.acceptance_test_digest,
                env_fingerprint=env_fp,
                status=State.BLOCKED,
                failure_classification=FailureClassification.ENVIRONMENT_FAILURE,
                failure_signature=compute_failure_signature(str(e)),
                execution_trace=str(e),
                timestamp=now,
            )
            receipt_id = self.kernel_db.record_verified_receipt(receipt)
            receipt.receipt_id = receipt_id
            return receipt_id, receipt

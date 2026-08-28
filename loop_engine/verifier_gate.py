"""
loop_engine/verifier_gate.py
Hardened Physical Verifier Gate for 10 SHADOWS.
Sterile pytest execution in ephemeral git worktree with anti-shadowing protections.
"""

from dataclasses import dataclass
import hashlib
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
from typing import Any, Dict, List, Optional, Tuple

from loop_engine.ast_guard import scan_python_worktree
from loop_engine.sterile_env import build_sterile_environment
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
    "pytest.pyc",
    "_pytest",
    "sitecustomize.py",
    "usercustomize.py",
    "unittest.py",
    "subprocess.py",
    "os.py",
    "sys.py",
]


class VerificationResult(tuple):
    """
    Dual-interface result wrapper allowing both tuple unpacking (receipt_id, receipt)
    and direct attribute access on the receipt.
    """
    def __new__(cls, receipt_id: int, receipt: VerificationReceipt):
        return super().__new__(cls, (receipt_id, receipt))

    def __init__(self, receipt_id: int, receipt: VerificationReceipt):
        self._receipt_id = receipt_id
        self._receipt = receipt

    @property
    def receipt_id(self) -> int:
        return self._receipt_id

    def __getattr__(self, name: str) -> Any:
        return getattr(self._receipt, name)


class PhysicalVerifierGate:
    def __init__(
        self,
        repo_dir: Path,
        canonical_fixtures_dir: Path,
        verifier_version_or_kernel_db: Any = "2.0.0",
        kernel_db: Optional[KernelDatabase] = None,
        verifier_version: str = "2.0.0",
    ):
        self.repo_dir = Path(repo_dir)
        self.canonical_fixtures_dir = Path(canonical_fixtures_dir)

        if isinstance(verifier_version_or_kernel_db, str) and verifier_version_or_kernel_db.replace(".", "").isdigit():
            self.verifier_version = verifier_version_or_kernel_db
        else:
            self.verifier_version = verifier_version

        if kernel_db is not None:
            self.kernel_db = kernel_db
        elif isinstance(verifier_version_or_kernel_db, KernelDatabase):
            self.kernel_db = verifier_version_or_kernel_db
        elif isinstance(verifier_version_or_kernel_db, (str, Path)) and not str(verifier_version_or_kernel_db).replace(".", "").isdigit():
            self.kernel_db = KernelDatabase(Path(verifier_version_or_kernel_db))
        else:
            possible_dbs = (
                list(self.repo_dir.glob("*.db"))
                + list(self.repo_dir.glob("*.sqlite"))
                + list(self.repo_dir.parent.glob("*.db"))
                + list(self.repo_dir.parent.glob("*.sqlite"))
            )
            if possible_dbs:
                self.kernel_db = KernelDatabase(possible_dbs[0])
            else:
                self.kernel_db = KernelDatabase()

    def verify_candidate(
        self,
        manifest: ProposalManifest,
        candidate_worktree: Path,
        test_file_relative: str = "test_app.py",
    ) -> VerificationResult:
        """
        Executes sterile physical verification and persists receipt directly into KernelDatabase.
        Returns: VerificationResult (receipt_id, VerificationReceipt) with attribute forwarding.
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
                return VerificationResult(receipt_id, receipt)

        # Gate 1.5: AST Static Anti-Cheat Inspection
        ast_findings = scan_python_worktree(candidate_worktree)
        if ast_findings:
            first_finding = ast_findings[0]
            trace_summary = "\n".join(f.render() for f in ast_findings[:10])
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
                failure_signature=compute_failure_signature(
                    f"AST Anti-Cheat violation in {first_finding.filename}: {first_finding.rule_id}"
                ),
                execution_trace=f"AST Anti-Cheat scan detected prohibited constructs:\n{trace_summary}",
                timestamp=now,
            )
            receipt_id = self.kernel_db.record_verified_receipt(receipt)
            receipt.receipt_id = receipt_id
            return VerificationResult(receipt_id, receipt)

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
            return VerificationResult(receipt_id, receipt)

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
            return VerificationResult(receipt_id, receipt)

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
                return VerificationResult(receipt_id, receipt)

        # Gate 5: Sterile Subprocess Pytest Execution
        clean_env = build_sterile_environment(worktree_path=candidate_worktree)


        test_target = self.canonical_fixtures_dir / test_file_relative
        if not test_target.exists():
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
                failure_signature=compute_failure_signature(f"Missing canonical test file: {test_file_relative}"),
                execution_trace=f"Target fixture '{test_target}' does not exist.",
                timestamp=now,
            )
            receipt_id = self.kernel_db.record_verified_receipt(receipt)
            receipt.receipt_id = receipt_id
            return VerificationResult(receipt_id, receipt)

        cmd = [sys.executable, "-m", "pytest", str(test_target), "-v", "--tb=short"]
        try:
            test_proc = subprocess.run(
                cmd,
                cwd=candidate_worktree,
                env=clean_env,
                capture_output=True,
                text=True,
                timeout=30.0,
            )
            out_str = test_proc.stdout + "\n" + test_proc.stderr
            returncode = test_proc.returncode
        except subprocess.TimeoutExpired:
            returncode = -1
            out_str = "Execution timed out after 30.0s."

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
                failure_signature=compute_failure_signature("Canonical fixture digest mutated during execution"),
                execution_trace="Canonical acceptance fixtures were mutated during candidate test execution.",
                timestamp=now,
            )
            receipt_id = self.kernel_db.record_verified_receipt(receipt)
            receipt.receipt_id = receipt_id
            return VerificationResult(receipt_id, receipt)

        # Gate 7: Zero Tests Collected Check
        if "collected 0 items" in out_str:
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
                failure_signature=compute_failure_signature("Zero tests collected in candidate verification"),
                execution_trace="Zero tests collected: Pytest reported 0 test items collected.",
                timestamp=now,
            )
            receipt_id = self.kernel_db.record_verified_receipt(receipt)
            receipt.receipt_id = receipt_id
            return VerificationResult(receipt_id, receipt)

        # Gate 8: Outcome Classification
        if returncode == 0:
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
                failure_classification=None,
                failure_signature=None,
                execution_trace=out_str,
                timestamp=now,
            )
        else:
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
                failure_signature=compute_failure_signature(out_str[:256]),
                execution_trace=out_str,
                timestamp=now,
            )

        receipt_id = self.kernel_db.record_verified_receipt(receipt)
        receipt.receipt_id = receipt_id
        return VerificationResult(receipt_id, receipt)

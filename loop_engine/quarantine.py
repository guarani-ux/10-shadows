"""
loop_engine/quarantine.py
Atomic, path-safe, symlink-resistant quarantine manager with KernelDatabase persistence.
"""

import json
import os
import shutil
import tempfile
import time
from pathlib import Path
from typing import Optional

from loop_engine.kernel_db import KernelDatabase
from loop_engine.schema import FailureClassification, QuarantineRecord, VerificationReceipt


class PathTraversalEscapeError(Exception):
    """Raised when a candidate or quarantine path attempts a path traversal or symlink escape."""

    pass


class QuarantineManager:
    def __init__(self, quarantine_base_dir: Path, kernel_db: Optional[KernelDatabase] = None):
        self.base_dir = quarantine_base_dir.resolve()
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self.kernel_db = kernel_db

    def preserve_candidate(
        self,
        task_id: str,
        worktree_path: Path,
        receipt: VerificationReceipt,
        failure_signature: str,
    ) -> QuarantineRecord:
        """
        Safely copies candidate artifacts, detects symlinks/traversals, writes forensics manifest,
        and records entry into KernelDatabase.
        """
        # Validate path safety
        resolved_wt = worktree_path.resolve()
        if ".." in str(worktree_path) or not resolved_wt.exists():
            raise PathTraversalEscapeError(f"Invalid worktree path: {worktree_path}")

        timestamp = time.time()
        final_dir_name = f"{task_id}_{int(timestamp)}"
        final_dir = (self.base_dir / final_dir_name).resolve()

        if not str(final_dir).startswith(str(self.base_dir)):
            raise PathTraversalEscapeError(f"Quarantine destination '{final_dir}' escapes base directory.")

        # Create temporary staging directory in quarantine base for atomic operation
        temp_stage = Path(tempfile.mkdtemp(dir=self.base_dir, prefix=".tmp_q_"))
        try:
            snapshot_dir = temp_stage / "candidate_snapshot"
            snapshot_dir.mkdir(parents=True, exist_ok=True)

            # Safely copy files avoiding symlinks
            for root, dirs, files in os.walk(resolved_wt):
                rel_root = Path(root).relative_to(resolved_wt)
                target_root = snapshot_dir / rel_root
                target_root.mkdir(parents=True, exist_ok=True)

                for f in files:
                    if f.startswith(".git") or f.endswith(".pyc") or f == "__pycache__":
                        continue
                    src_file = Path(root) / f
                    if src_file.is_symlink():
                        # Detect symlink escape
                        real_target = src_file.resolve()
                        if not str(real_target).startswith(str(resolved_wt)):
                            raise PathTraversalEscapeError(f"Symlink '{src_file}' escapes worktree root.")
                        continue
                    dst_file = target_root / f
                    shutil.copy2(src_file, dst_file)

            # Write forensics manifest
            manifest_data = {
                "task_id": task_id,
                "candidate_commit_sha": receipt.candidate_commit_sha,
                "candidate_tree_sha": receipt.candidate_tree_sha,
                "physical_tree_hash": receipt.physical_tree_hash,
                "failure_classification": receipt.failure_classification.value
                if receipt.failure_classification
                else None,
                "failure_signature": failure_signature,
                "execution_trace": receipt.execution_trace or "",
                "timestamp": timestamp,
            }
            (temp_stage / "manifest.json").write_text(json.dumps(manifest_data, indent=2), encoding="utf-8")

            # Atomic rename to final directory
            if final_dir.exists():
                shutil.rmtree(final_dir, ignore_errors=True)
            os.replace(temp_stage, final_dir)

        except Exception:
            if temp_stage.exists():
                shutil.rmtree(temp_stage, ignore_errors=True)
            raise

        record = QuarantineRecord(
            quarantine_id=None,
            task_id=task_id,
            quarantine_dir=str(final_dir),
            candidate_commit_sha=receipt.candidate_commit_sha,
            failure_classification=receipt.failure_classification or FailureClassification.CANDIDATE_FAILURE,
            failure_signature=failure_signature,
            execution_trace=receipt.execution_trace or "",
            timestamp=timestamp,
        )

        if self.kernel_db:
            q_id = self.kernel_db.record_quarantine_entry(record)
            record.quarantine_id = q_id

        return record

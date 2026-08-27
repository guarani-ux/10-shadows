import os
import shutil
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

import tempfile

# Workspace root
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
WORKTREES_ROOT = Path(tempfile.gettempdir()) / "10_shadows_worktrees"


class GitWorktreeError(Exception):
    """Raised when a Git worktree operation fails."""
    pass


def run_git(args: list[str], cwd: Optional[Path] = None) -> Tuple[int, str, str]:
    """Runs a git command synchronously."""
    work_dir = cwd or PROJECT_ROOT
    proc = subprocess.run(
        ["git"] + args,
        cwd=str(work_dir),
        capture_output=True,
        text=True,
        stdin=subprocess.DEVNULL,
    )
    return proc.returncode, proc.stdout.strip(), proc.stderr.strip()


class GitWorktreeHarness:
    """
    Industrial-Grade Ephemeral Git Worktree Isolation Harness.
    Guarantees:
    - Zero host codebase pollution during candidate execution.
    - Automatic tear-down of failed candidate branches.
    - Immutable Git commit SHAs as physical verification receipts.
    """

    def __init__(self, worktrees_dir: Optional[Path] = None):
        self.worktrees_dir = worktrees_dir or WORKTREES_ROOT
        self.worktrees_dir.mkdir(parents=True, exist_ok=True)

    def create_sandbox(self, task_id: str) -> Tuple[Path, str]:
        """
        Creates an isolated Git worktree branch for the given task.
        Returns (worktree_path: Path, branch_name: str).
        """
        timestamp = int(time.time() * 1000) % 10000000
        safe_task_id = "".join(c if c.isalnum() or c in "_-" else "_" for c in task_id)
        branch_name = f"sandbox/{safe_task_id}_{timestamp}"
        worktree_path = self.worktrees_dir / f"wt_{safe_task_id}_{timestamp}"

        # Invariant: Create branch and mount worktree
        code, out, err = run_git(["worktree", "add", "-b", branch_name, str(worktree_path), "HEAD"])
        if code != 0:
            raise GitWorktreeError(f"Failed to create git worktree '{branch_name}': {err}")

        return worktree_path, branch_name

    def destroy_sandbox(self, worktree_path: Path, branch_name: str) -> None:
        """
        Forcefully removes the worktree and prunes the temporary branch.
        Leaves the master branch completely pristine.
        """
        if worktree_path.exists():
            run_git(["worktree", "remove", "--force", str(worktree_path)])
            if worktree_path.exists():
                try:
                    shutil.rmtree(worktree_path, ignore_errors=True)
                except Exception:
                    pass

        run_git(["worktree", "prune"])
        run_git(["branch", "-D", branch_name])

    def commit_and_merge(
        self,
        worktree_path: Path,
        branch_name: str,
        commit_message: str,
    ) -> Dict[str, Any]:
        """
        Stages all changes in the sandbox, commits them, merges into current HEAD,
        and returns the immutable Git commit SHA.
        """
        # 1. Stage in worktree
        code, out, err = run_git(["add", "-A"], cwd=worktree_path)
        if code != 0:
            self.destroy_sandbox(worktree_path, branch_name)
            raise GitWorktreeError(f"Git add failed in sandbox: {err}")

        # Check if there are changes to commit
        code, status_out, _ = run_git(["status", "--porcelain"], cwd=worktree_path)
        if not status_out:
            # No changes made
            self.destroy_sandbox(worktree_path, branch_name)
            return {"status": "NOOP", "commit_sha": None, "branch": branch_name}

        # 2. Commit in worktree (bypass hook for internal staging worktree)
        code, out, err = run_git(["commit", "--no-verify", "-m", commit_message], cwd=worktree_path)
        if code != 0:
            self.destroy_sandbox(worktree_path, branch_name)
            raise GitWorktreeError(f"Git commit failed in sandbox: {err}")

        # 3. Get commit SHA
        code, commit_sha, _ = run_git(["rev-parse", "HEAD"], cwd=worktree_path)

        # 4. Merge back to main repository
        code, out, err = run_git(["merge", "--ff-only", branch_name])
        if code != 0:
            # Fallback to standard merge if ff-only is not clean
            code, out, err = run_git(["merge", "-m", f"merge: {commit_message}", branch_name])
            if code != 0:
                self.destroy_sandbox(worktree_path, branch_name)
                raise GitWorktreeError(f"Git merge failed back to main: {err}")

        # 5. Clean up ephemeral worktree
        self.destroy_sandbox(worktree_path, branch_name)

        return {
            "status": "MERGED",
            "commit_sha": commit_sha,
            "commit_message": commit_message,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

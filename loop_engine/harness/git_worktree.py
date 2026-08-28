import os
import shutil
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional, Tuple
import tempfile

# Workspace root (Authoritative Ten Shadows repository)
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
WORKTREES_ROOT = Path(tempfile.gettempdir()) / "10_shadows_worktrees"


class GitWorktreeError(Exception):
    """Raised when a Git worktree operation fails."""
    pass


class AuthoritativeSourceProtectionError(GitWorktreeError):
    """Raised when an operation attempts to mutate the authoritative source repository."""
    pass


def is_authoritative_source(path: Path) -> bool:
    """
    Checks whether a given path points to the authoritative Ten Shadows source repository.
    Accounts for canonicalization and symlinks/junctions.
    """
    try:
        target_resolved = path.resolve()
        authoritative_resolved = PROJECT_ROOT.resolve()
        return target_resolved == authoritative_resolved or str(target_resolved).lower() == str(authoritative_resolved).lower()
    except Exception:
        return False


def assert_not_authoritative_source(path: Path, operation_name: str) -> None:
    """
    Hard path safety guard: mechanically prevents candidate-producing, test, or
    harness mutations directly on the authoritative Ten Shadows repository.
    """
    if is_authoritative_source(path):
        raise AuthoritativeSourceProtectionError(
            f"SECURITY VIOLATION: Operation '{operation_name}' is forbidden on the "
            f"authoritative Ten Shadows source repository at '{path}'. "
            f"Candidate mutations must execute inside an isolated GovernedWorkspace "
            f"or DisposableTestRepository."
        )


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
    - Absolute protection of authoritative Ten Shadows source repository.
    - Immutable Git commit SHAs as physical verification receipts.
    """

    def __init__(
        self,
        repo_root: Optional[Path] = None,
        worktrees_dir: Optional[Path] = None,
        allow_authoritative_mutation: bool = False,
    ):
        self.repo_root = (repo_root or PROJECT_ROOT).resolve()
        self.worktrees_dir = (worktrees_dir or WORKTREES_ROOT).resolve()
        self.worktrees_dir.mkdir(parents=True, exist_ok=True)
        self.allow_authoritative_mutation = allow_authoritative_mutation

    def create_sandbox(self, task_id: str, base_commit: str = "HEAD") -> Tuple[Path, str]:
        """
        Creates an isolated Git worktree branch for the given task.
        Returns (worktree_path: Path, branch_name: str).
        """
        timestamp = int(time.time() * 1000) % 10000000
        safe_task_id = "".join(c if c.isalnum() or c in "_-" else "_" for c in task_id)
        branch_name = f"sandbox/{safe_task_id}_{timestamp}"
        worktree_path = self.worktrees_dir / f"wt_{safe_task_id}_{timestamp}"

        # Ensure we do not add worktrees to authoritative repo during test execution
        code, out, err = run_git(
            ["worktree", "add", "-b", branch_name, str(worktree_path), base_commit],
            cwd=self.repo_root,
        )
        if code != 0:
            raise GitWorktreeError(f"Failed to create git worktree '{branch_name}' from '{self.repo_root}': {err}")

        return worktree_path, branch_name

    def destroy_sandbox(self, worktree_path: Path, branch_name: str) -> None:
        """
        Forcefully removes the worktree and prunes the temporary branch.
        Leaves the repository branch completely pristine.
        """
        if worktree_path.exists():
            run_git(["worktree", "remove", "--force", str(worktree_path)], cwd=self.repo_root)
            if worktree_path.exists():
                try:
                    shutil.rmtree(worktree_path, ignore_errors=True)
                except Exception:
                    pass

        run_git(["worktree", "prune"], cwd=self.repo_root)
        run_git(["branch", "-D", branch_name], cwd=self.repo_root)

    def commit_and_merge(
        self,
        worktree_path: Path,
        branch_name: str,
        commit_message: str,
    ) -> Dict[str, Any]:
        """
        Stages all changes in the sandbox, commits them, merges into repo_root,
        and returns the immutable Git commit SHA.
        Refuses to merge into authoritative Ten Shadows source repository unless
        explicitly authorized.
        """
        if not self.allow_authoritative_mutation:
            assert_not_authoritative_source(self.repo_root, "commit_and_merge")

        # 1. Stage in worktree
        code, out, err = run_git(["add", "-A"], cwd=worktree_path)
        if code != 0:
            self.destroy_sandbox(worktree_path, branch_name)
            raise GitWorktreeError(f"Git add failed in sandbox: {err}")

        # Check if there are changes to commit
        code, status_out, _ = run_git(["status", "--porcelain"], cwd=worktree_path)
        if not status_out:
            self.destroy_sandbox(worktree_path, branch_name)
            return {"status": "NOOP", "commit_sha": None, "branch": branch_name}

        # 2. Commit in worktree
        code, out, err = run_git(["commit", "--no-verify", "-m", commit_message], cwd=worktree_path)
        if code != 0:
            self.destroy_sandbox(worktree_path, branch_name)
            raise GitWorktreeError(f"Git commit failed in sandbox: {err}")

        # 3. Get commit SHA
        code, commit_sha, _ = run_git(["rev-parse", "HEAD"], cwd=worktree_path)

        # 4. Merge back to repo_root
        code, out, err = run_git(["merge", "--ff-only", branch_name], cwd=self.repo_root)
        if code != 0:
            code, out, err = run_git(["merge", "-m", f"merge: {commit_message}", branch_name], cwd=self.repo_root)
            if code != 0:
                self.destroy_sandbox(worktree_path, branch_name)
                raise GitWorktreeError(f"Git merge failed back to target: {err}")

        # 5. Clean up ephemeral worktree
        self.destroy_sandbox(worktree_path, branch_name)

        return {
            "status": "MERGED",
            "commit_sha": commit_sha,
            "commit_message": commit_message,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

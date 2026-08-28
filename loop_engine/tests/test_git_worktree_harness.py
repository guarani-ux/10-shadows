import subprocess
import time
from pathlib import Path
import tempfile
import pytest

from loop_engine.harness.git_worktree import (
    GitWorktreeHarness,
    AuthoritativeSourceProtectionError,
    PROJECT_ROOT,
    run_git,
)


@pytest.fixture
def disposable_repo():
    """
    Creates an isolated, temporary Git repository for testing worktree mechanics.
    Leaves the authoritative Ten Shadows source repository completely untouched.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        repo_path = Path(tmpdir).resolve()
        # Initialize disposable repo
        subprocess.run(["git", "init"], cwd=str(repo_path), check=True, capture_output=True)
        subprocess.run(["git", "config", "user.name", "Test Harness"], cwd=str(repo_path), check=True, capture_output=True)
        subprocess.run(["git", "config", "user.email", "test@ten-shadows.local"], cwd=str(repo_path), check=True, capture_output=True)
        
        # Create initial baseline commit A
        baseline_file = repo_path / "plan.md"
        baseline_file.write_text("# Initial Plan", encoding="utf-8")
        subprocess.run(["git", "add", "plan.md"], cwd=str(repo_path), check=True, capture_output=True)
        subprocess.run(["git", "commit", "-m", "chore: initial baseline commit"], cwd=str(repo_path), check=True, capture_output=True)

        yield repo_path


def test_git_worktree_sandbox_lifecycle_in_disposable_repo(disposable_repo):
    """
    Verifies that worktree sandboxes, candidate generation, and atomic merges
    operate correctly inside a disposable test repository without touching the authoritative repo.
    """
    source_head_before, _, _ = run_git(["rev-parse", "HEAD"], cwd=PROJECT_ROOT)
    
    with tempfile.TemporaryDirectory() as wt_dir:
        harness = GitWorktreeHarness(
            repo_root=disposable_repo,
            worktrees_dir=Path(wt_dir),
            allow_authoritative_mutation=False,
        )
        task_id = "test_lifecycle_task"

        # 1. Create sandbox
        worktree_path, branch_name = harness.create_sandbox(task_id)
        assert worktree_path.exists()
        assert (worktree_path / "plan.md").exists()

        # 2. Write an ephemeral test file in sandbox
        unique_name = f"candidate_{int(time.time() * 1000)}.txt"
        test_artifact = worktree_path / unique_name
        test_artifact.write_text("Immutable Git Verification", encoding="utf-8")

        # 3. Commit and merge into the disposable repo
        result = harness.commit_and_merge(
            worktree_path=worktree_path,
            branch_name=branch_name,
            commit_message="test: verify git worktree atomic commit",
        )

        assert result["status"] == "MERGED"
        assert result["commit_sha"] is not None
        assert len(result["commit_sha"]) >= 40

        # 4. Verify artifact now exists in disposable repository
        target_artifact = disposable_repo / unique_name
        assert target_artifact.exists()
        assert target_artifact.read_text(encoding="utf-8") == "Immutable Git Verification"

        # 5. Verify sandbox was cleanly destroyed
        assert not worktree_path.exists()

    # Invariant: Authoritative source repo HEAD MUST be identical
    source_head_after, _, _ = run_git(["rev-parse", "HEAD"], cwd=PROJECT_ROOT)
    assert source_head_after == source_head_before, "Authoritative repository HEAD was polluted!"
    assert not (PROJECT_ROOT / unique_name).exists(), "Authoritative repository working tree was polluted!"


def test_git_worktree_discard_on_abort_in_disposable_repo(disposable_repo):
    """
    Verifies that aborted sandboxes are cleanly torn down without polluting the target repository.
    """
    with tempfile.TemporaryDirectory() as wt_dir:
        harness = GitWorktreeHarness(
            repo_root=disposable_repo,
            worktrees_dir=Path(wt_dir),
        )
        task_id = "test_abort_task"

        # 1. Create sandbox
        worktree_path, branch_name = harness.create_sandbox(task_id)
        assert worktree_path.exists()

        # 2. Write bad code in sandbox
        bad_artifact = worktree_path / "unwanted_dirty_file.py"
        bad_artifact.write_text("def broken(): pass", encoding="utf-8")

        # 3. Discard sandbox without committing
        harness.destroy_sandbox(worktree_path, branch_name)

        # 4. Ensure disposable repository was never polluted
        assert not (disposable_repo / "unwanted_dirty_file.py").exists()
        assert not worktree_path.exists()


def test_authoritative_source_mutation_blocked():
    """
    Hard security check: attempting to merge into the authoritative source repository
    must be mechanically blocked with AuthoritativeSourceProtectionError.
    """
    harness = GitWorktreeHarness(
        repo_root=PROJECT_ROOT,
        allow_authoritative_mutation=False,
    )
    
    with pytest.raises(AuthoritativeSourceProtectionError) as exc_info:
        # Mock worktree path and branch name to test safety gate
        harness.commit_and_merge(
            worktree_path=Path("dummy_path"),
            branch_name="sandbox/dummy_branch",
            commit_message="illegal direct mutation",
        )

    assert "forbidden on the authoritative Ten Shadows source repository" in str(exc_info.value)

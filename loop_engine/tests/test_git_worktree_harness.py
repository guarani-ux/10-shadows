import pytest
from pathlib import Path
from loop_engine.harness.git_worktree import GitWorktreeHarness, run_git, PROJECT_ROOT


def test_git_worktree_sandbox_lifecycle():
    harness = GitWorktreeHarness()
    task_id = "test_lifecycle_task"

    # 1. Create sandbox
    worktree_path, branch_name = harness.create_sandbox(task_id)
    assert worktree_path.exists()
    assert (worktree_path / "plan.md").exists()

    # 2. Write an ephemeral test file in sandbox
    test_artifact = worktree_path / "scratch_candidate.txt"
    test_artifact.write_text("Immutable Git Verification", encoding="utf-8")

    # 3. Commit and merge
    result = harness.commit_and_merge(
        worktree_path=worktree_path,
        branch_name=branch_name,
        commit_message="test: verify git worktree atomic commit",
    )

    assert result["status"] == "MERGED"
    assert result["commit_sha"] is not None
    assert len(result["commit_sha"]) >= 40

    # 4. Verify artifact now exists in main repository
    main_artifact = PROJECT_ROOT / "scratch_candidate.txt"
    assert main_artifact.exists()
    assert main_artifact.read_text(encoding="utf-8") == "Immutable Git Verification"

    # Clean up test artifact from main
    main_artifact.unlink()
    run_git(["commit", "-am", "cleanup: remove test_git_worktree_harness artifact"])

    # 5. Verify sandbox was cleanly destroyed
    assert not worktree_path.exists()


def test_git_worktree_discard_on_abort():
    harness = GitWorktreeHarness()
    task_id = "test_abort_task"

    # 1. Create sandbox
    worktree_path, branch_name = harness.create_sandbox(task_id)
    assert worktree_path.exists()

    # 2. Write bad code in sandbox
    bad_artifact = worktree_path / "unwanted_dirty_file.py"
    bad_artifact.write_text("def broken(): pass", encoding="utf-8")

    # 3. Discard sandbox without committing
    harness.destroy_sandbox(worktree_path, branch_name)

    # 4. Ensure main repository was never polluted
    assert not (PROJECT_ROOT / "unwanted_dirty_file.py").exists()
    assert not worktree_path.exists()

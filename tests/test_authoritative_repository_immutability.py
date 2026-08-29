import subprocess
import tempfile
from pathlib import Path

import pytest

from loop_engine.harness.git_worktree import (
    PROJECT_ROOT,
    AuthoritativeSourceProtectionError,
    GitWorktreeHarness,
    is_authoritative_source,
    run_git,
)


def test_authoritative_repo_head_remains_unchanged_during_worktree_runs():
    """
    Source-Repository Immutability Regression Test (Mission J / Step 6).
    Proves that running Git worktree lifecycle tests does NOT mutate the
    authoritative Ten Shadows repository HEAD, status, or branch list.
    """
    # 1. Capture Authoritative State Before
    code, head_before, _ = run_git(["rev-parse", "HEAD"], cwd=PROJECT_ROOT)
    assert code == 0
    code, status_before, _ = run_git(["status", "--porcelain"], cwd=PROJECT_ROOT)
    assert code == 0
    code, branches_before, _ = run_git(["branch"], cwd=PROJECT_ROOT)
    assert code == 0

    # 2. Run real worktree lifecycle inside a Disposable Test Repository
    with tempfile.TemporaryDirectory() as tmp_repo:
        repo_path = Path(tmp_repo).resolve()
        subprocess.run(["git", "init"], cwd=str(repo_path), check=True, capture_output=True)
        subprocess.run(
            ["git", "config", "user.name", "Test Harness"], cwd=str(repo_path), check=True, capture_output=True
        )
        subprocess.run(
            ["git", "config", "user.email", "test@ten-shadows.local"],
            cwd=str(repo_path),
            check=True,
            capture_output=True,
        )

        baseline_file = repo_path / "spec.txt"
        baseline_file.write_text("baseline spec v1", encoding="utf-8")
        subprocess.run(["git", "add", "spec.txt"], cwd=str(repo_path), check=True, capture_output=True)
        subprocess.run(
            ["git", "commit", "-m", "chore: baseline commit A"], cwd=str(repo_path), check=True, capture_output=True
        )

        with tempfile.TemporaryDirectory() as wt_dir:
            harness = GitWorktreeHarness(repo_root=repo_path, worktrees_dir=Path(wt_dir))

            # Execute multiple sandboxes
            wt1, b1 = harness.create_sandbox("task_pass")
            (wt1 / "change1.txt").write_text("governed change 1", encoding="utf-8")
            res1 = harness.commit_and_merge(wt1, b1, "feat: governed change 1")
            assert res1["status"] == "MERGED"

            wt2, b2 = harness.create_sandbox("task_abort")
            (wt2 / "bad.txt").write_text("bad change", encoding="utf-8")
            harness.destroy_sandbox(wt2, b2)

    # 3. Capture Authoritative State After
    code, head_after, _ = run_git(["rev-parse", "HEAD"], cwd=PROJECT_ROOT)
    assert code == 0
    code, status_after, _ = run_git(["status", "--porcelain"], cwd=PROJECT_ROOT)
    assert code == 0
    code, branches_after, _ = run_git(["branch"], cwd=PROJECT_ROOT)
    assert code == 0

    # 4. Strict Immutability Invariants
    assert head_after == head_before, f"Authoritative HEAD diverged! Before: {head_before}, After: {head_after}"
    assert status_after == status_before, f"Authoritative working tree dirtied! Status: {status_after}"
    assert branches_after == branches_before, (
        f"Authoritative branches leaked! Before: {branches_before}, After: {branches_after}"
    )

    # 5. Assert no candidate files leaked into authoritative root
    candidate_files = list(PROJECT_ROOT.glob("candidate_*.txt"))
    assert len(candidate_files) == 0, f"Found leaked candidate files in authoritative repo: {candidate_files}"


def test_is_authoritative_source_detection():
    """
    Verifies that is_authoritative_source correctly identifies the host repo.
    """
    assert is_authoritative_source(PROJECT_ROOT) is True
    assert is_authoritative_source(PROJECT_ROOT / "loop_engine") is False
    with tempfile.TemporaryDirectory() as tmp:
        assert is_authoritative_source(Path(tmp)) is False


def test_direct_authoritative_mutation_hard_rejected():
    """
    Verifies that attempting to commit and merge directly to PROJECT_ROOT
    is strictly rejected by AuthoritativeSourceProtectionError.
    """
    harness = GitWorktreeHarness(repo_root=PROJECT_ROOT, allow_authoritative_mutation=False)
    with pytest.raises(AuthoritativeSourceProtectionError):
        harness.commit_and_merge(Path("wt"), "branch", "illegal commit")

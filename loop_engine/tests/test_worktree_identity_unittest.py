"""Real Git regression: repeated requests must not share a millisecond identity."""
import importlib.util
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

MODULE = Path(__file__).resolve().parents[1] / 'harness' / 'git_worktree.py'
spec = importlib.util.spec_from_file_location('worktree_under_test', MODULE)
worktree = importlib.util.module_from_spec(spec)
spec.loader.exec_module(worktree)


class WorktreeIdentity(unittest.TestCase):
    def test_same_task_same_clock_creates_distinct_real_worktrees(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            repo = root / 'repo'
            repo.mkdir()

            def git(*args):
                return subprocess.run(['git', '-C', str(repo), *args], check=True,
                                      capture_output=True, text=True).stdout.strip()

            git('init')
            git('config', 'user.name', 'Regression Fixture')
            git('config', 'user.email', 'fixture@example.invalid')
            (repo / 'source.txt').write_text('unchanged\n')
            git('add', 'source.txt')
            git('commit', '-m', 'fixture baseline')
            original_head = git('rev-parse', 'HEAD')
            harness = worktree.GitWorktreeHarness(repo_root=repo, worktrees_dir=root / 'sandboxes')
            created = []
            try:
                # Only the clock is fixed. Both worktree operations execute real Git.
                with patch('time.time', return_value=1700000000.123):
                    created.append(harness.create_sandbox('repeated-task'))
                    created.append(harness.create_sandbox('repeated-task'))
                self.assertNotEqual(created[0][0], created[1][0])
                self.assertNotEqual(created[0][1], created[1][1])
                listing = git('worktree', 'list', '--porcelain')
                for path, branch in created:
                    self.assertIn(str(path), listing)
                    self.assertIn('refs/heads/' + branch, listing)
                    self.assertEqual((path / 'source.txt').read_text(), 'unchanged\n')
                self.assertEqual(git('rev-parse', 'HEAD'), original_head)
                self.assertEqual(git('status', '--porcelain'), '')
            finally:
                # Authorized fixture cleanup: only worktrees created in this tempdir.
                for path, branch in created:
                    harness.destroy_sandbox(path, branch)


if __name__ == '__main__':
    unittest.main(verbosity=2)

"""
scripts/install_git_hooks.py
Installs mechanical Git pre-commit hook that prevents commits on failing tests
or unresolved merge conflicts.
"""

import os
import stat
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
GIT_HOOKS_DIR = REPO_ROOT / ".git" / "hooks"
PRE_COMMIT_HOOK_PATH = GIT_HOOKS_DIR / "pre-commit"

HOOK_SHELL_SCRIPT = """#!/bin/sh
# TEN SHADOWS MECHANICAL PRE-COMMIT VERIFICATION GATE
# Enforces automated test suite pass and clean working tree before committing.

echo "[GIT PRE-COMMIT] Executing mechanical test verification..."

# 1. Reject unresolved merge conflict markers in staged files
CONFLICT_FILES=$(git diff --cached -G'^(<{7}|={7}|>{7})' --name-only 2>/dev/null | grep -v 'install_git_hooks.py' | grep -v 'pre-commit' | grep -v 'test_mechanical_enforcement.py')
if [ -n "$CONFLICT_FILES" ]; then
    echo "[GIT PRE-COMMIT] ERROR: Unresolved merge conflict markers detected in staged files:"
    echo "$CONFLICT_FILES"
    exit 1
fi

# 2. Run pytest suite from repository root in sterile git environment
unset GIT_DIR GIT_WORK_TREE GIT_INDEX_FILE GIT_OBJECT_DIRECTORY GIT_ALTERNATE_OBJECT_DIRECTORIES GIT_PREFIX
python -m pytest -q
TEST_EXIT_CODE=$?

if [ $TEST_EXIT_CODE -ne 0 ]; then
    echo "[GIT PRE-COMMIT] ERROR: Pre-commit test suite verification failed with exit code $TEST_EXIT_CODE."
    echo "[GIT PRE-COMMIT] Commit aborted. Fix failing tests before committing."
    exit 1
fi

echo "[GIT PRE-COMMIT] Verification PASSED. Commit accepted."
exit 0
"""


def install_hooks() -> bool:
    """Installs the pre-commit hook into .git/hooks/."""
    if not GIT_HOOKS_DIR.exists():
        print(f"[ERROR] .git/hooks directory not found at {GIT_HOOKS_DIR}")
        return False

    PRE_COMMIT_HOOK_PATH.write_text(HOOK_SHELL_SCRIPT, encoding="utf-8", newline="\n")

    # Make executable on Unix/Mac
    try:
        current_stat = os.stat(PRE_COMMIT_HOOK_PATH)
        os.chmod(PRE_COMMIT_HOOK_PATH, current_stat.st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    except Exception as e:
        print(f"[WARN] Could not set executable permission: {e}")

    print(f"[SUCCESS] Pre-commit hook installed at {PRE_COMMIT_HOOK_PATH}")
    return True


if __name__ == "__main__":
    success = install_hooks()
    sys.exit(0 if success else 1)

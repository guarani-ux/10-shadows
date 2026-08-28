"""
tests/test_ast_guard.py
Adversarial TDD Acceptance Suite for AST Static Anti-Cheat Guard.
Verifies that prohibited dynamic evaluation, execution evasion, and test harness
tampering constructs are detected and blocked prior to subprocess test execution.
"""

import os
import subprocess
import tempfile
from pathlib import Path
import pytest

from loop_engine.ast_guard import (
    ASTAuditResult,
    ASTFinding,
    ASTViolationType,
    scan_ast,
    scan_python_file,
    scan_python_worktree,
)
from loop_engine.kernel_db import KernelDatabase
from loop_engine.schema import (
    FailureClassification,
    ProposalManifest,
    State,
    compute_env_fingerprint,
    compute_failure_signature,
    compute_spec_hash,
    compute_test_digest,
    compute_tree_hash,
)
from loop_engine.verifier_gate import PhysicalVerifierGate



class TestASTGuardCleanCode:
    def test_clean_python_code_passes(self):
        code = """
import math
from typing import List, Optional

def compute_summary(items: List[int]) -> Optional[float]:
    if not items:
        return None
    return math.fsum(items) / len(items)

class Calculator:
    def __init__(self, offset: float = 0.0):
        self.offset = offset

    def add(self, a: float, b: float) -> float:
        return a + b + self.offset
"""
        result = scan_ast(code, filename="clean_module.py")
        assert result.is_clean is True
        assert len(result.findings) == 0


class TestASTGuardAdversarialPayloads:
    def test_banned_eval_call_blocked(self):
        code = "def malicious(): return eval('1 + 1')"
        result = scan_ast(code, filename="eval_payload.py")
        assert result.is_clean is False
        assert any(f.violation_type == ASTViolationType.DYNAMIC_EVAL for f in result.findings)

    def test_banned_exec_call_blocked(self):
        code = "def execute_payload(payload): exec(payload)"
        result = scan_ast(code, filename="exec_payload.py")
        assert result.is_clean is False
        assert any(f.violation_type == ASTViolationType.DYNAMIC_EXEC for f in result.findings)

    def test_banned_compile_call_blocked(self):
        code = "code_obj = compile('x = 1', '<string>', 'exec')"
        result = scan_ast(code, filename="compile_payload.py")
        assert result.is_clean is False
        assert any(f.violation_type == ASTViolationType.DYNAMIC_COMPILE for f in result.findings)

    def test_banned_dunder_import_call_blocked(self):
        code = "os_mod = __import__('os')"
        result = scan_ast(code, filename="import_payload.py")
        assert result.is_clean is False
        assert any(f.violation_type == ASTViolationType.DYNAMIC_IMPORT for f in result.findings)

    def test_banned_globals_manipulation_blocked(self):
        code = "def wipe_env(): globals().clear()"
        result = scan_ast(code, filename="globals_payload.py")
        assert result.is_clean is False
        assert any(f.violation_type == ASTViolationType.GLOBAL_MUTATION for f in result.findings)

    def test_banned_sys_modules_tampering_blocked(self):
        code = """
import sys
def bypass_pytest():
    sys.modules['pytest'] = None
"""
        result = scan_ast(code, filename="sys_modules_payload.py")
        assert result.is_clean is False
        assert any(f.violation_type == ASTViolationType.HARNESS_TAMPERING for f in result.findings)

    def test_syntax_error_handled_gracefully(self):
        broken_code = "def unparseable_code(: invalid syntax"
        result = scan_ast(broken_code, filename="broken.py")
        assert result.is_clean is False
        assert any(f.violation_type == ASTViolationType.SYNTAX_ERROR for f in result.findings)


class TestASTGuardWorktreeScanning:
    def test_scan_worktree_detects_nested_violations(self, tmp_path: Path):
        worktree = tmp_path / "wt"
        worktree.mkdir()
        (worktree / "clean.py").write_text("def ok(): return 42\n", encoding="utf-8")
        
        sub = worktree / "subpackage"
        sub.mkdir()
        (sub / "nested_bad.py").write_text("def bad(): return eval('10')\n", encoding="utf-8")

        # Ignore .git and pycache
        git_dir = worktree / ".git"
        git_dir.mkdir()
        (git_dir / "git_internal.py").write_text("eval('ignore_me')\n", encoding="utf-8")

        findings = scan_python_worktree(worktree)
        assert len(findings) == 1
        assert "nested_bad.py" in findings[0].filename
        assert findings[0].violation_type == ASTViolationType.DYNAMIC_EVAL


class TestPhysicalVerifierGateASTIntegration:
    def test_verifier_gate_blocks_candidate_with_ast_cheat(self, tmp_path: Path):
        repo_dir = tmp_path / "repo"
        repo_dir.mkdir()
        subprocess.run(["git", "init", "-b", "main"], cwd=repo_dir, check=True, capture_output=True)
        subprocess.run(["git", "config", "user.name", "ASTBot"], cwd=repo_dir, check=True)
        subprocess.run(["git", "config", "user.email", "bot@zero.trust"], cwd=repo_dir, check=True)

        fixtures_dir = repo_dir / "canonical_fixtures"
        fixtures_dir.mkdir()
        (fixtures_dir / "test_app.py").write_text(
            "from app import run\ndef test_app(): assert run() == 42\n", encoding="utf-8"
        )
        (repo_dir / "app.py").write_text("def run(): return 42\n", encoding="utf-8")
        subprocess.run(["git", "add", "."], cwd=repo_dir, check=True)
        subprocess.run(["git", "commit", "-m", "init"], cwd=repo_dir, check=True)

        base_sha = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=repo_dir, capture_output=True, text=True, check=True
        ).stdout.strip()

        # Candidate branch with AST evasion attempt
        candidate_wt = tmp_path / "candidate_wt"
        subprocess.run(
            ["git", "worktree", "add", "-b", "feature-cheat", str(candidate_wt), "main"],
            cwd=repo_dir,
            check=True,
            capture_output=True,
        )

        # Inject eval() into candidate file
        (candidate_wt / "app.py").write_text("def run(): return eval('42')\n", encoding="utf-8")
        subprocess.run(["git", "add", "app.py"], cwd=candidate_wt, check=True)
        subprocess.run(["git", "commit", "-m", "cheat commit"], cwd=candidate_wt, check=True)

        cand_sha = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=candidate_wt, capture_output=True, text=True, check=True
        ).stdout.strip()
        cand_tree = subprocess.run(
            ["git", "rev-parse", "HEAD^{tree}"], cwd=candidate_wt, capture_output=True, text=True, check=True
        ).stdout.strip()

        db = KernelDatabase(tmp_path / "kernel.db")
        verifier = PhysicalVerifierGate(
            repo_dir=repo_dir,
            canonical_fixtures_dir=fixtures_dir,
            kernel_db=db,
        )

        env_fp = compute_env_fingerprint()
        manifest = ProposalManifest(
            task_id="task_ast_cheat",
            spec_hash=compute_spec_hash("test spec"),
            base_commit_sha=base_sha,
            candidate_commit_sha=cand_sha,
            candidate_tree_sha=cand_tree,
            verifier_version="2.0.0",
            acceptance_test_digest=compute_test_digest(fixtures_dir),
            env_fingerprint=env_fp,
            state=State.CANDIDATE_SEALED,
        )


        db.record_proposal(manifest)


        # Execute verifier gate
        result = verifier.verify_candidate(manifest, candidate_wt)
        assert result.status == State.BLOCKED
        assert result.failure_classification == FailureClassification.GOVERNOR_FAILURE
        assert "AST Anti-Cheat" in result.execution_trace


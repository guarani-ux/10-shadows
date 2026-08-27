"""
tests/test_mechanical_enforcement.py
Comprehensive mechanical enforcement verification test suite for Ten Shadows.

Validates:
1. Git Pre-Commit Hook installation & execution logic.
2. Verifier Daemon sterile isolation & secret stripping.
3. Verifier Daemon atomic replacement & permanent receipt ledger (.receipts/).
4. 3-Strike Governor ceiling enforcement.
5. Pre-Tool Audit Gate execution.
"""

import json
import os
import sqlite3
import subprocess
import sys
import tempfile
from pathlib import Path
import pytest

from loop_engine.kernel_db import KernelDatabase
from loop_engine.schema import FailureClassification
from loop_engine.verifier_daemon import (
    process_intent,
    build_sterile_environment,
    RECEIPTS_LEDGER_DIR,
)
from scripts.install_git_hooks import install_hooks, PRE_COMMIT_HOOK_PATH
from scripts.verify_plan_audit import verify_plan, is_exempt_path


# ---------------------------------------------------------------------------
# 1. Git Pre-Commit Hook Tests
# ---------------------------------------------------------------------------
def test_git_pre_commit_hook_installation():
    """Verifies that the pre-commit hook installer creates the hook with expected content."""
    success = install_hooks()
    assert success is True
    assert PRE_COMMIT_HOOK_PATH.exists()
    hook_content = PRE_COMMIT_HOOK_PATH.read_text(encoding="utf-8")
    assert "python -m pytest -q" in hook_content
    assert "TEN SHADOWS MECHANICAL PRE-COMMIT VERIFICATION GATE" in hook_content
    assert "CONFLICT_FILES" in hook_content


# ---------------------------------------------------------------------------
# 2. Sterile Isolation Environment Tests
# ---------------------------------------------------------------------------
def test_verifier_daemon_sterile_environment_strips_secrets(monkeypatch):
    """Verifies that the daemon execution environment strips host API keys and tokens."""
    monkeypatch.setenv("OPENAI_API_KEY", "sk-secret-key-12345")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-secret-67890")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "aws-secret-access")
    monkeypatch.setenv("SYSTEMROOT", "C:\\Windows")
    monkeypatch.setenv("PATH", "C:\\Windows\\System32")

    sterile = build_sterile_environment()

    assert "OPENAI_API_KEY" not in sterile
    assert "ANTHROPIC_API_KEY" not in sterile
    assert "AWS_SECRET_ACCESS_KEY" not in sterile
    assert "SYSTEMROOT" in sterile or "systemroot" in sterile
    assert "PYTHONPATH" in sterile
    assert sterile["PYTHONDONTWRITEBYTECODE"] == "1"


# ---------------------------------------------------------------------------
# 3. Verifier Daemon Promotion & Receipt Ledger Tests
# ---------------------------------------------------------------------------
def test_verifier_daemon_pass_and_atomic_promotion(tmp_path):
    """Verifies that a passing test command creates an immutable receipt and promotes the file."""
    db_path = tmp_path / "test_kernel.db"
    test_db = KernelDatabase(db_path=db_path)

    candidate_file = tmp_path / "candidate_app.py"
    candidate_file.write_text("def answer(): return 42\n", encoding="utf-8")

    target_file = tmp_path / "production_app.py"

    intent_file = tmp_path / "intent.json"
    intent_payload = {
        "task_id": "test_pass_task_001",
        "plan_hash": "plan_hash_abcdef123456",
        "git_diff_hash": "diff_hash_11223344",
        "candidate_path": str(candidate_file),
        "target_path": str(target_file),
        "test_command": "python -c \"import sys; sys.exit(0)\"",
    }
    intent_file.write_text(json.dumps(intent_payload), encoding="utf-8")

    receipt = process_intent(intent_file, kernel_db=test_db)

    assert receipt["status"] == "VERIFIED"
    assert receipt["exit_code"] == 0
    assert target_file.exists()
    assert target_file.read_text(encoding="utf-8") == "def answer(): return 42\n"

    # Verify receipt written to permanent ledger
    ledger_file = RECEIPTS_LEDGER_DIR / "test_pass_task_001_receipt.json"
    assert ledger_file.exists()
    ledger_data = json.loads(ledger_file.read_text(encoding="utf-8"))
    assert ledger_data["status"] == "VERIFIED"
    assert ledger_data["task_id"] == "test_pass_task_001"
    assert ledger_data["plan_hash"] == "plan_hash_abcdef123456"

    # Clean up test ledger file
    if ledger_file.exists():
        ledger_file.unlink()


def test_verifier_daemon_fail_rejection(tmp_path):
    """Verifies that a failing test command marks status as REJECTED, records a strike, and does not promote."""
    db_path = tmp_path / "test_kernel.db"
    test_db = KernelDatabase(db_path=db_path)

    candidate_file = tmp_path / "candidate_fail.py"
    candidate_file.write_text("def broken(): raise ValueError\n", encoding="utf-8")
    target_file = tmp_path / "target_fail.py"

    intent_file = tmp_path / "intent_fail.json"
    intent_payload = {
        "task_id": "test_fail_task_002",
        "plan_hash": "plan_hash_fail_123",
        "candidate_path": str(candidate_file),
        "target_path": str(target_file),
        "test_command": "python -c \"import sys; sys.stderr.write('AssertionError: test failed'); sys.exit(1)\"",
    }
    intent_file.write_text(json.dumps(intent_payload), encoding="utf-8")

    receipt = process_intent(intent_file, kernel_db=test_db)

    assert receipt["status"] == "REJECTED"
    assert receipt["exit_code"] == 1
    assert not target_file.exists()
    assert test_db.get_strikes("test_fail_task_002") == 1

    # Clean up ledger receipt
    ledger_file = RECEIPTS_LEDGER_DIR / "test_fail_task_002_receipt.json"
    if ledger_file.exists():
        ledger_file.unlink()


# ---------------------------------------------------------------------------
# 4. Strike Governor 3-Strike Ceiling Tests
# ---------------------------------------------------------------------------
def test_verifier_daemon_strike_ceiling_blocks_execution(tmp_path):
    """Verifies that a task with 3 strikes is forcefully BLOCKED without executing tests."""
    db_path = tmp_path / "test_kernel.db"
    test_db = KernelDatabase(db_path=db_path)

    task_id = "test_strike_exhausted_task"
    # Seed 3 strikes in SQLite
    for i in range(3):
        test_db.record_strike(task_id, FailureClassification.CANDIDATE_FAILURE, f"strike_{i}")

    assert test_db.get_strikes(task_id) == 3

    intent_file = tmp_path / "intent_blocked.json"
    intent_payload = {
        "task_id": task_id,
        "test_command": "python -c \"import sys; sys.exit(0)\"",
    }
    intent_file.write_text(json.dumps(intent_payload), encoding="utf-8")

    receipt = process_intent(intent_file, kernel_db=test_db)

    assert receipt["status"] == "BLOCKED"
    assert "3-strike failure ceiling" in receipt["error"]

    # Clean up ledger receipt
    ledger_file = RECEIPTS_LEDGER_DIR / f"{task_id}_receipt.json"
    if ledger_file.exists():
        ledger_file.unlink()


# ---------------------------------------------------------------------------
# 5. Pre-Tool Audit Gate Tests
# ---------------------------------------------------------------------------
def test_pre_tool_audit_gate_exempt_paths():
    """Verifies that non-production paths (scratch, tests, artifacts) are automatically allowed."""
    assert is_exempt_path("c:\\10 SHADOWS\\scratch\\debug.py") is True
    assert is_exempt_path("c:\\10 SHADOWS\\.gemini\\artifacts\\plan.md") is True
    assert is_exempt_path("c:\\10 SHADOWS\\plan.md") is True
    assert is_exempt_path("c:\\10 SHADOWS\\svris\\core\\db.py") is False


def test_pre_tool_audit_gate_production_path_evaluation():
    """Verifies that production modifications evaluate active plan validity."""
    payload_exempt = {
        "toolCall": {
            "name": "write_to_file",
            "args": {"TargetFile": "c:\\10 SHADOWS\\scratch\\temp.py"},
        }
    }
    res_exempt = verify_plan(payload_exempt)
    assert res_exempt["decision"] == "allow"

    payload_prod = {
        "toolCall": {
            "name": "write_to_file",
            "args": {"TargetFile": "c:\\10 SHADOWS\\loop_engine\\base.py"},
        }
    }
    res_prod = verify_plan(payload_prod)
    # With valid plan.md present in repo, decision should be allow
    assert res_prod["decision"] == "allow"

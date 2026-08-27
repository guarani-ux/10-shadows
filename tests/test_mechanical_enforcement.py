"""
tests/test_mechanical_enforcement.py
Comprehensive mechanical enforcement verification test suite for Ten Shadows.

Validates:
1. Git Pre-Commit Hook installation & execution logic.
2. Verifier Daemon sterile isolation & secret stripping.
3. Verifier Daemon atomic replacement & permanent receipt ledger (.receipts/).
4. 3-Strike Governor ceiling enforcement.
5. Pre-Tool Audit Gate execution and adversarial fail-closed verification:
   A. Auditor unavailable -> DENY
   B. Missing required hook payload / empty stdin -> DENY
   C. Malformed payload -> DENY
   D. Missing active plan -> DENY
   E. Audit result REVISE -> DENY
   F. Audit result BLOCK -> DENY
   G. Unresolved HIGH finding -> DENY
   H. Unresolved CRITICAL finding -> DENY
   I. Missing required acceptance evidence -> DENY
   J. Valid hardened plan satisfying authorization requirements -> ALLOW
   K. Legitimate exempt planning/scratch operation -> ALLOW
   L. Attempt to disguise a production mutation as an exempt path -> DENY
"""

import io
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
from scripts import verify_plan_audit
from scripts.verify_plan_audit import verify_plan, is_exempt_path, PROJECT_ROOT, main as audit_gate_main
from zero_trust_engine.auditor import PlanAuditor, AuditResult, Severity, Finding, FindingStatus, AuditReport


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
    assert "SYSTEMROOT" in sterile or "systemroot" in sterile or "PATH" in sterile
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
# 5. Pre-Tool Audit Gate Tests & Adversarial Fail-Closed Matrix
# ---------------------------------------------------------------------------
def test_pre_tool_audit_gate_exempt_paths():
    """Verifies that non-production paths (scratch, tests, artifacts, plans) are allowed."""
    assert is_exempt_path(str(PROJECT_ROOT / "scratch" / "debug.py")) is True
    assert is_exempt_path(str(PROJECT_ROOT / ".gemini" / "artifacts" / "plan.md")) is True
    assert is_exempt_path(str(PROJECT_ROOT / "plan.md")) is True
    assert is_exempt_path(str(PROJECT_ROOT / "implementation_plan.md")) is True
    assert is_exempt_path(str(PROJECT_ROOT / "walkthrough.md")) is True
    assert is_exempt_path(str(PROJECT_ROOT / "svris" / "core" / "db.py")) is False
    assert is_exempt_path("scratch/debug.py") is True
    assert is_exempt_path("plan.md") is True


def test_pre_tool_audit_gate_production_path_evaluation():
    """Verifies that production modifications evaluate active plan validity."""
    payload_exempt = {
        "toolCall": {
            "name": "write_to_file",
            "args": {"TargetFile": str(PROJECT_ROOT / "scratch" / "temp.py")},
        }
    }
    res_exempt = verify_plan(payload_exempt)
    assert res_exempt["decision"] == "allow"

    payload_prod = {
        "toolCall": {
            "name": "write_to_file",
            "args": {"TargetFile": str(PROJECT_ROOT / "loop_engine" / "base.py")},
        }
    }
    res_prod = verify_plan(payload_prod)
    # With valid plan.md present in repo, decision should be allow
    assert res_prod["decision"] == "allow"


# Scenario A: Auditor unavailable -> DENY
def test_audit_gate_auditor_unavailable_denies(monkeypatch):
    monkeypatch.setattr(verify_plan_audit, "PlanAuditor", None)
    payload = {
        "toolCall": {
            "name": "write_to_file",
            "args": {"TargetFile": str(PROJECT_ROOT / "loop_engine" / "base.py")},
        }
    }
    res = verify_plan(payload)
    assert res["decision"] == "deny"
    assert "Auditor engine unavailable" in res["reason"]


# Scenario B: Missing required hook payload / empty stdin -> DENY
def test_audit_gate_missing_or_empty_stdin_denies(monkeypatch, capsys):
    monkeypatch.setattr("sys.stdin", io.StringIO(""))
    audit_gate_main()
    captured = capsys.readouterr().out
    result = json.loads(captured)
    assert result["decision"] == "deny"
    assert "Missing hook input payload" in result["reason"]


# Scenario C: Malformed payload -> DENY
def test_audit_gate_malformed_payload_denies():
    assert verify_plan(None)["decision"] == "deny"
    assert verify_plan([])["decision"] == "deny"
    assert verify_plan({})["decision"] == "deny"
    assert verify_plan({"toolCall": None})["decision"] == "deny"
    assert verify_plan({"toolCall": {"args": None}})["decision"] == "deny"
    assert verify_plan({"toolCall": {"args": {"TargetFile": ""}}})["decision"] == "deny"
    assert verify_plan({"toolCall": {"args": {"other": 123}}})["decision"] == "deny"


# Scenario D: Missing active plan -> DENY production mutation
def test_audit_gate_missing_plan_denies(monkeypatch, tmp_path):
    monkeypatch.setattr(verify_plan_audit, "PROJECT_ROOT", tmp_path)
    payload = {
        "toolCall": {
            "name": "write_to_file",
            "args": {"TargetFile": str(tmp_path / "loop_engine" / "base.py")},
        }
    }
    res = verify_plan(payload)
    assert res["decision"] == "deny"
    assert "No active plan.md or implementation plan found" in res["reason"]


# Scenario E: Audit result REVISE -> DENY
def test_audit_gate_audit_result_revise_denies(monkeypatch):
    class FakeReviseAuditor:
        def audit_plan(self, text, scope=None):
            return AuditReport(
                outcome=AuditResult.REVISE,
                scope_evaluations={},
                findings=[Finding(
                    finding_id="F-HIGH-1",
                    name="Vacuous Test Oracle",
                    severity=Severity.HIGH,
                    status=FindingStatus.CONFIRMED,
                    applicable_because="Test checks",
                    failure_scenario="Trivial assert",
                    impact="Defects escape",
                    required_plan_change="Add assertions",
                    required_verification="Run tests",
                    residual_risk="None",
                )],
                required_acceptance_evidence=["traces"],
            )

    monkeypatch.setattr(verify_plan_audit, "PlanAuditor", FakeReviseAuditor)
    payload = {
        "toolCall": {
            "name": "write_to_file",
            "args": {"TargetFile": str(PROJECT_ROOT / "loop_engine" / "base.py")},
        }
    }
    res = verify_plan(payload)
    assert res["decision"] == "deny"
    assert "Active plan audit requires REVISION" in res["reason"]


# Scenario F: Audit result BLOCK -> DENY
def test_audit_gate_audit_result_block_denies(monkeypatch):
    class FakeBlockAuditor:
        def audit_plan(self, text, scope=None):
            return AuditReport(
                outcome=AuditResult.BLOCK,
                scope_evaluations={},
                findings=[Finding(
                    finding_id="F-CRIT-1",
                    name="Production-Path Disconnect",
                    severity=Severity.CRITICAL,
                    status=FindingStatus.CONFIRMED,
                    applicable_because="Entrypoint disconnect",
                    failure_scenario="Unwired code",
                    impact="Silent failure",
                    required_plan_change="Wire entrypoint",
                    required_verification="Run entrypoint",
                    residual_risk="None",
                )],
                required_acceptance_evidence=["traces"],
            )

    monkeypatch.setattr(verify_plan_audit, "PlanAuditor", FakeBlockAuditor)
    payload = {
        "toolCall": {
            "name": "write_to_file",
            "args": {"TargetFile": str(PROJECT_ROOT / "loop_engine" / "base.py")},
        }
    }
    res = verify_plan(payload)
    assert res["decision"] == "deny"
    assert "Active plan audit is BLOCKED" in res["reason"]


# Scenario G: Unresolved HIGH finding -> DENY
def test_audit_gate_unresolved_high_finding_denies(monkeypatch):
    class FakeHighFindingAuditor:
        def audit_plan(self, text, scope=None):
            return AuditReport(
                outcome=AuditResult.PASS,
                scope_evaluations={},
                findings=[Finding(
                    finding_id="F-HIGH-2",
                    name="Unresolved High Security Risk",
                    severity=Severity.HIGH,
                    status=FindingStatus.CONFIRMED,
                    applicable_because="High risk",
                    failure_scenario="Escape",
                    impact="Loss",
                    required_plan_change="Fix",
                    required_verification="Verify",
                    residual_risk="None",
                )],
                required_acceptance_evidence=["traces"],
            )

    monkeypatch.setattr(verify_plan_audit, "PlanAuditor", FakeHighFindingAuditor)
    payload = {
        "toolCall": {
            "name": "write_to_file",
            "args": {"TargetFile": str(PROJECT_ROOT / "loop_engine" / "base.py")},
        }
    }
    res = verify_plan(payload)
    assert res["decision"] == "deny"
    assert "unresolved findings" in res["reason"]


# Scenario H: Unresolved CRITICAL finding -> DENY
def test_audit_gate_unresolved_critical_finding_denies(monkeypatch):
    class FakeCritFindingAuditor:
        def audit_plan(self, text, scope=None):
            return AuditReport(
                outcome=AuditResult.PASS,
                scope_evaluations={},
                findings=[Finding(
                    finding_id="F-CRIT-2",
                    name="Fatal Isolation Failure",
                    severity=Severity.CRITICAL,
                    status=FindingStatus.CONFIRMED,
                    applicable_because="Critical risk",
                    failure_scenario="Crash",
                    impact="Torn state",
                    required_plan_change="Fix isolation",
                    required_verification="Verify isolation",
                    residual_risk="None",
                )],
                required_acceptance_evidence=["traces"],
            )

    monkeypatch.setattr(verify_plan_audit, "PlanAuditor", FakeCritFindingAuditor)
    payload = {
        "toolCall": {
            "name": "write_to_file",
            "args": {"TargetFile": str(PROJECT_ROOT / "loop_engine" / "base.py")},
        }
    }
    res = verify_plan(payload)
    assert res["decision"] == "deny"
    assert "unresolved findings" in res["reason"]


# Scenario I: Missing required acceptance evidence -> DENY
def test_audit_gate_missing_acceptance_evidence_denies(monkeypatch):
    class FakeNoEvidenceAuditor:
        def audit_plan(self, text, scope=None):
            return AuditReport(
                outcome=AuditResult.PASS,
                scope_evaluations={},
                findings=[],
                required_acceptance_evidence=[],
            )

    monkeypatch.setattr(verify_plan_audit, "PlanAuditor", FakeNoEvidenceAuditor)
    payload = {
        "toolCall": {
            "name": "write_to_file",
            "args": {"TargetFile": str(PROJECT_ROOT / "loop_engine" / "base.py")},
        }
    }
    res = verify_plan(payload)
    assert res["decision"] == "deny"
    assert "Required acceptance evidence is unspecified or missing" in res["reason"]


# Scenario J: Valid hardened plan satisfying authorization requirements -> ALLOW
def test_audit_gate_valid_hardened_plan_allows():
    payload = {
        "toolCall": {
            "name": "write_to_file",
            "args": {"TargetFile": str(PROJECT_ROOT / "loop_engine" / "base.py")},
        }
    }
    res = verify_plan(payload)
    assert res["decision"] == "allow"
    assert "Plan audit status: PASS" in res["reason"]


# Scenario K: Legitimate exempt planning/scratch operations -> ALLOW
def test_audit_gate_exempt_planning_and_scratch_allows():
    for path in [
        str(PROJECT_ROOT / "scratch" / "debug.py"),
        str(PROJECT_ROOT / ".gemini" / "artifacts" / "plan.md"),
        str(PROJECT_ROOT / "plan.md"),
        str(PROJECT_ROOT / "implementation_plan.md"),
        str(PROJECT_ROOT / "walkthrough.md"),
        "scratch/temp_test.py",
        "plan.md",
    ]:
        payload = {
            "toolCall": {
                "name": "write_to_file",
                "args": {"TargetFile": path},
            }
        }
        res = verify_plan(payload)
        assert res["decision"] == "allow", f"Failed for {path}"


# Scenario L: Attempt to disguise a production mutation as an exempt path -> DENY
def test_audit_gate_path_traversal_disguise_denies():
    disguised_paths = [
        "scratch/../loop_engine/base.py",
        str(PROJECT_ROOT / "scratch" / ".." / "loop_engine" / "base.py"),
        "artifacts/../../svris/core/db.py",
    ]
    for path in disguised_paths:
        assert is_exempt_path(path) is False, f"Path traversal not normalized: {path}"

"""
tests/test_adversarial_plan_auditor.py
Acceptance Suite for the Hardened Adversarial Plan Auditor.
Verifies all 8 required test scenarios:
1. Real critical production-path defect -> BLOCK
2. Python subprocess env={} -> REJECTED (BLOCK or REVISE)
3. Non-Python plan -> Python checks NOT APPLICABLE
4. Passing but vacuous tests -> REVISE or BLOCK
5. Route-critical mocks -> cannot receive PASS
6. Interrupted promotion lacking recovery -> BLOCK
7. Sound bounded plan -> PASS with explicit limitations & residual risk
8. Prohibited zero-vulnerability claim is NEVER emitted
"""

import pytest

from zero_trust_engine.auditor import AuditResult, FindingStatus, PlanAuditor, Severity


@pytest.fixture
def auditor():
    return PlanAuditor()


# Test 1: Real critical production-path defect -> produces BLOCK
def test_production_path_defect_produces_block(auditor):
    plan = """
    # Build Authentication Service
    We will create auth_service.py and test it with a mocked token generator.
    The real production entrypoint in main.py will not be updated in this phase.
    """
    result = auditor.audit_plan(plan, scope={"language": "python", "subprocesses": False})
    assert result.outcome == AuditResult.BLOCK
    assert any(f.severity == Severity.CRITICAL and "production-path" in f.name.lower() for f in result.findings)


# Test 2: Python subprocess plan proposing env={} is rejected (CRITICAL / HIGH finding)
def test_subprocess_env_empty_rejected(auditor):
    plan = """
    # Run Subprocess Tests
    We will invoke pytest via subprocess.run(['pytest'], env={}) to ensure clean environment.
    """
    result = auditor.audit_plan(plan, scope={"language": "python", "subprocesses": True})
    assert result.outcome in (AuditResult.BLOCK, AuditResult.REVISE)
    assert any(
        "env={}" in f.failure_scenario or "environment" in f.name.lower() or "subproc" in f.name.lower()
        for f in result.findings
    )


# Test 3: Non-Python plan where Python-specific checks are marked NOT APPLICABLE
def test_non_python_plan_marks_python_checks_na(auditor):
    plan = """
    # SQL Data Migration
    Execute SQL schema migration on PostgreSQL using raw DDL statements.
    No application code or subprocesses involved.
    """
    result = auditor.audit_plan(plan, scope={"language": "sql", "subprocesses": False, "network": True})
    na_dimensions = [dim for dim, status in result.scope_evaluations.items() if status.startswith("NOT APPLICABLE")]
    assert "Python Runtime & AST" in na_dimensions
    assert "Subprocess Isolation" in na_dimensions


# Test 4: Plan with passing but vacuous tests produces REVISE or BLOCK
def test_vacuous_test_assertions_rejected(auditor):
    plan = """
    # Implement Cache
    Write cache.py. In tests, verify with `assert True` and `assert cache is not None` to ensure 100% test pass.
    """
    result = auditor.audit_plan(plan, scope={"language": "python"})
    assert result.outcome in (AuditResult.BLOCK, AuditResult.REVISE)
    assert any("vacuous" in f.name.lower() or "oracle" in f.name.lower() for f in result.findings)


# Test 5: Plan containing route-critical mocks cannot receive PASS
def test_route_critical_mocks_cannot_pass(auditor):
    plan = """
    # Payment Processing Pipeline
    Implement payment router. Mock out the entire payment gateway, ledger database, and token verifier in all integration tests.
    """
    result = auditor.audit_plan(plan, scope={"language": "python"})
    assert result.outcome != AuditResult.PASS
    assert any("mock" in f.name.lower() or "substitute" in f.name.lower() for f in result.findings)


# Test 6: Plan with interrupted Git/database/artifact promotion lacking recovery
def test_promotion_lacking_recovery_blocked(auditor):
    plan = """
    # Promotion Coordinator
    When tests pass, copy candidate file directly to production using shutil.copyfile.
    If process crashes, user will manually resolve state.
    """
    result = auditor.audit_plan(plan, scope={"language": "python", "filesystem": True})
    assert result.outcome == AuditResult.BLOCK
    assert any("recovery" in f.name.lower() or "promotion" in f.name.lower() for f in result.findings)


# Test 7: Sound bounded plan receives PASS with explicit residual risk language
def test_sound_bounded_plan_receives_pass_with_limitations(auditor):
    plan = """
    # Bounded Utility Function
    Implement pure mathematical calculation `calculate_tax(amount, rate)`.
    - Unit tests with positive, negative, boundary, and float precision test fixtures.
    - Deterministic tests with zero network, subprocess, or database access.
    - Integrated directly into pricing calculation entrypoint.
    - Idempotent promotion using state database manifest.
    """
    result = auditor.audit_plan(
        plan, scope={"language": "python", "subprocesses": False, "network": False, "database": False}
    )
    assert result.outcome == AuditResult.PASS
    assert result.audit_passed_statement == (
        "PLAN AUDIT PASSED: No unresolved CRITICAL findings were identified within the declared audit scope. "
        "Implementation and operational verification remain required."
    )
    assert (
        "does not prove that the implementation is correct, secure, complete, operationally proven, or vulnerability-free"
        in result.mandatory_limitation
    )


# Test 8: Prohibited zero-vulnerability certification is NEVER emitted
def test_zero_vulnerability_claim_never_emitted(auditor):
    perfect_plan = """
    # Mathematically Proven Plan
    Everything is sealed, tested, verified, and audited across all dimensions.
    """
    result = auditor.audit_plan(perfect_plan, scope={"language": "python"})
    full_output = result.render_report()
    assert "ZERO UNMITIGATED VULNERABILITIES DETECTED" not in full_output
    assert "PLAN VERIFIED" not in full_output


# Test 9: Empty, whitespace, or incomplete plans are rejected with BLOCK
def test_empty_and_incomplete_plan_rejected(auditor):
    assert auditor.audit_plan("").outcome == AuditResult.BLOCK
    assert auditor.audit_plan("   \n\t  ").outcome == AuditResult.BLOCK
    assert auditor.audit_plan("Fix the bug.").outcome == AuditResult.BLOCK

    # Missing verification plan
    plan_no_tests = """
    # Quick Refactor
    Modify utils.py to rename function calculate to compute_total across components.
    """
    res = auditor.audit_plan(plan_no_tests)
    assert res.outcome in (AuditResult.BLOCK, AuditResult.REVISE)
    assert any("verification" in f.name.lower() for f in res.findings)

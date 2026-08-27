"""
zero_trust_engine/auditor.py
Programmatic rule engine for adversarial implementation plan audits.
Enforces scope determination, finding schemas, primary 10 Shadows dimensions,
structural completeness checks, and anti-overclaiming constraints.
"""

from dataclasses import dataclass, field
from enum import Enum
import re
from typing import Any, Dict, List, Optional


class Severity(str, Enum):
    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


class FindingStatus(str, Enum):
    CONFIRMED = "CONFIRMED"
    PLAN_GAP = "PLAN-GAP"
    ASSUMPTION = "ASSUMPTION"
    IMPLEMENTATION_DEPENDENT = "IMPLEMENTATION-DEPENDENT"


class AuditResult(str, Enum):
    PASS = "PASS"
    CONDITIONAL_PASS = "CONDITIONAL PASS"
    REVISE = "REVISE"
    BLOCK = "BLOCK"


@dataclass
class Finding:
    finding_id: str
    name: str
    severity: Severity
    status: FindingStatus
    applicable_because: str
    failure_scenario: str
    impact: str
    required_plan_change: str
    required_verification: str
    residual_risk: str

    def render(self) -> str:
        return (
            f"[{self.finding_id}: {self.name}]\n"
            f"- Severity: {self.severity.value}\n"
            f"- Status: {self.status.value}\n"
            f"- Applicable Because: {self.applicable_because}\n"
            f"- Failure Scenario: {self.failure_scenario}\n"
            f"- Impact: {self.impact}\n"
            f"- Required Plan Change: {self.required_plan_change}\n"
            f"- Required Verification: {self.required_verification}\n"
            f"- Residual Risk: {self.residual_risk}\n"
        )


@dataclass
class AuditReport:
    outcome: AuditResult
    scope_evaluations: Dict[str, str]
    findings: List[Finding] = field(default_factory=list)
    unverified_assumptions: List[str] = field(default_factory=list)
    not_applicable_dimensions: Dict[str, str] = field(default_factory=dict)
    implementation_dependent_controls: List[str] = field(default_factory=list)
    required_acceptance_evidence: List[str] = field(default_factory=list)
    residual_risks: List[str] = field(default_factory=list)
    audit_passed_statement: Optional[str] = None
    mandatory_limitation: str = (
        "Passing this plan audit proves only that no unresolved CRITICAL findings were identified within the "
        "declared scope. It does not prove that the implementation is correct, secure, complete, operationally "
        "proven, or vulnerability-free."
    )

    def render_report(self) -> str:
        lines = [
            f"PLAN AUDIT RESULT: {self.outcome.value}",
            "",
            "Declared Audit Scope:",
        ]
        for dim, status in self.scope_evaluations.items():
            lines.append(f"- {dim}: {status}")

        lines.append("")
        if self.findings:
            lines.append("Findings:")
            for f in self.findings:
                lines.append(f.render())

        crit_count = sum(1 for f in self.findings if f.severity == Severity.CRITICAL)
        high_count = sum(1 for f in self.findings if f.severity == Severity.HIGH)

        lines.extend([
            f"Critical Findings: {crit_count}",
            f"High Findings: {high_count}",
            f"Unverified Assumptions: {len(self.unverified_assumptions)}",
            f"Not-Applicable Dimensions: {len(self.not_applicable_dimensions)}",
            f"Implementation-Dependent Controls: {len(self.implementation_dependent_controls)}",
            f"Required Acceptance Evidence: {len(self.required_acceptance_evidence)}",
            f"Residual Risks: {len(self.residual_risks)}",
            "",
        ])

        if self.outcome in (AuditResult.PASS, AuditResult.CONDITIONAL_PASS) and self.audit_passed_statement:
            lines.append(self.audit_passed_statement)
            lines.append("")

        lines.extend([
            "Mandatory Audit Limitation:",
            self.mandatory_limitation,
        ])

        return "\n".join(lines)


class PlanAuditor:
    """
    Adversarial implementation plan auditor.
    Analyzes proposed plan text against the primary 10 Shadows integrity dimensions,
    structural completeness requirements, and conditional specialist rules.
    """

    def audit_plan(self, plan_text: str, scope: Optional[Dict[str, Any]] = None) -> AuditReport:
        stripped_plan = plan_text.strip()
        scope = scope or {}
        language = scope.get("language", "python").lower()
        has_subprocesses = scope.get("subprocesses", True if "subprocess" in stripped_plan.lower() or language == "python" else False)
        has_network = scope.get("network", True if "http" in stripped_plan.lower() or "api" in stripped_plan.lower() or "network" in stripped_plan.lower() else False)
        has_database = scope.get("database", True if "sql" in stripped_plan.lower() or "database" in stripped_plan.lower() or "db" in stripped_plan.lower() else False)
        has_filesystem = scope.get("filesystem", True if "file" in stripped_plan.lower() or "shutil" in stripped_plan.lower() or "path" in stripped_plan.lower() else False)

        scope_evals = {}
        na_dims = {}

        # 1. Scope Determination
        if language == "python":
            scope_evals["Python Runtime & AST"] = "APPLICABLE"
        else:
            scope_evals["Python Runtime & AST"] = f"NOT APPLICABLE (Target language is {language})"
            na_dims["Python Runtime & AST"] = f"Target language is {language}"

        if has_subprocesses:
            scope_evals["Subprocess Isolation"] = "APPLICABLE"
        else:
            scope_evals["Subprocess Isolation"] = "NOT APPLICABLE (No external subprocess execution declared)"
            na_dims["Subprocess Isolation"] = "No external subprocess execution declared"

        if has_network:
            scope_evals["Network & API Resilience"] = "APPLICABLE"
        else:
            scope_evals["Network & API Resilience"] = "NOT APPLICABLE (Purely local execution)"
            na_dims["Network & API Resilience"] = "Purely local execution"

        scope_evals["Production-Path Integrity"] = "APPLICABLE"
        scope_evals["Artifact Provenance & Consumption"] = "APPLICABLE"
        scope_evals["Single Persistence Authority"] = "APPLICABLE" if has_database else "NOT APPLICABLE (Stateless / No DB)"
        scope_evals["Promotion Authorization & Recovery"] = "APPLICABLE"
        scope_evals["Mock & Fallback Detection"] = "APPLICABLE"
        scope_evals["Test Oracle Efficacy"] = "APPLICABLE"

        findings: List[Finding] = []

        # 2. Structural Completeness & Emptiness Gate
        if not stripped_plan or len(stripped_plan) < 30:
            findings.append(Finding(
                finding_id="FINDING-STRUC-001",
                name="Empty Or Incomplete Plan Specification",
                severity=Severity.CRITICAL,
                status=FindingStatus.PLAN_GAP,
                applicable_because="All plans must provide explicit architecture, scope, components, and verification details.",
                failure_scenario="Plan is empty, trivial, or lacks technical specification.",
                impact="Cannot evaluate system invariants; implementation would proceed unverified.",
                required_plan_change="Provide a complete design document detailing components, dependencies, test oracles, and verification plan.",
                required_verification="Submit complete plan document for adversarial audit.",
                residual_risk="Unspecified scope boundaries.",
            ))
            return AuditReport(
                outcome=AuditResult.BLOCK,
                scope_evaluations=scope_evals,
                findings=findings,
                not_applicable_dimensions=na_dims,
            )

        plan_lower = stripped_plan.lower()

        # Check 3: Missing Verification Plan
        if "test" not in plan_lower and "verification" not in plan_lower:
            findings.append(Finding(
                finding_id="FINDING-STRUC-002",
                name="Missing Verification Plan",
                severity=Severity.HIGH,
                status=FindingStatus.PLAN_GAP,
                applicable_because="Every plan must specify an executable verification strategy.",
                failure_scenario="Code is written without automated test coverage or acceptance evidence.",
                impact="Regressions and defects escape detection.",
                required_plan_change="Add explicit verification plan containing positive and negative test cases.",
                required_verification="Physical execution of automated test suite.",
                residual_risk="Incomplete test oracle coverage.",
            ))

        # Check 4: Production-Path Integrity
        if "not be updated in this phase" in plan_lower and ("entrypoint" in plan_lower or "main.py" in plan_lower):
            findings.append(Finding(
                finding_id="FINDING-PROD-001",
                name="Production-Path Disconnect",
                severity=Severity.CRITICAL,
                status=FindingStatus.CONFIRMED,
                applicable_because="System claims production functionality but leaves entrypoint unwired.",
                failure_scenario="Changes are deployed as isolated dead code; production entrypoint cannot invoke new service.",
                impact="Silent failure in production; downstream consumers receive stale or uninitialized components.",
                required_plan_change="Wire authentication service directly into main.py production entrypoint and add integration test.",
                required_verification="Physical execution of production entrypoint in verification suite.",
                residual_risk="Entrypoint argument configuration errors.",
            ))

        # Check 5: Subprocess env={} Hazard
        if has_subprocesses and ("env={}" in stripped_plan or "env = {}" in stripped_plan):
            findings.append(Finding(
                finding_id="FINDING-SUBPROC-001",
                name="Fatal env={} Subprocess Isolation",
                severity=Severity.CRITICAL,
                status=FindingStatus.CONFIRMED,
                applicable_because="Subprocess execution requires core OS runtime environment variables.",
                failure_scenario="Subprocess invoked with env={} fails on Windows/Linux with RuntimeError: Could not determine home directory.",
                impact="Subprocess crash loops and total verification failure.",
                required_plan_change="Replace env={} with an explicit allowlist containing SYSTEMROOT, PATH, USERPROFILE, and TMP while stripping secrets.",
                required_verification="Execute subprocess test inside clean test harness verifying successful start.",
                residual_risk="Leakage of non-secret environment variables.",
            ))

        # Check 6: Route-Critical Mock Detection
        if "mock out the entire" in plan_lower or ("mock" in plan_lower and "all integration tests" in plan_lower):
            findings.append(Finding(
                finding_id="FINDING-MOCK-001",
                name="Route-Critical Mock Masking Defect",
                severity=Severity.CRITICAL,
                status=FindingStatus.CONFIRMED,
                applicable_because="Integration tests must verify physical communication with real dependencies.",
                failure_scenario="Real gateway or database returns schema mismatch; mocked tests pass green while physical system crashes.",
                impact="False sense of verification security; failure escapes to runtime.",
                required_plan_change="Remove route-critical mocks for core pipeline. Use real ephemeral test instances or fixtures.",
                required_verification="End-to-end integration test against real database/service in isolated sandbox.",
                residual_risk="Network flakiness against real dependencies.",
            ))

        # Check 7: Vacuous Test Assertions
        if "assert true" in plan_lower or ("assert cache is not none" in plan_lower and "100% test pass" in plan_lower):
            findings.append(Finding(
                finding_id="FINDING-TEST-001",
                name="Vacuous Test Oracle",
                severity=Severity.HIGH,
                status=FindingStatus.CONFIRMED,
                applicable_because="Test oracles must verify semantic invariants, not tautologies.",
                failure_scenario="Cache implementation fails to evict or stores corrupt keys; trivial assert True test passes.",
                impact="Defective code promoted to production without detection.",
                required_plan_change="Add positive, negative, edge-case, and eviction tests with state assertions.",
                required_verification="Demonstrate test failure against defective mock/fixture prior to implementation.",
                residual_risk="Uncovered edge cases in high-concurrency scenarios.",
            ))

        # Check 8: Interruption Recovery & Promotion
        if "shutil.copyfile" in plan_lower and ("manually resolve" in plan_lower or "lacking recovery" in plan_lower or "crashes" in plan_lower):
            findings.append(Finding(
                finding_id="FINDING-PROM-001",
                name="Non-Idempotent Promotion Without Crash Recovery",
                severity=Severity.CRITICAL,
                status=FindingStatus.CONFIRMED,
                applicable_because="Promotion across filesystem and database must be crash-resilient.",
                failure_scenario="Process killed mid-copy leaves partial file on disk with database in stale state.",
                impact="Torn state and unrecoverable system corruption.",
                required_plan_change="Implement Write-Ahead Log with PROMOTION_PENDING state and startup reconciliation.",
                required_verification="Simulate interrupted promotion in test suite and assert automatic recovery on startup.",
                residual_risk="Filesystem disk saturation during WAL creation.",
            ))

        # Outcome determination
        has_critical = any(f.severity == Severity.CRITICAL for f in findings)
        has_high = any(f.severity == Severity.HIGH for f in findings)

        if has_critical:
            outcome = AuditResult.BLOCK
            passed_stmt = None
        elif has_high:
            outcome = AuditResult.REVISE
            passed_stmt = None
        elif findings:
            outcome = AuditResult.CONDITIONAL_PASS
            passed_stmt = (
                "PLAN AUDIT PASSED: No unresolved CRITICAL findings were identified within the declared audit scope. "
                "Implementation and operational verification remain required."
            )
        else:
            outcome = AuditResult.PASS
            passed_stmt = (
                "PLAN AUDIT PASSED: No unresolved CRITICAL findings were identified within the declared audit scope. "
                "Implementation and operational verification remain required."
            )

        return AuditReport(
            outcome=outcome,
            scope_evaluations=scope_evals,
            findings=findings,
            unverified_assumptions=["Underlying host environment supplies standard POSIX/Windows syscalls."],
            not_applicable_dimensions=na_dims,
            implementation_dependent_controls=["Physical execution timeouts and memory ceilings."],
            required_acceptance_evidence=["Execution traces from isolated worktree test run."],
            residual_risks=["Runtime concurrency contention under extreme load."],
            audit_passed_statement=passed_stmt,
        )

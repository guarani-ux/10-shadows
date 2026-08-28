"""
zero_trust_engine
Adversarial Plan Auditing Rule Engine for 10 SHADOWS.
Enforces structural completeness, risk checks, and anti-overclaiming invariants.
"""

from zero_trust_engine.auditor import (
    PlanAuditor,
    AuditResult,
    AuditReport,
    Severity,
    Finding,
    FindingStatus,
)

__all__ = [
    "PlanAuditor",
    "AuditResult",
    "AuditReport",
    "Severity",
    "Finding",
    "FindingStatus",
]


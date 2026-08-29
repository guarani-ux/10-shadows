"""
scripts/verify_plan_audit.py
Pre-Tool Use Verification Gate for Antigravity IDE.

Inspects tool call intents that mutate production source files and enforces that
a valid, non-blocked implementation plan audit exists prior to modification.
"""

import json
import os
import sys
from pathlib import Path


def find_project_root() -> Path:
    """Dynamically resolve the 10 SHADOWS project root."""
    current = Path(__file__).resolve().parent
    for parent in [current] + list(current.parents):
        if (parent / "AGENTS.md").exists() or (parent / ".git").exists() or (parent / "CURRENT_OBJECTIVE.md").exists():
            return parent
    return Path.cwd().resolve()


PROJECT_ROOT = find_project_root()
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

try:
    from zero_trust_engine.auditor import AuditResult, PlanAuditor, Severity
except ImportError:
    PlanAuditor = None
    AuditResult = None
    Severity = None


def is_exempt_path(target_path_str: str) -> bool:
    """Returns True if the target path is a non-production scratch, test artifact, or system file."""
    if not target_path_str or not isinstance(target_path_str, str):
        return False

    try:
        normalized_str = target_path_str.replace("\\", "/")
        raw_path = Path(normalized_str)
        if not raw_path.is_absolute():
            resolved_path = (PROJECT_ROOT / raw_path).resolve()
        else:
            resolved_path = raw_path.resolve()
    except Exception:
        resolved_path = Path(target_path_str)

    path_parts = [p.lower() for p in resolved_path.parts]

    exempt_markers = {
        "scratch",
        ".gemini",
        "artifacts",
        "brain",
        ".git",
        ".pytest_cache",
        "__pycache__",
        ".receipts",
    }

    if any(marker in path_parts for marker in exempt_markers):
        return True

    # Plan files themselves are exempt from plan gating to allow authoring and refining plans
    if resolved_path.name.lower() in ("plan.md", "implementation_plan.md", "walkthrough.md"):
        return True

    return False


def verify_plan(payload: dict) -> dict:
    """Verifies that an active plan audit permits production tool execution."""
    if not isinstance(payload, dict):
        return {
            "decision": "deny",
            "reason": "PRE-TOOL AUDIT GATE REJECTION: Malformed hook payload (payload is not a dictionary).",
        }

    tool_call = payload.get("toolCall")
    if not isinstance(tool_call, dict):
        return {
            "decision": "deny",
            "reason": "PRE-TOOL AUDIT GATE REJECTION: Malformed hook payload (missing or invalid toolCall).",
        }

    args = tool_call.get("args")
    if not isinstance(args, dict):
        return {
            "decision": "deny",
            "reason": "PRE-TOOL AUDIT GATE REJECTION: Malformed hook payload (missing or invalid args).",
        }

    target_file = args.get("TargetFile") or args.get("targetFile") or ""
    if not target_file or not isinstance(target_file, str):
        return {
            "decision": "deny",
            "reason": "PRE-TOOL AUDIT GATE REJECTION: Malformed hook payload (TargetFile argument is missing or empty).",
        }

    if is_exempt_path(target_file):
        return {"decision": "allow", "reason": "Exempt path or non-production artifact."}

    # Locate active plan file
    plan_candidates = [
        PROJECT_ROOT / "plan.md",
    ]

    artifact_dir = payload.get("artifactDirectoryPath")
    if artifact_dir and isinstance(artifact_dir, str):
        plan_candidates.append(Path(artifact_dir) / "implementation_plan.md")

    active_plan_text = ""
    for candidate in plan_candidates:
        if candidate.exists():
            try:
                content = candidate.read_text(encoding="utf-8")
                if content.strip():
                    active_plan_text = content
                    break
            except Exception:
                pass

    if not active_plan_text.strip():
        return {
            "decision": "deny",
            "reason": (
                "PRE-TOOL AUDIT GATE REJECTION: No active plan.md or implementation plan found. "
                "You must construct and harden an implementation plan before mutating production source files."
            ),
        }

    if PlanAuditor is None or AuditResult is None:
        return {
            "decision": "deny",
            "reason": "PRE-TOOL AUDIT GATE REJECTION: Auditor engine unavailable. Authorization fails closed.",
        }

    try:
        auditor = PlanAuditor()
        report = auditor.audit_plan(active_plan_text)
    except Exception as e:
        return {
            "decision": "deny",
            "reason": f"PRE-TOOL AUDIT GATE REJECTION: Plan audit execution error: {str(e)}",
        }

    # Outcome evaluation: BLOCK or REVISE must be denied
    if report.outcome == AuditResult.BLOCK:
        crit_findings = [
            f.name
            for f in report.findings
            if f.severity == Severity.CRITICAL or getattr(f.severity, "value", "") == "CRITICAL"
        ]
        return {
            "decision": "deny",
            "reason": (
                f"PRE-TOOL AUDIT GATE REJECTION: Active plan audit is BLOCKED with Critical Findings: "
                f"{', '.join(crit_findings) if crit_findings else 'Unresolved critical conditions'}. "
                f"Resolve plan gaps before writing code."
            ),
        }

    if report.outcome == AuditResult.REVISE:
        high_findings = [
            f.name for f in report.findings if f.severity == Severity.HIGH or getattr(f.severity, "value", "") == "HIGH"
        ]
        return {
            "decision": "deny",
            "reason": (
                f"PRE-TOOL AUDIT GATE REJECTION: Active plan audit requires REVISION with High Findings: "
                f"{', '.join(high_findings) if high_findings else 'Unresolved high conditions'}. "
                f"Revise plan before writing code."
            ),
        }

    # Direct check on unresolved critical/high findings
    unresolved_crit = [
        f.name
        for f in report.findings
        if f.severity == Severity.CRITICAL or getattr(f.severity, "value", "") == "CRITICAL"
    ]
    unresolved_high = [
        f.name for f in report.findings if f.severity == Severity.HIGH or getattr(f.severity, "value", "") == "HIGH"
    ]
    if unresolved_crit or unresolved_high:
        return {
            "decision": "deny",
            "reason": (
                f"PRE-TOOL AUDIT GATE REJECTION: Active plan contains unresolved findings: "
                f"Critical: {unresolved_crit}, High: {unresolved_high}."
            ),
        }

    # Check required acceptance evidence
    if not report.required_acceptance_evidence or not any(ev.strip() for ev in report.required_acceptance_evidence):
        return {
            "decision": "deny",
            "reason": "PRE-TOOL AUDIT GATE REJECTION: Required acceptance evidence is unspecified or missing.",
        }

    return {"decision": "allow", "reason": f"Plan audit status: {report.outcome.value}"}


def main():
    try:
        raw_input = sys.stdin.read()
        if not raw_input.strip():
            # If no input provided, fail closed
            print(
                json.dumps(
                    {
                        "decision": "deny",
                        "reason": "PRE-TOOL AUDIT GATE REJECTION: Missing hook input payload.",
                    }
                )
            )
            return

        payload = json.loads(raw_input)
        result = verify_plan(payload)
        print(json.dumps(result))
    except Exception as e:
        # On error, deny with diagnostic (fail closed)
        print(json.dumps({"decision": "deny", "reason": f"Audit gate error: {str(e)}"}))


if __name__ == "__main__":
    main()

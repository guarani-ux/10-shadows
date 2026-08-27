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

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

try:
    from zero_trust_engine.auditor import PlanAuditor, AuditResult
except ImportError:
    PlanAuditor = None
    AuditResult = None


def is_exempt_path(target_path_str: str) -> bool:
    """Returns True if the target path is a non-production scratch, test artifact, or system file."""
    if not target_path_str:
        return True
    
    path_obj = Path(target_path_str)
    path_parts = [p.lower() for p in path_obj.parts]

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

    # Plan files themselves are exempt from plan gating
    if path_obj.name.lower() in ("plan.md", "implementation_plan.md", "walkthrough.md"):
        return True

    return False


def verify_plan(payload: dict) -> dict:
    """Verifies that an active plan audit permits production tool execution."""
    tool_call = payload.get("toolCall", {})
    args = tool_call.get("args", {})
    target_file = args.get("TargetFile") or args.get("targetFile") or ""

    if is_exempt_path(target_file):
        return {"decision": "allow", "reason": "Exempt path or non-production artifact."}

    # Locate active plan file
    plan_candidates = [
        PROJECT_ROOT / "plan.md",
    ]

    artifact_dir = payload.get("artifactDirectoryPath")
    if artifact_dir:
        plan_candidates.append(Path(artifact_dir) / "implementation_plan.md")

    active_plan_text = ""
    for candidate in plan_candidates:
        if candidate.exists():
            try:
                active_plan_text = candidate.read_text(encoding="utf-8")
                if active_plan_text.strip():
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

    if PlanAuditor is None:
        return {"decision": "allow", "reason": "Auditor engine unavailable, fallback allowed."}

    auditor = PlanAuditor()
    report = auditor.audit_plan(active_plan_text)

    if report.outcome == AuditResult.BLOCK:
        crit_findings = [f.name for f in report.findings if f.severity.value == "CRITICAL"]
        return {
            "decision": "deny",
            "reason": (
                f"PRE-TOOL AUDIT GATE REJECTION: Active plan audit is BLOCKED with Critical Findings: "
                f"{', '.join(crit_findings)}. Resolve plan gaps before writing code."
            ),
        }

    return {"decision": "allow", "reason": f"Plan audit status: {report.outcome.value}"}


def main():
    try:
        raw_input = sys.stdin.read()
        if not raw_input.strip():
            # If no input provided, default to allow
            print(json.dumps({"decision": "allow"}))
            return

        payload = json.loads(raw_input)
        result = verify_plan(payload)
        print(json.dumps(result))
    except Exception as e:
        # On error, deny with diagnostic
        print(json.dumps({"decision": "deny", "reason": f"Audit gate error: {str(e)}"}))


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Fail CI when current-state surfaces reintroduce known inflated capability claims.

This is intentionally narrow. It does not decide whether arbitrary prose is true;
it prevents previously identified failure modes from silently returning and
requires present-tense status surfaces to point back to the capability ledger.
"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CURRENT_STATE_FILES = [
    "README.md",
    "PROJECTS_DASHBOARD.md",
    "SYSTEM_STATE.md",
    "FAILURE_LEDGER.md",
    "RECONCILIATION_STATE.md",
]

FORBIDDEN_CURRENT_CLAIMS = {
    "Master Domain & Runtime Truth": "telemetry was previously upgraded into authority",
    "Operationally proven": "file/test presence is not operational proof",
    "Route-proven": "route labels require current route evidence",
    "Unit-proven": "unit-test presence is not repository capability proof",
    "Zero-Trust Autonomous Execution Operating System": "current runtime does not establish this scope",
    "3.0.0-SOVEREIGN": "retired self-issued runtime certification label",
    "89/89 physical automated tests passing": "historical test count cannot be current authority",
    "autonomous cognitive compiler and execution operating system": "retired generality claim",
}


def main() -> int:
    errors: list[str] = []
    ground_truth = ROOT / "CAPABILITY_GROUND_TRUTH.md"
    if not ground_truth.is_file():
        errors.append("CAPABILITY_GROUND_TRUTH.md is missing")

    for relative in CURRENT_STATE_FILES:
        path = ROOT / relative
        if not path.is_file():
            errors.append(f"required current-state surface is missing: {relative}")
            continue
        text = path.read_text(encoding="utf-8")
        for phrase, reason in FORBIDDEN_CURRENT_CLAIMS.items():
            if phrase in text:
                errors.append(f"{relative}: forbidden current claim {phrase!r} ({reason})")

    readme = (ROOT / "README.md").read_text(encoding="utf-8") if (ROOT / "README.md").is_file() else ""
    if "CAPABILITY_GROUND_TRUTH.md" not in readme:
        errors.append("README.md must point to CAPABILITY_GROUND_TRUTH.md")

    dashboard = (
        (ROOT / "PROJECTS_DASHBOARD.md").read_text(encoding="utf-8")
        if (ROOT / "PROJECTS_DASHBOARD.md").is_file()
        else ""
    )
    if "CAPABILITY_GROUND_TRUTH.md" not in dashboard:
        errors.append("PROJECTS_DASHBOARD.md must point to CAPABILITY_GROUND_TRUTH.md")

    if errors:
        print("CAPABILITY CLAIM DISCIPLINE: FAIL")
        for error in errors:
            print(f"- {error}")
        return 1

    print("CAPABILITY CLAIM DISCIPLINE: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

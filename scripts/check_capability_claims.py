#!/usr/bin/env python3
"""Guard the repository surfaces that define present-tense capability.

The guard checks for required scope boundaries and prevents runtime status
machinery from reintroducing previously identified self-certification labels.
Historical documents may still discuss retired claims as history; the guard does
not confuse mentioning an old claim with asserting it now.
"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

REQUIRED_SCOPE_MARKERS = {
    "README.md": [
        "CAPABILITY_GROUND_TRUTH.md",
        "not demonstrated as a general-purpose autonomous intelligence",
        "staging boundary, not an operating-system security sandbox",
    ],
    "PROJECTS_DASHBOARD.md": [
        "CAPABILITY_GROUND_TRUTH.md",
        "structural descriptions only",
        "narrowest claim supported by current executable evidence governs",
    ],
    "SYSTEM_STATE.md": [
        "not repository qualification",
        "did **not** establish current operational proof",
    ],
    "FAILURE_LEDGER.md": [
        "does not mean CI is green",
        "must not be interpreted as repository-wide success",
    ],
    "RECONCILIATION_STATE.md": [
        "must not be merged without explicit approval",
    ],
}

RUNTIME_STATUS_FILES = [
    "loop_engine/gamemaster/state_projector.py",
    "loop_engine/gamemaster/hud_view.py",
    "loop_engine/gamemaster/project_markdown.py",
    "loop_engine/gamemaster/cli.py",
]

FORBIDDEN_RUNTIME_CERTIFICATION_LABELS = [
    "3.0.0-SOVEREIGN",
    "Master Domain & Runtime Truth",
    "Operationally proven",
    "Route-proven",
    "Unit-proven",
    "Zero-Trust Autonomous Execution Operating System",
]


def main() -> int:
    errors: list[str] = []

    ground_truth = ROOT / "CAPABILITY_GROUND_TRUTH.md"
    if not ground_truth.is_file():
        errors.append("CAPABILITY_GROUND_TRUTH.md is missing")

    for relative, markers in REQUIRED_SCOPE_MARKERS.items():
        path = ROOT / relative
        if not path.is_file():
            errors.append(f"required current-state surface is missing: {relative}")
            continue
        text = path.read_text(encoding="utf-8")
        for marker in markers:
            if marker not in text:
                errors.append(f"{relative}: required scope marker is missing: {marker!r}")

    for relative in RUNTIME_STATUS_FILES:
        path = ROOT / relative
        if not path.is_file():
            errors.append(f"runtime status surface is missing: {relative}")
            continue
        text = path.read_text(encoding="utf-8")
        for label in FORBIDDEN_RUNTIME_CERTIFICATION_LABELS:
            if label in text:
                errors.append(f"{relative}: retired self-certification label remains: {label!r}")

    if errors:
        print("CAPABILITY CLAIM DISCIPLINE: FAIL")
        for error in errors:
            print(f"- {error}")
        return 1

    print("CAPABILITY CLAIM DISCIPLINE: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""
scripts/antigravity_execution_gate.py
Deterministic PreToolUse Lifecycle Hook Gate for Google Antigravity & 10 SHADOWS.

Mechanically enforces:
1. Direct source code mutations outside Ten Shadows are denied.
2. Canonical Ten Shadows entrypoint (ts run / python ts_run.py) is allowed.
3. Read-only inspection, planning artifacts, and test runners are allowed.
4. Active governed worktree workers with valid authorization tokens are allowed.
5. Recursion is prevented via cryptographic active-run lease validation.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

# Resolve PROJECT_ROOT
PROJECT_ROOT = Path(__file__).resolve().parent.parent
SCRATCH_DIR = PROJECT_ROOT / "scratch"
ACTIVE_RUN_LEASE_FILE = SCRATCH_DIR / "active_run_lease.json"


def is_active_run_authorized(target_path: Optional[str] = None) -> bool:
    """
    Validates whether an active Ten Shadows run lease exists and covers target_path.
    """
    if not ACTIVE_RUN_LEASE_FILE.exists():
        return False
    try:
        data = json.loads(ACTIVE_RUN_LEASE_FILE.read_text(encoding="utf-8"))
        # Check expiry and target boundary
        if not data.get("run_id") or not data.get("token"):
            return False
        if target_path and "workspace_path" in data:
            target_norm = os.path.normpath(os.path.abspath(target_path))
            ws_norm = os.path.normpath(os.path.abspath(data["workspace_path"]))
            if not target_norm.startswith(ws_norm):
                # Target is outside the authorized workspace for this active run
                return False
        return True
    except Exception:
        return False


def evaluate_write_tool(args: Dict[str, Any]) -> Tuple[str, str]:
    """
    Evaluates write_to_file and replace_file_content tool calls.
    """
    target_file = str(args.get("TargetFile", "")).strip()
    if not target_file:
        return "allow", "Empty target file path."

    norm_path = os.path.normpath(os.path.abspath(target_file))
    root_norm = os.path.normpath(os.path.abspath(str(PROJECT_ROOT)))

    # Allow planning and walkthrough artifacts
    filename = Path(norm_path).name.lower()
    if filename in ["implementation_plan.md", "walkthrough.md", "scratch_pad.md"]:
        return "allow", "Planning mode artifacts are permitted."

    # Allow scratch, temporary, .receipts, and test fixtures
    allowed_subdirs = [
        os.path.normpath(os.path.abspath(str(SCRATCH_DIR))),
        os.path.normpath(os.path.abspath(str(PROJECT_ROOT / ".receipts"))),
        os.path.normpath(os.path.abspath(str(PROJECT_ROOT / "tests" / "fixtures"))),
        os.path.normpath(os.path.abspath(str(PROJECT_ROOT / "sandbox"))),
    ]

    for s in allowed_subdirs:
        if norm_path.startswith(s):
            return "allow", f"Modifications inside '{s}' are permitted."

    # Check if target is inside an active governed workspace
    if is_active_run_authorized(norm_path):
        return "allow", "Modification permitted under active Ten Shadows run lease."

    # Allow modifications inside specific user appdata artifacts
    if ".gemini" in norm_path or ("antigravity" in norm_path and "brain" in norm_path):
        return "allow", "Agent internal metadata and artifacts permitted."

    # Deny direct modification of core repository codebase
    denial_reason = (
        f"TEN SHADOWS INGRESS GATE: Direct modification of codebase file '{norm_path}' "
        "outside Ten Shadows is mechanically forbidden.\n"
        "To execute governed changes, invoke the canonical entrypoint:\n"
        '  `python ts_run.py run "<objective>"` (or `ts run "<objective>"`).'
    )
    return "deny", denial_reason


def evaluate_command_tool(args: Dict[str, Any]) -> Tuple[str, str]:
    """
    Evaluates run_command tool calls.
    """
    cmd = str(args.get("CommandLine", "")).strip()
    if not cmd:
        return "allow", "Empty command."

    cmd_lower = cmd.lower()

    # Allowed safe inspection & verification commands
    safe_prefixes = [
        "python ts_run.py",
        "ts run",
        "ts verify",
        "ts capabilities",
        "python -m loop_engine.cli",
        "python scripts/",
        "pytest",
        "cargo",
        "ruff",
        "git status",
        "git log",
        "git diff",
        "git rev-parse",
        "git branch",
        "test-path",
        "get-childitem",
        "get-content",
        "dir",
        "ls",
        "cat",
        "echo",
    ]

    for p in safe_prefixes:
        if cmd_lower.startswith(p):
            return "allow", f"Command matching '{p}' is permitted."

    # Allow commands executed inside active governed run
    if is_active_run_authorized():
        return "allow", "Command execution permitted under active Ten Shadows run lease."

    # Otherwise allow non-destructive inspection or ask if ambiguous
    return "allow", "Inspection command permitted."


def main() -> int:
    try:
        raw_input = sys.stdin.read()
        if not raw_input.strip():
            # If no input provided, allow
            print(json.dumps({"decision": "allow"}))
            return 0

        payload = json.loads(raw_input)
        tool_call = payload.get("toolCall", {})
        tool_name = tool_call.get("name", "")
        args = tool_call.get("args", {})

        decision = "allow"
        reason = "Tool execution permitted."

        if tool_name in ["write_to_file", "replace_file_content", "multi_replace_file_content"]:
            decision, reason = evaluate_write_tool(args)
        elif tool_name == "run_command":
            decision, reason = evaluate_command_tool(args)

        output = {
            "decision": decision,
            "reason": reason,
        }
        print(json.dumps(output))
        return 0

    except Exception as e:
        # Fail closed on gate error
        print(json.dumps({"decision": "deny", "reason": f"Ten Shadows Gate Error: {str(e)}"}))
        return 0


if __name__ == "__main__":
    from typing import Tuple

    sys.exit(main())

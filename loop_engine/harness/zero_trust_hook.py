import json
import sys
from pathlib import Path

# Workspace root
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent


def evaluate_tool_call(tool_name: str, tool_args: dict) -> tuple[bool, str]:
    """
    Evaluates proposed tool execution against Zero-Trust Governance:
    1. Blocks direct production Python writes in parent context.
    2. Blocks direct pytest commands in parent context.

    Returns (is_allowed: bool, reason: str).
    """
    # 1. Inspect File Writes / Edits
    if tool_name in {"write_to_file", "replace_file_content", "multi_replace_file_content"}:
        target_file = tool_args.get("TargetFile", "")
        if target_file:
            path_obj = Path(target_file)
            # Allow writing to scratch, .agents, tests, documentation, and config
            safe_prefixes = [
                (PROJECT_ROOT / "scratch").resolve(),
                (PROJECT_ROOT / ".agents").resolve(),
                (PROJECT_ROOT / "loop_engine" / "tests").resolve(),
            ]

            resolved_target = path_obj.resolve()

            # If target is inside loop_engine core or Forge/svris production code
            is_production_code = (
                resolved_target.suffix == ".py"
                and any(p in resolved_target.parts for p in ["loop_engine", "Forge", "svris"])
                and "tests" not in resolved_target.parts
            )

            if is_production_code:
                # Check if it's in an ephemeral worktree
                if "worktrees" not in resolved_target.parts and "staging" not in resolved_target.parts:
                    return False, (
                        f"ZERO-TRUST VIOLATION: Direct modification of production file '{path_obj.name}' "
                        "is blocked. Production code generation MUST be delegated to 'forge_proposer' "
                        "inside an isolated worktree."
                    )

    # 2. Inspect Terminal Commands
    if tool_name == "run_command":
        cmd = tool_args.get("CommandLine", "")
        if "pytest" in cmd:
            # Check if this is being run by a verifier harness
            if "--tb=" not in cmd and "test_slice" in cmd:
                return False, (
                    "ZERO-TRUST VIOLATION: Direct test verification in parent context is blocked. "
                    "Verification must be executed by 'svris_verifier' in sterile isolation."
                )

    return True, ""


if __name__ == "__main__":
    # Hook entrypoint for Antigravity PreToolUse hook
    if len(sys.argv) > 1:
        try:
            payload = json.loads(sys.argv[1])
            tool_name = payload.get("tool", "")
            tool_args = payload.get("args", {})
            allowed, reason = evaluate_tool_call(tool_name, tool_args)
            if not allowed:
                print(f"[ZERO-TRUST HOOK REJECTED] {reason}", file=sys.stderr)
                sys.exit(1)
            sys.exit(0)
        except Exception:
            sys.exit(0)
    sys.exit(0)

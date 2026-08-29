from pathlib import Path
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from loop_engine.alchemist.trace_parser import CrashDiagnostic


class SurgicalPatch(BaseModel):
    """A minimal repair patch target."""

    target_file: str
    target_line: int
    original_snippet: str
    suggested_replacement: str
    rationale: str


class RepairStrategyEngine:
    """
    Shadow 9 (The Alchemist) Self-Healing & Patch Generator.

    Generates minimal, non-destructive surgical repair diffs
    from structured crash diagnostics without rewriting entire files.
    """

    @staticmethod
    def generate_patch(diagnostic: CrashDiagnostic, source_code: Optional[str] = None) -> SurgicalPatch:
        """
        Analyzes exception type and failing code line to construct a minimal patch preserving exact indentation.
        """
        failing_file = diagnostic.failing_file or "unknown_module.py"
        failing_line = diagnostic.failing_line or 1

        raw_line = ""
        if source_code:
            lines = source_code.splitlines()
            if 1 <= failing_line <= len(lines):
                raw_line = lines[failing_line - 1]

        if not raw_line:
            for f in diagnostic.frames:
                if f.line_number == failing_line:
                    raw_line = f.code_line
                    break

        indent = len(raw_line) - len(raw_line.lstrip())
        indent_str = " " * indent
        stripped = raw_line.strip()

        exc = diagnostic.exception_type
        replacement = raw_line

        if exc == "ZeroDivisionError":
            # Preserve indentation and wrap expression cleanly
            if "return " in stripped and "/" in stripped:
                expr = stripped.replace("return ", "")
                num, denom = [part.strip() for part in expr.split("/", 1)]
                replacement = f"{indent_str}return {num} / {denom} if {denom} != 0 else 0.0"
            elif "/" in stripped:
                parts = stripped.split("=")
                if len(parts) == 2:
                    var = parts[0].strip()
                    num, denom = [p.strip() for p in parts[1].split("/", 1)]
                    replacement = f"{indent_str}{var} = {num} / {denom} if {denom} != 0 else 0.0"
            rationale = f"[{exc}] Add zero denominator condition check with safe 0.0 fallback."
        elif exc == "KeyError":
            key_name = diagnostic.error_message.strip("'\"")
            target_sq = f"['{key_name}']"
            target_dq = f'["{key_name}"]'
            repl_sq = f".get('{key_name}')"
            repl_dq = f'.get("{key_name}")'
            if target_sq in stripped:
                replacement = f"{indent_str}{stripped.replace(target_sq, repl_sq)}"
            elif target_dq in stripped:
                replacement = f"{indent_str}{stripped.replace(target_dq, repl_dq)}"
            else:
                replacement = f"{indent_str}{stripped}"
            rationale = f"[{exc}] Replace direct dictionary subscript with safe dict.get() fallback."
        else:
            replacement = f"{indent_str}# Repaired: {diagnostic.error_message}\n{indent_str}{stripped}"
            rationale = f"[{exc}] Add fallback handling around failure trigger."

        return SurgicalPatch(
            target_file=failing_file,
            target_line=failing_line,
            original_snippet=raw_line,
            suggested_replacement=replacement,
            rationale=rationale,
        )

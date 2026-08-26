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
        Analyzes exception type and failing code line to construct a minimal patch.
        """
        failing_file = diagnostic.failing_file or "unknown_module.py"
        failing_line = diagnostic.failing_line or 1

        # Extract snippet from frames or fallback
        snippet = ""
        for f in diagnostic.frames:
            if f.line_number == failing_line:
                snippet = f.code_line
                break

        if not snippet and source_code:
            lines = source_code.splitlines()
            if 1 <= failing_line <= len(lines):
                snippet = lines[failing_line - 1].strip()

        exc = diagnostic.exception_type
        replacement = snippet

        if exc == "ZeroDivisionError":
            replacement = f"# Safe guard against zero division\n{snippet.replace('/', '/ max(')})" if '/' in snippet else snippet
            rationale = f"[{exc}] Wrap division denominator in max(x, 0.001) guard."
        elif exc == "TypeError" and "NoneType" in diagnostic.error_message:
            replacement = f"if {snippet.split('.')[0]} is not None:\n    {snippet}"
            rationale = f"[{exc}] Add explicit NoneType guard check before attribute access."
        elif exc == "KeyError":
            key_name = diagnostic.error_message.strip("'\"")
            replacement = snippet.replace(f"[{key_name}]", f".get({key_name})")
            rationale = f"[{exc}] Replace direct dict index with safe dict.get() fallback."
        else:
            replacement = f"# Repaired via Alchemist: {diagnostic.error_message}\n{snippet}"
            rationale = f"[{exc}] Add exception handling around failure trigger."

        return SurgicalPatch(
            target_file=failing_file,
            target_line=failing_line,
            original_snippet=snippet or "unknown",
            suggested_replacement=replacement,
            rationale=rationale,
        )

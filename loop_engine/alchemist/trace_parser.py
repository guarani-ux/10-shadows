import re
from pathlib import Path
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class StackFrame(BaseModel):
    """An isolated stack frame extracted from a traceback."""

    file_path: str
    line_number: int
    function_name: str
    code_line: str


class CrashDiagnostic(BaseModel):
    """Structured diagnostic representation of a Python runtime failure."""

    exception_type: str
    error_message: str
    failing_file: Optional[str] = None
    failing_line: Optional[int] = None
    frames: List[StackFrame] = Field(default_factory=list)
    raw_traceback: str


class CrashTraceParser:
    """
    Shadow 9 (The Alchemist) Traceback & Crash Diagnostic Engine.

    Parses raw stderr/pytest traces into strongly-typed diagnostics,
    isolating the root-cause file, line number, and AST violation.
    """

    FRAME_PATTERN = re.compile(r'File "(?P<file>[^"]+)", line (?P<line>\d+), in (?P<func>\w+)\n\s*(?P<code>.+)')
    EXCEPTION_PATTERN = re.compile(
        r"^(?P<type>[a-zA-Z_][a-zA-Z0-9_.]*(?:Error|Exception|Violation|AssertionError)):\s*(?P<msg>.*)$", re.MULTILINE
    )

    @classmethod
    def parse(cls, raw_trace: str) -> CrashDiagnostic:
        """Parses raw text traceback into a structured CrashDiagnostic."""
        if not raw_trace or not raw_trace.strip():
            return CrashDiagnostic(
                exception_type="UnknownError",
                error_message="Empty traceback provided.",
                raw_traceback="",
            )

        frames = []
        for match in cls.FRAME_PATTERN.finditer(raw_trace):
            frames.append(
                StackFrame(
                    file_path=match.group("file"),
                    line_number=int(match.group("line")),
                    function_name=match.group("func"),
                    code_line=match.group("code").strip(),
                )
            )

        # Extract exception type and message from the tail
        exc_type = "RuntimeError"
        exc_msg = "Execution failed."

        exc_matches = list(cls.EXCEPTION_PATTERN.finditer(raw_trace))
        if exc_matches:
            last_exc = exc_matches[-1]
            exc_type = last_exc.group("type")
            exc_msg = last_exc.group("msg").strip()
        else:
            # Fallback line scan for common assertion lines
            for line in reversed(raw_trace.splitlines()):
                if "Error" in line or "Exception" in line or "FAILED" in line:
                    parts = line.split(":", 1)
                    if len(parts) == 2:
                        exc_type = parts[0].strip().split()[-1]
                        exc_msg = parts[1].strip()
                    break

        failing_file = frames[-1].file_path if frames else None
        failing_line = frames[-1].line_number if frames else None

        return CrashDiagnostic(
            exception_type=exc_type,
            error_message=exc_msg,
            failing_file=failing_file,
            failing_line=failing_line,
            frames=frames,
            raw_traceback=raw_trace[:2000],
        )

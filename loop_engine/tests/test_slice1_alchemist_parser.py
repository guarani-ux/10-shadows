import pytest
from loop_engine.alchemist.trace_parser import CrashTraceParser


def test_crash_trace_parser_standard_traceback():
    sample_trace = """
Traceback (most recent call last):
  File "C:\\10 SHADOWS\\loop_engine\\governor.py", line 45, in run_loop
    candidate = runner.execute_staging(task_spec, staging_dir)
  File "C:\\10 SHADOWS\\loop_engine\\runners\\custom_runner.py", line 82, in execute_staging
    result = 10 / 0
ZeroDivisionError: division by zero
"""
    diag = CrashTraceParser.parse(sample_trace)

    assert diag.exception_type == "ZeroDivisionError"
    assert "division by zero" in diag.error_message
    assert len(diag.frames) == 2
    assert diag.frames[0].function_name == "run_loop"
    assert diag.frames[1].function_name == "execute_staging"
    assert diag.frames[1].line_number == 82
    assert "result = 10 / 0" in diag.frames[1].code_line
    assert diag.failing_file == "C:\\10 SHADOWS\\loop_engine\\runners\\custom_runner.py"
    assert diag.failing_line == 82


def test_crash_trace_parser_empty_input():
    diag = CrashTraceParser.parse("")
    assert diag.exception_type == "UnknownError"
    assert len(diag.frames) == 0

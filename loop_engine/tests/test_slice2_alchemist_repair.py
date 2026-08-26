import pytest
from loop_engine.alchemist.trace_parser import CrashTraceParser
from loop_engine.alchemist.repair_strategy import RepairStrategyEngine


def test_repair_strategy_zero_division():
    trace = """
Traceback (most recent call last):
  File "math_utils.py", line 12, in calculate_ratio
    ratio = count / total
ZeroDivisionError: division by zero
"""
    diag = CrashTraceParser.parse(trace)
    patch = RepairStrategyEngine.generate_patch(diag)

    assert patch.target_file == "math_utils.py"
    assert patch.target_line == 12
    assert "ratio = count / total" in patch.original_snippet
    assert "ZeroDivisionError" in patch.rationale


def test_repair_strategy_key_error():
    trace = """
Traceback (most recent call last):
  File "handler.py", line 40, in get_user_id
    user_id = data['user_id']
KeyError: 'user_id'
"""
    diag = CrashTraceParser.parse(trace)
    patch = RepairStrategyEngine.generate_patch(diag)

    assert patch.target_file == "handler.py"
    assert patch.target_line == 40
    assert "KeyError" in patch.rationale

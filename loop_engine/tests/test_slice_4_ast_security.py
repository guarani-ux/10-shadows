from pathlib import Path

import pytest

from loop_engine.verifiers.ast_gate import (
    inspect_file_ast,
    validate_ast_security,
)


def test_clean_python_code_passes():
    code = """
def calculate_metrics(values: list[int]) -> int:
    return sum(values) * 2

result = calculate_metrics([1, 2, 3])
"""
    passed, violations = validate_ast_security(code)
    assert passed is True
    assert violations == []


def test_banned_eval_call_rejected():
    code = """
def bad_function():
    return eval("2 + 2")
"""
    passed, violations = validate_ast_security(code)
    assert passed is False
    assert any("Banned function call 'eval()'" in v for v in violations)


def test_banned_exec_call_rejected():
    code = """
exec("import os; os.system('calc')")
"""
    passed, violations = validate_ast_security(code)
    assert passed is False
    assert any("Banned function call 'exec()'" in v for v in violations)


def test_banned_os_system_rejected():
    code = """
import os
os.system("whoami")
"""
    passed, violations = validate_ast_security(code)
    assert passed is False
    assert any("Banned execution call 'os.system()'" in v for v in violations)


def test_banned_dynamic_import_rejected():
    code = """
import importlib
mod = importlib.import_module("os")
"""
    passed, violations = validate_ast_security(code)
    assert passed is False
    assert any("Banned dynamic import 'importlib.import_module()'" in v for v in violations)


def test_banned_network_module_rejected():
    code = """
import socket
s = socket.socket()
"""
    passed, violations = validate_ast_security(code)
    assert passed is False
    assert any("Banned network module import 'socket'" in v for v in violations)


def test_syntax_error_extracted_cleanly():
    broken_code = "def broken(:\n    pass"
    passed, violations = validate_ast_security(broken_code)
    assert passed is False
    assert any("SyntaxError" in v for v in violations)


def test_inspect_file_ast(tmp_path):
    safe_file = tmp_path / "safe.py"
    safe_file.write_text("x = 42\n", encoding="utf-8")
    passed, violations = inspect_file_ast(safe_file)
    assert passed is True

    unsafe_file = tmp_path / "unsafe.py"
    unsafe_file.write_text("eval('1+1')\n", encoding="utf-8")
    passed, violations = inspect_file_ast(unsafe_file)
    assert passed is False

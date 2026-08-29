from pathlib import Path

import pytest

from loop_engine.verifiers.test_gate import PROJECT_ROOT, run_isolated_pytest


def test_isolated_pytest_success(tmp_path):
    # Create a temporary passing test
    test_file = tmp_path / "test_sample_pass.py"
    test_file.write_text("def test_ok():\n    assert 1 + 1 == 2\n", encoding="utf-8")

    result = run_isolated_pytest(str(test_file), cwd=tmp_path, timeout_seconds=10.0)

    assert result["status"] == "PASS"
    assert result["exit_code"] == 0
    assert result["timed_out"] is False
    assert "1 passed" in result["stdout"]


def test_isolated_pytest_failure(tmp_path):
    # Create a temporary failing test
    test_file = tmp_path / "test_sample_fail.py"
    test_file.write_text("def test_fail():\n    assert 1 == 2\n", encoding="utf-8")

    result = run_isolated_pytest(str(test_file), cwd=tmp_path, timeout_seconds=10.0)

    assert result["status"] == "FAIL"
    assert result["exit_code"] != 0
    assert result["timed_out"] is False
    assert "1 failed" in result["stdout"]


def test_isolated_pytest_timeout_enforcement(tmp_path):
    # Create a test that sleeps longer than the timeout
    test_file = tmp_path / "test_sample_timeout.py"
    test_file.write_text("import time\ndef test_slow():\n    time.sleep(3)\n", encoding="utf-8")

    # Enforce strict 1-second timeout
    result = run_isolated_pytest(str(test_file), cwd=tmp_path, timeout_seconds=1.0)

    assert result["status"] == "TIMEOUT"
    assert result["exit_code"] == 124
    assert result["timed_out"] is True
    assert "timed out after 1.0 seconds" in result["stderr"]

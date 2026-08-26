import pytest
import subprocess
import sys
from loop_engine.gamemaster.cli import run_cli


def test_cli_invocation_returns_zero():
    cmd = [sys.executable, "-m", "loop_engine.gamemaster.cli", "--hud"]
    res = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert res.returncode == 0
    assert "10 SHADOWS" in res.stdout
    assert "The Game Master" in res.stdout

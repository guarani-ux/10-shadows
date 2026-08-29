import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# Invariant: Explicit workspace anchoring
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent


class SubprocessGateError(Exception):
    """Raised when subprocess execution harness encounters an unrecoverable error."""

    pass


def run_isolated_pytest(
    test_target: str,
    cwd: Optional[Path] = None,
    timeout_seconds: float = 10.0,
    extra_env: Optional[Dict[str, str]] = None,
) -> Dict[str, Any]:
    """
    Executes a pytest target inside an isolated subprocess environment:
    - Binds strictly to sys.executable (exact Python runtime)
    - Injects clean PYTHONPATH anchored to PROJECT_ROOT
    - Prevents stdin deadlocks with subprocess.DEVNULL
    - Enforces hard execution timeout
    - Returns structured execution result telemetry
    """
    execution_cwd = cwd or PROJECT_ROOT

    # Build clean environment with PYTHONPATH
    env = os.environ.copy()
    env["PYTHONPATH"] = str(PROJECT_ROOT)
    env["PYTHONUNBUFFERED"] = "1"
    if extra_env:
        env.update(extra_env)

    command = [
        sys.executable,
        "-m",
        "pytest",
        str(test_target),
        "-v",
        "--tb=short",
    ]

    start_time = time.time()
    try:
        proc = subprocess.run(
            command,
            cwd=str(execution_cwd),
            env=env,
            capture_output=True,
            text=True,
            stdin=subprocess.DEVNULL,
            timeout=timeout_seconds,
        )
        duration = round(time.time() - start_time, 3)
        exit_code = proc.returncode
        stdout = proc.stdout
        stderr = proc.stderr
        passed = exit_code == 0

        return {
            "status": "PASS" if passed else "FAIL",
            "exit_code": exit_code,
            "duration_seconds": duration,
            "stdout": stdout,
            "stderr": stderr,
            "timed_out": False,
        }

    except subprocess.TimeoutExpired as e:
        duration = round(time.time() - start_time, 3)
        return {
            "status": "TIMEOUT",
            "exit_code": 124,
            "duration_seconds": duration,
            "stdout": e.stdout or "",
            "stderr": f"Process execution timed out after {timeout_seconds} seconds.",
            "timed_out": True,
        }
    except Exception as e:
        duration = round(time.time() - start_time, 3)
        return {
            "status": "ERROR",
            "exit_code": 1,
            "duration_seconds": duration,
            "stdout": "",
            "stderr": f"Subprocess harness invocation error: {str(e)}",
            "timed_out": False,
        }

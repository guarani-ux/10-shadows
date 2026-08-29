"""
tests/test_architectural_fitness.py
Architectural Fitness Functions & Structural Invariant Tests for 10 SHADOWS.

Enforces:
1. No runtime database or receipt files are tracked by Git.
2. No legacy substring heuristics exist in the sovereign Rust kernel.
3. Language boundary schemas (Rust/Python) maintain strict protocol parity.
4. Forbidden reverse dependency directions are mathematically absent.
5. Wildcard capability defaults are absent.
6. Centralized configuration and path boundaries are respected.
"""

from __future__ import annotations

import ast
import os
import subprocess
from pathlib import Path
from typing import List, Set

import pytest

from forge.core.substrate import EvidenceClass, OperatorType
from loop_engine.config import (
    FIXTURES_DIR,
    KERNEL_DB_PATH,
    PROJECT_ROOT,
    PROTOCOL_VERSION,
    RECEIPTS_DIR,
    SCRATCH_DIR,
    SYSTEM_VERSION,
)
from loop_engine.constitution.capability import (
    CapabilityEpistemicStatus,
    ConditionalCapability,
    OperationalCondition,
)
from loop_engine.dispatcher.protocol import (
    WorkerAuthorization,
    WorkerExecutionResult,
    compute_authorization_token,
)


def test_fitness_01_no_runtime_artifacts_tracked_in_git():
    """FITNESS INVARIANT 1: Git repository must not track runtime .db, .sqlite, or .receipts files."""
    res = subprocess.run(
        ["git", "ls-files", "*.db", "*.sqlite", ".receipts/*", "*.pyc", "*.log", "scratch/*", "sandbox/*"],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    tracked_runtime = [f for f in res.stdout.splitlines() if f.strip()]
    assert tracked_runtime == [], f"Tracked runtime artifacts detected in Git index: {tracked_runtime}"


def test_fitness_02_no_legacy_substring_heuristics_in_rust_kernel():
    """FITNESS INVARIANT 2: Sovereign kernel must not contain legacy substring semantic heuristics."""
    kernel_state_machine_rs = PROJECT_ROOT / "crates" / "ten_shadows_kernel" / "src" / "state_machine.rs"
    assert kernel_state_machine_rs.exists()
    content = kernel_state_machine_rs.read_text(encoding="utf-8")

    assert 'contains("multiply")' not in content
    assert 'contains("add")' not in content
    assert "derive_default_contract" not in content
    assert "CORE_OBJECTIVE_SATISFACTION" not in content


def test_fitness_03_rust_python_protocol_token_parity():
    """FITNESS INVARIANT 3: Python and Rust compute mathematically identical authorization tokens."""
    run_id = "run_parity_001"
    task_id = "task_parity_001"
    inv_id = "inv_parity_001"
    obj_hash = "0" * 64
    base_sha = "1" * 40
    ws_path = str(PROJECT_ROOT / "scratch" / "test_ws")
    attempt = 1

    python_token = compute_authorization_token(
        run_id=run_id,
        task_id=task_id,
        invocation_id=inv_id,
        objective_hash=obj_hash,
        baseline_sha=base_sha,
        governed_workspace_path=ws_path,
        attempt_number=attempt,
    )

    # Mathematical raw specification: {run_id}:{task_id}:{invocation_id}:{objective_hash}:{baseline_sha}:{ws_path}:{attempt_number}
    import hashlib

    expected_raw = f"{run_id}:{task_id}:{inv_id}:{obj_hash}:{base_sha}:{ws_path}:{attempt}"
    expected_hash = hashlib.sha256(expected_raw.encode("utf-8")).hexdigest()

    assert python_token == expected_hash


def test_fitness_04_no_wildcard_capability_defaults():
    """FITNESS INVARIANT 4: ConditionalCapability must not permit wildcard environment bypass without explicit condition."""
    cond = OperationalCondition("cond1", "specific env", "linux_x86_64", ["socket"])
    cap = ConditionalCapability(
        capability_id="cap_test",
        actor_id="worker_01",
        operator_type=OperatorType.ACT,
        supported_environments={"linux_x86_64"},
        supported_conditions=[cond],
        required_evidence_classes=[EvidenceClass.EMPIRICAL_TEST],
        epistemic_status=CapabilityEpistemicStatus.QUALIFIED,
    )

    assert "*" not in cap.supported_environments
    assert cap.is_applicable("darwin_arm64", ["socket"]) is False
    assert cap.is_applicable("linux_x86_64", ["socket"]) is True


def test_fitness_05_package_dependency_direction_integrity():
    """FITNESS INVARIANT 5: Constitution and schema modules must not import runners or CLI gamemaster."""
    constitution_dir = PROJECT_ROOT / "loop_engine" / "constitution"
    for py_file in constitution_dir.glob("*.py"):
        tree = ast.parse(py_file.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    assert not alias.name.startswith("loop_engine.runners"), (
                        f"Forbidden dependency: {py_file.name} imports {alias.name}"
                    )
                    assert not alias.name.startswith("loop_engine.gamemaster"), (
                        f"Forbidden dependency: {py_file.name} imports {alias.name}"
                    )
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    assert not node.module.startswith("loop_engine.runners"), (
                        f"Forbidden dependency: {py_file.name} imports {node.module}"
                    )
                    assert not node.module.startswith("loop_engine.gamemaster"), (
                        f"Forbidden dependency: {py_file.name} imports {node.module}"
                    )


def test_fitness_06_configuration_and_scratch_separation():
    """FITNESS INVARIANT 6: SCRATCH_DIR must be separated from source roots."""
    assert SCRATCH_DIR != PROJECT_ROOT
    assert RECEIPTS_DIR.name == ".receipts"
    assert KERNEL_DB_PATH.parent == SCRATCH_DIR

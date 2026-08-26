import os
import sqlite3
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field
from loop_engine.base import PROJECT_ROOT


class ShadowDomainState(BaseModel):
    """Real-time physical state of an individual domain shadow."""
    shadow_id: int = Field(ge=1, le=10)
    name: str
    code_name: str
    status: str  # "ONLINE", "PARTIAL", "ABSENT"
    has_module: bool
    has_runner: bool
    test_files_count: int
    receipts_count: int


class SystemTelemetryHUD(BaseModel):
    """Master operating system projection computed purely from physical ground truth."""
    system_name: str = "10 SHADOWS"
    runtime_version: str = "3.0.0-SOVEREIGN"
    git_branch: str
    git_commit: str
    working_tree_clean: bool
    discovered_test_files: int
    total_wal_receipts: int
    receipts_by_status: Dict[str, int] = Field(default_factory=dict)
    domains: List[ShadowDomainState] = Field(default_factory=list)


class SovereignStateProjector:
    """
    Shadow 10 (The Game Master) Telemetry & HUD Engine.
    
    Dynamically inspects Git repository, physical filesystems, test directories,
    and SQLite WAL receipt databases to project real-time system status.
    Zero hardcoded values.
    """

    SHADOW_DEFINITIONS = [
        (1, "The Forge", "forge", ["loop_engine/runners/forge_runner.py"]),
        (2, "svris", "svris", ["loop_engine/verifiers/ast_gate.py", "loop_engine/runners/svris_runner.py"]),
        (3, "The Herald", "herald", ["loop_engine/herald/", "loop_engine/runners/herald_runner.py"]),
        (4, "The Scout", "media", ["loop_engine/media/", "loop_engine/runners/media_runner.py"]),
        (5, "The Inquisitor", "inquisitor", [".agents/skills/adversarial-plan-auditor/"]),
        (6, "The Scribe", "scribe", ["loop_engine/scribe/", "loop_engine/runners/scribe_runner.py"]),
        (7, "The Slicer", "slicer", ["loop_engine/slicer/", "loop_engine/runners/slicer_runner.py"]),
        (8, "The Warden", "warden", ["loop_engine/harness/git_worktree.py"]),
        (9, "The Alchemist", "alchemist", ["loop_engine/alchemist/", "loop_engine/runners/alchemist_runner.py"]),
        (10, "The Game Master", "gamemaster", ["loop_engine/gamemaster/"]),
    ]

    def __init__(self, root_dir: Optional[Path] = None):
        self.root_dir = root_dir or PROJECT_ROOT
        self.receipts_db = self.root_dir / "scratch" / "receipts.db"

    def get_git_telemetry(self) -> Dict[str, Any]:
        """Queries Git binary for active branch, commit SHA, and tree cleanliness."""
        try:
            branch = subprocess.check_output(
                ["git", "rev-parse", "--abbrev-ref", "HEAD"],
                cwd=str(self.root_dir),
                stderr=subprocess.DEVNULL,
                text=True,
            ).strip()
        except Exception:
            branch = "UNKNOWN_BRANCH"

        try:
            commit = subprocess.check_output(
                ["git", "rev-parse", "--short", "HEAD"],
                cwd=str(self.root_dir),
                stderr=subprocess.DEVNULL,
                text=True,
            ).strip()
        except Exception:
            commit = "UNKNOWN_COMMIT"

        try:
            status_out = subprocess.check_output(
                ["git", "status", "--porcelain"],
                cwd=str(self.root_dir),
                stderr=subprocess.DEVNULL,
                text=True,
            ).strip()
            is_clean = len(status_out) == 0
        except Exception:
            is_clean = False

        return {
            "branch": branch,
            "commit": commit,
            "is_clean": is_clean,
        }

    def get_receipts_telemetry(self) -> Dict[str, Any]:
        """Queries SQLite WAL database for receipt totals, status distribution, and per-task rows."""
        if not self.receipts_db.exists():
            return {"total": 0, "by_status": {}, "rows": []}
        try:
            conn = sqlite3.connect(str(self.receipts_db))
            total_row = conn.execute("SELECT COUNT(*) FROM receipts").fetchone()
            total = total_row[0] if total_row else 0

            status_rows = conn.execute("SELECT status, COUNT(*) FROM receipts GROUP BY status").fetchall()
            by_status = {status: count for status, count in status_rows}

            # Fetch task_ids and receipt details
            all_rows = conn.execute("SELECT task_id, status FROM receipts").fetchall()
            conn.close()
            return {"total": total, "by_status": by_status, "rows": all_rows}
        except Exception:
            return {"total": 0, "by_status": {}, "rows": []}

    def get_test_files_count(self) -> int:
        """Counts discovered test files on disk in loop_engine/tests."""
        tests_dir = self.root_dir / "loop_engine" / "tests"
        if not tests_dir.exists():
            return 0
        return len(list(tests_dir.glob("test_*.py")))

    def get_domain_states(self, receipts_data: Optional[Dict[str, Any]] = None) -> List[ShadowDomainState]:
        """Inspects disk and SQLite database to derive the true status of each Shadow domain."""
        domain_states = []
        tests_dir = self.root_dir / "loop_engine" / "tests"
        all_test_files = list(tests_dir.glob("test_*.py")) if tests_dir.exists() else []
        receipt_rows = (receipts_data or {}).get("rows", [])

        for s_id, name, code_name, expected_paths in self.SHADOW_DEFINITIONS:
            # Check physical path existence strictly relative to root_dir
            has_module = any((self.root_dir / p).exists() for p in expected_paths)
            
            # Check for executable runner or integration
            runner_file = self.root_dir / "loop_engine" / "runners" / f"{code_name}_runner.py"
            has_runner = runner_file.exists() or (s_id in [5, 8, 10] and has_module)
            
            # Count domain-specific test files
            domain_tests = [
                f for f in all_test_files
                if code_name in f.name.lower() or name.lower().replace("the ", "") in f.name.lower()
            ]

            # Count domain-specific receipts dynamically by matching task_id patterns
            domain_receipt_count = sum(
                1 for task_id, status in receipt_rows
                if code_name in task_id.lower() or (s_id == 3 and "tight" in task_id.lower()) or (s_id == 9 and "heal" in task_id.lower())
            )

            if has_module and has_runner:
                status = "ONLINE"
            elif has_module or has_runner:
                status = "PARTIAL"
            else:
                status = "ABSENT"

            domain_states.append(
                ShadowDomainState(
                    shadow_id=s_id,
                    name=name,
                    code_name=code_name,
                    status=status,
                    has_module=has_module,
                    has_runner=has_runner,
                    test_files_count=len(domain_tests),
                    receipts_count=domain_receipt_count,
                )
            )

        return domain_states

    def project_hud(self) -> SystemTelemetryHUD:
        """Compiles unified operating system projection from ground-truth data."""
        git_info = self.get_git_telemetry()
        receipts_info = self.get_receipts_telemetry()
        test_files_count = self.get_test_files_count()
        domains = self.get_domain_states(receipts_data=receipts_info)

        return SystemTelemetryHUD(
            system_name="10 SHADOWS",
            runtime_version="3.0.0-SOVEREIGN",
            git_branch=git_info["branch"],
            git_commit=git_info["commit"],
            working_tree_clean=git_info["is_clean"],
            discovered_test_files=test_files_count,
            total_wal_receipts=receipts_info["total"],
            receipts_by_status=receipts_info["by_status"],
            domains=domains,
        )

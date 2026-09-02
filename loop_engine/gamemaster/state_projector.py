import sqlite3
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from loop_engine.base import PROJECT_ROOT


class ShadowDomainState(BaseModel):
    """Structural telemetry for one named Ten Shadows domain."""

    shadow_id: int = Field(ge=1, le=10)
    name: str
    code_name: str
    status: str  # "PRESENT", "PARTIAL", "ABSENT"
    has_module: bool
    has_runner: bool
    test_files_count: int
    receipts_count: int


class SystemTelemetryHUD(BaseModel):
    """Local repository/runtime telemetry. It is not a capability certification."""

    system_name: str = "10 SHADOWS"
    runtime_version: str = "telemetry-v1"
    git_branch: str
    git_commit: str
    working_tree_clean: bool
    discovered_test_files: int
    total_wal_receipts: int
    receipts_by_status: Dict[str, int] = Field(default_factory=dict)
    domains: List[ShadowDomainState] = Field(default_factory=list)


class SovereignStateProjector:
    """
    Shadow 10 (Game Master) telemetry projector.

    It inspects Git metadata, selected filesystem paths, test-file names, and a
    local receipt database. Those observations establish structural/runtime
    telemetry only. They do not prove that a domain is operational, verified,
    secure, or repository-qualified.
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
        """Query Git for branch, commit, and working-tree cleanliness."""
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

        return {"branch": branch, "commit": commit, "is_clean": is_clean}

    def get_receipts_telemetry(self) -> Dict[str, Any]:
        """Read local receipt totals and distributions if the receipt database exists."""
        if not self.receipts_db.exists():
            return {"total": 0, "by_status": {}, "by_shadow": {}, "by_code": {}}
        try:
            conn = sqlite3.connect(str(self.receipts_db))
            total_row = conn.execute("SELECT COUNT(*) FROM receipts").fetchone()
            total = total_row[0] if total_row else 0

            status_rows = conn.execute("SELECT status, COUNT(*) FROM receipts GROUP BY status").fetchall()
            by_status = {status: count for status, count in status_rows}

            shadow_rows = conn.execute(
                "SELECT shadow_id, domain_code, COUNT(*) FROM receipts GROUP BY shadow_id, domain_code"
            ).fetchall()
            by_shadow: Dict[int, int] = {}
            by_code: Dict[str, int] = {}
            for shadow_id, domain_code, count in shadow_rows:
                by_shadow[shadow_id] = count
                by_code[domain_code] = count

            conn.close()
            return {"total": total, "by_status": by_status, "by_shadow": by_shadow, "by_code": by_code}
        except Exception:
            return {"total": 0, "by_status": {}, "by_shadow": {}, "by_code": {}}

    def get_test_files_count(self) -> int:
        """Count test files in loop_engine/tests; this is not a pass/fail result."""
        tests_dir = self.root_dir / "loop_engine" / "tests"
        if not tests_dir.exists():
            return 0
        return len(list(tests_dir.glob("test_*.py")))

    def get_domain_states(self, receipts_data: Optional[Dict[str, Any]] = None) -> List[ShadowDomainState]:
        """Derive structural presence only; never infer operational proof from file presence."""
        domain_states = []
        tests_dir = self.root_dir / "loop_engine" / "tests"
        all_test_files = list(tests_dir.glob("test_*.py")) if tests_dir.exists() else []
        receipt_info = receipts_data or {}
        by_shadow = receipt_info.get("by_shadow", {})
        by_code = receipt_info.get("by_code", {})

        for shadow_id, name, code_name, expected_paths in self.SHADOW_DEFINITIONS:
            has_module = any((self.root_dir / path).exists() for path in expected_paths)
            runner_file = self.root_dir / "loop_engine" / "runners" / f"{code_name}_runner.py"
            has_runner = runner_file.exists() or (shadow_id in [5, 8, 10] and has_module)

            domain_tests = [
                file
                for file in all_test_files
                if code_name in file.name.lower() or name.lower().replace("the ", "") in file.name.lower()
            ]

            receipts_count = by_shadow.get(shadow_id, 0) or by_code.get(code_name, 0)

            if has_module and has_runner:
                status = "PRESENT"
            elif has_module or has_runner:
                status = "PARTIAL"
            else:
                status = "ABSENT"

            domain_states.append(
                ShadowDomainState(
                    shadow_id=shadow_id,
                    name=name,
                    code_name=code_name,
                    status=status,
                    has_module=has_module,
                    has_runner=has_runner,
                    test_files_count=len(domain_tests),
                    receipts_count=receipts_count,
                )
            )

        return domain_states

    def project_hud(self) -> SystemTelemetryHUD:
        """Compile local telemetry without upgrading observations into capability claims."""
        git_info = self.get_git_telemetry()
        receipts_info = self.get_receipts_telemetry()
        test_files_count = self.get_test_files_count()
        domains = self.get_domain_states(receipts_data=receipts_info)

        return SystemTelemetryHUD(
            system_name="10 SHADOWS",
            runtime_version="telemetry-v1",
            git_branch=git_info["branch"],
            git_commit=git_info["commit"],
            working_tree_clean=git_info["is_clean"],
            discovered_test_files=test_files_count,
            total_wal_receipts=receipts_info["total"],
            receipts_by_status=receipts_info["by_status"],
            domains=domains,
        )

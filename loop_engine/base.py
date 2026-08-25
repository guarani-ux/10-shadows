import os
import shutil
import stat
import uuid
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

# Invariant: Explicitly discover and anchor to the project root
PROJECT_ROOT = Path(__file__).resolve().parent.parent
STAGING_ROOT = PROJECT_ROOT / "scratch" / "staging"


def force_remove_readonly(func, path, excinfo):
    """
    Error callback for shutil.rmtree on Windows.
    Clears read-only file attribute and retries deletion.
    """
    try:
        os.chmod(path, stat.S_IWRITE)
        func(path)
    except Exception:
        pass


class BaseLoop(ABC):
    """
    Abstract Base Class for all autonomous execution loops.
    Enforces isolated staging, deterministic verification, and atomic state transition.
    """

    def __init__(self, name: str, max_strikes: int = 3):
        self.name = name
        self.max_strikes = max_strikes

    @abstractmethod
    def normalize(self, raw_input: Any) -> Dict[str, Any]:
        """Convert raw input into structured TaskSpec."""
        pass

    @abstractmethod
    def execute_staging(
        self,
        task_spec: Dict[str, Any],
        staging_dir: Path,
        feedback: Optional[str] = None,
    ) -> Path:
        """Execute candidate generation within the isolated staging directory."""
        pass

    @abstractmethod
    def verify(
        self,
        candidate_path: Path,
        task_spec: Dict[str, Any],
    ) -> Tuple[bool, str]:
        """
        Evaluate candidate artifact against deterministic verification gates.
        Returns (passed: bool, error_message: str).
        """
        pass

    @abstractmethod
    def commit(
        self,
        candidate_path: Path,
        task_spec: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Atomically commit verified artifact to destination workspace."""
        pass

    def run(self, raw_input: Any) -> Dict[str, Any]:
        """
        Core Execution Driver (Slice 1: Hollow Pipe Lifecycle).
        """
        task_spec = self.normalize(raw_input)
        task_id = task_spec.get("task_id", f"task_{uuid.uuid4().hex[:8]}")
        run_id = f"run_{task_id}_{uuid.uuid4().hex[:6]}"

        # Allocate unique, isolated staging workspace
        staging_dir = STAGING_ROOT / run_id
        if staging_dir.exists():
            shutil.rmtree(staging_dir, onerror=force_remove_readonly)
        staging_dir.mkdir(parents=True, exist_ok=True)

        try:
            # 1. Execute generation into staging
            candidate_path = self.execute_staging(task_spec, staging_dir)

            # 2. Verify candidate
            passed, error_msg = self.verify(candidate_path, task_spec)

            if not passed:
                return {
                    "status": "FAILED",
                    "run_id": run_id,
                    "task_id": task_id,
                    "error": error_msg,
                }

            # 3. Commit verified artifact
            receipt = self.commit(candidate_path, task_spec)

            return {
                "status": "SUCCESS",
                "run_id": run_id,
                "task_id": task_id,
                "receipt": receipt,
            }

        finally:
            # Clean up staging directory
            if staging_dir.exists():
                shutil.rmtree(staging_dir, onerror=force_remove_readonly)

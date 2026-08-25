from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from loop_engine.base import BaseLoop, PROJECT_ROOT
from loop_engine.extractor import strip_markdown_fences, safe_extract_target
from loop_engine.receipts import atomic_two_phase_commit, ReceiptStore
from loop_engine.verifiers.ast_gate import validate_ast_security
from loop_engine.verifiers.test_gate import run_isolated_pytest


class CodeRunnerLoop(BaseLoop):
    """
    Domain 1: The Forge Code Runner.
    Executes Python tool generation and modifications with mandatory AST static security
    and subprocess pytest gates.
    """

    def __init__(
        self,
        name: str = "TheForgeRunner",
        max_strikes: int = 3,
        receipt_store: Optional[ReceiptStore] = None,
    ):
        super().__init__(name=name, max_strikes=max_strikes)
        self.receipt_store = receipt_store or ReceiptStore()

    def normalize(self, raw_input: Any) -> Dict[str, Any]:
        """
        Normalizes task payload into a structured TaskSpec.
        """
        if isinstance(raw_input, dict):
            task_id = raw_input.get("task_id", "forge_task")
            target_filename = raw_input.get("target_filename", "generated_tool.py")
            code_payload = raw_input.get("code", "")
            test_file = raw_input.get("test_file")
            destination_path = raw_input.get("destination_path")
        else:
            task_id = "forge_task"
            target_filename = "generated_tool.py"
            code_payload = str(raw_input)
            test_file = None
            destination_path = None

        clean_code = strip_markdown_fences(code_payload)
        return {
            "task_id": task_id,
            "target_filename": target_filename,
            "code": clean_code,
            "test_file": test_file,
            "destination_path": str(destination_path) if destination_path else None,
        }

    def execute_staging(
        self,
        task_spec: Dict[str, Any],
        staging_dir: Path,
        feedback: Optional[str] = None,
    ) -> Path:
        """
        Writes candidate code into the isolated staging sandbox.
        """
        target_path = safe_extract_target(task_spec["target_filename"], staging_dir)
        target_path.parent.mkdir(parents=True, exist_ok=True)
        target_path.write_text(task_spec["code"], encoding="utf-8")
        return target_path

    def verify(
        self,
        candidate_path: Path,
        task_spec: Dict[str, Any],
    ) -> Tuple[bool, str]:
        """
        Two-Tier Verification Gate:
        1. Static AST Security Gate (No eval, exec, os.system, raw sockets).
        2. Subprocess Pytest Gate (if test_file is provided in task_spec).
        """
        # Tier 1: AST Static Security Gate
        ast_ok, ast_violations = validate_ast_security(candidate_path.read_text(encoding="utf-8"))
        if not ast_ok:
            return False, f"AST Security Gate Failed: {'; '.join(ast_violations)}"

        # Tier 2: Subprocess Test Gate (if test is attached)
        test_target = task_spec.get("test_file")
        if test_target:
            test_path = Path(test_target)
            if test_path.exists():
                test_result = run_isolated_pytest(
                    test_target=str(test_path),
                    cwd=candidate_path.parent,
                    timeout_seconds=10.0,
                )
                if test_result["status"] != "PASS":
                    return False, f"Subprocess Pytest Gate Failed:\n{test_result.get('stderr') or test_result.get('stdout')}"

        return True, ""

    def commit(
        self,
        candidate_path: Path,
        task_spec: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Executes atomic 2-phase commit and records audit receipt to SQLite WAL store.
        """
        if task_spec.get("destination_path"):
            destination = Path(task_spec["destination_path"])
        else:
            destination = PROJECT_ROOT / "scratch" / "forge_output" / task_spec["target_filename"]

        commit_result = atomic_two_phase_commit(candidate_path, destination)

        # Log receipt
        receipt_id = self.receipt_store.record_receipt(
            task_id=task_spec["task_id"],
            run_id=f"run_{task_spec['task_id']}",
            spec_hash=commit_result["sha256"][:16],
            status="COMMITTED",
            strikes_used=1,
            target_file=str(destination.as_posix()),
            artifact_sha256=commit_result["sha256"],
            extra_data={"bytes": commit_result["bytes_written"]},
        )
        commit_result["receipt_id"] = receipt_id
        return commit_result

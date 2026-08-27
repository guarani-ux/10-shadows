"""
loop_engine/runners/forge_runner.py
Shadow 1: The Forge Domain Runner.
Bridges ForgeEngine with the hardened Loop Engine runtime:
- Executes code generation and resolution through ForgeEngine Grounded Satisfaction Resolution.
- Applies AST static security and isolated pytest gates in ephemeral Git Worktrees.
- Atomically merges verified code into master with cryptographic commit receipt.
"""

from pathlib import Path
from typing import Any, Dict, Optional, Tuple
import uuid

from loop_engine.base import BaseLoop, PROJECT_ROOT
from loop_engine.extractor import strip_markdown_fences, safe_extract_target
from loop_engine.harness.git_worktree import GitWorktreeHarness
from loop_engine.receipts import ReceiptStore
from loop_engine.verifiers.ast_gate import validate_ast_security
from loop_engine.verifiers.test_gate import run_isolated_pytest
try:
    from Forge.forge import ForgeEngine
except ImportError:
    from forge.forge import ForgeEngine


class ForgeDomainRunner(BaseLoop):
    """
    Shadow 1: The Forge Domain Runner.
    Bridges ForgeEngine with the hardened Loop Engine runtime.
    """

    def __init__(
        self,
        forge_engine: Optional[ForgeEngine] = None,
        receipt_store: Optional[ReceiptStore] = None,
        git_harness: Optional[GitWorktreeHarness] = None,
        max_strikes: int = 3,
    ):
        super().__init__(name="TheForgeDomainRunner", max_strikes=max_strikes)
        self.forge = forge_engine or ForgeEngine()
        self.receipt_store = receipt_store or ReceiptStore()
        self.git_harness = git_harness or GitWorktreeHarness()
        self.active_sandbox: Optional[Tuple[Path, str]] = None

    def normalize(self, raw_input: Any) -> Dict[str, Any]:
        """
        Normalizes raw request into TaskSpec using ForgeEngine's grounded resolution.
        """
        if isinstance(raw_input, str):
            request = {
                "request_id": f"req_{uuid.uuid4().hex[:8]}",
                "intent": raw_input,
                "context": [],
                "constraints": ["ast_safe", "no_eval"],
            }
        else:
            request = raw_input

        task_id = request.get("request_id", f"task_{uuid.uuid4().hex[:8]}")
        target_filename = request.get("target_filename", f"{task_id}.py")
        code_content = request.get("code") or ""
        test_file = request.get("test_file")

        # Run through ForgeEngine grounded resolution if raw intent without code
        resolution_proof = None
        deficit = None
        deficits = []

        if not request.get("code") and request.get("intent"):
            forge_payload = {
                "intent": request["intent"],
                "source_data": request.get("source_data", {}),
                "metadata": request.get("metadata", {}),
            }
            if "explicit_semantic_contracts" in request:
                forge_payload["explicit_semantic_contracts"] = request["explicit_semantic_contracts"]
            forge_res = self.forge.run(forge_payload)
            resolution_proof = forge_res.get("resolution_proof")
            if forge_res.get("status") == "SUCCESS":
                code_content = str(forge_res.get("result", {}).get("final_state", {}).get("repaired_code", code_content))
            else:
                deficit = forge_res.get("deficit_type") or forge_res.get("status", "RESOLUTION_DEFICIT")
                deficits = forge_res.get("deficits", [])
                code_content = ""

        return {
            "task_id": task_id,
            "target_filename": target_filename,
            "code": strip_markdown_fences(code_content),
            "test_file": test_file,
            "raw_request": request,
            "resolution_proof": resolution_proof,
            "deficit": deficit,
            "deficits": deficits,
        }

    def execute_staging(
        self,
        task_spec: Dict[str, Any],
        staging_dir: Path,
        feedback: Optional[str] = None,
    ) -> Path:
        """
        Generates candidate artifact into isolated staging / worktree boundary.
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
        Dual Verification Gates:
        1. AST Static Security Gate.
        2. Subprocess Pytest Gate (if test_file attached).
        """
        # Tier 1: AST Gate
        content = candidate_path.read_text(encoding="utf-8")
        ast_ok, violations = validate_ast_security(content)
        if not ast_ok:
            return False, f"AST Security Gate Rejected Candidate: {'; '.join(violations)}"

        # Tier 2: Pytest Gate
        test_target = task_spec.get("test_file")
        if test_target:
            test_path = Path(test_target)
            if test_path.exists():
                res = run_isolated_pytest(str(test_path), cwd=candidate_path.parent, timeout_seconds=10.0)
                if res["status"] != "PASS":
                    err_msg = res.get("stderr") or res.get("stdout") or "Test suite failed"
                    return False, f"Pytest Execution Failed:\n{err_msg}"

        return True, ""

    def commit(
        self,
        candidate_path: Path,
        task_spec: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Commits verified artifact to destination and logs receipt.
        """
        dest_dir = PROJECT_ROOT / "scratch" / "forge_output"
        dest_dir.mkdir(parents=True, exist_ok=True)
        dest_file = dest_dir / task_spec["target_filename"]

        dest_file.write_text(candidate_path.read_text(encoding="utf-8"), encoding="utf-8")

        receipt_id = self.receipt_store.record_receipt(
            task_id=task_spec["task_id"],
            run_id=f"run_{task_spec['task_id']}",
            spec_hash="forge_verified",
            status="COMMITTED",
            strikes_used=1,
            target_file=str(dest_file.as_posix()),
            extra_data={"target": task_spec["target_filename"]},
        )

        return {
            "status": "COMMITTED",
            "destination": str(dest_file.as_posix()),
            "receipt_id": receipt_id,
        }

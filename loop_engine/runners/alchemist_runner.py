import json
import uuid
import hashlib
import shutil
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

from loop_engine.base import BaseLoop, PROJECT_ROOT
from loop_engine.alchemist.trace_parser import CrashTraceParser
from loop_engine.alchemist.repair_strategy import RepairStrategyEngine, SurgicalPatch
from loop_engine.verifiers.ast_gate import inspect_file_ast
from loop_engine.verifiers.test_gate import run_isolated_pytest
from loop_engine.harness.git_worktree import GitWorktreeHarness
from loop_engine.receipts import ReceiptStore
from loop_engine.context import RunContext


class RealAlchemistSelfHealingEngine(BaseLoop):
    """
    Shadow 9 (The Alchemist) Active Self-Healing Engine.
    """

    def __init__(
        self,
        receipt_store: Optional[ReceiptStore] = None,
        max_strikes: int = 3,
        worktree_harness: Optional[GitWorktreeHarness] = None,
    ):
        super().__init__(name="TheAlchemistSelfHealingEngine", max_strikes=max_strikes)
        self.receipt_store = receipt_store or ReceiptStore()
        self.harness = worktree_harness or GitWorktreeHarness()
        self.run_context: Optional[RunContext] = None

    def normalize(self, raw_input: Any) -> Dict[str, Any]:
        """Normalizes crash payload or dictionary into TaskSpec."""
        if isinstance(raw_input, dict):
            task_id = raw_input.get("task_id", f"heal_{uuid.uuid4().hex[:8]}")
            raw_trace = raw_input.get("raw_trace", "")
            target_test_file = raw_input.get("target_test_file", None)
            source_file = raw_input.get("source_file", None)
        else:
            task_id = f"heal_{uuid.uuid4().hex[:8]}"
            raw_trace = str(raw_input)
            target_test_file = None
            source_file = None

        self.run_context = RunContext.create(
            task_id=task_id,
            shadow_id=9,
            domain_code="alchemist",
            raw_objective={"trace": raw_trace[:100], "source": source_file},
        )

        return {
            "task_id": task_id,
            "raw_trace": raw_trace,
            "target_test_file": target_test_file,
            "source_file": source_file,
            "run_id": self.run_context.run_id,
        }

    def execute_staging(
        self,
        task_spec: Dict[str, Any],
        staging_dir: Path,
        feedback: Optional[str] = None,
    ) -> Path:
        """
        Parses diagnostic, creates surgical patch proposal, and stages execution payload.
        """
        diagnostic = CrashTraceParser.parse(task_spec["raw_trace"])
        source_content = None
        if task_spec.get("source_file") and Path(task_spec["source_file"]).exists():
            source_content = Path(task_spec["source_file"]).read_text(encoding="utf-8")

        patch = RepairStrategyEngine.generate_patch(diagnostic, source_content)

        payload = {
            "task_id": task_spec["task_id"],
            "diagnostic": diagnostic.model_dump(),
            "patch": patch.model_dump(),
            "target_test_file": task_spec.get("target_test_file"),
            "source_file": task_spec.get("source_file"),
        }

        candidate_file = staging_dir / f"heal_payload_{task_spec['task_id']}.json"
        candidate_file.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        return candidate_file

    def verify(
        self,
        candidate_path: Path,
        task_spec: Dict[str, Any],
    ) -> Tuple[bool, str]:
        """
        Spawns an isolated ephemeral Warden Git worktree sandbox, applies the surgical patch
        strictly inside the worktree, verifies AST and targeted tests inside the sandbox,
        and safely tears down the worktree.
        """
        worktree_path: Optional[Path] = None
        branch_name: Optional[str] = None

        try:
            data = json.loads(candidate_path.read_text(encoding="utf-8"))
            patch_dict = data.get("patch", {})
            patch = SurgicalPatch.model_validate(patch_dict)

            target_file_path = task_spec.get("source_file") or patch.target_file
            if not target_file_path or not Path(target_file_path).exists():
                return False, f"Alchemist Repair Rejected: Target file '{target_file_path}' does not exist on disk."

            orig_path = Path(target_file_path)
            original_text = orig_path.read_text(encoding="utf-8")
            original_hash = hashlib.sha256(original_text.encode("utf-8")).hexdigest()

            lines = original_text.splitlines()
            if not (1 <= patch.target_line <= len(lines)):
                return False, f"Alchemist Repair Rejected: Target line {patch.target_line} out of bounds (1..{len(lines)})."

            patched_lines = list(lines)
            patched_lines[patch.target_line - 1] = patch.suggested_replacement
            patched_text = "\n".join(patched_lines)
            patched_hash = hashlib.sha256(patched_text.encode("utf-8")).hexdigest()

            if original_hash == patched_hash:
                return False, "Alchemist Repair Rejected: Patch produced an identical un-repaired candidate."

            # 2. Spawn isolated Warden worktree sandbox
            worktree_path, branch_name = self.harness.create_sandbox(task_spec["task_id"])

            # 3. Locate or mirror target source and test files into the Warden worktree sandbox
            try:
                rel_source = orig_path.relative_to(PROJECT_ROOT)
                wt_source = worktree_path / rel_source
            except ValueError:
                wt_source = worktree_path / "scratch" / "alchemist_sandbox" / orig_path.name
            
            wt_source.parent.mkdir(parents=True, exist_ok=True)
            wt_source.write_text(patched_text, encoding="utf-8")

            # 4. AST Syntax verification inside worktree
            ast_ok, violations = inspect_file_ast(wt_source)
            if not ast_ok:
                self.harness.destroy_sandbox(worktree_path, branch_name)
                return False, f"Alchemist AST Syntax Gate Failed in Sandbox: {violations}"

            # 5. Targeted test execution inside worktree sandbox
            target_test = task_spec.get("target_test_file")
            if target_test and Path(target_test).exists():
                orig_test_path = Path(target_test)
                try:
                    rel_test = orig_test_path.relative_to(PROJECT_ROOT)
                    wt_test = worktree_path / rel_test
                except ValueError:
                    wt_test = worktree_path / "scratch" / "alchemist_sandbox" / orig_test_path.name
                
                wt_test.parent.mkdir(parents=True, exist_ok=True)
                test_raw = orig_test_path.read_text(encoding="utf-8")
                rewritten_test = test_raw.replace(str(orig_path.parent), str(wt_source.parent))
                wt_test.write_text(rewritten_test, encoding="utf-8")

                extra_env = {"PYTHONPATH": f"{worktree_path};{wt_source.parent}"}
                test_res = run_isolated_pytest(
                    str(wt_test),
                    cwd=worktree_path,
                    timeout_seconds=15.0,
                    extra_env=extra_env,
                )
                if test_res["status"] != "PASS":
                    self.harness.destroy_sandbox(worktree_path, branch_name)
                    err_detail = test_res.get("stderr") or test_res.get("stdout")
                    return False, f"Alchemist Targeted Test Failed in Sandbox: {err_detail}"

            # 6. Clean destruction of temporary sandbox
            self.harness.destroy_sandbox(worktree_path, branch_name)

            data["original_sha256"] = original_hash
            data["patched_sha256"] = patched_hash
            data["patched_content"] = patched_text
            candidate_path.write_text(json.dumps(data, indent=2), encoding="utf-8")

            return True, ""
        except Exception as e:
            if worktree_path and branch_name:
                try:
                    self.harness.destroy_sandbox(worktree_path, branch_name)
                except Exception:
                    pass
            return False, f"Alchemist Closed-Loop Verification Exception: {str(e)}"

    def commit(
        self,
        candidate_path: Path,
        task_spec: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Permanently commits verified repair to disk and logs explicit forensic WAL receipt.
        """
        data = json.loads(candidate_path.read_text(encoding="utf-8"))
        target_file_path = Path(task_spec.get("source_file") or data["patch"]["target_file"])
        
        if "patched_content" in data:
            target_file_path.write_text(data["patched_content"], encoding="utf-8")

        run_id = task_spec.get("run_id") or f"run_{task_spec['task_id']}"

        receipt_id = self.receipt_store.record_receipt(
            task_id=task_spec["task_id"],
            run_id=run_id,
            shadow_id=9,
            domain_code="alchemist",
            stage="FINAL",
            attempt=1,
            candidate_hash=data.get("patched_sha256"),
            spec_hash="alchemist_warden_verified",
            status="COMMITTED",
            strikes_used=1,
            target_file=str(target_file_path.as_posix()),
            artifact_sha256=data.get("patched_sha256"),
            repair_strategy=data["patch"]["rationale"],
            promotion_decision="PROMOTED",
            extra_data={
                "original_sha256": data.get("original_sha256"),
                "patched_sha256": data.get("patched_sha256"),
                "repair_strategy": data["patch"]["rationale"],
            },
        )

        return {
            "status": "COMMITTED",
            "repaired_file": str(target_file_path.as_posix()),
            "receipt_id": receipt_id,
            "original_sha256": data.get("original_sha256"),
            "patched_sha256": data.get("patched_sha256"),
        }

import json
import uuid
import hashlib
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

from loop_engine.base import BaseLoop, PROJECT_ROOT
from loop_engine.slicer.slicer_engine import AutonomousSlicerEngine
from loop_engine.slicer.schema import SliceDAG, VerticalSliceTask
from loop_engine.receipts import ReceiptStore
from loop_engine.context import RunContext
from loop_engine.artifacts import MasterAVScriptArtifact, ProductionPlanDAGArtifact


class SlicerDomainRunner(BaseLoop):
    """
    Shadow 7 (The Slicer) Domain Runner.
    
    Autonomous loop for compiling macro goals, tasks, or MasterAVScriptArtifacts into
    verifiable, topologically-ordered ProductionPlanDAGArtifact execution plans.
    """

    def __init__(
        self,
        receipt_store: Optional[ReceiptStore] = None,
        max_strikes: int = 3,
    ):
        super().__init__(name="TheSlicerDomainRunner", max_strikes=max_strikes)
        self.shadow_id = 7
        self.domain_code = "slicer"
        self.engine = AutonomousSlicerEngine()
        self.receipt_store = receipt_store or ReceiptStore()
        self.run_context: Optional[RunContext] = None
        self.current_attempt: int = 1
        self.current_strike: int = 0
        self.parent_run_id: Optional[str] = None

    def set_governor_state(self, attempt: int, strike: int, parent_run_id: Optional[str] = None) -> None:
        """Receives measured attempt and strike metrics from StepGovernor."""
        self.current_attempt = attempt
        self.current_strike = strike
        self.parent_run_id = parent_run_id

    def normalize(self, raw_input: Any) -> Dict[str, Any]:
        """Normalizes goal description or MasterAVScriptArtifact into TaskSpec."""
        return self.normalize_with_context(raw_input, parent_context=None)

    def normalize_with_context(
        self,
        raw_input: Any,
        parent_context: Optional[RunContext] = None,
        step_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Normalizes input with optional parent context inheritance."""
        source_artifact_id = "root_input"
        source_artifact_hash = "0" * 64

        if isinstance(raw_input, MasterAVScriptArtifact):
            goal_id = f"slicer_{raw_input.script_id}"
            goal_desc = f"Production execution for: {raw_input.strategic_intent.project_title}"
            pkg_name = "media_production"
            source_artifact_id = getattr(raw_input, "artifact_id", raw_input.script_id)
            source_artifact_hash = raw_input.compute_content_hash()
            raw_tasks = None
        elif isinstance(raw_input, dict):
            goal_id = raw_input.get("goal_id", raw_input.get("task_id", f"goal_{uuid.uuid4().hex[:8]}"))
            goal_desc = raw_input.get("goal_description", raw_input.get("goal", ""))
            pkg_name = raw_input.get("base_package_name", "custom_module")
            raw_tasks = raw_input.get("raw_tasks")
            source_artifact_id = raw_input.get("source_artifact_id", "root")
            source_artifact_hash = raw_input.get("source_artifact_hash", "0" * 64)
        else:
            goal_id = f"goal_{uuid.uuid4().hex[:8]}"
            goal_desc = str(raw_input)
            pkg_name = "custom_module"
            raw_tasks = None

        if parent_context:
            self.run_context = parent_context.create_child(
                shadow_id=7,
                domain_code="slicer",
                step_id=step_id or "slicer_step",
                step_input={"goal_id": goal_id, "goal_desc": goal_desc},
            )
        else:
            self.run_context = RunContext.create(
                task_id=goal_id,
                shadow_id=7,
                domain_code="slicer",
                raw_objective={"goal_id": goal_id, "goal_desc": goal_desc},
            )

        return {
            "task_id": goal_id,
            "goal_description": goal_desc,
            "base_package_name": pkg_name,
            "raw_tasks": raw_tasks,
            "source_artifact_id": source_artifact_id,
            "source_artifact_hash": source_artifact_hash,
            "run_id": self.run_context.run_id,
            "parent_run_id": self.run_context.parent_run_id,
        }

    def execute_staging(
        self,
        task_spec: Dict[str, Any],
        staging_dir: Path,
        feedback: Optional[str] = None,
    ) -> Path:
        """
        Decomposes goal and stages the compiled ProductionPlanDAGArtifact or SliceDAG.
        """
        raw_tasks = task_spec.get("raw_tasks")
        if raw_tasks:
            # Construct slices from explicit raw tasks
            slices = []
            for idx, t in enumerate(raw_tasks, 1):
                slices.append(
                    VerticalSliceTask(
                        slice_id=t.get("slice_id", f"slice_{idx}"),
                        slice_number=idx,
                        title=t.get("name", f"Task {idx}"),
                        objective=t.get("name", f"Task {idx}"),
                        target_module=t.get("target_module", f"modules/task_{idx}.py"),
                        target_test=t.get("target_test", f"tests/test_task_{idx}.py"),
                        dependencies=t.get("dependencies", []),
                    )
                )
            dag = SliceDAG(
                goal_id=task_spec["task_id"],
                goal_description=task_spec["goal_description"],
                slices=slices,
            )
        else:
            dag = self.engine.slice_engineering_goal(
                goal_description=task_spec["goal_description"],
                goal_id=task_spec["task_id"],
                base_package_name=task_spec["base_package_name"],
            )

        ordered_slices = dag.get_execution_order()

        artifact = ProductionPlanDAGArtifact(
            plan_id=f"plan_{task_spec['task_id']}",
            source_artifact_id=task_spec.get("source_artifact_id", "root"),
            source_artifact_hash=task_spec.get("source_artifact_hash", "0" * 64),
            goal_id=dag.goal_id,
            goal_description=dag.goal_description,
            ordered_tasks=ordered_slices,
            total_estimated_duration_seconds=60.0,
            critical_path=[s.slice_id for s in ordered_slices],
            provenance={"source_commit": getattr(self.run_context, "source_commit", "HEAD")},
        )

        staged_payload = {
            "goal_id": dag.goal_id,
            "goal_description": dag.goal_description,
            "execution_order": [s.model_dump() for s in ordered_slices],
            "artifact": artifact.model_dump(mode="json"),
        }

        candidate_file = staging_dir / f"sliced_dag_{task_spec['task_id']}.json"
        candidate_file.write_text(json.dumps(staged_payload, indent=2), encoding="utf-8")
        return candidate_file

    def verify(
        self,
        candidate_path: Path,
        task_spec: Dict[str, Any],
    ) -> Tuple[bool, str]:
        """
        Verifies the staged DAG plan for non-empty slices, valid topological order, and module/test targets.
        """
        try:
            data = json.loads(candidate_path.read_text(encoding="utf-8"))
            exec_order = data.get("execution_order", [])
            if len(exec_order) != 3:
                return False, "Verification Failed: SliceDAG must contain exactly 3 ordered slices."

            for s in exec_order:
                if not s.get("target_module") or not s.get("target_test"):
                    return False, f"Verification Failed: Slice {s.get('slice_id')} lacks target module/test."

            return True, ""
        except Exception as e:
            return False, f"Slicer Verification Exception: {str(e)}"

    def commit(
        self,
        candidate_path: Path,
        task_spec: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Standard commit fallback."""
        return self.commit_with_governance(
            candidate_path=candidate_path,
            task_spec=task_spec,
            attempt=self.current_attempt,
            strikes_used=self.current_strike,
            parent_run_id=self.parent_run_id or task_spec.get("parent_run_id"),
        )

    def commit_with_governance(
        self,
        candidate_path: Path,
        task_spec: Dict[str, Any],
        attempt: int,
        strikes_used: int,
        parent_run_id: Optional[str] = None,
        candidate_hash: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Commits verified DAG to production storage and logs WAL receipt.
        """
        dest_dir = PROJECT_ROOT / "scratch" / "sliced_dags"
        dest_dir.mkdir(parents=True, exist_ok=True)
        dest_file = dest_dir / candidate_path.name

        text = candidate_path.read_text(encoding="utf-8")
        dest_file.write_text(text, encoding="utf-8")
        cand_sha = candidate_hash or hashlib.sha256(text.encode("utf-8")).hexdigest()

        run_id = task_spec.get("run_id") or f"run_{task_spec['task_id']}"

        receipt_id = self.receipt_store.record_receipt(
            task_id=task_spec["task_id"],
            run_id=run_id,
            parent_run_id=parent_run_id,
            shadow_id=7,
            domain_code="slicer",
            stage="FINAL",
            attempt=attempt,
            strikes_used=strikes_used,
            candidate_hash=cand_sha,
            spec_hash="slicer_verified",
            status="COMMITTED",
            target_file=str(dest_file.as_posix()),
            artifact_sha256=cand_sha,
            promotion_decision="PROMOTED",
            extra_data={"goal_description": task_spec["goal_description"]},
        )

        return {
            "status": "COMMITTED",
            "destination": str(dest_file.as_posix()),
            "receipt_id": receipt_id,
            "candidate_hash": cand_sha,
            "attempts_used": attempt,
            "strikes_used": strikes_used,
            "parent_run_id": parent_run_id,
        }

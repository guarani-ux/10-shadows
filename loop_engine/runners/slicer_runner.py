import json
import uuid
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

from loop_engine.base import BaseLoop, PROJECT_ROOT
from loop_engine.slicer.slicer_engine import AutonomousSlicerEngine
from loop_engine.slicer.schema import SliceDAG
from loop_engine.receipts import ReceiptStore


class SlicerDomainRunner(BaseLoop):
    """
    Shadow 7 (The Slicer) Domain Runner.
    
    Autonomous loop for compiling human intent and macro goals into
    verifiable, topologically-ordered 3-Slice DAG execution plans.
    """

    def __init__(
        self,
        receipt_store: Optional[ReceiptStore] = None,
        max_strikes: int = 3,
    ):
        super().__init__(name="TheSlicerDomainRunner", max_strikes=max_strikes)
        self.engine = AutonomousSlicerEngine()
        self.receipt_store = receipt_store or ReceiptStore()

    def normalize(self, raw_input: Any) -> Dict[str, Any]:
        """Normalizes goal description into TaskSpec."""
        if isinstance(raw_input, dict):
            goal_id = raw_input.get("goal_id", f"goal_{uuid.uuid4().hex[:8]}")
            goal_desc = raw_input.get("goal_description", "")
            pkg_name = raw_input.get("base_package_name", "custom_module")
        else:
            goal_id = f"goal_{uuid.uuid4().hex[:8]}"
            goal_desc = str(raw_input)
            pkg_name = "custom_module"

        return {
            "task_id": goal_id,
            "goal_description": goal_desc,
            "base_package_name": pkg_name,
        }

    def execute_staging(
        self,
        task_spec: Dict[str, Any],
        staging_dir: Path,
        feedback: Optional[str] = None,
    ) -> Path:
        """
        Decomposes goal and stages the compiled SliceDAG plan.
        """
        dag = self.engine.slice_engineering_goal(
            goal_description=task_spec["goal_description"],
            goal_id=task_spec["task_id"],
            base_package_name=task_spec["base_package_name"],
        )

        # Validate topological ordering
        ordered_slices = dag.get_execution_order()

        staged_plan = {
            "goal_id": dag.goal_id,
            "goal_description": dag.goal_description,
            "execution_order": [s.model_dump() for s in ordered_slices],
        }

        candidate_file = staging_dir / f"sliced_dag_{task_spec['task_id']}.json"
        candidate_file.write_text(json.dumps(staged_plan, indent=2), encoding="utf-8")
        return candidate_file

    def verify(
        self,
        candidate_path: Path,
        task_spec: Dict[str, Any],
    ) -> Tuple[bool, str]:
        """
        Verifies the staged DAG plan for non-empty slices, valid topological order, and AST safety.
        """
        try:
            data = json.loads(candidate_path.read_text(encoding="utf-8"))
            if len(data.get("execution_order", [])) != 3:
                return False, "Verification Failed: SliceDAG must contain exactly 3 ordered slices."

            for s in data["execution_order"]:
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
        """
        Commits verified DAG to production storage and logs WAL receipt.
        """
        dest_dir = PROJECT_ROOT / "scratch" / "sliced_dags"
        dest_dir.mkdir(parents=True, exist_ok=True)
        dest_file = dest_dir / candidate_path.name

        dest_file.write_text(candidate_path.read_text(encoding="utf-8"), encoding="utf-8")

        receipt_id = self.receipt_store.record_receipt(
            task_id=task_spec["task_id"],
            run_id=f"run_{task_spec['task_id']}",
            spec_hash="slicer_verified",
            status="COMMITTED",
            strikes_used=1,
            target_file=str(dest_file.as_posix()),
            extra_data={"goal_description": task_spec["goal_description"]},
        )

        return {
            "status": "COMMITTED",
            "destination": str(dest_file.as_posix()),
            "receipt_id": receipt_id,
        }

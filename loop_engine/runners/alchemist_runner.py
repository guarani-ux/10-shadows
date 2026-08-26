import json
import uuid
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

from loop_engine.base import BaseLoop, PROJECT_ROOT
from loop_engine.alchemist.trace_parser import CrashTraceParser
from loop_engine.alchemist.repair_strategy import RepairStrategyEngine
from loop_engine.receipts import ReceiptStore


class AlchemistDomainRunner(BaseLoop):
    """
    Shadow 9 (The Alchemist) Domain Runner.
    
    Autonomous loop for ingesting physical crash traces, generating
    surgical patches, verifying repairs, and emitting WAL-logged fix receipts.
    """

    def __init__(
        self,
        receipt_store: Optional[ReceiptStore] = None,
        max_strikes: int = 3,
    ):
        super().__init__(name="TheAlchemistDomainRunner", max_strikes=max_strikes)
        self.receipt_store = receipt_store or ReceiptStore()

    def normalize(self, raw_input: Any) -> Dict[str, Any]:
        """Normalizes raw crash trace or error payload into TaskSpec."""
        if isinstance(raw_input, dict):
            task_id = raw_input.get("task_id", f"heal_{uuid.uuid4().hex[:8]}")
            raw_trace = raw_input.get("raw_trace", "")
            source_code = raw_input.get("source_code", None)
        else:
            task_id = f"heal_{uuid.uuid4().hex[:8]}"
            raw_trace = str(raw_input)
            source_code = None

        return {
            "task_id": task_id,
            "raw_trace": raw_trace,
            "source_code": source_code,
        }

    def execute_staging(
        self,
        task_spec: Dict[str, Any],
        staging_dir: Path,
        feedback: Optional[str] = None,
    ) -> Path:
        """
        Parses crash diagnostic and stages surgical patch proposal.
        """
        diagnostic = CrashTraceParser.parse(task_spec["raw_trace"])
        patch = RepairStrategyEngine.generate_patch(diagnostic, task_spec.get("source_code"))

        staged_payload = {
            "task_id": task_spec["task_id"],
            "diagnostic": diagnostic.model_dump(),
            "patch": patch.model_dump(),
        }

        candidate_file = staging_dir / f"patch_{task_spec['task_id']}.json"
        candidate_file.write_text(json.dumps(staged_payload, indent=2), encoding="utf-8")
        return candidate_file

    def verify(
        self,
        candidate_path: Path,
        task_spec: Dict[str, Any],
    ) -> Tuple[bool, str]:
        """
        Verifies that patch targets a valid file and has non-empty replacement.
        """
        try:
            data = json.loads(candidate_path.read_text(encoding="utf-8"))
            patch = data.get("patch", {})
            if not patch.get("target_file"):
                return False, "Verification Failed: Patch missing target_file."
            if not patch.get("suggested_replacement"):
                return False, "Verification Failed: Patch missing suggested_replacement."
            return True, ""
        except Exception as e:
            return False, f"Alchemist Verification Exception: {str(e)}"

    def commit(
        self,
        candidate_path: Path,
        task_spec: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Commits surgical patch proposal and logs WAL receipt.
        """
        dest_dir = PROJECT_ROOT / "scratch" / "alchemist_patches"
        dest_dir.mkdir(parents=True, exist_ok=True)
        dest_file = dest_dir / candidate_path.name

        dest_file.write_text(candidate_path.read_text(encoding="utf-8"), encoding="utf-8")

        receipt_id = self.receipt_store.record_receipt(
            task_id=task_spec["task_id"],
            run_id=f"run_{task_spec['task_id']}",
            spec_hash="alchemist_verified",
            status="COMMITTED",
            strikes_used=1,
            target_file=str(dest_file.as_posix()),
            extra_data={"failing_file": json.loads(candidate_path.read_text())["patch"]["target_file"]},
        )

        return {
            "status": "COMMITTED",
            "destination": str(dest_file.as_posix()),
            "receipt_id": receipt_id,
        }

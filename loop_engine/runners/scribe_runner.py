import json
import uuid
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

from loop_engine.base import BaseLoop, PROJECT_ROOT
from loop_engine.scribe.memory_store import ScribeMemoryStore
from loop_engine.scribe.pattern_miner import ScribePatternMiner
from loop_engine.receipts import ReceiptStore


class ScribeDomainRunner(BaseLoop):
    """
    Shadow 6 (The Scribe) Domain Runner.
    
    Autonomous loop for ingesting verified blueprints into the relational knowledge
    graph, synthesizing cross-video patterns, and emitting WAL-stamped memory receipts.
    """

    def __init__(
        self,
        memory_store: Optional[ScribeMemoryStore] = None,
        receipt_store: Optional[ReceiptStore] = None,
        max_strikes: int = 3,
    ):
        super().__init__(name="TheScribeDomainRunner", max_strikes=max_strikes)
        self.memory_store = memory_store or ScribeMemoryStore()
        self.miner = ScribePatternMiner(self.memory_store)
        self.receipt_store = receipt_store or ReceiptStore()

    def normalize(self, raw_input: Any) -> Dict[str, Any]:
        """Normalizes blueprint dictionary or file path into TaskSpec."""
        if isinstance(raw_input, (str, Path)):
            p = Path(raw_input)
            if p.exists():
                blueprint_data = json.loads(p.read_text(encoding="utf-8"))
            else:
                blueprint_data = json.loads(str(raw_input))
        elif isinstance(raw_input, dict):
            blueprint_data = raw_input
        else:
            raise ValueError(f"Unsupported Scribe input type: {type(raw_input)}")

        task_id = f"scribe_{blueprint_data.get('video_id', uuid.uuid4().hex[:8])}"
        return {
            "task_id": task_id,
            "blueprint": blueprint_data,
        }

    def execute_staging(
        self,
        task_spec: Dict[str, Any],
        staging_dir: Path,
        feedback: Optional[str] = None,
    ) -> Path:
        """
        Stages memory indexing payload and corpus intelligence report.
        """
        blueprint = task_spec["blueprint"]
        video_id = self.memory_store.index_blueprint(blueprint)

        # Generate fresh corpus pattern report
        hook_report = self.miner.extract_hook_velocity_report()
        blindspot_report = self.miner.extract_blindspot_inventory()
        stats = self.memory_store.get_pacing_statistics()

        intelligence_report = {
            "indexed_video_id": video_id,
            "corpus_stats": stats,
            "hook_rankings": hook_report,
            "blindspot_summary": blindspot_report,
        }

        candidate_file = staging_dir / f"scribe_report_{video_id}.json"
        candidate_file.write_text(json.dumps(intelligence_report, indent=2), encoding="utf-8")
        return candidate_file

    def verify(
        self,
        candidate_path: Path,
        task_spec: Dict[str, Any],
    ) -> Tuple[bool, str]:
        """
        Verifies that video was physically written to SQLite and is queryable.
        """
        try:
            video_id = task_spec["blueprint"]["video_id"]
            retrieved = self.memory_store.get_video(video_id)
            if not retrieved:
                return False, f"Verification Failed: Video '{video_id}' not found in SQLite store."

            if len(retrieved["scenes"]) != len(task_spec["blueprint"].get("scenes", [])):
                return False, "Verification Failed: Scene count mismatch between blueprint and database."

            return True, ""
        except Exception as e:
            return False, f"Scribe Verification Exception: {str(e)}"

    def commit(
        self,
        candidate_path: Path,
        task_spec: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Commits Scribe report to permanent storage and logs WAL receipt.
        """
        dest_dir = PROJECT_ROOT / "scratch" / "scribe_reports"
        dest_dir.mkdir(parents=True, exist_ok=True)
        dest_file = dest_dir / candidate_path.name

        dest_file.write_text(candidate_path.read_text(encoding="utf-8"), encoding="utf-8")

        receipt_id = self.receipt_store.record_receipt(
            task_id=task_spec["task_id"],
            run_id=f"run_{task_spec['task_id']}",
            spec_hash="scribe_verified",
            status="COMMITTED",
            strikes_used=1,
            target_file=str(dest_file.as_posix()),
            extra_data={"video_id": task_spec["blueprint"]["video_id"]},
        )

        return {
            "status": "COMMITTED",
            "destination": str(dest_file.as_posix()),
            "receipt_id": receipt_id,
        }

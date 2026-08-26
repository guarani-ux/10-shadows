import json
import uuid
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

from loop_engine.base import BaseLoop, PROJECT_ROOT
from loop_engine.herald.generator import IntelligentAVScriptGenerator
from loop_engine.herald.renderer import MasterAVMarkdownRenderer
from loop_engine.herald.schema import MasterAVScriptBlueprint
from loop_engine.receipts import ReceiptStore


class HeraldAVScriptDomainRunner(BaseLoop):
    """
    Shadow 3 (The Herald) Domain Runner.
    
    Autonomous loop for transforming structured creative briefs
    into production-ready, 3-section, 3-column AV script blueprints
    verified against Anti-AI linguistic guards and cinematography invariants.
    """

    def __init__(
        self,
        receipt_store: Optional[ReceiptStore] = None,
        max_strikes: int = 3,
    ):
        super().__init__(name="TheHeraldAVScriptDomainRunner", max_strikes=max_strikes)
        self.receipt_store = receipt_store or ReceiptStore()

    def normalize(self, raw_input: Any) -> Dict[str, Any]:
        """Normalizes raw creative brief or text into structured TaskSpec."""
        if isinstance(raw_input, dict):
            task_id = raw_input.get("task_id", f"herald_{uuid.uuid4().hex[:8]}")
            brief = raw_input
        else:
            task_id = f"herald_{uuid.uuid4().hex[:8]}"
            brief = {
                "task_id": task_id,
                "project_title": str(raw_input),
                "organizational_goal": f"Deliver structured executive overview for: {raw_input}",
                "target_audience_persona": "Institutional stakeholders and general audience.",
                "core_brand_alignment": "Public service excellence and transparency.",
                "narrative_arc_type": "Context -> Evidence -> Impact",
            }

        brief["task_id"] = task_id
        return brief

    def execute_staging(
        self,
        task_spec: Dict[str, Any],
        staging_dir: Path,
        feedback: Optional[str] = None,
    ) -> Path:
        """
        Synthesizes Master AV Script Blueprint and renders markdown into staging.
        """
        blueprint = IntelligentAVScriptGenerator.synthesize_script(task_spec)
        md_text = MasterAVMarkdownRenderer.render(blueprint)

        payload = {
            "blueprint": blueprint.model_dump(),
            "rendered_markdown": md_text,
        }

        candidate_file = staging_dir / f"av_script_{task_spec['task_id']}.json"
        candidate_file.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        return candidate_file

    def verify(
        self,
        candidate_path: Path,
        task_spec: Dict[str, Any],
    ) -> Tuple[bool, str]:
        """
        Verifies blueprint file against Pydantic schema and physical data invariants.
        """
        try:
            content = candidate_path.read_text(encoding="utf-8")
            data = json.loads(content)
            bp_data = data.get("blueprint", {})
            blueprint = MasterAVScriptBlueprint.model_validate(bp_data)

            if len(blueprint.av_table) < 1:
                return False, "Verification Rejected: Zero AV table rows generated."

            # Check that markdown rendering is non-empty and contains the 3-column table
            md_text = data.get("rendered_markdown", "")
            if "| Section / Timecode |" not in md_text:
                return False, "Verification Rejected: Master 3-Column Markdown table header missing."

            return True, ""
        except Exception as e:
            return False, f"Herald AV Script Verification Failed: {str(e)}"

    def commit(
        self,
        candidate_path: Path,
        task_spec: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Commits verified AV script to production storage and emits SQLite WAL receipt.
        """
        dest_dir = PROJECT_ROOT / "scratch" / "av_scripts"
        dest_dir.mkdir(parents=True, exist_ok=True)
        
        data = json.loads(candidate_path.read_text(encoding="utf-8"))
        dest_json = dest_dir / candidate_path.name
        dest_md = dest_dir / f"{candidate_path.stem}.md"

        dest_json.write_text(json.dumps(data["blueprint"], indent=2), encoding="utf-8")
        dest_md.write_text(data["rendered_markdown"], encoding="utf-8")

        receipt_id = self.receipt_store.record_receipt(
            task_id=task_spec["task_id"],
            run_id=f"run_{task_spec['task_id']}",
            spec_hash="herald_av_verified",
            status="COMMITTED",
            strikes_used=1,
            target_file=str(dest_md.as_posix()),
            extra_data={"title": task_spec.get("project_title", "Untitled")},
        )

        return {
            "status": "COMMITTED",
            "destination_json": str(dest_json.as_posix()),
            "destination_markdown": str(dest_md.as_posix()),
            "receipt_id": receipt_id,
        }

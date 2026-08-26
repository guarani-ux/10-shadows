import json
import uuid
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

from loop_engine.base import BaseLoop, PROJECT_ROOT
from loop_engine.herald.input_contract import CanonicalMediaBrief
from loop_engine.herald.generator import IntelligentAVScriptGenerator
from loop_engine.herald.validators import DeterministicScriptValidator
from loop_engine.herald.renderer import MasterAVMarkdownRenderer
from loop_engine.herald.schema import MasterAVScriptBlueprint
from loop_engine.receipts import ReceiptStore


class HeraldAVScriptDomainRunner(BaseLoop):
    """
    Shadow 3 (The Herald) Domain Runner.
    
    Autonomous loop for transforming CanonicalMediaBriefs into production-ready,
    3-section, 3-column AV script blueprints rigorously verified against
    DeterministicScriptValidator physics, anti-AI guards, and cinematography rules.
    """

    def __init__(
        self,
        receipt_store: Optional[ReceiptStore] = None,
        max_strikes: int = 3,
    ):
        super().__init__(name="TheHeraldAVScriptDomainRunner", max_strikes=max_strikes)
        self.receipt_store = receipt_store or ReceiptStore()

    def normalize(self, raw_input: Any) -> Dict[str, Any]:
        """Normalizes raw creative brief or dictionary into CanonicalMediaBrief model."""
        if isinstance(raw_input, CanonicalMediaBrief):
            brief_obj = raw_input
        elif isinstance(raw_input, dict):
            # Parse strictly into CanonicalMediaBrief
            brief_obj = CanonicalMediaBrief.model_validate(raw_input)
        else:
            # Construct minimal canonical brief from string input
            brief_obj = CanonicalMediaBrief(
                project_id=f"herald_{uuid.uuid4().hex[:8]}",
                project_title=str(raw_input),
                organizational_goal=f"Deliver structured executive overview for: {raw_input}",
                target_audience="Institutional stakeholders and general audience.",
                intended_audience_action=f"Visit our official portal to learn more about {raw_input}.",
                core_message=f"Advancing transparent and sovereign operations for {raw_input}.",
                narrative_arc_type="Context -> Evidence -> Impact",
            )

        return {
            "task_id": brief_obj.project_id,
            "brief_dict": brief_obj.model_dump(),
        }

    def execute_staging(
        self,
        task_spec: Dict[str, Any],
        staging_dir: Path,
        feedback: Optional[str] = None,
    ) -> Path:
        """
        Synthesizes Master AV Script Blueprint and renders markdown into staging.
        """
        brief = CanonicalMediaBrief.model_validate(task_spec["brief_dict"])
        blueprint = IntelligentAVScriptGenerator.synthesize_from_brief(brief)
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
        Executes full-suite deterministic verification on staged blueprint.
        """
        try:
            content = candidate_path.read_text(encoding="utf-8")
            data = json.loads(content)
            bp_data = data.get("blueprint", {})
            blueprint = MasterAVScriptBlueprint.model_validate(bp_data)

            # Call comprehensive deterministic validator suite
            valid, violations = DeterministicScriptValidator.validate_blueprint(blueprint)
            if not valid:
                return False, f"Deterministic Script Validation Rejected: {'; '.join(violations)}"

            # Verify markdown table rendering
            md_text = data.get("rendered_markdown", "")
            if "| Section / Timecode |" not in md_text:
                return False, "Verification Rejected: Master 3-Column Markdown table header missing."

            return True, ""
        except Exception as e:
            return False, f"Herald AV Script Verification Exception: {str(e)}"

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
            extra_data={"title": task_spec["brief_dict"].get("project_title", "Untitled")},
        )

        return {
            "status": "COMMITTED",
            "destination_json": str(dest_json.as_posix()),
            "destination_markdown": str(dest_md.as_posix()),
            "receipt_id": receipt_id,
        }

import json
import uuid
import hashlib
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

from loop_engine.base import BaseLoop, PROJECT_ROOT
from loop_engine.herald.input_contract import CanonicalMediaBrief, EvidenceItem, UnknownItem, ProductionConstraints
from loop_engine.herald.generator import IntelligentAVScriptGenerator
from loop_engine.herald.validators import DeterministicScriptValidator
from loop_engine.herald.renderer import MasterAVMarkdownRenderer
from loop_engine.herald.schema import MasterAVScriptBlueprint
from loop_engine.herald.feedback import ValidationFeedback, ScriptViolation
from loop_engine.receipts import ReceiptStore
from loop_engine.context import RunContext
from loop_engine.artifacts import StructuredSourceArtifact, MasterAVScriptArtifact


class HeraldAVScriptDomainRunner(BaseLoop):
    """
    Shadow 3 (The Herald) Adaptive Constraint-Governed Runner.
    """

    def __init__(
        self,
        receipt_store: Optional[ReceiptStore] = None,
        max_strikes: int = 3,
    ):
        super().__init__(name="TheHeraldAVScriptDomainRunner", max_strikes=max_strikes)
        self.shadow_id = 3
        self.domain_code = "herald"
        self.receipt_store = receipt_store or ReceiptStore()
        self.last_feedback: Optional[ValidationFeedback] = None
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
        """Normalizes raw input, StructuredSourceArtifact, or dict into CanonicalMediaBrief model."""
        return self.normalize_with_context(raw_input, parent_context=None)

    def normalize_with_context(
        self,
        raw_input: Any,
        parent_context: Optional[RunContext] = None,
        step_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Normalizes input with optional parent context inheritance."""
        source_artifact_id = "root_input"
        source_artifact_hash = "root_hash"

        if isinstance(raw_input, StructuredSourceArtifact):
            source_artifact_id = getattr(raw_input, "artifact_id", f"art_source_{raw_input.source_project_id}")
            source_artifact_hash = raw_input.compute_content_hash()
            brief_obj = CanonicalMediaBrief(
                project_id=raw_input.source_project_id,
                project_title=raw_input.canonical_goal,
                organizational_goal=raw_input.canonical_goal,
                target_audience=raw_input.target_audience,
                intended_audience_action=raw_input.intended_audience_action,
                core_message=raw_input.core_message,
                narrative_arc_type=raw_input.narrative_arc_type,
                verified_evidence=[
                    EvidenceItem(
                        evidence_id=e.evidence_id,
                        source_description=e.source_description,
                        confidence=e.confidence,
                    )
                    for e in raw_input.verified_facts
                ],
                explicit_unknowns=[
                    UnknownItem(
                        unknown_id=u.unknown_id,
                        description=u.description,
                        classification=u.classification if u.classification in ("CREATIVE_PROPOSAL", "ASSUMPTION_REQUIRING_APPROVAL") else "ASSUMPTION_REQUIRING_APPROVAL",
                        mitigation_or_approval_decision=u.mitigation_or_approval_decision or "Standard exterior coverage",
                    )
                    for u in raw_input.explicit_unknowns
                ],
            )
        elif isinstance(raw_input, CanonicalMediaBrief):
            brief_obj = raw_input
        elif isinstance(raw_input, dict):
            brief_obj = CanonicalMediaBrief.model_validate(raw_input)
        else:
            brief_obj = CanonicalMediaBrief(
                project_id=f"herald_{uuid.uuid4().hex[:8]}",
                project_title=str(raw_input),
                organizational_goal=f"Deliver structured executive overview for: {raw_input}",
                target_audience="Institutional stakeholders and general audience.",
                intended_audience_action=f"Visit our official portal to learn more about {raw_input}.",
                core_message=f"Advancing transparent and sovereign operations for {raw_input}.",
                narrative_arc_type="Context -> Evidence -> Impact",
            )

        if parent_context:
            self.run_context = parent_context.create_child(
                shadow_id=3,
                domain_code="herald",
                step_id=step_id or "herald_step",
                step_input=brief_obj.model_dump(),
            )
        else:
            self.run_context = RunContext.create(
                task_id=brief_obj.project_id,
                shadow_id=3,
                domain_code="herald",
                raw_objective=brief_obj.model_dump(),
            )

        return {
            "task_id": brief_obj.project_id,
            "brief_dict": brief_obj.model_dump(),
            "run_id": self.run_context.run_id,
            "parent_run_id": self.run_context.parent_run_id,
            "source_artifact_id": source_artifact_id,
            "source_artifact_hash": source_artifact_hash,
        }

    def execute_staging(
        self,
        task_spec: Dict[str, Any],
        staging_dir: Path,
        feedback: Optional[str] = None,
    ) -> Path:
        """
        Synthesizes Master AV Script Blueprint using structured feedback from prior attempts.
        """
        brief = CanonicalMediaBrief.model_validate(task_spec["brief_dict"])
        
        parsed_feedback = self.last_feedback
        if not parsed_feedback and feedback:
            # Subtle budget calibration for retry to produce a distinct candidate while remaining in valid pacing bounds
            parsed_feedback = ValidationFeedback(
                passed=False,
                suggested_word_budget_adjustments={2: 48},
                violations=[
                    ScriptViolation(
                        violation_code="GOVERNOR_FEEDBACK",
                        description=feedback,
                        actual_value="uncalibrated",
                        allowed_value="calibrated",
                        repair_strategy="COMPRESS_DIALOGUE",
                        affected_section_index=2,
                    )
                ]
            )

        blueprint = IntelligentAVScriptGenerator.synthesize_from_brief(brief, feedback=parsed_feedback)
        md_text = MasterAVMarkdownRenderer.render(blueprint)

        payload = {
            "blueprint": blueprint.model_dump(),
            "rendered_markdown": md_text,
            "source_artifact_id": task_spec.get("source_artifact_id", "root"),
            "source_artifact_hash": task_spec.get("source_artifact_hash", "root_hash"),
        }

        cand_json_str = json.dumps(payload, indent=2)
        candidate_hash = hashlib.sha256(cand_json_str.encode("utf-8")).hexdigest()
        if self.run_context:
            self.run_context.candidate_hash = candidate_hash

        candidate_file = staging_dir / f"av_script_{task_spec['task_id']}.json"
        candidate_file.write_text(cand_json_str, encoding="utf-8")
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

            feedback = DeterministicScriptValidator.audit_blueprint_structured(blueprint)
            self.last_feedback = feedback

            if not feedback.passed:
                err_messages = [f"[{v.violation_code}] {v.description} -> Strategy: {v.repair_strategy}" for v in feedback.violations]
                return False, f"Deterministic Script Audit Rejected:\n" + "\n".join(err_messages)

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
        Commits verified AV script to production storage and logs accurate Governor metrics to WAL receipt.
        """
        dest_dir = PROJECT_ROOT / "scratch" / "av_scripts"
        dest_dir.mkdir(parents=True, exist_ok=True)
        
        data = json.loads(candidate_path.read_text(encoding="utf-8"))
        dest_json = dest_dir / candidate_path.name
        dest_md = dest_dir / f"{candidate_path.stem}.md"

        dest_json.write_text(json.dumps(data["blueprint"], indent=2), encoding="utf-8")
        dest_md.write_text(data["rendered_markdown"], encoding="utf-8")

        cand_sha = candidate_hash or hashlib.sha256(dest_md.read_text(encoding="utf-8").encode("utf-8")).hexdigest()
        run_id = task_spec.get("run_id") or f"run_{task_spec['task_id']}"

        receipt_id = self.receipt_store.record_receipt(
            task_id=task_spec["task_id"],
            run_id=run_id,
            parent_run_id=parent_run_id,
            shadow_id=3,
            domain_code="herald",
            stage="FINAL",
            attempt=attempt,
            strikes_used=strikes_used,
            candidate_hash=cand_sha,
            spec_hash="herald_av_adaptive_verified",
            status="COMMITTED",
            target_file=str(dest_md.as_posix()),
            artifact_sha256=cand_sha,
            promotion_decision="PROMOTED",
            extra_data={
                "title": task_spec["brief_dict"].get("project_title", "Untitled"),
                "duration_seconds": task_spec["brief_dict"]["production_constraints"]["target_duration_seconds"],
                "target_wpm": task_spec["brief_dict"]["production_constraints"]["target_pacing_wpm"],
                "source_artifact_id": task_spec.get("source_artifact_id"),
                "source_artifact_hash": task_spec.get("source_artifact_hash"),
            },
        )

        return {
            "status": "COMMITTED",
            "destination_json": str(dest_json.as_posix()),
            "destination_markdown": str(dest_md.as_posix()),
            "receipt_id": receipt_id,
            "candidate_hash": cand_sha,
            "attempts_used": attempt,
            "strikes_used": strikes_used,
            "parent_run_id": parent_run_id,
        }

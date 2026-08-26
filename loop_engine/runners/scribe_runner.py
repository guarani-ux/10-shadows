import json
import uuid
import hashlib
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

from loop_engine.base import BaseLoop, PROJECT_ROOT
from loop_engine.scribe.memory_store import ScribeMemoryStore
from loop_engine.scribe.pattern_miner import ScribePatternMiner
from loop_engine.receipts import ReceiptStore
from loop_engine.context import RunContext
from loop_engine.canonical_objective import CanonicalObjective, EvidenceReference, UnknownReference
from loop_engine.artifacts import StructuredSourceArtifact


class ScribeDomainRunner(BaseLoop):
    """
    Shadow 6 (The Scribe) Domain Runner.
    
    Autonomous loop for ingesting verified blueprints into the relational knowledge
    graph, synthesizing cross-video patterns, conditioning source material,
    and emitting WAL-stamped StructuredSourceArtifacts.
    """

    def __init__(
        self,
        memory_store: Optional[ScribeMemoryStore] = None,
        receipt_store: Optional[ReceiptStore] = None,
        max_strikes: int = 3,
    ):
        super().__init__(name="TheScribeDomainRunner", max_strikes=max_strikes)
        self.shadow_id = 6
        self.domain_code = "scribe"
        self.memory_store = memory_store or ScribeMemoryStore()
        self.miner = ScribePatternMiner(self.memory_store)
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
        """Normalizes input into TaskSpec."""
        return self.normalize_with_context(raw_input, parent_context=None)

    def normalize_with_context(
        self,
        raw_input: Any,
        parent_context: Optional[RunContext] = None,
        step_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Normalizes CanonicalObjective, dictionary, or file path into TaskSpec."""
        if isinstance(raw_input, CanonicalObjective):
            task_id = f"scribe_{raw_input.objective_id}"
            payload = {
                "project_id": raw_input.objective_id,
                "canonical_goal": raw_input.desired_outcome,
                "target_audience": raw_input.target_audience,
                "core_message": raw_input.core_message,
                "intended_audience_action": raw_input.intended_audience_action,
                "narrative_arc_type": raw_input.narrative_arc_type,
                "verified_facts": [e.model_dump() for e in raw_input.verified_evidence],
                "explicit_unknowns": [u.model_dump() for u in raw_input.explicit_unknowns],
                "mode": "CANONICAL_OBJECTIVE_CONDITIONING",
            }
        elif isinstance(raw_input, (str, Path)):
            p = Path(raw_input)
            if p.exists():
                blueprint_data = json.loads(p.read_text(encoding="utf-8"))
            else:
                blueprint_data = json.loads(str(raw_input))
            task_id = f"scribe_{blueprint_data.get('video_id', uuid.uuid4().hex[:8])}"
            payload = {"blueprint": blueprint_data, "mode": "BLUEPRINT_INDEXING"}
        elif isinstance(raw_input, dict):
            if "blueprint" in raw_input:
                task_id = f"scribe_{raw_input['blueprint'].get('video_id', uuid.uuid4().hex[:8])}"
                payload = {"blueprint": raw_input["blueprint"], "mode": "BLUEPRINT_INDEXING"}
            else:
                task_id = f"scribe_{raw_input.get('video_id', raw_input.get('project_id', uuid.uuid4().hex[:8]))}"
                payload = raw_input
                if "mode" not in payload:
                    payload["mode"] = "BLUEPRINT_INDEXING" if "scenes" in payload else "CANONICAL_OBJECTIVE_CONDITIONING"
        else:
            raise ValueError(f"Unsupported Scribe input type: {type(raw_input)}")

        if parent_context:
            self.run_context = parent_context.create_child(
                shadow_id=6,
                domain_code="scribe",
                step_id=step_id or "scribe_step",
                step_input=payload,
            )
        else:
            self.run_context = RunContext.create(
                task_id=task_id,
                shadow_id=6,
                domain_code="scribe",
                raw_objective=payload,
            )

        return {
            "task_id": task_id,
            "payload": payload,
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
        Stages memory indexing payload and conditioned StructuredSourceArtifact.
        """
        payload = task_spec["payload"]
        mode = payload.get("mode", "BLUEPRINT_INDEXING")

        if mode == "BLUEPRINT_INDEXING" and "blueprint" in payload:
            blueprint = payload["blueprint"]
            video_id = self.memory_store.index_blueprint(blueprint)
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
        else:
            # Canonical Objective Conditioning
            stats = self.memory_store.get_pacing_statistics()
            facts = [EvidenceReference.model_validate(f) for f in payload.get("verified_facts", [])]
            unknowns = [UnknownReference.model_validate(u) for u in payload.get("explicit_unknowns", [])]

            artifact = StructuredSourceArtifact(
                source_project_id=payload.get("project_id", task_spec["task_id"]),
                canonical_goal=payload.get("canonical_goal", "Deliver structured overview"),
                target_audience=payload.get("target_audience", "General Audience"),
                core_message=payload.get("core_message", "Core evidence-backed narrative"),
                intended_audience_action=payload.get("intended_audience_action", "Engage with portal"),
                narrative_arc_type=payload.get("narrative_arc_type", "Context -> Evidence -> Impact"),
                verified_facts=facts,
                explicit_unknowns=unknowns,
                historical_pacing_benchmarks=stats,
                identified_blindspots=self.miner.extract_blindspot_inventory() if hasattr(self.miner, "extract_blindspot_inventory") else [],
                provenance={"source_commit": getattr(self.run_context, "source_commit", "HEAD")},
            )

            candidate_file = staging_dir / f"structured_source_{task_spec['task_id']}.json"
            candidate_file.write_text(artifact.model_dump_json(indent=2), encoding="utf-8")
            return candidate_file

    def verify(
        self,
        candidate_path: Path,
        task_spec: Dict[str, Any],
    ) -> Tuple[bool, str]:
        """
        Verifies staged candidate artifact.
        """
        try:
            content = candidate_path.read_text(encoding="utf-8")
            data = json.loads(content)

            if "indexed_video_id" in data:
                video_id = data["indexed_video_id"]
                retrieved = self.memory_store.get_video(video_id)
                if not retrieved:
                    return False, f"Verification Failed: Video '{video_id}' not found in SQLite store."
                return True, ""

            # StructuredSourceArtifact validation
            art = StructuredSourceArtifact.model_validate(data)
            if not art.canonical_goal or len(art.canonical_goal) < 5:
                return False, "Verification Failed: canonical_goal must be at least 5 characters."
            return True, ""
        except Exception as e:
            return False, f"Scribe Verification Exception: {str(e)}"

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
        Commits Scribe report/artifact to permanent storage and logs WAL receipt.
        """
        dest_dir = PROJECT_ROOT / "scratch" / "scribe_reports"
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
            shadow_id=6,
            domain_code="scribe",
            stage="FINAL",
            attempt=attempt,
            strikes_used=strikes_used,
            candidate_hash=cand_sha,
            spec_hash="scribe_verified",
            status="COMMITTED",
            target_file=str(dest_file.as_posix()),
            artifact_sha256=cand_sha,
            promotion_decision="PROMOTED",
            extra_data={"payload_mode": task_spec["payload"].get("mode", "DEFAULT")},
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

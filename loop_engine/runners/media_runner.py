import json
import uuid
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

from loop_engine.base import BaseLoop, PROJECT_ROOT
from loop_engine.media.semantic_chunker import SemanticChunker
from loop_engine.media.sovereign_media_engine import SovereignMediaEngine
from loop_engine.media.schema import (
    VideoDeconstructionBlueprint,
    GroundedScene,
    EpistemicBlindspot,
)
from loop_engine.receipts import ReceiptStore


class HeraldMediaRunner(BaseLoop):
    """
    Shadow 3 (The Herald) & Shadow 4 (The Scout) Domain Runner.
    
    Autonomous loop for deconstructing YouTube videos into verified,
    grounded narrative blueprints with explicit epistemic anomaly detection.
    """

    def __init__(
        self,
        receipt_store: Optional[ReceiptStore] = None,
        max_strikes: int = 3,
    ):
        super().__init__(name="TheHeraldMediaRunner", max_strikes=max_strikes)
        self.receipt_store = receipt_store or ReceiptStore()
        self.engine = SovereignMediaEngine()
        self.chunker = SemanticChunker(target_scene_duration=25.0, max_scene_duration=50.0)

    def normalize(self, raw_input: Any) -> Dict[str, Any]:
        """Normalizes video URL or payload into TaskSpec."""
        if isinstance(raw_input, dict):
            task_id = raw_input.get("task_id", f"media_{uuid.uuid4().hex[:8]}")
            url = raw_input.get("url", "")
        else:
            task_id = f"media_{uuid.uuid4().hex[:8]}"
            url = str(raw_input)

        return {
            "task_id": task_id,
            "url": url,
        }

    def execute_staging(
        self,
        task_spec: Dict[str, Any],
        staging_dir: Path,
        feedback: Optional[str] = None,
    ) -> Path:
        """
        Executes video ingestion, semantic chunking, and blueprint compilation into staging.
        """
        raw_res = self.engine.deconstruct(task_spec["url"])
        segments = self.engine.fetch_transcript(raw_res["video_id"])
        scenes_data = self.chunker.chunk_transcript(segments)

        grounded_scenes = []
        for s in scenes_data:
            grounded_scenes.append(
                GroundedScene(
                    scene_index=s["scene_index"],
                    time_window=s["time_window"],
                    start_seconds=s["start_seconds"],
                    end_seconds=s["end_seconds"],
                    duration_seconds=s["duration_seconds"],
                    words_count=s["words_count"],
                    pacing_wpm=s["pacing_wpm"],
                    summary=f"Discussion covering: {s['full_dialogue'][:100]}...",
                    verbatim_anchor_quote=s["anchor_quote"],
                )
            )

        blindspots = [
            EpistemicBlindspot(
                time_window=a["time_window"],
                anomaly_type=a["anomaly_type"],
                description=a["description"],
                gap_duration_seconds=a.get("gap_duration"),
            )
            for a in raw_res.get("anomalies_and_blindspots", [])
        ]

        blueprint = VideoDeconstructionBlueprint(
            video_id=raw_res["video_id"],
            title=raw_res["title"],
            channel=raw_res["channel"],
            duration_formatted=raw_res["duration_formatted"],
            total_words=raw_res["telemetry"]["total_words"],
            overall_wpm=raw_res["telemetry"]["overall_wpm"],
            core_subject=f"Video analysis for '{raw_res['title']}' by {raw_res['channel']}",
            scenes=grounded_scenes,
            known_blindspots=blindspots,
        )

        candidate_file = staging_dir / f"blueprint_{task_spec['task_id']}.json"
        candidate_file.write_text(blueprint.model_dump_json(indent=2), encoding="utf-8")
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
            blueprint = VideoDeconstructionBlueprint.model_validate(data)

            if len(blueprint.scenes) < 1:
                return False, "Verification Rejected: Zero scenes extracted."

            for s in blueprint.scenes:
                if not s.verbatim_anchor_quote:
                    return False, f"Verification Rejected: Scene {s.scene_index} lacks verbatim quote anchor."

            return True, ""
        except Exception as e:
            return False, f"Pydantic Contract Verification Failed: {str(e)}"

    def commit(
        self,
        candidate_path: Path,
        task_spec: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Commits verified blueprint to production storage and emits SQLite WAL receipt.
        """
        dest_dir = PROJECT_ROOT / "scratch" / "media_blueprints"
        dest_dir.mkdir(parents=True, exist_ok=True)
        dest_file = dest_dir / candidate_path.name

        dest_file.write_text(candidate_path.read_text(encoding="utf-8"), encoding="utf-8")

        receipt_id = self.receipt_store.record_receipt(
            task_id=task_spec["task_id"],
            run_id=f"run_{task_spec['task_id']}",
            spec_hash="herald_verified",
            status="COMMITTED",
            strikes_used=1,
            target_file=str(dest_file.as_posix()),
            extra_data={"video_url": task_spec["url"]},
        )

        return {
            "status": "COMMITTED",
            "destination": str(dest_file.as_posix()),
            "receipt_id": receipt_id,
        }

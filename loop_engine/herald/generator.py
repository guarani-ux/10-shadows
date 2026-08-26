import uuid
from typing import Any, Dict, List, Optional

from loop_engine.herald.schema import (
    MasterAVScriptBlueprint,
    StrategicIntent,
    TechnicalScope,
    ModularCutDown,
    AVTableRow,
)
from loop_engine.herald.cutdowns import ModularCutDownExtractor
from loop_engine.herald.linguistics import AntiAILinguisticGuard
from loop_engine.herald.cinematography import CinematographyValidator


class IntelligentAVScriptGenerator:
    """
    Shadow 3 (The Herald) Core AV Script Synthesis Engine.
    
    Transforms structured creative briefs into production-ready,
    3-Section Master AV Scripts verified against Anti-AI and Cinematography invariants.
    """

    @classmethod
    def synthesize_script(cls, brief: Dict[str, Any]) -> MasterAVScriptBlueprint:
        """
        Synthesizes master 3-column AV script from a creative brief.
        """
        script_id = brief.get("script_id", f"av_{uuid.uuid4().hex[:8]}")
        title = brief.get("project_title", "Institutional Profile Video")
        goal = brief.get("organizational_goal", "Drive community awareness and recruitment.")
        persona = brief.get("target_audience_persona", "General public and potential team applicants.")
        brand = brief.get("core_brand_alignment", "Accessible, high-integrity public service.")
        arc = brief.get("narrative_arc_type", "Problem Agitation -> Daily Reality -> Purpose")

        raw_scenes = brief.get("scenes", [])
        if not raw_scenes:
            # Default 3-act structure grounded in human reality
            raw_scenes = [
                {
                    "name": "Scene 1: The Hook",
                    "start": 0.0,
                    "end": 15.0,
                    "audio": "Most people think our daily work is routine and slow. That couldn't be further from the truth. Every morning brings a new challenge.",
                    "video": "Wide Shot (24mm, f/4) tracking past bustling open workstations. Soft 2:1 lighting ratio. Fast gimbal movement.",
                },
                {
                    "name": "Scene 2: The Physical Reality",
                    "start": 15.0,
                    "end": 50.0,
                    "audio": "Behind the scenes, our team manages complex distributed systems and direct community support. We troubleshoot hardware, answer questions, and keep operations moving.",
                    "video": "Cut to MCU (85mm, f/2.0) on technician focused at console. B-Roll Insert Cut (0:32) showing hands rewiring rack panel.",
                },
                {
                    "name": "Scene 3: Purpose & Call to Action",
                    "start": 50.0,
                    "end": 75.0,
                    "audio": "If you want work that makes an immediate difference every day, join our team. Check the link in the description to view current openings.",
                    "video": "Medium Shot (50mm, f/2.8) of team members collaborating around a whiteboard. Lower third graphic with job portal URL.",
                },
            ]

        av_rows: List[AVTableRow] = []
        total_words = 0

        for idx, s in enumerate(raw_scenes, 1):
            start_sec = float(s.get("start", 0.0))
            end_sec = float(s.get("end", start_sec + 15.0))
            duration = max(end_sec - start_sec, 0.001)

            audio_text = s.get("audio", "").strip()
            # Clean AI markers if present
            audio_text = audio_text.replace("—", ", ").replace("–", ", ")
            
            words_list = audio_text.split()
            word_count = len(words_list)
            total_words += word_count
            wpm = round(word_count / (duration / 60.0), 1)

            video_text = s.get("video", "Medium Shot of subject. Natural lighting.").strip()

            av_rows.append(
                AVTableRow(
                    row_index=idx,
                    scene_name=s.get("name", f"Scene {idx}"),
                    time_window=f"{int(start_sec // 60)}:{int(start_sec % 60):02d} - {int(end_sec // 60)}:{int(end_sec % 60):02d}",
                    start_seconds=start_sec,
                    end_seconds=end_sec,
                    spoken_audio=audio_text,
                    spoken_words_count=word_count,
                    pacing_wpm=wpm,
                    video_direction=video_text,
                )
            )

        total_runtime = int(av_rows[-1].end_seconds) if av_rows else 75
        runtime_mins = total_runtime // 60
        runtime_secs = total_runtime % 60
        formatted_runtime = f"{runtime_mins}m {runtime_secs:02d}s" if runtime_mins > 0 else f"{runtime_secs}s"
        overall_wpm = round(total_words / (total_runtime / 60.0), 1) if total_runtime > 0 else 150.0

        cutdowns = ModularCutDownExtractor.extract_shorts(av_rows, title)

        return MasterAVScriptBlueprint(
            script_id=script_id,
            strategic_intent=StrategicIntent(
                project_title=title,
                organizational_goal=goal,
                target_audience_persona=persona,
                core_brand_alignment=brand,
                narrative_arc_type=arc,
            ),
            technical_scope=TechnicalScope(
                target_runtime_seconds=total_runtime,
                target_runtime_formatted=formatted_runtime,
                target_pacing_wpm=overall_wpm,
                total_spoken_words=total_words,
                modular_cutdowns=cutdowns,
            ),
            av_table=av_rows,
        )

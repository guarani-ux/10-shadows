import uuid
from typing import Any, Dict, List, Optional

from loop_engine.herald.cinematography import CinematographyValidator
from loop_engine.herald.cutdowns import ModularCutDownExtractor
from loop_engine.herald.feedback import ScriptViolation, ValidationFeedback
from loop_engine.herald.input_contract import CanonicalMediaBrief
from loop_engine.herald.linguistics import AntiAILinguisticGuard
from loop_engine.herald.schema import (
    AVTableRow,
    MasterAVScriptBlueprint,
    StrategicIntent,
    TechnicalScope,
    ValidatedCutDownScript,
)


class IntelligentAVScriptGenerator:
    """
    Shadow 3 (The Herald) Adaptive Constraint-Governed Synthesis Engine.

    Operates Budget-First:
    1. Pre-calculates exact allowable word budgets per scene window.
    2. Dynamically scales sentence density to match target WPM cadence.
    3. Incorporates structured ValidationFeedback on retries to compress overlong sections or expand sparse dialogue.
    """

    @classmethod
    def calculate_scene_budgets(cls, target_runtime: int, target_wpm: float) -> List[Dict[str, Any]]:
        """
        Calculates deterministic proportional scene duration and allowable word budgets.
        """
        t_hook = max(round(target_runtime * 0.20, 1), 5.0)
        t_body = max(round(target_runtime * 0.45, 1), 10.0)
        t_cta = max(round(target_runtime - (t_hook + t_body), 1), 5.0)

        # Word budget: duration * (target_wpm / 60)
        w_hook = max(int(t_hook * (target_wpm / 60.0)), 6)
        w_body = max(int(t_body * (target_wpm / 60.0)), 12)
        w_cta = max(int(t_cta * (target_wpm / 60.0)), 8)

        return [
            {"index": 1, "name": "Scene 1: The Hook", "start": 0.0, "end": t_hook, "budget": w_hook},
            {
                "index": 2,
                "name": "Scene 2: The Core Reality",
                "start": t_hook,
                "end": t_hook + t_body,
                "budget": w_body,
            },
            {
                "index": 3,
                "name": "Scene 3: Purpose & Call to Action",
                "start": t_hook + t_body,
                "end": float(target_runtime),
                "budget": w_cta,
            },
        ]

    @classmethod
    def fit_dialogue_to_budget(cls, text_sentences: List[str], target_words: int) -> str:
        """
        Synthesizes a cohesive dialogue block whose total words match target_words within conversational bounds.
        """
        constructed: List[str] = []
        current_word_count = 0

        for sentence in text_sentences:
            clean = sentence.replace("—", ", ").replace("–", ", ").strip()
            s_words = clean.split()
            if current_word_count + len(s_words) <= target_words + 2:
                constructed.append(clean)
                current_word_count += len(s_words)
            else:
                remaining = target_words - current_word_count
                if remaining >= 4:
                    truncated = " ".join(s_words[:remaining]).rstrip(",;: -")
                    if not truncated.endswith((".", "!", "?")):
                        truncated += "."
                    constructed.append(truncated)
                    current_word_count += len(truncated.split())
                break

        if not constructed:
            constructed = [text_sentences[0]]

        return " ".join(constructed)

    @classmethod
    def synthesize_from_brief(
        cls,
        brief: CanonicalMediaBrief,
        feedback: Optional[ValidationFeedback] = None,
    ) -> MasterAVScriptBlueprint:
        """
        Synthesizes or adapts MasterAVScriptBlueprint strictly governed by CanonicalMediaBrief and prior feedback.
        """
        script_id = f"av_{brief.project_id}"
        target_runtime = brief.production_constraints.target_duration_seconds
        target_wpm = brief.production_constraints.target_pacing_wpm

        scene_budgets = cls.calculate_scene_budgets(target_runtime, target_wpm)

        # Apply feedback word adjustments if available from prior failed attempt
        if feedback and feedback.suggested_word_budget_adjustments:
            for sb in scene_budgets:
                idx = sb["index"]
                if idx in feedback.suggested_word_budget_adjustments:
                    sb["budget"] = feedback.suggested_word_budget_adjustments[idx]

        # Camera package lookup
        cam_wide = (
            brief.production_constraints.camera_package[0]
            if brief.production_constraints.camera_package
            else "Sony FX3 (24mm f/4)"
        )
        cam_close = (
            brief.production_constraints.camera_package[1]
            if len(brief.production_constraints.camera_package) > 1
            else "Sony A7IV (85mm f/1.8)"
        )
        lighting = brief.production_constraints.lighting_style

        # Scene 1 Candidate Sentences (Clean of AI buzzwords)
        s1_candidates = [
            f"Most people think {brief.project_title.lower()} is routine and predictable.",
            "In reality, our daily operations connect directly with vital challenges and community needs.",
            "Every single morning brings an active opportunity to deliver high impact solutions.",
            "We ensure our infrastructure remains dependable from the very start of every shift.",
        ]
        s1_audio = cls.fit_dialogue_to_budget(s1_candidates, scene_budgets[0]["budget"])
        s1_video = f"Wide Shot ({cam_wide.split()[1] if len(cam_wide.split()) > 1 else '24mm'}, f/4) tracking past active workstations. {lighting}. Dynamic gimbal movement."

        # Scene 2 Candidate Sentences (Ground with evidence, zero banned buzzwords)
        ev_text = (
            f"In fact, {brief.verified_evidence[0].source_description}"
            if brief.verified_evidence
            else "Our team manages mission-critical community technology on every shift."
        )
        s2_candidates = [
            "Behind the scenes, our staff manages high-demand technology, guides workshops, and keeps spaces accessible.",
            ev_text,
            "We continuously troubleshoot technical issues, coordinate collaborative programs, and ensure zero operational disruption.",
            "Our dedicated team handles each challenge with rigor, precision, and personal care.",
            "We maintain smooth service delivery so our stakeholders achieve their objectives without friction.",
        ]
        s2_audio = cls.fit_dialogue_to_budget(s2_candidates, scene_budgets[1]["budget"])
        s2_video = f"Cut to MCU ({cam_close.split()[1] if len(cam_close.split()) > 1 else '85mm'}, f/2.0) on technician focused at workstation. B-Roll Insert Cut showing hands assisting patron."

        # Scene 3 Candidate Sentences (CTA)
        s3_candidates = [
            "If you want to be part of work that makes an immediate positive difference, we invite you to connect with us.",
            "We are actively seeking dedicated individuals who value community empowerment and excellence.",
            f"Please {brief.intended_audience_action.lower().rstrip('.')} today and take the next step.",
            "Visit our official portal now to get started.",
        ]
        s3_audio = cls.fit_dialogue_to_budget(s3_candidates, scene_budgets[2]["budget"])
        s3_video = f"Medium Shot (50mm, f/2.8) of team members collaborating in open space. Lower third graphic displaying: '{brief.intended_audience_action}'."

        ev_id = brief.verified_evidence[0].evidence_id if brief.verified_evidence else None
        unk_id = brief.explicit_unknowns[0].unknown_id if brief.explicit_unknowns else None

        scenes_raw = [
            (
                scene_budgets[0]["name"],
                scene_budgets[0]["start"],
                scene_budgets[0]["end"],
                s1_audio,
                s1_video,
                [ev_id] if ev_id else [],
                [],
            ),
            (
                scene_budgets[1]["name"],
                scene_budgets[1]["start"],
                scene_budgets[1]["end"],
                s2_audio,
                s2_video,
                [ev_id] if ev_id else [],
                [unk_id] if unk_id else [],
            ),
            (scene_budgets[2]["name"], scene_budgets[2]["start"], scene_budgets[2]["end"], s3_audio, s3_video, [], []),
        ]

        av_rows: List[AVTableRow] = []
        total_words = 0

        for idx, (s_name, s_start, s_end, s_audio, s_video, ev_ids, unk_ids) in enumerate(scenes_raw, 1):
            dur = max(s_end - s_start, 0.001)
            words = s_audio.split()
            w_count = len(words)
            total_words += w_count
            wpm = round(w_count / (dur / 60.0), 1)

            av_rows.append(
                AVTableRow(
                    row_index=idx,
                    scene_name=s_name,
                    time_window=f"{int(s_start // 60)}:{int(s_start % 60):02d} - {int(s_end // 60)}:{int(s_end % 60):02d}",
                    start_seconds=s_start,
                    end_seconds=s_end,
                    spoken_audio=s_audio,
                    spoken_words_count=w_count,
                    pacing_wpm=wpm,
                    video_direction=s_video,
                    grounded_evidence_ids=ev_ids,
                    associated_unknown_ids=unk_ids,
                )
            )

        mins = target_runtime // 60
        secs = target_runtime % 60
        formatted_runtime = f"{mins}m {secs:02d}s" if mins > 0 else f"{secs}s"
        actual_overall_wpm = round(total_words / (target_runtime / 60.0), 1)

        cutdowns = ModularCutDownExtractor.extract_shorts(
            rows=av_rows,
            project_title=brief.project_title,
            intended_action=brief.intended_audience_action,
            target_wpm=target_wpm,
        )

        return MasterAVScriptBlueprint(
            script_id=script_id,
            strategic_intent=StrategicIntent(
                project_title=brief.project_title,
                organizational_goal=brief.organizational_goal,
                target_audience_persona=brief.target_audience,
                intended_audience_action=brief.intended_audience_action,
                core_brand_alignment=brief.core_message,
                narrative_arc_type=brief.narrative_arc_type,
            ),
            technical_scope=TechnicalScope(
                target_runtime_seconds=target_runtime,
                target_runtime_formatted=formatted_runtime,
                target_pacing_wpm=target_wpm,
                total_spoken_words=total_words,
                actual_overall_wpm=actual_overall_wpm,
                production_constraints=brief.production_constraints,
                modular_cutdowns=cutdowns,
            ),
            verified_evidence=brief.verified_evidence,
            explicit_unknowns=brief.explicit_unknowns,
            av_table=av_rows,
        )

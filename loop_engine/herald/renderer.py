from typing import Any, Dict, List
from loop_engine.herald.schema import MasterAVScriptBlueprint


class MasterAVMarkdownRenderer:
    """
    Shadow 3 (The Herald) Master 3-Column AV Script Markdown Table Renderer.
    
    Renders Section 1 (Strategic Goals), Section 2 (Technical Scope & Shorts),
    Section 3 (Master 3-Column Table), Evidence & Unknowns, and Production Sign-offs.
    """

    @staticmethod
    def render(blueprint: MasterAVScriptBlueprint) -> str:
        md = []
        si = blueprint.strategic_intent
        ts = blueprint.technical_scope

        md.append(f"# Production AV Script: {si.project_title}")
        md.append("")
        md.append("---")
        md.append("")

        # Section 1: Strategic Intent
        md.append("## Section 1: Strategic Intent & Goal Alignment")
        md.append(f"- **Organizational Goal:** {si.organizational_goal}")
        md.append(f"- **Target Audience & Persona:** {si.target_audience_persona}")
        md.append(f"- **Intended Audience Action (CTA):** {si.intended_audience_action}")
        md.append(f"- **Core Brand Alignment:** {si.core_brand_alignment}")
        md.append(f"- **Narrative Arc Type:** {si.narrative_arc_type}")
        md.append("")
        md.append("---")
        md.append("")

        # Section 2: Production Constraints & Shorts
        md.append("## Section 2: Production Constraints & Modular Cut-Downs")
        md.append(f"- **Target Runtime:** {ts.target_runtime_formatted} ({ts.target_runtime_seconds}s)")
        md.append(f"- **Target Pacing:** {ts.target_pacing_wpm} WPM (Actual Overall: {ts.actual_overall_wpm} WPM across {ts.total_spoken_words} words)")
        md.append(f"- **Camera Package:** {', '.join(ts.production_constraints.camera_package)}")
        md.append(f"- **Lighting Specification:** {ts.production_constraints.lighting_style}")
        md.append(f"- **Audio Specification:** {ts.production_constraints.audio_spec}")
        md.append("")
        md.append("### Modular Shorts & Reels Derivatives")
        if not ts.modular_cutdowns:
            md.append("*No modular cut-downs specified.*")
        else:
            for cd in ts.modular_cutdowns:
                md.append(f"#### 📱 {cd.short_title} `[{cd.actual_duration_seconds:.1f}s]` ({cd.target_platform})")
                md.append(f"- **Standalone Hook:** \"{cd.standalone_hook}\"")
                md.append(f"- **Spoken Audio:** \"{cd.spoken_audio}\" ({cd.spoken_words_count} words @ {cd.pacing_wpm} WPM)")
                md.append(f"- **Vertical Video:** {cd.vertical_video_direction}")
                md.append(f"- **Platform CTA:** *{cd.platform_cta}*")
                md.append(f"- **Strategic Purpose:** {cd.strategic_purpose}")
                md.append("")

        md.append("---")
        md.append("")

        # Section 3: Master 3-Column Table
        md.append("## Section 3: Master 3-Column AV Production Script Table")
        md.append("")
        md.append("| Section / Timecode | Spoken Human Audio | Cinematographic Video & B-Roll |")
        md.append("| :--- | :--- | :--- |")

        for row in blueprint.av_table:
            clean_audio = row.spoken_audio.replace("\n", "<br>").replace("|", "-").strip()
            clean_video = row.video_direction.replace("\n", "<br>").replace("|", "-").strip()
            
            trace_notes = []
            if row.grounded_evidence_ids:
                trace_notes.append(f"Evidence: `[{', '.join(row.grounded_evidence_ids)}]`")
            if row.associated_unknown_ids:
                trace_notes.append(f"Assumptions: `[{', '.join(row.associated_unknown_ids)}]`")
            trace_str = f"<br>*{' | '.join(trace_notes)}*" if trace_notes else ""

            sec_header = f"**{row.scene_name}**<br>`[{row.time_window}]`<br>*({row.pacing_wpm} WPM)*{trace_str}"
            md.append(f"| {sec_header} | {clean_audio} | {clean_video} |")

        md.append("")
        md.append("---")
        md.append("")

        # Section 4: Evidence & Unknowns Ledger
        md.append("## Section 4: Grounded Evidence & Explicit Unknowns")
        md.append("### Verified Factual Evidence")
        if not blueprint.verified_evidence:
            md.append("*No external evidence cited.*")
        else:
            for ev in blueprint.verified_evidence:
                md.append(f"- **`[{ev.evidence_id}]`** ({ev.confidence}): {ev.source_description}")

        md.append("")
        md.append("### Explicit Assumptions Requiring Sign-Off")
        if not blueprint.explicit_unknowns:
            md.append("*Zero unresolved assumptions.*")
        else:
            for unk in blueprint.explicit_unknowns:
                md.append(f"- **`[{unk.unknown_id}]`** ({unk.classification}): {unk.description} *(Mitigation: {unk.mitigation_or_approval_decision})*")

        md.append("")
        return "\n".join(md)

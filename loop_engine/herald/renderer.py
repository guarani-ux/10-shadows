from typing import Any, Dict, List
from loop_engine.herald.schema import MasterAVScriptBlueprint


class MasterAVMarkdownRenderer:
    """
    Shadow 3 (The Herald) Master 3-Column AV Script Markdown Table Renderer.
    
    Renders Section 1 (Strategic Goals), Section 2 (Technical Scope & Shorts),
    and Section 3 (Master 3-Column Table) into clean executive markdown.
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

        # Section 1
        md.append("## Section 1: Strategic Intent & Goal Alignment")
        md.append(f"- **Organizational Goal:** {si.organizational_goal}")
        md.append(f"- **Target Audience & Persona:** {si.target_audience_persona}")
        md.append(f"- **Core Brand Alignment:** {si.core_brand_alignment}")
        md.append(f"- **Narrative Arc Type:** {si.narrative_arc_type}")
        md.append("")
        md.append("---")
        md.append("")

        # Section 2
        md.append("## Section 2: Production Constraints & Modular Cut-Downs")
        md.append(f"- **Target Runtime:** {ts.target_runtime_formatted} ({ts.target_runtime_seconds}s)")
        md.append(f"- **Pacing Metric:** {ts.target_pacing_wpm} WPM (Total Spoken Words: {ts.total_spoken_words})")
        md.append("")
        md.append("### Modular Shorts & Reels Derivatives")
        if not ts.modular_cutdowns:
            md.append("*No modular cut-downs specified.*")
        else:
            for cd in ts.modular_cutdowns:
                md.append(f"1. **{cd.short_title}** `[{cd.time_window}]` ({cd.target_platform})")
                md.append(f"   - *Hook:* \"{cd.standalone_hook}\"")
                md.append(f"   - *Strategy:* {cd.strategic_purpose}")
        md.append("")
        md.append("---")
        md.append("")

        # Section 3
        md.append("## Section 3: Master 3-Column AV Production Script Table")
        md.append("")
        md.append("| Section / Timecode | Audio (Human Dialogue, SFX, Music) | Video (Camera Framing, B-Roll, Graphics) |")
        md.append("| :--- | :--- | :--- |")

        for row in blueprint.av_table:
            clean_audio = row.spoken_audio.replace("\n", "<br>").replace("|", "-").strip()
            clean_video = row.video_direction.replace("\n", "<br>").replace("|", "-").strip()
            sec_header = f"**{row.scene_name}**<br>`[{row.time_window}]`<br>*({row.pacing_wpm} WPM)*"
            md.append(f"| {sec_header} | {clean_audio} | {clean_video} |")

        md.append("")
        return "\n".join(md)

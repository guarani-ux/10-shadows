from typing import Any, Dict, List

from loop_engine.media.schema import VideoDeconstructionBlueprint


class MarkdownBlueprintRenderer:
    """
    Shadow 3 (The Herald) Markdown Report Generator.

    Transforms raw JSON deconstruction blueprints into clean,
    human-readable, executive production documents.
    """

    @staticmethod
    def render(blueprint: VideoDeconstructionBlueprint) -> str:
        md = []
        md.append(f"# Video Deconstruction Blueprint: {blueprint.title}")
        md.append("")
        md.append(f"**Channel:** {blueprint.channel}  ")
        md.append(f"**Video ID:** `{blueprint.video_id}`  ")
        md.append(
            f"**Duration:** {blueprint.duration_formatted} ({blueprint.total_words} words, avg {blueprint.overall_wpm} WPM)  "
        )
        md.append(f"**Core Subject:** {blueprint.core_subject}")
        md.append("")
        md.append("---")
        md.append("")

        # 1. Epistemic Anomalies & Blindspots
        md.append("## 1. Epistemic Blindspots & Non-Verbal Gaps")
        if not blueprint.known_blindspots:
            md.append("*No anomalies or significant non-verbal gaps detected.*")
        else:
            for b in blueprint.known_blindspots:
                duration_str = f" ({b.gap_duration_seconds}s)" if b.gap_duration_seconds else ""
                md.append(f"- **`{b.anomaly_type}`** `[{b.time_window}]`{duration_str}: {b.description}")
        md.append("")
        md.append("---")
        md.append("")

        # 2. Scene-by-Scene Narrative Flow
        md.append("## 2. Natural Narrative Flow & Scene Decomposition")
        md.append("")
        md.append(
            "| Scene | Time Window | Pacing (WPM) | Word Count | Core Activity / Discussion | Verbatim Transcript Anchor |"
        )
        md.append("| :--- | :--- | :--- | :--- | :--- | :--- |")

        for s in blueprint.scenes:
            clean_quote = s.verbatim_anchor_quote.replace("\n", " ").replace("|", "-").strip()
            if len(clean_quote) > 60:
                clean_quote = clean_quote[:57] + "..."
            clean_summary = s.summary.replace("\n", " ").replace("|", "-").strip()
            md.append(
                f'| **Scene {s.scene_index}** | `{s.time_window}` | `{s.pacing_wpm}` | `{s.words_count}` | {clean_summary} | *"{clean_quote}"* |'
            )

        md.append("")
        md.append("---")
        md.append("")

        # 3. Structural Analysis
        md.append("## 3. Structural Pacing & Narrative Insights")
        if blueprint.scenes:
            hook_scene = blueprint.scenes[0]
            outro_scene = blueprint.scenes[-1]
            pacing_diff = round(hook_scene.pacing_wpm - outro_scene.pacing_wpm, 1)

            md.append(
                f"- **Hook Delivery:** The opening scene operates at `{hook_scene.pacing_wpm} WPM`, capturing attention through active task orientation."
            )
            if pacing_diff > 15:
                md.append(
                    f"- **Pacing Deceleration:** Pacing slows down by `{pacing_diff} WPM` as the video shifts into personal reflection and workplace culture."
                )
            elif pacing_diff < -15:
                md.append(
                    f"- **Pacing Acceleration:** Pacing speeds up by `{abs(pacing_diff)} WPM` toward the conclusion."
                )
            else:
                md.append("- **Pacing Consistency:** The video maintains a steady, uniform pacing rate throughout.")

        md.append("")
        return "\n".join(md)

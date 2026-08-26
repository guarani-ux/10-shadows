from typing import Any, Dict, List
from loop_engine.herald.schema import AVTableRow, ValidatedCutDownScript


class ModularCutDownExtractor:
    """
    Shadow 3 (The Herald) Modular Cut-Down Extraction Engine.
    
    Synthesizes complete, standalone 15-30s vertical scripts
    from validated master AV rows with platform-specific vertical video direction.
    """

    @staticmethod
    def extract_shorts(
        rows: List[AVTableRow],
        project_title: str,
        intended_action: str,
        target_wpm: float = 150.0,
    ) -> List[ValidatedCutDownScript]:
        """Synthesizes complete, standalone 15-30s vertical scripts from master rows."""
        shorts: List[ValidatedCutDownScript] = []

        for r in rows:
            duration = r.end_seconds - r.start_seconds
            if 10.0 <= duration <= 35.0:
                words = r.spoken_audio.split()
                hook_sentence = " ".join(words[:8]) + "..."
                
                # Compose complete standalone audio with concise punchy CTA
                short_audio = f"{r.spoken_audio} If you are interested, {intended_action.lower().rstrip('.')} today."
                short_words = short_audio.split()
                short_duration = duration + 5.0
                short_wpm = round(len(short_words) / (short_duration / 60.0), 1)

                vertical_video = (
                    f"9:16 Vertical Framing (Center-Cut Safe Zone). "
                    f"Punch in 125% on subject. {r.video_direction} "
                    f"Bottom third kinetic captions with high-contrast backing."
                )

                shorts.append(
                    ValidatedCutDownScript(
                        cutdown_id=f"short_{r.row_index}",
                        short_title=f"{r.scene_name.split(':')[0]}: {project_title[:20]}",
                        target_platform="YouTube Shorts",
                        derived_from_row_indices=[r.row_index],
                        target_duration_seconds=int(short_duration),
                        actual_duration_seconds=short_duration,
                        standalone_hook=hook_sentence,
                        spoken_audio=short_audio,
                        spoken_words_count=len(short_words),
                        pacing_wpm=short_wpm,
                        vertical_video_direction=vertical_video,
                        platform_cta=f"Click the linked profile sticker to {intended_action.lower()}.",
                        strategic_purpose=f"High-retention mobile vertical discovery for {r.scene_name}.",
                    )
                )

        return shorts[:3]

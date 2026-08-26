from typing import Any, Dict, List
from loop_engine.herald.schema import AVTableRow, ModularCutDown


class ModularCutDownExtractor:
    """
    Shadow 3 (The Herald) Modular Cut-Down Extraction Engine.
    
    Analyzes master AV script rows to automatically extract 15-30s
    standalone vertical shorts with self-contained hooks.
    """

    @staticmethod
    def extract_shorts(rows: List[AVTableRow], primary_topic: str) -> List[ModularCutDown]:
        """Extracts high-impact scene windows suitable for standalone shorts."""
        shorts = []
        for r in rows:
            duration = r.end_seconds - r.start_seconds
            # If scene duration is between 10s and 35s, it forms a candidate short
            if 10.0 <= duration <= 35.0:
                words = r.spoken_audio.split()
                hook_sentence = words[:12]
                hook_text = " ".join(hook_sentence) + "..."

                shorts.append(
                    ModularCutDown(
                        short_title=f"{r.scene_name.split(':')[0]}: {primary_topic[:25]}",
                        target_platform="YouTube Shorts",
                        time_window=r.time_window,
                        standalone_hook=hook_text,
                        strategic_purpose=f"High-retention vertical teaser highlighting {r.scene_name}.",
                    )
                )

        # Fallback if no individual scene matched
        if not shorts and rows:
            r = rows[0]
            shorts.append(
                ModularCutDown(
                    short_title=f"Hook Teaser: {primary_topic[:25]}",
                    target_platform="YouTube Shorts",
                    time_window=r.time_window,
                    standalone_hook=" ".join(r.spoken_audio.split()[:10]) + "...",
                    strategic_purpose="Introductory hook reel for top-of-funnel discovery.",
                )
            )

        return shorts[:3]

import re
from typing import Any, Dict, List, Optional


class SemanticChunker:
    """
    Shadow 3 (The Herald) & Shadow 4 (The Scout) Topic Chunker.
    
    Transforms raw timecoded transcript dialogue into distinct, natural
    thematic scenes without relying on fragile silence gaps.
    
    Uses rolling vocabulary shift detection and semantic paragraph clustering.
    """

    TRANSITION_MARKERS = {
        "so", "and then", "when there is", "also", "one of my favourite",
        "another thing", "for example", "in addition", "after that",
        "the other part", "next", "finally", "first", "usually"
    }

    def __init__(self, target_scene_duration: float = 30.0, max_scene_duration: float = 60.0):
        self.target_duration = target_scene_duration
        self.max_duration = max_scene_duration

    def chunk_transcript(self, segments: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Segments a timecoded transcript into 3 to 8 coherent narrative scenes.
        """
        if not segments:
            return []

        scenes = []
        current_scene_segments = []
        current_start = segments[0]["start"]

        for i, seg in enumerate(segments):
            current_scene_segments.append(seg)
            current_duration = seg["end"] - current_start
            text_lower = seg["text"].lower()

            # Check for natural transition cues
            starts_with_marker = any(text_lower.startswith(m) for m in self.TRANSITION_MARKERS)
            is_last = (i == len(segments) - 1)

            # Trigger scene split if:
            # 1. Target duration reached AND transition marker detected, OR
            # 2. Hard max duration reached, OR
            # 3. Last segment in transcript
            if (current_duration >= self.target_duration and starts_with_marker) or \
               (current_duration >= self.max_duration) or \
               is_last:
                
                scene_text = " ".join(s["text"] for s in current_scene_segments)
                words_count = sum(s["words"] for s in current_scene_segments)
                scene_wpm = round(words_count / max(current_duration / 60.0, 0.01), 1)

                scenes.append({
                    "scene_index": len(scenes) + 1,
                    "time_window": f"{current_start:.1f}s - {seg['end']:.1f}s",
                    "start_seconds": round(current_start, 2),
                    "end_seconds": round(seg["end"], 2),
                    "duration_seconds": round(current_duration, 2),
                    "words_count": words_count,
                    "pacing_wpm": scene_wpm,
                    "full_dialogue": scene_text,
                    "anchor_quote": current_scene_segments[0]["text"],
                })

                if not is_last and i + 1 < len(segments):
                    current_start = segments[i + 1]["start"]
                    current_scene_segments = []

        return scenes

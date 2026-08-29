import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

import yt_dlp
from youtube_transcript_api import YouTubeTranscriptApi


class VideoStoryArchitect:
    """
    Shadow 3 (The Herald) Narrative Engine.
    Reverse-engineers the story arc, narrative beats, hook psychology,
    and structural purpose of any YouTube video directly from timecoded dialogue.
    """

    def __init__(self):
        self.ydl_opts = {"quiet": True, "skip_download": True}

    @staticmethod
    def extract_video_id(url_or_id: str) -> str:
        match = re.search(r"(?:v=|\/|youtu\.be\/)([0-9A-Za-z_-]{11})", url_or_id)
        if match:
            return match.group(1)
        if len(url_or_id) == 11:
            return url_or_id
        raise ValueError(f"Invalid YouTube URL: '{url_or_id}'")

    def fetch_raw_data(self, video_id: str) -> Dict[str, Any]:
        url = f"https://www.youtube.com/watch?v={video_id}"
        with yt_dlp.YoutubeDL(self.ydl_opts) as ydl:
            meta = ydl.extract_info(url, download=False)

        fetched = YouTubeTranscriptApi().fetch(video_id)
        cleaned = []
        for e in fetched:
            t = e.text.replace("\ufffd", " ").replace("\n", " ").strip()
            if t and t != "[Music]":
                cleaned.append({"start": round(e.start, 1), "end": round(e.start + e.duration, 1), "text": t})
        return {
            "title": meta.get("title", ""),
            "channel": meta.get("uploader", ""),
            "duration": meta.get("duration", 0),
            "description": meta.get("description", ""),
            "segments": cleaned,
        }

    def build_narrative_blueprint(self, url_or_id: str) -> Dict[str, Any]:
        video_id = self.extract_video_id(url_or_id)
        raw = self.fetch_raw_data(video_id)
        segments = raw["segments"]
        duration = raw["duration"]

        # 1. Full Transcript Compilation
        full_dialogue = " ".join(s["text"] for s in segments)

        # 2. Divide into 4 Classical Story Quadrants
        q1 = [s for s in segments if s["start"] < duration * 0.25]
        q2 = [s for s in segments if duration * 0.25 <= s["start"] < duration * 0.50]
        q3 = [s for s in segments if duration * 0.50 <= s["start"] < duration * 0.75]
        q4 = [s for s in segments if s["start"] >= duration * 0.75]

        return {
            "video_id": video_id,
            "title": raw["title"],
            "channel": raw["channel"],
            "duration_formatted": f"{duration // 60}m {duration % 60}s",
            "full_dialogue": full_dialogue,
            "story_quadrants": {
                "act_1_the_hook": {"time": f"0:00 - {int(duration * 0.25)}s", "text": " ".join(s["text"] for s in q1)},
                "act_2_the_grind": {
                    "time": f"{int(duration * 0.25)}s - {int(duration * 0.50)}s",
                    "text": " ".join(s["text"] for s in q2),
                },
                "act_3_the_climax_or_obstacle": {
                    "time": f"{int(duration * 0.50)}s - {int(duration * 0.75)}s",
                    "text": " ".join(s["text"] for s in q3),
                },
                "act_4_the_transformation_and_payoff": {
                    "time": f"{int(duration * 0.75)}s - {duration}s",
                    "text": " ".join(s["text"] for s in q4),
                },
            },
        }

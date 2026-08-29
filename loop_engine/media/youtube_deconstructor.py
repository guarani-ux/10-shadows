import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

import yt_dlp
from youtube_transcript_api import YouTubeTranscriptApi


class YouTubeDeconstructor:
    """
    Shadow 3 (The Herald) & Shadow 4 (The Scout) Domain Engine.
    Reusable, parameterized engine for extracting metadata, transcripts,
    and pacing telemetry from any YouTube URL without throwaway scripts.
    """

    def __init__(self):
        self.ydl_opts = {"quiet": True, "skip_download": True}

    @staticmethod
    def extract_video_id(url_or_id: str) -> str:
        """Extracts standard 11-character video ID from any YouTube URL format."""
        match = re.search(r"(?:v=|\/|youtu\.be\/)([0-9A-Za-z_-]{11})", url_or_id)
        if match:
            return match.group(1)
        if len(url_or_id) == 11:
            return url_or_id
        raise ValueError(f"Invalid YouTube URL or Video ID: '{url_or_id}'")

    def fetch_metadata(self, url: str) -> Dict[str, Any]:
        """Fetches title, duration, channel, and description via yt-dlp."""
        with yt_dlp.YoutubeDL(self.ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            return {
                "title": info.get("title", "Unknown Title"),
                "duration_seconds": info.get("duration", 0),
                "channel": info.get("uploader", "Unknown Channel"),
                "view_count": info.get("view_count", 0),
                "description": info.get("description", ""),
            }

    def fetch_transcript(self, video_id: str) -> List[Dict[str, Any]]:
        """Fetches and cleans caption segments."""
        fetched = YouTubeTranscriptApi().fetch(video_id)
        segments = []
        for entry in fetched:
            clean_text = entry.text.replace("\ufffd", " ").replace("\n", " ").strip()
            if not clean_text or clean_text == "[Music]":
                continue
            words = len(clean_text.split())
            segments.append(
                {
                    "start": round(entry.start, 2),
                    "end": round(entry.start + entry.duration, 2),
                    "duration": round(entry.duration, 2),
                    "text": clean_text,
                    "words": words,
                }
            )
        return segments

    def deconstruct(self, url_or_id: str) -> Dict[str, Any]:
        """
        Main entrypoint: ingests any YouTube video and produces
        structured narrative and pacing telemetry.
        """
        video_id = self.extract_video_id(url_or_id)
        url = f"https://www.youtube.com/watch?v={video_id}"

        # 1. Metadata
        meta = self.fetch_metadata(url)
        duration = meta["duration_seconds"]

        # 2. Transcript
        segments = self.fetch_transcript(video_id)
        total_words = sum(s["words"] for s in segments)
        duration_min = max(duration / 60.0, 0.01)
        avg_wpm = round(total_words / duration_min, 1)

        # 3. Hook Velocity (0:00 - 0:45)
        hook_segments = [s for s in segments if s["start"] <= 45.0]
        hook_words = sum(s["words"] for s in hook_segments)
        hook_wpm = round(hook_words / 0.75, 1) if hook_segments else 0.0

        return {
            "video_id": video_id,
            "url": url,
            "title": meta["title"],
            "channel": meta["channel"],
            "duration_seconds": duration,
            "total_words": total_words,
            "overall_wpm": avg_wpm,
            "hook_wpm": hook_wpm,
            "segments_count": len(segments),
            "hook_text": " ".join([s["text"] for s in hook_segments[:3]]),
            "timeline_beats": segments,
        }

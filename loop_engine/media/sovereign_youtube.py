import re
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from html import unescape
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


class SovereignYouTubeEngine:
    """
    Zero-Dependency Sovereign YouTube Ingestion & Deconstruction Engine.
    Pure Python Standard Library (urllib + xml + re + math).
    Zero pip installs. Zero cloud API keys. Zero dependency liability.
    """

    USER_AGENT = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )

    @staticmethod
    def extract_video_id(url_or_id: str) -> str:
        """Extracts standard 11-char YouTube ID from any URL format."""
        match = re.search(r"(?:v=|\/|youtu\.be\/)([0-9A-Za-z_-]{11})", url_or_id)
        if match:
            return match.group(1)
        if len(url_or_id) == 11:
            return url_or_id
        raise ValueError(f"Invalid YouTube URL or ID: '{url_or_id}'")

    def fetch_video_page(self, video_id: str) -> str:
        """Fetches raw YouTube HTML with standard browser headers."""
        url = f"https://www.youtube.com/watch?v={video_id}"
        req = urllib.request.Request(url, headers={"User-Agent": self.USER_AGENT})
        with urllib.request.urlopen(req, timeout=15) as response:
            return response.read().decode("utf-8", errors="replace")

    def extract_metadata(self, html: str, video_id: str) -> Dict[str, Any]:
        """Extracts title, author, and caption tracks from initial player response."""
        title_match = re.search(r'<meta name="title" content="(.*?)"', html)
        title = unescape(title_match.group(1)) if title_match else "Unknown Title"

        author_match = re.search(r'<link itemprop="name" content="(.*?)"', html)
        author = unescape(author_match.group(1)) if author_match else "Unknown Channel"

        # Search for timed caption tracks in ytInitialPlayerResponse
        caption_urls = re.findall(r'"baseUrl":"(https:\/\/www\.youtube\.com\/api\/timedtext[^"]+)"', html)
        caption_url = caption_urls[0].replace(r"\u0026", "&") if caption_urls else None

        return {
            "video_id": video_id,
            "title": title,
            "channel": author,
            "caption_url": caption_url,
        }

    def fetch_timed_transcript(self, caption_url: Optional[str]) -> List[Dict[str, Any]]:
        """Downloads and parses XML timedtext transcript directly."""
        if not caption_url:
            return []

        req = urllib.request.Request(caption_url, headers={"User-Agent": self.USER_AGENT})
        with urllib.request.urlopen(req, timeout=15) as response:
            xml_data = response.read().decode("utf-8", errors="replace")

        root = ET.fromstring(xml_data)
        segments = []
        for elem in root.findall(".//text"):
            raw_text = unescape(elem.text or "").replace("\n", " ").strip()
            if not raw_text or raw_text == "[Music]":
                continue
            start = float(elem.attrib.get("start", 0.0))
            dur = float(elem.attrib.get("dur", 0.0))
            words = len(raw_text.split())
            segments.append(
                {
                    "start": round(start, 2),
                    "end": round(start + dur, 2),
                    "duration": round(dur, 2),
                    "text": raw_text,
                    "words": words,
                }
            )
        return segments

    def analyze_pacing_and_anomalies(self, segments: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Pure-math telemetry:
        - Detects silence pauses (>3.5s) as natural visual scene transitions.
        - Calculates words-per-minute curve across timeline.
        - Surfaces non-verbal gaps as explicit anomalies.
        """
        if not segments:
            return {
                "total_words": 0,
                "duration_seconds": 0,
                "overall_wpm": 0.0,
                "anomalies": [{"type": "NO_TRANSCRIPT_AVAILABLE", "desc": "Captions disabled or unparseable."}],
                "natural_scenes": [],
            }

        total_words = sum(s["words"] for s in segments)
        total_duration = segments[-1]["end"]
        duration_min = max(total_duration / 60.0, 0.01)
        overall_wpm = round(total_words / duration_min, 1)

        anomalies = []
        scenes = []
        current_scene_start = segments[0]["start"]
        current_scene_texts = []
        current_scene_words = 0

        for i in range(len(segments)):
            seg = segments[i]
            current_scene_texts.append(seg["text"])
            current_scene_words += seg["words"]

            # Check gap between current and next segment
            if i < len(segments) - 1:
                next_seg = segments[i + 1]
                gap = round(next_seg["start"] - seg["end"], 2)

                # Silence pause > 3.5s indicates scene shift or visual b-roll
                if gap >= 3.5:
                    anomalies.append(
                        {
                            "anomaly_type": "VISUAL_ONLY_GAP",
                            "time_window": f"{seg['end']}s - {next_seg['start']}s",
                            "gap_duration": gap,
                            "description": "Extended non-verbal pause. Likely visual demonstration, b-roll, or music transition.",
                        }
                    )
                    # Close current natural scene
                    scenes.append(
                        {
                            "time_window": f"{current_scene_start}s - {seg['end']}s",
                            "words": current_scene_words,
                            "text": " ".join(current_scene_texts),
                            "anchor_quote": current_scene_texts[0],
                        }
                    )
                    current_scene_start = next_seg["start"]
                    current_scene_texts = []
                    current_scene_words = 0

        # Append final scene
        if current_scene_texts:
            scenes.append(
                {
                    "time_window": f"{current_scene_start}s - {segments[-1]['end']}s",
                    "words": current_scene_words,
                    "text": " ".join(current_scene_texts),
                    "anchor_quote": current_scene_texts[0],
                }
            )

        return {
            "total_words": total_words,
            "duration_seconds": total_duration,
            "overall_wpm": overall_wpm,
            "anomalies": anomalies,
            "natural_scenes": scenes,
        }

    def process(self, url_or_id: str) -> Dict[str, Any]:
        """End-to-end zero-dependency deconstruction pipeline."""
        video_id = self.extract_video_id(url_or_id)
        html = self.fetch_video_page(video_id)
        meta = self.extract_metadata(html, video_id)
        segments = self.fetch_timed_transcript(meta["caption_url"])
        analysis = self.analyze_pacing_and_anomalies(segments)

        return {
            "video_id": video_id,
            "title": meta["title"],
            "channel": meta["channel"],
            "telemetry": {
                "total_words": analysis["total_words"],
                "duration_seconds": analysis["duration_seconds"],
                "overall_wpm": analysis["overall_wpm"],
            },
            "anomalies_and_blindspots": analysis["anomalies"],
            "natural_scenes": analysis["natural_scenes"],
        }

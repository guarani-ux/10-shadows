import json
from typing import Any, Dict, List, Optional

from loop_engine.scribe.memory_store import ScribeMemoryStore


class ScribePatternMiner:
    """
    Shadow 6 Pattern & Anomaly Synthesis Engine.

    Cross-references multi-video corpora to identify:
    1. Hook Velocity Distributions (e.g. fastest vs. slowest intro hooks).
    2. Common Blindspots across channels (e.g. recurring visual-only gaps).
    3. Structural Archetypes (e.g. workplace spotlights vs. lectures).
    """

    def __init__(self, memory_store: ScribeMemoryStore):
        self.store = memory_store

    def extract_hook_velocity_report(self) -> List[Dict[str, Any]]:
        """Finds the opening scene (Hook) pacing for all indexed videos."""
        with self.store._get_connection() as conn:
            rows = conn.execute(
                """
                SELECT 
                    v.video_id,
                    v.title,
                    v.channel,
                    v.overall_wpm,
                    s.pacing_wpm as hook_wpm,
                    s.duration_seconds as hook_duration,
                    s.verbatim_anchor_quote as hook_quote
                FROM scenes s
                JOIN videos v ON s.video_id = v.video_id
                WHERE s.scene_index = 1
                ORDER BY s.pacing_wpm DESC
                """
            ).fetchall()
            return [dict(r) for r in rows]

    def extract_blindspot_inventory(self) -> Dict[str, Any]:
        """Aggregates all epistemic anomalies across the entire knowledge base."""
        with self.store._get_connection() as conn:
            rows = conn.execute(
                """
                SELECT 
                    anomaly_type,
                    COUNT(*) as occurrence_count,
                    AVG(gap_duration_seconds) as avg_gap_seconds
                FROM blindspots
                GROUP BY anomaly_type
                """
            ).fetchall()
            return {
                "anomaly_breakdown": [dict(r) for r in rows],
                "total_flagged_anomalies": sum(r["occurrence_count"] for r in rows),
            }

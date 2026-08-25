"""Editorial Intelligence Engine: Insights and Story Angles."""

from datetime import datetime, timezone
import hashlib
from typing import Optional
from svris.core.db import get_connection


def create_insight(
    db_path: str,
    topic_id: str,
    primary_claim_id: str,
    insight_text: str,
) -> str:
    """Creates a derived editorial insight linked directly to a verified primary claim."""
    conn = get_connection(db_path)
    cur = conn.cursor()

    # Generate deterministic ID
    hash_seed = f"{topic_id}:{primary_claim_id}:{insight_text}"
    insight_id = f"ins_{hashlib.sha256(hash_seed.encode('utf-8')).hexdigest()[:16]}"
    now_iso = datetime.now(timezone.utc).isoformat()

    cur.execute(
        """INSERT INTO insights (
            insight_id, topic_id, insight_text, primary_claim_id, created_at
        ) VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(insight_id) DO UPDATE SET
            insight_text = excluded.insight_text""",
        (insight_id, topic_id, insight_text.strip(), primary_claim_id, now_iso),
    )

    conn.commit()
    conn.close()
    return insight_id


def create_story_angle(
    db_path: str,
    insight_id: str,
    angle_text: str,
    target_audience: str,
    emotional_hook_hypothesis: Optional[str] = None,
) -> str:
    """Derives a format-agnostic story angle from an insight."""
    conn = get_connection(db_path)
    cur = conn.cursor()

    hash_seed = f"{insight_id}:{angle_text}:{target_audience}"
    angle_id = f"ang_{hashlib.sha256(hash_seed.encode('utf-8')).hexdigest()[:16]}"
    now_iso = datetime.now(timezone.utc).isoformat()

    cur.execute(
        """INSERT INTO story_angles (
            angle_id, insight_id, angle_text, target_audience, emotional_hook_hypothesis, used_count, created_at
        ) VALUES (?, ?, ?, ?, ?, 0, ?)
        ON CONFLICT(angle_id) DO UPDATE SET
            angle_text = excluded.angle_text,
            target_audience = excluded.target_audience,
            emotional_hook_hypothesis = excluded.emotional_hook_hypothesis""",
        (
            angle_id,
            insight_id,
            angle_text.strip(),
            target_audience.strip(),
            emotional_hook_hypothesis.strip() if emotional_hook_hypothesis else None,
            now_iso,
        ),
    )

    conn.commit()
    conn.close()
    return angle_id

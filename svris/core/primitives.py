"""Script Primitive Generation Engine."""

from datetime import datetime, timezone
import hashlib
from svris.core.db import get_connection


def generate_script_primitive(
    db_path: str,
    angle_id: str,
    primitive_type: str,
    content: str,
    platform: str = "ALL",
    format: str = "ALL",
    orientation: str = "ALL",
) -> str:
    """Creates an atomic script primitive foreign-keyed to a story angle."""
    conn = get_connection(db_path)
    cur = conn.cursor()

    hash_seed = f"{angle_id}:{primitive_type}:{platform}:{format}:{orientation}:{content}"
    primitive_id = f"prim_{hashlib.sha256(hash_seed.encode('utf-8')).hexdigest()[:16]}"
    now_iso = datetime.now(timezone.utc).isoformat()

    cur.execute(
        """INSERT INTO script_primitives (
            primitive_id, angle_id, primitive_type, content, platform, format, orientation, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(primitive_id) DO UPDATE SET
            content = excluded.content""",
        (
            primitive_id,
            angle_id,
            primitive_type,
            content.strip(),
            platform,
            format,
            orientation,
            now_iso,
        ),
    )

    conn.commit()
    conn.close()
    return primitive_id

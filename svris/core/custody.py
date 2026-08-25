"""Physical Content Custody and Chunking Engine."""

import hashlib
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
from svris.core.db import get_connection


def create_source_snapshot(
    db_path: str,
    source_id: str,
    raw_text: str,
    media_type: str = "text/plain",
    canonical_url: Optional[str] = None,
) -> Dict[str, Any]:
    """Stores physical immutable source snapshot with deterministic SHA-256."""
    conn = get_connection(db_path)
    cur = conn.cursor()

    content_hash = hashlib.sha256(raw_text.encode("utf-8")).hexdigest()
    now_iso = datetime.now(timezone.utc).isoformat()
    snapshot_id = f"snp_{content_hash[:16]}"

    cur.execute(
        """INSERT INTO source_snapshots (
            snapshot_id, source_id, retrieved_at, content_sha256, raw_text, media_type, canonical_url, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(snapshot_id) DO NOTHING""",
        (
            snapshot_id,
            source_id,
            now_iso,
            content_hash,
            raw_text,
            media_type,
            canonical_url,
            now_iso,
        ),
    )

    conn.commit()
    conn.close()

    return {
        "snapshot_id": snapshot_id,
        "source_id": source_id,
        "content_sha256": content_hash,
        "retrieved_at": now_iso,
    }


def create_source_chunk(
    db_path: str,
    snapshot_id: str,
    ordinal: int,
    start_char: int,
    end_char: int,
    content: str,
) -> Dict[str, Any]:
    """Stores a deterministic chunk of a source snapshot."""
    conn = get_connection(db_path)
    cur = conn.cursor()

    content_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()
    chunk_id = f"chk_{snapshot_id}_{ordinal}"

    cur.execute(
        """INSERT INTO source_chunks (
            chunk_id, snapshot_id, ordinal, start_char, end_char, content, content_sha256
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(snapshot_id, ordinal) DO NOTHING""",
        (
            chunk_id,
            snapshot_id,
            ordinal,
            start_char,
            end_char,
            content,
            content_hash,
        ),
    )

    conn.commit()
    conn.close()

    return {
        "chunk_id": chunk_id,
        "snapshot_id": snapshot_id,
        "ordinal": ordinal,
        "content_sha256": content_hash,
    }

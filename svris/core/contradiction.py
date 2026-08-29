"""Contradiction Detection and Registry Engine."""

import hashlib
from datetime import datetime, timezone

from svris.core.db import get_connection


def detect_and_register_contradictions(
    db_path: str,
    claim_id_a: str,
    claim_id_b: str,
    nature_of_conflict: str,
    status: str = "OPEN_UNRESOLVED",
) -> str:
    """Registers an explicit conflict between two claims, preventing lossy silent merges."""
    conn = get_connection(db_path)
    cur = conn.cursor()

    # Ensure deterministic ID regardless of argument order
    ordered_ids = sorted([claim_id_a, claim_id_b])
    hash_seed = f"{ordered_ids[0]}:{ordered_ids[1]}"
    contradiction_id = f"cntr_{hashlib.sha256(hash_seed.encode('utf-8')).hexdigest()[:16]}"
    now_iso = datetime.now(timezone.utc).isoformat()

    cur.execute(
        """INSERT INTO contradictions (
            contradiction_id, claim_id_a, claim_id_b, nature_of_conflict, status, created_at
        ) VALUES (?, ?, ?, ?, ?, ?)
        ON CONFLICT(contradiction_id) DO UPDATE SET
            nature_of_conflict = excluded.nature_of_conflict,
            status = excluded.status""",
        (
            contradiction_id,
            ordered_ids[0],
            ordered_ids[1],
            nature_of_conflict,
            status,
            now_iso,
        ),
    )

    # Invariant: Mark claims as CONTRADICTED
    cur.execute(
        "UPDATE claims SET verification_state = 'CONTRADICTED', updated_at = ? WHERE claim_id IN (?, ?)",
        (now_iso, ordered_ids[0], ordered_ids[1]),
    )

    conn.commit()
    conn.close()
    return contradiction_id

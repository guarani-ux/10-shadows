"""Temporal Freshness, Expiration, and Successor Lineage Engine."""

import hashlib
from datetime import datetime, timezone
from typing import Optional
from svris.core.db import get_connection


def evaluate_freshness(db_path: str) -> int:
    """Scans claims and marks records STALE if valid_until or review_after has passed.

    Returns the number of claims marked STALE.
    """
    conn = get_connection(db_path)
    cur = conn.cursor()

    now_date = datetime.now(timezone.utc).date().isoformat()
    now_iso = datetime.now(timezone.utc).isoformat()

    cur.execute(
        """UPDATE claims
           SET verification_state = 'STALE',
               updated_at = ?
           WHERE verification_state IN ('VERIFIED', 'UNVERIFIED')
             AND (
                 (valid_until IS NOT NULL AND valid_until < ?)
                 OR
                 (review_after IS NOT NULL AND review_after < ?)
             )""",
        (now_iso, now_date, now_date),
    )
    stale_count = cur.rowcount
    conn.commit()
    conn.close()
    return stale_count


def mark_claim_superseded(
    db_path: str,
    old_claim_id: str,
    superseding_claim_id: str,
    rationale: str = "Superseded by newer canonical claim",
) -> str:
    """Marks an older claim as SUPERSEDED and records explicit successor lineage in claim_relations."""
    conn = get_connection(db_path)
    cur = conn.cursor()

    now_iso = datetime.now(timezone.utc).isoformat()
    relation_id = f"rel_{hashlib.sha256(f'{old_claim_id}:{superseding_claim_id}:SUPERSEDES'.encode('utf-8')).hexdigest()[:16]}"

    cur.execute(
        """UPDATE claims
           SET verification_state = 'SUPERSEDED',
               updated_at = ?
           WHERE claim_id = ?""",
        (now_iso, old_claim_id),
    )

    cur.execute(
        """INSERT INTO claim_relations (
            relation_id, from_claim_id, to_claim_id, relation_type, rationale, created_at
        ) VALUES (?, ?, ?, 'SUPERSEDES', ?, ?)
        ON CONFLICT(relation_id) DO UPDATE SET
            rationale = excluded.rationale""",
        (relation_id, old_claim_id, superseding_claim_id, rationale, now_iso),
    )

    conn.commit()
    conn.close()
    return relation_id

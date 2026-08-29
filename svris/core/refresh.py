"""Incremental Topic Refresh and Delta Analyzer."""

from typing import Any, Dict, List

from svris.core.db import get_connection


def compute_topic_delta(db_path: str, topic_id: str) -> Dict[str, Any]:
    """Analyzes accumulated facts for a topic and isolates stale/unverified claims requiring refresh."""
    conn = get_connection(db_path, readonly=True)
    cur = conn.cursor()

    cur.execute(
        """SELECT claim_id, verification_state FROM claims WHERE topic_id = ?""",
        (topic_id,),
    )
    rows = cur.fetchall()
    conn.close()

    total_claims = len(rows)
    fresh_claims = 0
    stale_claims = 0
    unverified_claims = 0
    contradicted_claims = 0
    superseded_claims = 0

    stale_claim_ids: List[str] = []
    unverified_claim_ids: List[str] = []

    for r in rows:
        state = r["verification_state"]
        cid = r["claim_id"]
        if state == "VERIFIED":
            fresh_claims += 1
        elif state == "STALE":
            stale_claims += 1
            stale_claim_ids.append(cid)
        elif state == "UNVERIFIED":
            unverified_claims += 1
            unverified_claim_ids.append(cid)
        elif state == "CONTRADICTED":
            contradicted_claims += 1
        elif state == "SUPERSEDED":
            superseded_claims += 1

    return {
        "topic_id": topic_id,
        "total_claims": total_claims,
        "fresh_claims": fresh_claims,
        "stale_claims": stale_claims,
        "unverified_claims": unverified_claims,
        "contradicted_claims": contradicted_claims,
        "superseded_claims": superseded_claims,
        "stale_claim_ids": stale_claim_ids,
        "unverified_claim_ids": unverified_claim_ids,
    }

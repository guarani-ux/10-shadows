"""Read-Only Projection Views for Scriptwriters."""

from typing import Any, Dict, List, Optional

from svris.core.db import get_connection


def query_script_primitives_with_provenance(
    db_path: str,
    platform: str = "ALL",
    format_filter: str = "ALL",
    primitive_type: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Retrieves script primitives with complete traceable lineage to canonical sources.

    Runs via a read-only database connection.
    """
    conn = get_connection(db_path, readonly=True)
    cur = conn.cursor()

    query = """
        SELECT
            sp.primitive_id,
            sp.primitive_type,
            sp.content,
            sp.platform,
            sp.format,
            sp.orientation,
            sa.angle_text,
            sa.target_audience,
            ins.insight_text,
            c.claim_id,
            c.claim_text,
            c.verification_state,
            s.source_id,
            s.url AS source_url,
            s.title AS source_title,
            s.publisher,
            er.relationship_state,
            er.quote_text
        FROM script_primitives sp
        JOIN story_angles sa ON sp.angle_id = sa.angle_id
        JOIN insights ins ON sa.insight_id = ins.insight_id
        JOIN claims c ON ins.primary_claim_id = c.claim_id
        LEFT JOIN evidence_relationships er ON c.claim_id = er.claim_id
        LEFT JOIN sources s ON er.source_id = s.source_id
        WHERE (sp.platform = ? OR sp.platform = 'ALL' OR ? = 'ALL')
          AND (sp.format = ? OR sp.format = 'ALL' OR ? = 'ALL')
    """
    params = [platform, platform, format_filter, format_filter]

    if primitive_type:
        query += " AND sp.primitive_type = ?"
        params.append(primitive_type)

    query += " ORDER BY sp.created_at ASC"

    cur.execute(query, tuple(params))
    rows = cur.fetchall()
    results = [dict(r) for r in rows]
    conn.close()
    return results

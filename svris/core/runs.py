"""Research Runs Orchestration and Batch Source Custody Engine."""

import hashlib
import json
import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Tuple

from jsonschema import validate

from svris.core.custody import create_source_chunks, create_source_snapshot
from svris.core.db import get_connection
from svris.core.source_normalizer import normalize_url


class InvalidRunTransitionError(Exception):
    """Raised when an illegal status transition is attempted on a research run."""

    pass


_ALLOWED_TRANSITIONS = {
    "PENDING": ["RUNNING", "FAILED"],
    "RUNNING": ["COMPLETED", "FAILED"],
    "COMPLETED": [],
    "FAILED": [],
}


def _load_run_schema() -> dict:
    schema_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "../schemas/research_run.schema.json"))
    with open(schema_path, "r", encoding="utf-8") as f:
        return json.load(f)


def create_research_run(db_path: str, plan_dict: Dict[str, Any]) -> str:
    """Validates plan against JSON schema, records new research run in PENDING status."""
    schema = _load_run_schema()
    validate(instance=plan_dict, schema=schema)

    conn = get_connection(db_path)
    cur = conn.cursor()

    now_iso = datetime.now(timezone.utc).isoformat()
    plan_hash = hashlib.sha256(json.dumps(plan_dict, sort_keys=True).encode("utf-8")).hexdigest()[:12]
    run_id = f"run_{plan_hash}_{now_iso[:10].replace('-', '')}"

    cur.execute(
        """INSERT INTO research_runs (
            run_id, topic_id, objective, status, plan_json, created_at
        ) VALUES (?, ?, ?, 'PENDING', ?, ?)""",
        (
            run_id,
            plan_dict["topic_id"],
            plan_dict["objective"],
            json.dumps(plan_dict),
            now_iso,
        ),
    )

    conn.commit()
    conn.close()
    return run_id


def update_run_status(db_path: str, run_id: str, new_status: str) -> None:
    """Updates research run status while enforcing strict state machine transitions."""
    conn = get_connection(db_path)
    cur = conn.cursor()

    cur.execute("SELECT status FROM research_runs WHERE run_id = ?", (run_id,))
    row = cur.fetchone()
    if not row:
        conn.close()
        raise ValueError(f"Research run '{run_id}' does not exist.")

    current_status = row["status"]
    allowed = _ALLOWED_TRANSITIONS.get(current_status, [])
    if new_status not in allowed:
        conn.close()
        raise InvalidRunTransitionError(
            f"Cannot transition research run '{run_id}' from '{current_status}' to '{new_status}'. "
            f"Allowed transitions: {allowed}"
        )

    cur.execute("UPDATE research_runs SET status = ? WHERE run_id = ?", (new_status, run_id))
    conn.commit()
    conn.close()


def ingest_and_bind_source(
    db_path: str,
    run_id: str,
    source_data: Dict[str, Any],
    raw_text: str,
) -> Tuple[str, List[str]]:
    """Ingests source origin, creates immutable content snapshot and chunks, and binds to run."""
    conn = get_connection(db_path)
    cur = conn.cursor()

    # 1. Verify run existence
    cur.execute("SELECT run_id FROM research_runs WHERE run_id = ?", (run_id,))
    if not cur.fetchone():
        conn.close()
        raise ValueError(f"Research run '{run_id}' does not exist.")

    now_iso = datetime.now(timezone.utc).isoformat()
    raw_sha = hashlib.sha256(raw_text.encode("utf-8")).hexdigest()
    canonical_url = normalize_url(source_data.get("url", "")) if source_data.get("url") else None
    source_id = source_data.get("source_id", f"src_{raw_sha[:16]}")

    # 2. Persist Source Origin
    cur.execute(
        """INSERT INTO sources (
            source_id, url, title, publisher, author, publication_date,
            retrieval_date, source_type, trust_tier, raw_content_sha256, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(source_id) DO UPDATE SET
            raw_content_sha256 = excluded.raw_content_sha256""",
        (
            source_id,
            canonical_url,
            source_data.get("title", "Untitled Source"),
            source_data.get("publisher"),
            source_data.get("author"),
            source_data.get("publication_date"),
            source_data.get("retrieval_date", now_iso[:10]),
            source_data.get("source_type", "WEB"),
            source_data.get("trust_tier", "UNTRUSTED_RETRIEVAL"),
            raw_sha,
            now_iso,
        ),
    )
    conn.commit()
    conn.close()

    # 3. Create Physical Content Snapshot & Chunks
    snapshot_res = create_source_snapshot(
        db_path=db_path,
        source_id=source_id,
        raw_text=raw_text,
        media_type="text/plain",
        canonical_url=canonical_url,
    )
    snapshot_id = snapshot_res["snapshot_id"] if isinstance(snapshot_res, dict) else snapshot_res
    chunk_ids = create_source_chunks(db_path=db_path, snapshot_id=snapshot_id)

    # 4. Bind Source & Snapshot to Research Run
    conn = get_connection(db_path)
    cur = conn.cursor()
    cur.execute(
        """INSERT INTO research_run_sources (
            run_id, source_id, snapshot_id, discovered_at
        ) VALUES (?, ?, ?, ?)
        ON CONFLICT(run_id, source_id) DO NOTHING""",
        (run_id, source_id, snapshot_id, now_iso),
    )

    conn.commit()
    conn.close()
    return snapshot_id, chunk_ids


def complete_research_run(db_path: str, run_id: str, summary_dict: Dict[str, Any]) -> None:
    """Marks research run as COMPLETED and stores summary JSON."""
    conn = get_connection(db_path)
    cur = conn.cursor()

    now_iso = datetime.now(timezone.utc).isoformat()
    cur.execute(
        """UPDATE research_runs
           SET status = 'COMPLETED',
               summary_json = ?,
               completed_at = ?
           WHERE run_id = ?""",
        (json.dumps(summary_dict), now_iso, run_id),
    )
    conn.commit()
    conn.close()

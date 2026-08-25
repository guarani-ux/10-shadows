"""Database substrate and CAS transaction manager for SVRIS."""

import os
import sqlite3
from typing import Optional, Dict, Any


class CASUpdateError(Exception):
    """Raised when an optimistic concurrency update fails due to revision mismatch."""
    pass


def get_connection(db_path: str, readonly: bool = False) -> sqlite3.Connection:
    """Creates a configured SQLite connection with foreign keys and WAL mode."""
    if readonly:
        # SQLite URI read-only connection
        normalized_path = os.path.abspath(db_path).replace("\\", "/")
        uri = f"file:{normalized_path}?mode=ro"
        conn = sqlite3.connect(uri, uri=True)
    else:
        conn = sqlite3.connect(db_path)
        conn.execute("PRAGMA journal_mode = WAL;")

    conn.execute("PRAGMA foreign_keys = ON;")
    conn.row_factory = sqlite3.Row
    return conn


def init_db(db_path: str) -> None:
    """Initializes the database using canonical DDL schema."""
    schema_path = os.path.join(os.path.dirname(__file__), "schema.sql")
    with open(schema_path, "r", encoding="utf-8") as f:
        schema_sql = f.read()

    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys = ON;")
    conn.executescript(schema_sql)
    conn.commit()
    conn.close()


def update_claim_cas(
    db_path: str,
    claim_id: str,
    expected_revision: int,
    new_text: str,
    new_verification_state: str,
    valid_from: Optional[str] = None,
    valid_until: Optional[str] = None,
    review_after: Optional[str] = None,
    updated_at: Optional[str] = None,
) -> int:
    """Executes an atomic Compare-And-Swap update on a claim.

    Returns the incremented revision number upon success.
    Raises CASUpdateError if the expected revision does not match.
    """
    conn = get_connection(db_path)
    cur = conn.cursor()

    target_revision = expected_revision + 1
    update_time = updated_at if updated_at else "CURRENT_TIMESTAMP"

    cur.execute(
        """UPDATE claims
           SET claim_text = ?,
               verification_state = ?,
               valid_from = ?,
               valid_until = ?,
               review_after = ?,
               revision = ?,
               updated_at = ?
           WHERE claim_id = ? AND revision = ?""",
        (
            new_text,
            new_verification_state,
            valid_from,
            valid_until,
            review_after,
            target_revision,
            update_time,
            claim_id,
            expected_revision,
        ),
    )
    if cur.rowcount == 0:
        conn.rollback()
        conn.close()
        raise CASUpdateError(
            f"CAS collision on claim '{claim_id}': expected revision {expected_revision}."
        )

    conn.commit()
    conn.close()
    return target_revision

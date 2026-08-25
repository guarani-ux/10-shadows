"""Red-Team Adversary Test Suite for Vertical Slice 1: Relational Substrate & Provenance

Strict value assertions and negative mutation traps.
"""

import os
import sqlite3
import pytest
from svris.core.db import get_connection, init_db, CASUpdateError
from svris.core.source_normalizer import normalize_source, normalize_url, compute_sha256


@pytest.fixture
def test_db_path(tmp_path):
    db_file = str(tmp_path / "test_svris.db")
    init_db(db_file)
    return db_file


def test_positive_source_topic_claim_evidence_lifecycle(test_db_path):
    """Positive assertion: complete valid lifecycle persists with relational integrity."""
    norm = normalize_source(
        raw_text="The global economy showed resilient growth in 2025 according to IMF reports.",
        url="https://WWW.Example.COM/report/2025?ref=utm_source#intro",
        title="  Global Economic Outlook 2025  ",
        publisher="IMF",
        author="John Doe",
        publication_date="2025-01-15",
        source_type="INDUSTRY_REPORT",
        trust_tier="AUTHORITATIVE_SECONDARY",
    )
    assert norm["url"] == "https://example.com/report/2025"
    assert norm["title"] == "Global Economic Outlook 2025"
    assert len(norm["raw_content_sha256"]) == 64

    conn = get_connection(test_db_path)
    cur = conn.cursor()

    # 1. Insert topic
    cur.execute(
        "INSERT INTO topics (topic_id, name, parent_topic_id, description) VALUES (?, ?, ?, ?)",
        ("top_macro", "Macroeconomics", None, "Global macro trends"),
    )

    # 2. Insert source
    cur.execute(
        """INSERT INTO sources (
            source_id, url, title, publisher, author, publication_date,
            retrieval_date, source_type, trust_tier, raw_content_sha256, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            norm["source_id"],
            norm["url"],
            norm["title"],
            norm["publisher"],
            norm["author"],
            norm["publication_date"],
            norm["retrieval_date"],
            norm["source_type"],
            norm["trust_tier"],
            norm["raw_content_sha256"],
            norm["created_at"],
        ),
    )

    # 3. Insert claim
    cur.execute(
        """INSERT INTO claims (
            claim_id, claim_text, topic_id, verification_state, valid_from, valid_until,
            review_after, revision, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            "clm_gdp_growth",
            "Global GDP grew by 3.2% in 2024.",
            "top_macro",
            "VERIFIED",
            "2024-01-01",
            "2024-12-31",
            "2025-06-01",
            1,
            "2025-01-15T10:00:00Z",
            "2025-01-15T10:00:00Z",
        ),
    )

    # 4. Insert evidence relationship
    cur.execute(
        """INSERT INTO evidence_relationships (
            evidence_id, claim_id, source_id, relationship_state, quote_text, confidence, rationale, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            "evi_001",
            "clm_gdp_growth",
            norm["source_id"],
            "SUPPORTS",
            "Global economic growth reached 3.2 percent.",
            0.95,
            "Direct quote from IMF annual report table 1.1",
            "2025-01-15T10:00:00Z",
        ),
    )
    conn.commit()

    # Query verification
    cur.execute("SELECT relationship_state, confidence FROM evidence_relationships WHERE evidence_id = ?", ("evi_001",))
    row = cur.fetchone()
    assert row[0] == "SUPPORTS"
    assert row[1] == 0.95
    conn.close()


def test_negative_trap_foreign_key_missing_topic(test_db_path):
    """Negative Trap 1: Inserting claim with non-existent topic must fail foreign key constraint."""
    conn = get_connection(test_db_path)
    cur = conn.cursor()
    with pytest.raises(sqlite3.IntegrityError):
        cur.execute(
            """INSERT INTO claims (
                claim_id, claim_text, topic_id, verification_state, valid_from, valid_until,
                review_after, revision, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                "clm_bad_topic",
                "Orphan claim",
                "non_existent_topic",
                "UNVERIFIED",
                None,
                None,
                None,
                1,
                "2025-01-15T10:00:00Z",
                "2025-01-15T10:00:00Z",
            ),
        )
    conn.close()


def test_negative_trap_foreign_key_missing_source(test_db_path):
    """Negative Trap 2: Evidence row referencing non-existent source must trigger IntegrityError."""
    conn = get_connection(test_db_path)
    cur = conn.cursor()
    cur.execute("INSERT INTO topics (topic_id, name) VALUES ('top_1', 'AI')")
    cur.execute(
        """INSERT INTO claims (
            claim_id, claim_text, topic_id, verification_state, revision, created_at, updated_at
        ) VALUES ('clm_1', 'AI is scaling', 'top_1', 'UNVERIFIED', 1, '2025-01-15T10:00:00Z', '2025-01-15T10:00:00Z')"""
    )
    conn.commit()

    with pytest.raises(sqlite3.IntegrityError):
        cur.execute(
            """INSERT INTO evidence_relationships (
                evidence_id, claim_id, source_id, relationship_state, confidence, rationale, created_at
            ) VALUES ('evi_orphan', 'clm_1', 'fake_source_id', 'SUPPORTS', 0.9, 'No source', '2025-01-15T10:00:00Z')"""
        )
    conn.close()


def test_negative_trap_invalid_enum_check_constraint(test_db_path):
    """Negative Trap 3: Inserting invalid enum bounds must fail CHECK constraint."""
    conn = get_connection(test_db_path)
    cur = conn.cursor()
    with pytest.raises(sqlite3.IntegrityError):
        cur.execute(
            """INSERT INTO sources (
                source_id, title, retrieval_date, source_type, trust_tier, raw_content_sha256, created_at
            ) VALUES ('src_bad', 'Bad Source', '2025-01-15', 'INVALID_SOURCE_TYPE', 'UNTRUSTED_RETRIEVAL', 'hash', '2025-01-15')"""
        )
    conn.close()


def test_negative_trap_readonly_connection_isolation(test_db_path):
    """Negative Trap 4: Scriptwriter read-only connection must reject mutations."""
    conn_ro = get_connection(test_db_path, readonly=True)
    cur = conn_ro.cursor()
    with pytest.raises(sqlite3.OperationalError):
        cur.execute("INSERT INTO topics (topic_id, name) VALUES ('top_ro', 'ReadOnlyViolation')")
    conn_ro.close()


def test_negative_trap_cas_optimistic_concurrency(test_db_path):
    """Negative Trap 5: Stale revision CAS update must raise CASUpdateError."""
    from svris.core.db import update_claim_cas

    conn = get_connection(test_db_path)
    cur = conn.cursor()
    cur.execute("INSERT INTO topics (topic_id, name) VALUES ('top_cas', 'CAS Testing')")
    cur.execute(
        """INSERT INTO claims (
            claim_id, claim_text, topic_id, verification_state, revision, created_at, updated_at
        ) VALUES ('clm_cas', 'Initial text', 'top_cas', 'UNVERIFIED', 1, '2025-01-15T10:00:00Z', '2025-01-15T10:00:00Z')"""
    )
    conn.commit()
    conn.close()

    # Successful CAS update from revision 1 -> 2
    new_rev = update_claim_cas(
        db_path=test_db_path,
        claim_id="clm_cas",
        expected_revision=1,
        new_text="Updated text",
        new_verification_state="VERIFIED",
    )
    assert new_rev == 2

    # Stale CAS attempt (still claiming revision 1) must fail
    with pytest.raises(CASUpdateError):
        update_claim_cas(
            db_path=test_db_path,
            claim_id="clm_cas",
            expected_revision=1,
            new_text="Conflict text",
            new_verification_state="VERIFIED",
        )

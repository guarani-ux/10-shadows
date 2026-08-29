"""Red-Team Adversary Test Suite for Vertical Slice 3: Editorial Intelligence & Script Primitives

Strict value assertions and negative mutation traps.
"""

import sqlite3

import pytest

from svris.core.db import get_connection, init_db
from svris.core.editorial import create_insight, create_story_angle
from svris.core.primitives import generate_script_primitive
from svris.core.views import query_script_primitives_with_provenance


@pytest.fixture
def test_db_path(tmp_path):
    db_file = str(tmp_path / "test_svris_slice3.db")
    init_db(db_file)
    conn = get_connection(db_file)
    cur = conn.cursor()
    cur.execute("INSERT INTO topics (topic_id, name) VALUES ('top_ai', 'Artificial Intelligence')")
    cur.execute(
        """INSERT INTO sources (
            source_id, url, title, publisher, retrieval_date, source_type, trust_tier, raw_content_sha256, created_at
        ) VALUES (
            'src_paper', 'https://arxiv.org/abs/2025.1234', 'Autonomous Systems', 'ArXiv', '2025-01-01',
            'ACADEMIC', 'VERIFIED_PRIMARY', 'c'*64, '2025-01-01T00:00:00Z'
        )"""
    )
    cur.execute(
        """INSERT INTO claims (
            claim_id, claim_text, topic_id, verification_state, revision, created_at, updated_at
        ) VALUES (
            'clm_ai_latency', 'Local inference latency dropped under 10ms for 7B parameter models.',
            'top_ai', 'VERIFIED', 1, '2025-01-01T00:00:00Z', '2025-01-01T00:00:00Z'
        )"""
    )
    cur.execute(
        """INSERT INTO evidence_relationships (
            evidence_id, claim_id, source_id, relationship_state, quote_text, confidence, rationale, created_at
        ) VALUES (
            'evi_latency', 'clm_ai_latency', 'src_paper', 'SUPPORTS', 'Sub-10ms response recorded on Apple M-series chips.',
            0.99, 'Direct benchmark table 4', '2025-01-01T00:00:00Z'
        )"""
    )
    conn.commit()
    conn.close()
    return db_file


def _get_table_fingerprint(db_path: str, table_name: str) -> str:
    """Computes a checksum fingerprint of all rows in a canonical table."""
    conn = get_connection(db_path, readonly=True)
    cur = conn.cursor()
    cur.execute(f"SELECT * FROM {table_name} ORDER BY 1")
    rows = cur.fetchall()
    conn.close()
    return str([tuple(r) for r in rows])


def test_positive_editorial_synthesis_and_primitive_projections(test_db_path):
    """Positive test: Derive insight -> story angle -> platform script primitive."""
    # 1. Create Insight
    insight_id = create_insight(
        db_path=test_db_path,
        topic_id="top_ai",
        primary_claim_id="clm_ai_latency",
        insight_text="Edge AI now executes faster than human visual reflex time, enabling real-time offline assistants.",
    )
    assert insight_id.startswith("ins_")

    # 2. Create Story Angle
    angle_id = create_story_angle(
        db_path=test_db_path,
        insight_id=insight_id,
        angle_text="The Death of Cloud AI: Why your next phone won't need the internet to think.",
        target_audience="Tech enthusiasts & developers",
        emotional_hook_hypothesis="Curiosity + Privacy sovereignty",
    )
    assert angle_id.startswith("ang_")

    # 3. Generate Primitives for YouTube Shorts and Instagram Reels
    prim_yt = generate_script_primitive(
        db_path=test_db_path,
        angle_id=angle_id,
        primitive_type="HOOK",
        content="Stop paying cloud subscriptions for AI. Your phone can now think in under 10 milliseconds entirely offline.",
        platform="YOUTUBE",
        format="SHORT_FORM",
        orientation="VERTICAL",
    )
    assert prim_yt.startswith("prim_")

    prim_vis = generate_script_primitive(
        db_path=test_db_path,
        angle_id=angle_id,
        primitive_type="VISUAL_CUE",
        content="Split screen: Airplane mode enabled on phone while live local LLM terminal generates instant code.",
        platform="ALL",
        format="SHORT_FORM",
        orientation="VERTICAL",
    )
    assert prim_vis.startswith("prim_")

    # 4. Query Read View with Complete Provenance
    results = query_script_primitives_with_provenance(
        db_path=test_db_path,
        platform="YOUTUBE",
        format_filter="SHORT_FORM",
    )
    assert len(results) >= 1
    item = results[0]
    assert item["primitive_type"] == "HOOK"
    assert item["platform"] == "YOUTUBE"
    assert item["source_url"] == "https://arxiv.org/abs/2025.1234"
    assert item["publisher"] == "ArXiv"
    assert item["claim_text"] == "Local inference latency dropped under 10ms for 7B parameter models."


def test_negative_trap_zero_contamination_of_canonical_research(test_db_path):
    """Negative Trap 1: Script primitive generation must not modify canonical tables (claims, sources, evidence)."""
    sources_before = _get_table_fingerprint(test_db_path, "sources")
    claims_before = _get_table_fingerprint(test_db_path, "claims")
    evidence_before = _get_table_fingerprint(test_db_path, "evidence_relationships")

    insight_id = create_insight(
        db_path=test_db_path,
        topic_id="top_ai",
        primary_claim_id="clm_ai_latency",
        insight_text="Edge compute unlocks offline privacy.",
    )
    angle_id = create_story_angle(
        db_path=test_db_path,
        insight_id=insight_id,
        angle_text="Offline AI Revolution",
        target_audience="General audience",
    )
    generate_script_primitive(
        db_path=test_db_path,
        angle_id=angle_id,
        primitive_type="HOOK",
        content="Is the cloud dead?",
        platform="INSTAGRAM",
        format="SHORT_FORM",
        orientation="VERTICAL",
    )

    sources_after = _get_table_fingerprint(test_db_path, "sources")
    claims_after = _get_table_fingerprint(test_db_path, "claims")
    evidence_after = _get_table_fingerprint(test_db_path, "evidence_relationships")

    assert sources_before == sources_after
    assert claims_before == claims_after
    assert evidence_before == evidence_after


def test_negative_trap_invalid_primitive_type_constraint(test_db_path):
    """Negative Trap 2: Invalid primitive type or platform must fail SQLite CHECK constraints."""
    insight_id = create_insight(
        db_path=test_db_path,
        topic_id="top_ai",
        primary_claim_id="clm_ai_latency",
        insight_text="Edge AI test.",
    )
    angle_id = create_story_angle(
        db_path=test_db_path,
        insight_id=insight_id,
        angle_text="Angle test",
        target_audience="Engineers",
    )

    conn = get_connection(test_db_path)
    cur = conn.cursor()
    with pytest.raises(sqlite3.IntegrityError):
        cur.execute(
            """INSERT INTO script_primitives (
                primitive_id, angle_id, primitive_type, content, platform, format, orientation, created_at
            ) VALUES ('prim_bad', ?, 'INVALID_PRIMITIVE_TYPE', 'Content', 'YOUTUBE', 'SHORT_FORM', 'VERTICAL', '2025-01-01')""",
            (angle_id,),
        )
    conn.close()

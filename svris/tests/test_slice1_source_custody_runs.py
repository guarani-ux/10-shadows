"""Red-Team Adversary Test Suite for Slice 1: Source Custody & Research Runs."""

import json
import os

import pytest
from jsonschema.exceptions import ValidationError

from svris.core.db import get_connection, initialize_database
from svris.core.runs import (
    InvalidRunTransitionError,
    complete_research_run,
    create_research_run,
    ingest_and_bind_source,
    update_run_status,
)


@pytest.fixture
def test_db(tmp_path):
    db_path = str(tmp_path / "svris_runs_test.db")
    schema_path = os.path.abspath("svris/core/schema.sql")
    initialize_database(db_path, schema_path)

    conn = get_connection(db_path)
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO topics (topic_id, name, description) VALUES ('top_energy', 'Global Energy', 'Energy transition')"
    )
    conn.commit()
    conn.close()
    return db_path


def test_positive_research_run_full_lifecycle_and_idempotency(test_db):
    """Verifies valid plan creation, source ingestion, chunking, and run completion."""
    plan = {
        "topic_id": "top_energy",
        "objective": "Map nuclear reactor rollout timelines across Western Europe.",
        "target_source_types": ["INDUSTRY_REPORT", "PRIMARY_DOC"],
        "search_queries": ["nuclear energy deployment 2025 europe", "EIA nuclear capacity report"],
        "max_sources": 5,
    }

    run_id = create_research_run(test_db, plan)
    assert run_id.startswith("run_")

    source_data = {
        "source_id": "src_wcapt_01",
        "url": "https://www.world-nuclear.org/report/2025.html",
        "title": "World Nuclear Performance Report 2025",
        "publisher": "World Nuclear Association",
        "author": "Dr. Aris Thorne",
        "publication_date": "2025-03-01",
        "retrieval_date": "2025-08-15",
        "source_type": "INDUSTRY_REPORT",
        "trust_tier": "AUTHORITATIVE_SECONDARY",
    }
    raw_text = "Global nuclear generation increased by 3.2% in 2024. France connected 1.6 GW of new capacity."

    # 1. Ingest & Bind
    snap_id, chunk_ids = ingest_and_bind_source(test_db, run_id, source_data, raw_text)
    assert snap_id.startswith("snap_")
    assert len(chunk_ids) >= 1

    # Verify rows in DB
    conn = get_connection(test_db)
    cur = conn.cursor()
    cur.execute("SELECT run_id, source_id, snapshot_id FROM research_run_sources WHERE run_id = ?", (run_id,))
    bound_rows = cur.fetchall()
    assert len(bound_rows) == 1
    assert bound_rows[0]["source_id"] == "src_wcapt_01"
    assert bound_rows[0]["snapshot_id"] == snap_id

    # 2. Test Idempotency: Re-ingest exact same source & text into the run
    snap_id2, chunk_ids2 = ingest_and_bind_source(test_db, run_id, source_data, raw_text)
    assert snap_id2 == snap_id
    assert chunk_ids2 == chunk_ids

    # 3. Complete Run
    summary = {"sources_ingested": 1, "status": "ALL_TARGETS_ACQUIRED"}
    complete_research_run(test_db, run_id, summary)

    cur.execute("SELECT status, summary_json, completed_at FROM research_runs WHERE run_id = ?", (run_id,))
    run_row = cur.fetchone()
    assert run_row["status"] == "COMPLETED"
    assert run_row["completed_at"] is not None
    assert json.loads(run_row["summary_json"])["sources_ingested"] == 1
    conn.close()


def test_negative_trap_invalid_plan_schema_rejected(test_db):
    """Negative failure trap: missing mandatory fields in research plan must raise ValidationError."""
    invalid_plan = {
        "topic_id": "top_energy",
        # Missing objective, target_source_types, and search_queries
    }
    with pytest.raises(ValidationError):
        create_research_run(test_db, invalid_plan)


def test_negative_trap_ingest_into_nonexistent_run_rejected(test_db):
    """Negative failure trap: binding source to non-existent run_id raises ValueError."""
    source_data = {
        "source_id": "src_fake",
        "url": "https://example.com/test",
        "title": "Fake Source",
        "retrieval_date": "2025-08-15",
        "source_type": "WEB",
        "trust_tier": "UNTRUSTED_RETRIEVAL",
    }
    raw_text = "Some unverified text payload."
    with pytest.raises(ValueError, match="does not exist"):
        ingest_and_bind_source(test_db, "run_nonexistent_999", source_data, raw_text)


def test_negative_trap_illegal_run_status_transition_rejected(test_db):
    """Negative failure trap: illegal state transition (e.g. COMPLETED -> RUNNING) must raise InvalidRunTransitionError."""
    plan = {
        "topic_id": "top_energy",
        "objective": "Energy baseline analysis.",
        "target_source_types": ["ACADEMIC"],
        "search_queries": ["energy consumption metrics"],
    }
    run_id = create_research_run(test_db, plan)
    complete_research_run(test_db, run_id, {"result": "done"})

    with pytest.raises(InvalidRunTransitionError):
        update_run_status(test_db, run_id, "RUNNING")

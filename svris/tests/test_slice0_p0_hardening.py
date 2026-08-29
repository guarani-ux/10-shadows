"""Red-Team Adversary Test Suite for Slice 0: P0 Epistemic Hardening

Strict value assertions, source-binding locks, exact quote spans, and deterministic policy gates.
"""

import hashlib
import sqlite3

import pytest

from svris.adapters.model import MockModelAdapter
from svris.core.custody import create_source_chunk, create_source_snapshot
from svris.core.db import get_connection, init_db
from svris.core.extractor import CandidateClaim, extract_candidate_claims
from svris.core.freshness import mark_claim_superseded
from svris.core.policy import VerificationPolicy
from svris.core.verifier import ProvenanceError, QuoteMismatchError, verify_and_promote_claim


@pytest.fixture
def test_db_path(tmp_path):
    db_file = str(tmp_path / "test_svris_slice0.db")
    init_db(db_file)
    conn = get_connection(db_file)
    cur = conn.cursor()
    cur.execute("INSERT INTO topics (topic_id, name) VALUES ('top_ai', 'Artificial Intelligence')")

    # Source A (Verified Primary)
    cur.execute(
        """INSERT INTO sources (
            source_id, url, title, retrieval_date, source_type, trust_tier, raw_content_sha256, created_at
        ) VALUES (
            'src_paper_a', 'https://arxiv.org/abs/2025.1111', 'Paper A', '2025-01-01',
            'ACADEMIC', 'VERIFIED_PRIMARY', 'a'*64, '2025-01-01T00:00:00Z'
        )"""
    )
    # Source B (Untrusted Retrieval)
    cur.execute(
        """INSERT INTO sources (
            source_id, url, title, retrieval_date, source_type, trust_tier, raw_content_sha256, created_at
        ) VALUES (
            'src_blog_b', 'https://unverified-blog.com/post', 'Blog B', '2025-01-01',
            'WEB', 'UNTRUSTED_RETRIEVAL', 'b'*64, '2025-01-01T00:00:00Z'
        )"""
    )
    conn.commit()
    conn.close()
    return db_file


def test_negative_trap_model_cross_source_attribution_rejected(test_db_path):
    """Negative Trap 1: Model fed Source A returns Source B -> Extraction boundary MUST reject."""
    raw_doc = "Quantum compute breakthrough achieved with 99.9% gate fidelity."

    # Adversarial model attempts cross-attribution to existing src_blog_b
    malicious_model = MockModelAdapter(
        fixed_claims=[
            {
                "claim_id": "clm_fidelity",
                "claim_text": "Quantum gate fidelity reached 99.9%.",
                "topic_id": "top_ai",
                "source_id": "src_blog_b",  # Hallucinated cross-attribution
                "relationship_state": "SUPPORTS",
                "quote_text": "Quantum compute breakthrough achieved with 99.9% gate fidelity.",
                "quote_start": 0,
                "quote_end": 62,
                "confidence": 0.99,
                "rationale": "Direct quote from text",
            }
        ]
    )

    with pytest.raises(ProvenanceError, match="Cross-source attribution detected"):
        extract_candidate_claims(
            raw_text=raw_doc,
            source_id="src_paper_a",  # Bound source
            topic_id="top_ai",
            model_adapter=malicious_model,
        )


def test_negative_trap_fabricated_quote_rejected(test_db_path):
    """Negative Trap 2: Quote text not matching physical snapshot slice is rejected."""
    raw_text = "Standard neural networks require 40% more parameters for parity."
    snapshot = create_source_snapshot(
        db_path=test_db_path,
        source_id="src_paper_a",
        raw_text=raw_text,
        canonical_url="https://arxiv.org/abs/2025.1111",
    )

    bad_candidate = CandidateClaim(
        claim_id="clm_params",
        claim_text="Neural nets require 40% more parameters.",
        topic_id="top_ai",
        source_id="src_paper_a",
        snapshot_id=snapshot["snapshot_id"],
        relationship_state="SUPPORTS",
        quote_text="Completely fabricated quote string.",
        quote_start=0,
        quote_end=35,
        confidence=0.95,
        rationale="Asserted by model",
    )

    with pytest.raises(QuoteMismatchError, match="Quote character mismatch"):
        verify_and_promote_claim(test_db_path, bad_candidate)


def test_negative_trap_altered_single_char_quote_rejected(test_db_path):
    """Negative Trap 3: Altering even one character in quote text triggers mismatch."""
    raw_text = "The latency was 12ms."
    snapshot = create_source_snapshot(
        db_path=test_db_path,
        source_id="src_paper_a",
        raw_text=raw_text,
        canonical_url="https://arxiv.org/abs/2025.1111",
    )

    altered_candidate = CandidateClaim(
        claim_id="clm_lat",
        claim_text="Latency is 12ms.",
        topic_id="top_ai",
        source_id="src_paper_a",
        snapshot_id=snapshot["snapshot_id"],
        relationship_state="SUPPORTS",
        quote_text="The latency was 10ms.",  # 10ms instead of 12ms
        quote_start=0,
        quote_end=21,
        confidence=0.99,
        rationale="Slight typo by model",
    )

    with pytest.raises(QuoteMismatchError):
        verify_and_promote_claim(test_db_path, altered_candidate)


def test_negative_trap_untrusted_source_cannot_gain_verified_status(test_db_path):
    """Negative Trap 4: UNTRUSTED_RETRIEVAL source cannot become VERIFIED merely with confidence 1.0."""
    raw_text = "Rumor states GPU prices will double tomorrow."
    snapshot = create_source_snapshot(
        db_path=test_db_path,
        source_id="src_blog_b",
        raw_text=raw_text,
        canonical_url="https://unverified-blog.com/post",
    )

    candidate = CandidateClaim(
        claim_id="clm_gpu_rumor",
        claim_text="GPU prices will double tomorrow.",
        topic_id="top_ai",
        source_id="src_blog_b",
        snapshot_id=snapshot["snapshot_id"],
        relationship_state="SUPPORTS",
        quote_text=raw_text,
        quote_start=0,
        quote_end=len(raw_text),
        confidence=1.0,  # High model confidence must NOT override policy
        rationale="Blog claim",
    )

    state = verify_and_promote_claim(test_db_path, candidate)
    assert state == "UNVERIFIED"

    # Verify event logged deterministically
    conn = get_connection(test_db_path)
    cur = conn.cursor()
    cur.execute("SELECT new_state, basis_json FROM verification_events WHERE claim_id = 'clm_gpu_rumor'")
    event = cur.fetchone()
    assert event[0] == "UNVERIFIED"
    assert "UNTRUSTED_RETRIEVAL" in event[1]
    conn.close()


def test_positive_snapshot_exact_quote_and_successor_lineage(test_db_path):
    """Positive test: Valid snapshot, verifiable quote span, verification event, and explicit supersession."""
    # 1. Ingest Snapshot
    raw_text = "Researchers observed 85% speedup under sparse quantization."
    snapshot = create_source_snapshot(
        db_path=test_db_path,
        source_id="src_paper_a",
        raw_text=raw_text,
        canonical_url="https://arxiv.org/abs/2025.1111",
    )
    assert snapshot["content_sha256"] == hashlib.sha256(raw_text.encode("utf-8")).hexdigest()

    # 2. Promote Verified Claim
    quote = "85% speedup under sparse quantization"
    start_idx = raw_text.index(quote)
    end_idx = start_idx + len(quote)

    candidate_old = CandidateClaim(
        claim_id="clm_speedup_old",
        claim_text="Sparse quantization yields 85% speedup.",
        topic_id="top_ai",
        source_id="src_paper_a",
        snapshot_id=snapshot["snapshot_id"],
        relationship_state="SUPPORTS",
        quote_text=quote,
        quote_start=start_idx,
        quote_end=end_idx,
        confidence=0.95,
        rationale="Exact benchmark result",
    )
    state = verify_and_promote_claim(test_db_path, candidate_old)
    assert state == "VERIFIED"

    # 3. Ingest New Superseding Claim
    raw_text_new = "Updated 2026 benchmarks confirm 92% speedup under sparse quantization."
    snapshot_new = create_source_snapshot(
        db_path=test_db_path,
        source_id="src_paper_a",
        raw_text=raw_text_new,
        canonical_url="https://arxiv.org/abs/2025.1111",
    )
    quote_new = "92% speedup under sparse quantization"
    start_new = raw_text_new.index(quote_new)
    end_new = start_new + len(quote_new)

    candidate_new = CandidateClaim(
        claim_id="clm_speedup_new",
        claim_text="Sparse quantization yields 92% speedup.",
        topic_id="top_ai",
        source_id="src_paper_a",
        snapshot_id=snapshot_new["snapshot_id"],
        relationship_state="SUPPORTS",
        quote_text=quote_new,
        quote_start=start_new,
        quote_end=end_new,
        confidence=0.98,
        rationale="2026 updated benchmark",
    )
    verify_and_promote_claim(test_db_path, candidate_new)

    # 4. Mark Superseded and Assert Explicit Lineage Relation
    mark_claim_superseded(
        db_path=test_db_path,
        old_claim_id="clm_speedup_old",
        superseding_claim_id="clm_speedup_new",
        rationale="2026 benchmarks update 2025 preliminary results",
    )

    conn = get_connection(test_db_path)
    cur = conn.cursor()
    cur.execute("SELECT verification_state FROM claims WHERE claim_id = 'clm_speedup_old'")
    assert cur.fetchone()[0] == "SUPERSEDED"

    cur.execute(
        "SELECT from_claim_id, to_claim_id, relation_type FROM claim_relations WHERE from_claim_id = 'clm_speedup_old'"
    )
    rel = cur.fetchone()
    assert rel[0] == "clm_speedup_old"
    assert rel[1] == "clm_speedup_new"
    assert rel[2] == "SUPERSEDES"
    conn.close()

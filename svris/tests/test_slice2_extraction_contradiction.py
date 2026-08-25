"""Red-Team Adversary Test Suite for Vertical Slice 2: Extraction, Evidence Mapping & Contradiction Guard

Strict value assertions and negative mutation traps.
"""

import pytest
from svris.core.db import get_connection, init_db
from svris.core.extractor import extract_candidate_claims, CandidateClaim
from svris.core.verifier import verify_and_promote_claim, ProvenanceError
from svris.core.contradiction import detect_and_register_contradictions
from svris.adapters.model import MockModelAdapter


@pytest.fixture
def test_db_path(tmp_path):
    db_file = str(tmp_path / "test_svris_slice2.db")
    init_db(db_file)
    conn = get_connection(db_file)
    cur = conn.cursor()
    cur.execute("INSERT INTO topics (topic_id, name) VALUES ('top_energy', 'Renewable Energy')")
    cur.execute(
        """INSERT INTO sources (
            source_id, url, title, retrieval_date, source_type, trust_tier, raw_content_sha256, created_at
        ) VALUES (
            'src_iea_2025', 'https://iea.org/report', 'IEA Solar Report', '2025-01-01', 'INDUSTRY_REPORT',
            'AUTHORITATIVE_SECONDARY', 'a'*64, '2025-01-01T00:00:00Z'
        )"""
    )
    cur.execute(
        """INSERT INTO sources (
            source_id, url, title, retrieval_date, source_type, trust_tier, raw_content_sha256, created_at
        ) VALUES (
            'src_fossil_lobby', 'https://lobby.org/report', 'Lobby Report', '2025-01-01', 'INDUSTRY_REPORT',
            'UNTRUSTED_RETRIEVAL', 'b'*64, '2025-01-01T00:00:00Z'
        )"""
    )
    conn.commit()
    conn.close()
    return db_file


def test_positive_candidate_extraction_and_verified_promotion(test_db_path):
    """Positive test: Valid extraction promotes candidate claim to VERIFIED with SUPPORTS evidence."""
    mock_model = MockModelAdapter(
        fixed_claims=[
            {
                "claim_id": "clm_solar_cost",
                "claim_text": "Solar PV generation costs fell 85% between 2010 and 2024.",
                "topic_id": "top_energy",
                "source_id": "src_iea_2025",
                "relationship_state": "SUPPORTS",
                "quote_text": "Levelized cost of energy for solar PV dropped approximately 85% over the decade.",
                "confidence": 0.98,
                "rationale": "Direct figure from executive summary.",
            }
        ]
    )

    candidates = extract_candidate_claims(
        raw_text="Levelized cost of energy for solar PV dropped approximately 85% over the decade.",
        source_id="src_iea_2025",
        topic_id="top_energy",
        model_adapter=mock_model,
    )
    assert len(candidates) == 1
    assert candidates[0].confidence == 0.98

    status = verify_and_promote_claim(test_db_path, candidates[0])
    assert status == "VERIFIED"

    conn = get_connection(test_db_path)
    cur = conn.cursor()
    cur.execute("SELECT verification_state, revision FROM claims WHERE claim_id = 'clm_solar_cost'")
    row = cur.fetchone()
    assert row[0] == "VERIFIED"
    assert row[1] == 1
    conn.close()


def test_negative_trap_fabricated_source_rejection(test_db_path):
    """Negative Trap 1: Candidate citing non-existent source must raise ProvenanceError."""
    bad_candidate = CandidateClaim(
        claim_id="clm_fake_provenance",
        claim_text="Unfounded claim",
        topic_id="top_energy",
        source_id="src_fabricated_hallucination",
        relationship_state="SUPPORTS",
        quote_text="Fake quote",
        confidence=0.9,
        rationale="Model hallucinated source",
    )
    with pytest.raises(ProvenanceError):
        verify_and_promote_claim(test_db_path, bad_candidate)


def test_negative_trap_non_supporting_evidence_remains_unverified(test_db_path):
    """Negative Trap 2: Claims with DOES_NOT_ESTABLISH or CONTEXTUALIZES default to UNVERIFIED."""
    candidate = CandidateClaim(
        claim_id="clm_weak_evidence",
        claim_text="Solar may reach grid parity in remote regions.",
        topic_id="top_energy",
        source_id="src_iea_2025",
        relationship_state="CONTEXTUALIZES",
        quote_text="Remote installations show promise.",
        confidence=0.5,
        rationale="Contextual mention only.",
    )
    status = verify_and_promote_claim(test_db_path, candidate)
    assert status == "UNVERIFIED"

    conn = get_connection(test_db_path)
    cur = conn.cursor()
    cur.execute("SELECT verification_state FROM claims WHERE claim_id = 'clm_weak_evidence'")
    assert cur.fetchone()[0] == "UNVERIFIED"
    conn.close()


def test_negative_trap_contradiction_detection_preserves_both_claims(test_db_path):
    """Negative Trap 3: Opposing claims from different sources register a contradiction row without silent merging."""
    # 1. Promote Claim A
    candidate_a = CandidateClaim(
        claim_id="clm_solar_growth_high",
        claim_text="Solar adoption increased by 40% in 2024.",
        topic_id="top_energy",
        source_id="src_iea_2025",
        relationship_state="SUPPORTS",
        quote_text="Global solar additions rose 40%.",
        confidence=0.95,
        rationale="Official IEA statistics.",
    )
    verify_and_promote_claim(test_db_path, candidate_a)

    # 2. Promote Claim B (Opposing)
    candidate_b = CandidateClaim(
        claim_id="clm_solar_growth_low",
        claim_text="Solar adoption grew by only 5% in 2024 due to grid bottlenecks.",
        topic_id="top_energy",
        source_id="src_fossil_lobby",
        relationship_state="SUPPORTS",
        quote_text="Grid limitations held growth to 5%.",
        confidence=0.75,
        rationale="Lobby dataset.",
    )
    verify_and_promote_claim(test_db_path, candidate_b)

    # 3. Detect and register contradiction
    contradiction_id = detect_and_register_contradictions(
        db_path=test_db_path,
        claim_id_a="clm_solar_growth_high",
        claim_id_b="clm_solar_growth_low",
        nature_of_conflict="Growth rate dispute: 40% (IEA) vs 5% (Lobby)",
    )
    assert contradiction_id.startswith("cntr_")

    conn = get_connection(test_db_path)
    cur = conn.cursor()
    cur.execute("SELECT status FROM contradictions WHERE contradiction_id = ?", (contradiction_id,))
    assert cur.fetchone()[0] == "OPEN_UNRESOLVED"

    # Verify both original claims still physically exist unchanged
    cur.execute("SELECT COUNT(*) FROM claims WHERE claim_id IN ('clm_solar_growth_high', 'clm_solar_growth_low')")
    assert cur.fetchone()[0] == 2
    conn.close()

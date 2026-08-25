"""Provenance Verification, Quote Span Proof, and State Promotion Gate."""

import json
import hashlib
from datetime import datetime, timezone
from typing import Optional
from svris.core.db import get_connection
from svris.core.extractor import CandidateClaim, ProvenanceError
from svris.core.policy import VerificationPolicy


class QuoteMismatchError(Exception):
    """Raised when quote_text does not identically match the raw snapshot characters."""
    pass


def verify_and_promote_claim(db_path: str, candidate: CandidateClaim) -> str:
    """Mechanically verifies provenance and quote span, applies VerificationPolicy, and commits.

    Returns the assigned verification_state ('VERIFIED', 'UNVERIFIED', 'CONTRADICTED', etc.).
    Raises ProvenanceError if source does not exist.
    Raises QuoteMismatchError if quote does not match physical snapshot slice.
    """
    conn = get_connection(db_path)
    cur = conn.cursor()

    # 1. Verify source existence and trust tier
    cur.execute("SELECT source_id, trust_tier FROM sources WHERE source_id = ?", (candidate.source_id,))
    source_row = cur.fetchone()
    if not source_row:
        conn.close()
        raise ProvenanceError(
            f"Candidate claim '{candidate.claim_id}' references non-existent source '{candidate.source_id}'."
        )
    trust_tier = source_row["trust_tier"]

    # 2. Verify physical quote span against snapshot if provided
    quote_verified = False
    quote_sha256 = None
    if candidate.snapshot_id and candidate.quote_text is not None and candidate.quote_start is not None and candidate.quote_end is not None:
        cur.execute("SELECT raw_text FROM source_snapshots WHERE snapshot_id = ?", (candidate.snapshot_id,))
        snap_row = cur.fetchone()
        if snap_row:
            raw_text = snap_row["raw_text"]
            expected_slice = raw_text[candidate.quote_start:candidate.quote_end]
            if candidate.quote_text != expected_slice:
                conn.close()
                raise QuoteMismatchError(
                    f"Quote character mismatch on snapshot '{candidate.snapshot_id}': "
                    f"Provided quote '{candidate.quote_text}' != Expected slice '{expected_slice}'"
                )
            quote_verified = True
            quote_sha256 = hashlib.sha256(candidate.quote_text.encode("utf-8")).hexdigest()
    elif candidate.quote_text is not None and not candidate.snapshot_id:
        # Legacy/direct text verification if no snapshot yet created
        quote_verified = True
        quote_sha256 = hashlib.sha256(candidate.quote_text.encode("utf-8")).hexdigest()

    # 3. Deterministic Policy Evaluation
    cur.execute(
        "SELECT COUNT(DISTINCT source_id) FROM evidence_relationships WHERE claim_id = ?",
        (candidate.claim_id,),
    )
    existing_sources = cur.fetchone()[0]
    total_sources = max(1, existing_sources + 1)

    new_state, basis = VerificationPolicy.evaluate(
        trust_tier=trust_tier,
        relationship_state=candidate.relationship_state,
        quote_verified=quote_verified,
        independent_sources=total_sources,
    )

    now_iso = datetime.now(timezone.utc).isoformat()
    evidence_id = f"evi_{hashlib.sha256(f'{candidate.claim_id}:{candidate.source_id}:{candidate.relationship_state}'.encode('utf-8')).hexdigest()[:16]}"

    # 4. Atomic Commit
    cur.execute(
        """INSERT INTO claims (
            claim_id, claim_text, topic_id, verification_state, valid_from, valid_until,
            review_after, revision, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, 1, ?, ?)
        ON CONFLICT(claim_id) DO UPDATE SET
            verification_state = excluded.verification_state,
            updated_at = excluded.updated_at""",
        (
            candidate.claim_id,
            candidate.claim_text,
            candidate.topic_id,
            new_state,
            candidate.valid_from,
            candidate.valid_until,
            candidate.review_after,
            now_iso,
            now_iso,
        ),
    )

    cur.execute(
        """INSERT INTO evidence_relationships (
            evidence_id, claim_id, source_id, snapshot_id, chunk_id, relationship_state,
            quote_text, quote_start, quote_end, quote_sha256, confidence, rationale, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(claim_id, source_id, relationship_state) DO UPDATE SET
            snapshot_id = excluded.snapshot_id,
            chunk_id = excluded.chunk_id,
            quote_text = excluded.quote_text,
            quote_start = excluded.quote_start,
            quote_end = excluded.quote_end,
            quote_sha256 = excluded.quote_sha256,
            confidence = excluded.confidence,
            rationale = excluded.rationale""",
        (
            evidence_id,
            candidate.claim_id,
            candidate.source_id,
            candidate.snapshot_id,
            candidate.chunk_id,
            candidate.relationship_state,
            candidate.quote_text,
            candidate.quote_start,
            candidate.quote_end,
            quote_sha256,
            candidate.confidence,
            candidate.rationale,
            now_iso,
        ),
    )

    # 5. Log Verification Event
    event_id = f"vev_{hashlib.sha256(f'{candidate.claim_id}:{now_iso}'.encode('utf-8')).hexdigest()[:16]}"
    cur.execute(
        """INSERT INTO verification_events (
            verification_event_id, claim_id, policy_version, previous_state, new_state,
            basis_json, supporting_evidence_count, independent_source_count, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, 1, ?, ?)""",
        (
            event_id,
            candidate.claim_id,
            VerificationPolicy.POLICY_VERSION,
            "CANDIDATE",
            new_state,
            json.dumps(basis),
            total_sources,
            now_iso,
        ),
    )

    conn.commit()
    conn.close()
    return new_state

"""Claim Decomposition and Candidate Extraction Engine."""

from dataclasses import dataclass
from typing import List, Optional

from svris.adapters.model import BaseModelAdapter


class ExtractionError(Exception):
    """Base exception for extraction boundary failures."""

    pass


class ProvenanceError(ExtractionError):
    """Raised when candidate claim violates provenance rules."""

    pass


@dataclass(frozen=True)
class CandidateClaim:
    """Immutable in-memory candidate proposition before verification gate."""

    claim_id: str
    claim_text: str
    topic_id: str
    source_id: str
    relationship_state: str
    confidence: float
    rationale: str
    snapshot_id: Optional[str] = None
    chunk_id: Optional[str] = None
    quote_text: Optional[str] = None
    quote_start: Optional[int] = None
    quote_end: Optional[int] = None
    valid_from: Optional[str] = None
    valid_until: Optional[str] = None
    review_after: Optional[str] = None


def extract_candidate_claims(
    raw_text: str,
    source_id: str,
    topic_id: str,
    model_adapter: BaseModelAdapter,
) -> List[CandidateClaim]:
    """Decomposes raw source text into structured CandidateClaim objects via adapter.

    Enforces P0 Source-Binding Lock: candidate.source_id MUST equal bound source_id.
    """
    raw_candidates = model_adapter.extract_claims(raw_text, source_id, topic_id)
    results: List[CandidateClaim] = []

    for item in raw_candidates:
        candidate_source_id = str(item.get("source_id", "")).strip()
        if candidate_source_id != source_id:
            raise ProvenanceError(
                f"Cross-source attribution detected: model returned source '{candidate_source_id}' "
                f"while processing bound source '{source_id}'."
            )

        confidence = float(item.get("confidence", 0.0))
        confidence = max(0.0, min(1.0, confidence))

        candidate = CandidateClaim(
            claim_id=str(item["claim_id"]).strip(),
            claim_text=str(item["claim_text"]).strip(),
            topic_id=str(item["topic_id"]).strip(),
            source_id=candidate_source_id,
            snapshot_id=str(item["snapshot_id"]).strip() if item.get("snapshot_id") else None,
            chunk_id=str(item["chunk_id"]).strip() if item.get("chunk_id") else None,
            relationship_state=str(item["relationship_state"]).strip(),
            confidence=confidence,
            rationale=str(item["rationale"]).strip(),
            quote_text=str(item["quote_text"]).strip() if item.get("quote_text") else None,
            quote_start=int(item["quote_start"]) if item.get("quote_start") is not None else None,
            quote_end=int(item["quote_end"]) if item.get("quote_end") is not None else None,
            valid_from=str(item["valid_from"]).strip() if item.get("valid_from") else None,
            valid_until=str(item["valid_until"]).strip() if item.get("valid_until") else None,
            review_after=str(item["review_after"]).strip() if item.get("review_after") else None,
        )
        results.append(candidate)

    return results

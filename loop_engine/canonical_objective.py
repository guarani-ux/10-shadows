import hashlib
import json
import uuid
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field


class EvidenceReference(BaseModel):
    """A verified factual source or evidence reference with provenance."""

    evidence_id: str = Field(min_length=2)
    source_description: str = Field(min_length=5)
    confidence: Literal["VERIFIED_FACT", "DOCUMENTED_METRIC", "DIRECT_QUOTE"] = "VERIFIED_FACT"
    reference_url_or_doc: Optional[str] = None
    extracted_by_shadow_id: Optional[int] = None


class UnknownReference(BaseModel):
    """An explicit unknown, assumption, or required approval gate."""

    unknown_id: str = Field(min_length=2)
    description: str = Field(min_length=5)
    classification: Literal[
        "CREATIVE_PROPOSAL",
        "ASSUMPTION_REQUIRING_APPROVAL",
        "UNRESOLVED_FACTUAL_CONFLICT",
        "UNRESOLVED_UNKNOWN",
    ] = "ASSUMPTION_REQUIRING_APPROVAL"
    mitigation_or_approval_decision: Optional[str] = None
    requires_human_gate: bool = False


class ConstraintSet(BaseModel):
    """Execution, production, and linguistic invariants."""

    target_duration_seconds: int = Field(default=60, ge=5, le=7200)
    target_pacing_wpm: float = Field(default=150.0, ge=50.0, le=250.0)
    primary_platform: str = "YouTube"
    camera_package: List[str] = Field(default_factory=lambda: ["Sony FX3 (24mm, 35mm)", "Sony A7IV (85mm f/1.8)"])
    lighting_style: str = "2:1 Corporate Natural Key with 5600K Rim"
    audio_spec: str = "Broadcast Boom + Lavalier (-14 LUFS, -1 dBTP ceiling)"
    brand_safety_banned_words: List[str] = Field(
        default_factory=lambda: ["delve", "tapestry", "seamlessly", "testament", "revolutionize"]
    )
    banned_linguistic_patterns: List[str] = Field(default_factory=lambda: ["—"])
    time_budget_seconds: float = Field(default=60.0, ge=1.0)
    max_step_retries: int = Field(default=3, ge=1, le=5)


class CanonicalObjective(BaseModel):
    """
    Universal, versioned canonical input contract for 10 Shadows execution routes.
    Establishes a single canonical understanding of objective, evidence, unknowns,
    invariants, authority level, and success conditions.
    """

    objective_id: str = Field(min_length=3)
    objective_type: Literal[
        "media_production",
        "av_production",
        "self_healing",
        "relational_memory",
        "dag_decomposition",
        "general_execution",
    ] = "media_production"
    description: str = Field(min_length=5)
    desired_outcome: str = Field(min_length=5)

    # Authority & Governance
    authority_level: Literal["AUTOMATIC", "HUMAN_REQUIRED", "GOVERNOR_LOCKED"] = "AUTOMATIC"
    allowed_capabilities: List[str] = Field(default_factory=list)
    forbidden_actions: List[str] = Field(
        default_factory=lambda: ["direct_production_write", "unverified_external_publish", "destructive_file_delete"]
    )

    # Epistemic Grounding
    verified_evidence: List[EvidenceReference] = Field(default_factory=list)
    explicit_unknowns: List[UnknownReference] = Field(default_factory=list)

    # Constraints & Scope
    constraints: ConstraintSet = Field(default_factory=ConstraintSet)
    target_audience: str = "General Audience"
    intended_audience_action: str = "Engage with content"
    core_message: str = "Clear and verifiable message"
    narrative_arc_type: str = "Context -> Evidence -> Impact"

    # Lineage & Provenance
    source_documents: List[str] = Field(default_factory=list)
    provenance_metadata: Dict[str, Any] = Field(default_factory=dict)
    schema_version: str = "1.0.0"

    def compute_canonical_hash(self) -> str:
        """
        Computes deterministic SHA-256 digest of canonical objective content.
        Guarantees zero timestamp entropy.
        """
        payload = self.model_dump(mode="json")
        serialized = json.dumps(payload, sort_keys=True)
        return hashlib.sha256(serialized.encode("utf-8")).hexdigest()

    def compute_objective_hash(self) -> str:
        """Alias for compute_canonical_hash."""
        return self.compute_canonical_hash()

    @classmethod
    def normalize_raw_input(cls, raw: Any) -> "CanonicalObjective":
        """Normalizes arbitrary raw input (str, dict, or object) into a valid CanonicalObjective."""
        if isinstance(raw, cls):
            return raw
        if isinstance(raw, dict):
            raw_copy = dict(raw)
            if "objective_id" not in raw_copy:
                raw_copy["objective_id"] = f"obj_{uuid.uuid4().hex[:8]}"
            if "description" not in raw_copy:
                raw_copy["description"] = (
                    raw_copy.get("project_title") or raw_copy.get("goal") or "Standard Execution Objective"
                )
            if "desired_outcome" not in raw_copy:
                raw_copy["desired_outcome"] = (
                    raw_copy.get("organizational_goal") or raw_copy.get("description") or "Fulfill bounded objective"
                )
            return cls.model_validate(raw_copy)

        raw_str = str(raw)
        return cls(
            objective_id=f"obj_{uuid.uuid4().hex[:8]}",
            objective_type="general_execution",
            description=raw_str,
            desired_outcome=f"Execute and fulfill: {raw_str}",
        )

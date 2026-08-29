from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field, field_validator


class EvidenceItem(BaseModel):
    """A verified factual source or reference."""

    evidence_id: str
    source_description: str
    confidence: Literal["VERIFIED_FACT", "DOCUMENTED_METRIC", "DIRECT_QUOTE"] = "VERIFIED_FACT"
    reference_url_or_doc: Optional[str] = None


class UnknownItem(BaseModel):
    """An explicit unknown or assumption requiring approval."""

    unknown_id: str
    description: str
    classification: Literal["CREATIVE_PROPOSAL", "ASSUMPTION_REQUIRING_APPROVAL", "UNRESOLVED_UNKNOWN"]
    mitigation_or_approval_decision: str


class ProductionConstraints(BaseModel):
    """Physical production and equipment constraints."""

    target_duration_seconds: int = Field(default=75, ge=10, le=3600)
    target_pacing_wpm: float = Field(default=150.0, ge=80.0, le=220.0)
    primary_platform: Literal["YouTube", "LinkedIn", "Broadcast", "Internal / All-Hands"] = "YouTube"
    camera_package: List[str] = Field(default_factory=lambda: ["Sony FX3 (24mm, 35mm)", "Sony A7IV (85mm f/1.8)"])
    lighting_style: str = "2:1 Corporate Natural Key with 5600K Rim"
    audio_spec: str = "Broadcast Boom + Lavalier (-14 LUFS, -1 dBTP ceiling)"
    brand_safety_banned_words: List[str] = Field(
        default_factory=lambda: ["delve", "tapestry", "seamlessly", "testament", "revolutionize"]
    )


class CanonicalMediaBrief(BaseModel):
    """
    Slice 1: Strict Canonical Input Contract for Media Production.

    Distinguishes verified facts, assumptions requiring approval,
    creative proposals, and explicit unknowns. Never silently invents data.
    """

    project_id: str = Field(min_length=3)
    project_title: str = Field(min_length=3)

    # 1. Strategic Goals & Persona
    organizational_goal: str = Field(min_length=10)
    target_audience: str = Field(min_length=10)
    intended_audience_action: str = Field(
        min_length=10, description="The specific CTA / next step the viewer must take"
    )
    core_message: str = Field(min_length=10, description="The single takeaway the viewer must remember")
    narrative_arc_type: str = Field(min_length=5)

    # 2. Evidence vs Unknowns
    verified_evidence: List[EvidenceItem] = Field(default_factory=list)
    explicit_unknowns: List[UnknownItem] = Field(default_factory=list)

    # 3. Production Scope
    production_constraints: ProductionConstraints = Field(default_factory=ProductionConstraints)
    requested_cutdowns: List[str] = Field(default_factory=lambda: ["YouTube Shorts (15-30s)"])

from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field, field_validator

from loop_engine.herald.cinematography import CinematographyValidator
from loop_engine.herald.input_contract import EvidenceItem, ProductionConstraints, UnknownItem
from loop_engine.herald.linguistics import AntiAILinguisticGuard


class AVTableRow(BaseModel):
    """A single row in the Master 3-Column AV Script Table."""

    row_index: int = Field(ge=1)
    scene_name: str = Field(min_length=2)
    time_window: str = Field(description="e.g. '0:00 - 0:15'")
    start_seconds: float = Field(ge=0.0)
    end_seconds: float = Field(ge=0.0)

    spoken_audio: str = Field(min_length=5, description="Spoken voiceover, dialogue, music cues, and sound effects")
    spoken_words_count: int = Field(ge=0)
    pacing_wpm: float = Field(ge=0.0)

    video_direction: str = Field(
        min_length=10, description="Framing, camera move, lighting ratio, focal length, on-screen text"
    )

    grounded_evidence_ids: List[str] = Field(
        default_factory=list, description="IDs of verified evidence supporting this scene"
    )
    associated_unknown_ids: List[str] = Field(
        default_factory=list, description="IDs of explicit assumptions/unknowns in this scene"
    )

    @field_validator("end_seconds")
    @classmethod
    def validate_timecodes(cls, v: float, info: Any) -> float:
        start = info.data.get("start_seconds", 0.0)
        if v <= start:
            raise ValueError(f"end_seconds ({v}) must be strictly greater than start_seconds ({start})")
        return v

    @field_validator("spoken_audio")
    @classmethod
    def validate_spoken_audio(cls, v: str) -> str:
        valid, violations = AntiAILinguisticGuard.validate_text(v)
        if not valid:
            raise ValueError(f"Linguistic Violation in Audio: {'; '.join(violations)}")
        return v

    @field_validator("video_direction")
    @classmethod
    def validate_video_direction(cls, v: str) -> str:
        valid, violations = CinematographyValidator.validate_visual_direction(v)
        if not valid:
            raise ValueError(f"Cinematography Violation in Video: {'; '.join(violations)}")
        return v


class ValidatedCutDownScript(BaseModel):
    """Structured, validated modular cut-down script representation."""

    cutdown_id: str
    short_title: str
    target_platform: Literal["YouTube Shorts", "Instagram Reels", "TikTok", "LinkedIn Video"]
    derived_from_row_indices: List[int] = Field(min_length=1)
    target_duration_seconds: int = Field(ge=10, le=60)
    actual_duration_seconds: float
    standalone_hook: str = Field(min_length=10)
    spoken_audio: str = Field(min_length=10)
    spoken_words_count: int
    pacing_wpm: float
    vertical_video_direction: str = Field(
        min_length=10, description="9:16 vertical framing, camera move, safe-zone graphics"
    )
    platform_cta: str = Field(min_length=5)
    strategic_purpose: str


class StrategicIntent(BaseModel):
    """Section 1: Organizational Goal Alignment & Strategic Persona."""

    project_title: str = Field(min_length=3)
    organizational_goal: str = Field(min_length=10)
    target_audience_persona: str = Field(min_length=10)
    intended_audience_action: str = Field(min_length=10)
    core_brand_alignment: str = Field(min_length=10)
    narrative_arc_type: str = Field(min_length=5)


class TechnicalScope(BaseModel):
    """Section 2: Production Constraints & Technical Scope."""

    target_runtime_seconds: int = Field(ge=10, le=3600)
    target_runtime_formatted: str
    target_pacing_wpm: float = Field(ge=10.0, le=300.0)
    total_spoken_words: int
    actual_overall_wpm: float
    production_constraints: ProductionConstraints
    modular_cutdowns: List[ValidatedCutDownScript] = Field(default_factory=list)


class MasterAVScriptBlueprint(BaseModel):
    """Structured 3-section AV script document with evidence-preservation fields."""

    script_id: str
    strategic_intent: StrategicIntent
    technical_scope: TechnicalScope
    verified_evidence: List[EvidenceItem] = Field(default_factory=list)
    explicit_unknowns: List[UnknownItem] = Field(default_factory=list)
    av_table: List[AVTableRow] = Field(min_length=1)

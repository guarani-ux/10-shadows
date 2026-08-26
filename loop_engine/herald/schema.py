from typing import Any, Dict, List, Literal, Optional
from pydantic import BaseModel, Field, field_validator
from loop_engine.herald.linguistics import AntiAILinguisticGuard
from loop_engine.herald.cinematography import CinematographyValidator


class AVTableRow(BaseModel):
    """A single row in the Master 3-Column AV Script Table."""
    row_index: int = Field(ge=1)
    scene_name: str = Field(min_length=2)
    time_window: str = Field(description="e.g. '0:00 - 0:15'")
    start_seconds: float = Field(ge=0.0)
    end_seconds: float = Field(ge=0.0)
    
    # Column 2: Spoken Human Audio & SFX
    spoken_audio: str = Field(min_length=5, description="Spoken voiceover, dialogue, music cues, and sound effects")
    spoken_words_count: int = Field(ge=0)
    pacing_wpm: float = Field(ge=0.0)

    # Column 3: Cinematographic Video & Visual Directions
    video_direction: str = Field(min_length=10, description="Framing, camera move, lighting ratio, focal length, on-screen text")

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


class ModularCutDown(BaseModel):
    """Section 2: Modular 15-30s Shorts/Reels derivative from the main script."""
    short_title: str
    target_platform: Literal["YouTube Shorts", "Instagram Reels", "TikTok", "LinkedIn Video"]
    time_window: str
    standalone_hook: str
    strategic_purpose: str


class StrategicIntent(BaseModel):
    """Section 1: Organizational Goal Alignment & Strategic Persona."""
    project_title: str = Field(min_length=3)
    organizational_goal: str = Field(min_length=10)
    target_audience_persona: str = Field(min_length=10)
    core_brand_alignment: str = Field(min_length=10)
    narrative_arc_type: str = Field(min_length=5)


class TechnicalScope(BaseModel):
    """Section 2: Production Constraints & Technical Scope."""
    target_runtime_seconds: int = Field(ge=10, le=3600)
    target_runtime_formatted: str
    target_pacing_wpm: float = Field(ge=80.0, le=250.0)
    total_spoken_words: int
    modular_cutdowns: List[ModularCutDown] = Field(default_factory=list)


class MasterAVScriptBlueprint(BaseModel):
    """The complete 3-Section Production-Ready AV Script Document."""
    script_id: str
    strategic_intent: StrategicIntent
    technical_scope: TechnicalScope
    av_table: List[AVTableRow] = Field(min_length=1)

from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field, field_validator


class EpistemicBlindspot(BaseModel):
    """Explicitly surfaced gap or anomaly in the video data."""

    time_window: str
    anomaly_type: Literal["VISUAL_ONLY_GAP", "UNRESOLVED_REFERENCE", "AMBIGUOUS_STRUCTURE", "NO_TRANSCRIPT_AVAILABLE"]
    description: str = Field(min_length=5)
    gap_duration_seconds: Optional[float] = None


class GroundedScene(BaseModel):
    """An organic video segment with mandatory verbatim transcript grounding."""

    scene_index: int = Field(ge=1)
    time_window: str
    start_seconds: float
    end_seconds: float
    duration_seconds: float
    words_count: int
    pacing_wpm: float
    summary: str = Field(min_length=5)
    verbatim_anchor_quote: str = Field(min_length=3)

    @field_validator("end_seconds")
    @classmethod
    def validate_time_order(cls, v: float, info: Any) -> float:
        start = info.data.get("start_seconds", 0.0)
        if v < start:
            raise ValueError(f"end_seconds ({v}) cannot be less than start_seconds ({start})")
        return v


class VideoDeconstructionBlueprint(BaseModel):
    """The master verifiable deconstruction schema for any video format."""

    video_id: str
    title: str
    channel: str
    duration_formatted: str
    total_words: int
    overall_wpm: float
    core_subject: str = Field(min_length=5)
    scenes: List[GroundedScene] = Field(min_length=1)
    known_blindspots: List[EpistemicBlindspot] = Field(default_factory=list)

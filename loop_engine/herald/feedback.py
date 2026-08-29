from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field


class ScriptViolation(BaseModel):
    """
    Machine-actionable violation representation for feedback-driven adaptive repair.
    """

    violation_code: str = Field(
        description="e.g. WORD_COUNT_OVERFLOW, WPM_OVERFLOW, TIME_OVERLAP, MISSING_CTA, BANNED_LANGUAGE"
    )
    affected_section_index: Optional[int] = Field(
        default=None, description="1-indexed row index if localized to a scene"
    )
    affected_section_name: Optional[str] = None
    affected_cutdown_id: Optional[str] = None
    actual_value: Any
    allowed_value: Any
    severity: Literal["FATAL_REJECT", "REPAIRABLE_OVERFLOW", "LINGUISTIC_ERROR"] = "REPAIRABLE_OVERFLOW"
    repair_strategy: str = Field(
        description="Explicit programmatic instructions for the generator on how to compress or repair"
    )
    evidence_or_unknown_id: Optional[str] = None
    description: str


class ValidationFeedback(BaseModel):
    """
    Structured feedback package passed from Governor/Validator to Generator on retry.
    """

    passed: bool
    attempt_index: int = 1
    candidate_hash: str = ""
    violations: List[ScriptViolation] = Field(default_factory=list)
    suggested_word_budget_adjustments: Dict[int, int] = Field(
        default_factory=dict, description="row_index -> max_allowed_words"
    )
    applied_repair_strategies: List[str] = Field(default_factory=list)

from typing import Any, Dict, List, Optional, Tuple

from loop_engine.herald.cinematography import CinematographyValidator
from loop_engine.herald.feedback import ScriptViolation, ValidationFeedback
from loop_engine.herald.linguistics import AntiAILinguisticGuard
from loop_engine.herald.schema import AVTableRow, MasterAVScriptBlueprint, ValidatedCutDownScript


class DeterministicScriptValidator:
    """
    Multi-Layer Deterministic Validation Suite emitting structured machine-actionable violations.
    """

    @classmethod
    def validate_row_pacing(cls, row: AVTableRow, target_wpm: float = 150.0) -> Tuple[bool, Optional[ScriptViolation]]:
        duration = row.end_seconds - row.start_seconds
        if duration <= 0:
            return False, ScriptViolation(
                violation_code="INVALID_DURATION",
                affected_section_index=row.row_index,
                affected_section_name=row.scene_name,
                actual_value=duration,
                allowed_value="> 0.0",
                severity="FATAL_REJECT",
                repair_strategy="Recalculate positive timecode boundaries.",
                description=f"Row {row.row_index}: Invalid duration {duration}s.",
            )

        allowed_words = duration * (target_wpm / 60.0)
        max_allowed_words = int(allowed_words * 1.15) + 1
        actual_words = row.spoken_words_count

        if actual_words > max_allowed_words:
            return False, ScriptViolation(
                violation_code="WORD_COUNT_OVERFLOW",
                affected_section_index=row.row_index,
                affected_section_name=row.scene_name,
                actual_value=actual_words,
                allowed_value=max_allowed_words,
                severity="REPAIRABLE_OVERFLOW",
                repair_strategy=f"Compress spoken dialogue in Row {row.row_index} from {actual_words} down to <= {max_allowed_words} words.",
                description=(
                    f"Row {row.row_index} ('{row.scene_name}'): Spoken word count ({actual_words} words) "
                    f"exceeds binding target pacing ceiling ({max_allowed_words} words max for {duration:.1f}s at {target_wpm} WPM)."
                ),
            )

        min_allowed_words = max(int(allowed_words * 0.50), 2)
        if actual_words < min_allowed_words and duration >= 5.0:
            return False, ScriptViolation(
                violation_code="PACING_DRAGGING",
                affected_section_index=row.row_index,
                affected_section_name=row.scene_name,
                actual_value=actual_words,
                allowed_value=min_allowed_words,
                severity="REPAIRABLE_OVERFLOW",
                repair_strategy=f"Expand spoken dialogue in Row {row.row_index} to meet minimum conversational pace ({min_allowed_words} words min).",
                description=(
                    f"Row {row.row_index} ('{row.scene_name}'): Spoken word count ({actual_words} words) "
                    f"is dragging significantly below target pacing ({min_allowed_words} words minimum for {duration:.1f}s at {target_wpm} WPM)."
                ),
            )

        return True, None

    @classmethod
    def validate_cutdown(
        cls, cutdown: ValidatedCutDownScript, target_wpm: float = 150.0
    ) -> Tuple[bool, List[ScriptViolation]]:
        violations: List[ScriptViolation] = []
        duration = cutdown.actual_duration_seconds
        if duration < 10.0 or duration > 60.0:
            violations.append(
                ScriptViolation(
                    violation_code="CUTDOWN_DURATION_OUT_OF_BOUNDS",
                    affected_cutdown_id=cutdown.cutdown_id,
                    actual_value=duration,
                    allowed_value="10.0 - 60.0s",
                    severity="FATAL_REJECT",
                    repair_strategy="Rescale cutdown duration to 15-30s vertical window.",
                    description=f"CutDown '{cutdown.short_title}': Duration {duration:.1f}s outside vertical Short/Reel bounds (10s-60s).",
                )
            )

        allowed_words = duration * (target_wpm / 60.0)
        max_words = int(allowed_words * 1.20) + 2
        if cutdown.spoken_words_count > max_words:
            violations.append(
                ScriptViolation(
                    violation_code="CUTDOWN_WORD_COUNT_OVERFLOW",
                    affected_cutdown_id=cutdown.cutdown_id,
                    actual_value=cutdown.spoken_words_count,
                    allowed_value=max_words,
                    severity="REPAIRABLE_OVERFLOW",
                    repair_strategy=f"Compress cutdown dialogue from {cutdown.spoken_words_count} to <= {max_words} words.",
                    description=f"CutDown '{cutdown.short_title}': Spoken words ({cutdown.spoken_words_count}) exceeds ceiling ({max_words} max for {duration:.1f}s).",
                )
            )

        l_ok, l_errs = AntiAILinguisticGuard.validate_text(cutdown.spoken_audio)
        if not l_ok:
            for err in l_errs:
                violations.append(
                    ScriptViolation(
                        violation_code="CUTDOWN_BANNED_LANGUAGE",
                        affected_cutdown_id=cutdown.cutdown_id,
                        actual_value=cutdown.spoken_audio[:30],
                        allowed_value="Clean spoken English",
                        severity="LINGUISTIC_ERROR",
                        repair_strategy="Remove em-dashes and AI buzzwords from cutdown dialogue.",
                        description=f"CutDown '{cutdown.short_title}' Audio: {err}",
                    )
                )

        return len(violations) == 0, violations

    @classmethod
    def audit_blueprint_structured(cls, blueprint: MasterAVScriptBlueprint) -> ValidationFeedback:
        """
        Executes full deterministic audit and returns structured machine-actionable ValidationFeedback.
        """
        violations: List[ScriptViolation] = []
        word_adjustments: Dict[int, int] = {}
        target_wpm = blueprint.technical_scope.target_pacing_wpm
        target_runtime = blueprint.technical_scope.target_runtime_seconds

        # 1. Total duration check
        actual_runtime = blueprint.av_table[-1].end_seconds if blueprint.av_table else 0.0
        if abs(actual_runtime - target_runtime) > (target_runtime * 0.15) + 2:
            violations.append(
                ScriptViolation(
                    violation_code="RUNTIME_MISMATCH",
                    actual_value=actual_runtime,
                    allowed_value=target_runtime,
                    severity="REPAIRABLE_OVERFLOW",
                    repair_strategy=f"Rescale row timecodes so total script duration equals {target_runtime}s.",
                    description=f"Duration Mismatch: Total script runtime ({actual_runtime:.1f}s) diverges from target scope ({target_runtime}s).",
                )
            )

        # 2. Row level audits
        prev_end = 0.0
        known_evidence_ids = {e.evidence_id for e in blueprint.verified_evidence}
        known_unknown_ids = {u.unknown_id for u in blueprint.explicit_unknowns}

        for idx, row in enumerate(blueprint.av_table, 1):
            dur = row.end_seconds - row.start_seconds
            max_allowed = int(dur * (target_wpm / 60.0) * 1.15) + 1
            word_adjustments[row.row_index] = max_allowed

            if row.start_seconds < prev_end - 0.01:
                violations.append(
                    ScriptViolation(
                        violation_code="TIMECODE_OVERLAP",
                        affected_section_index=row.row_index,
                        affected_section_name=row.scene_name,
                        actual_value=row.start_seconds,
                        allowed_value=f">= {prev_end}",
                        severity="FATAL_REJECT",
                        repair_strategy=f"Shift start timecode of Row {row.row_index} to {prev_end}s.",
                        description=f"Row {row.row_index}: Timecode overlap detected (start {row.start_seconds}s < prev end {prev_end}s).",
                    )
                )
            prev_end = row.end_seconds

            # Pacing
            p_ok, p_violation = cls.validate_row_pacing(row, target_wpm)
            if not p_ok and p_violation:
                violations.append(p_violation)

            # Linguistic
            l_ok, l_errs = AntiAILinguisticGuard.validate_text(row.spoken_audio)
            if not l_ok:
                for e in l_errs:
                    violations.append(
                        ScriptViolation(
                            violation_code="BANNED_LANGUAGE",
                            affected_section_index=row.row_index,
                            affected_section_name=row.scene_name,
                            actual_value="AI markers in audio",
                            allowed_value="Clean human speech",
                            severity="LINGUISTIC_ERROR",
                            repair_strategy=f"Purge em-dashes and AI buzzwords in Row {row.row_index}.",
                            description=f"Row {row.row_index} Audio: {e}",
                        )
                    )

            # Cinematography
            c_ok, c_errs = CinematographyValidator.validate_visual_direction(row.video_direction)
            if not c_ok:
                for e in c_errs:
                    violations.append(
                        ScriptViolation(
                            violation_code="INVALID_CINEMATOGRAPHY",
                            affected_section_index=row.row_index,
                            affected_section_name=row.scene_name,
                            actual_value="Invalid video direction",
                            allowed_value="Explicit camera focal lengths and lighting",
                            severity="REPAIRABLE_OVERFLOW",
                            repair_strategy=f"Insert valid focal length (e.g. 24mm/85mm) and lighting ratio into Row {row.row_index}.",
                            description=f"Row {row.row_index} Video: {e}",
                        )
                    )

        # 3. CTA validation
        last_row = blueprint.av_table[-1] if blueprint.av_table else None
        if not last_row or not any(
            cta_word in (last_row.spoken_audio.lower() + last_row.scene_name.lower())
            for cta_word in [
                "cta",
                "call to action",
                "link",
                "visit",
                "join",
                "apply",
                "contact",
                "sign up",
                "register",
            ]
        ):
            violations.append(
                ScriptViolation(
                    violation_code="MISSING_CTA",
                    affected_section_index=len(blueprint.av_table),
                    actual_value="No action verb in finale",
                    allowed_value="Clear Call to Action",
                    severity="REPAIRABLE_OVERFLOW",
                    repair_strategy="Append explicit CTA linking to intended audience action in the finale scene.",
                    description="Structure Violation: Final scene must provide a clear Call to Action (CTA) aligned with intended audience action.",
                )
            )

        # 4. Cutdown validation
        for cd in blueprint.technical_scope.modular_cutdowns:
            cd_ok, cd_violations = cls.validate_cutdown(cd, target_wpm)
            if not cd_ok:
                violations.extend(cd_violations)

        return ValidationFeedback(
            passed=len(violations) == 0,
            violations=violations,
            suggested_word_budget_adjustments=word_adjustments,
        )

    @classmethod
    def validate_blueprint(cls, blueprint: MasterAVScriptBlueprint) -> Tuple[bool, List[str]]:
        """Legacy string tuple interface calling the structured audit engine."""
        feedback = cls.audit_blueprint_structured(blueprint)
        str_violations = [v.description for v in feedback.violations]
        return feedback.passed, str_violations

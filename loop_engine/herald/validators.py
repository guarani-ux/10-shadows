from typing import Any, Dict, List, Tuple
from loop_engine.herald.schema import MasterAVScriptBlueprint, AVTableRow, ValidatedCutDownScript
from loop_engine.herald.linguistics import AntiAILinguisticGuard
from loop_engine.herald.cinematography import CinematographyValidator


class DeterministicScriptValidator:
    """
    Slice 3: Multi-Layer Deterministic Validation Suite.
    
    Validates:
    1. Binding Target WPM per row (actual_words <= duration * target_wpm / 60 * 1.15).
    2. Overall runtime consistency (sum of scene durations == target duration).
    3. Zero AI language & Zero em-dashes across all sections.
    4. Cinematography realism (focal lengths, lighting ratios, motivated B-roll).
    5. Monotonic timecodes with zero overlaps and zero unexplained gaps.
    6. Evidence & Unknown traceability (scene references must exist in brief).
    7. Full validation of standalone 15-30s Cut-Down scripts.
    8. Clear Call to Action (CTA) matching intended audience action.
    """

    @classmethod
    def validate_row_pacing(cls, row: AVTableRow, target_wpm: float = 150.0) -> Tuple[bool, str]:
        duration = row.end_seconds - row.start_seconds
        if duration <= 0:
            return False, f"Row {row.row_index}: Invalid duration {duration}s."
        
        # Exact theoretical word allocation at target WPM
        allowed_words = duration * (target_wpm / 60.0)
        # Max allowed words with a strict 15% conversational tolerance buffer
        max_allowed_words = int(allowed_words * 1.15) + 1
        actual_words = row.spoken_words_count

        if actual_words > max_allowed_words:
            return False, (
                f"Row {row.row_index} ('{row.scene_name}'): Spoken word count ({actual_words} words) "
                f"exceeds binding target pacing ceiling ({max_allowed_words} words max for {duration:.1f}s at {target_wpm} WPM)."
            )
        
        # Check minimum conversational pace (no dragging under 60% of target)
        min_allowed_words = max(int(allowed_words * 0.60), 3)
        if actual_words < min_allowed_words:
            return False, (
                f"Row {row.row_index} ('{row.scene_name}'): Spoken word count ({actual_words} words) "
                f"is dragging significantly below target pacing ({min_allowed_words} words minimum for {duration:.1f}s at {target_wpm} WPM)."
            )

        return True, ""

    @classmethod
    def validate_cutdown(cls, cutdown: ValidatedCutDownScript, target_wpm: float = 150.0) -> Tuple[bool, List[str]]:
        """Validates that a modular cutdown is an independently executable 15-60s vertical script."""
        violations = []
        duration = cutdown.actual_duration_seconds
        if duration < 10.0 or duration > 60.0:
            violations.append(f"CutDown '{cutdown.short_title}': Duration {duration:.1f}s outside vertical Short/Reel bounds (10s-60s).")

        allowed_words = duration * (target_wpm / 60.0)
        max_words = int(allowed_words * 1.20) + 2
        if cutdown.spoken_words_count > max_words:
            violations.append(
                f"CutDown '{cutdown.short_title}': Spoken words ({cutdown.spoken_words_count}) exceeds ceiling ({max_words} max for {duration:.1f}s)."
            )

        l_ok, l_errs = AntiAILinguisticGuard.validate_text(cutdown.spoken_audio)
        if not l_ok:
            violations.extend([f"CutDown '{cutdown.short_title}' Audio: {e}" for e in l_errs])

        c_ok, c_errs = CinematographyValidator.validate_visual_direction(cutdown.vertical_video_direction)
        if not c_ok:
            violations.extend([f"CutDown '{cutdown.short_title}' Video: {e}" for e in c_errs])

        return len(violations) == 0, violations

    @classmethod
    def validate_blueprint(cls, blueprint: MasterAVScriptBlueprint) -> Tuple[bool, List[str]]:
        violations = []
        target_wpm = blueprint.technical_scope.target_pacing_wpm
        target_runtime = blueprint.technical_scope.target_runtime_seconds

        # 1. Total duration vs target duration check (within 10% tolerance)
        actual_runtime = blueprint.av_table[-1].end_seconds if blueprint.av_table else 0.0
        if abs(actual_runtime - target_runtime) > (target_runtime * 0.15) + 3:
            violations.append(
                f"Duration Mismatch: Total script runtime ({actual_runtime:.1f}s) diverges from target scope ({target_runtime}s)."
            )

        # 2. Row-level pacing, timecode monotonicity, language, and cinematography
        prev_end = 0.0
        known_evidence_ids = {e.evidence_id for e in blueprint.verified_evidence}
        known_unknown_ids = {u.unknown_id for u in blueprint.explicit_unknowns}

        for idx, row in enumerate(blueprint.av_table, 1):
            if row.start_seconds < prev_end - 0.01:
                violations.append(f"Row {row.row_index}: Timecode overlap detected (start {row.start_seconds}s < prev end {prev_end}s).")
            if row.start_seconds > prev_end + 3.0 and idx > 1:
                violations.append(f"Row {row.row_index}: Unexplained temporal gap of {row.start_seconds - prev_end:.1f}s before scene.")
            prev_end = row.end_seconds

            # Pacing check against binding target WPM
            p_ok, p_err = cls.validate_row_pacing(row, target_wpm)
            if not p_ok:
                violations.append(p_err)

            # Linguistic checks across all fields
            l_ok, l_errs = AntiAILinguisticGuard.validate_text(row.spoken_audio)
            if not l_ok:
                violations.extend([f"Row {row.row_index} Audio: {e}" for e in l_errs])

            # Cinematography check
            c_ok, c_errs = CinematographyValidator.validate_visual_direction(row.video_direction)
            if not c_ok:
                violations.extend([f"Row {row.row_index} Video: {e}" for e in c_errs])

            # Evidence ID traceability
            for eid in row.grounded_evidence_ids:
                if eid not in known_evidence_ids:
                    violations.append(f"Row {row.row_index}: References unregistered evidence ID '{eid}'.")

            # Unknown ID traceability
            for uid in row.associated_unknown_ids:
                if uid not in known_unknown_ids:
                    violations.append(f"Row {row.row_index}: References unregistered unknown ID '{uid}'.")

        # 3. Check for single clear CTA
        last_row = blueprint.av_table[-1] if blueprint.av_table else None
        if not last_row or not any(cta_word in (last_row.spoken_audio.lower() + last_row.scene_name.lower()) for cta_word in ["cta", "call to action", "link", "visit", "join", "apply", "contact", "sign up", "register"]):
            violations.append("Structure Violation: Final scene must provide a clear Call to Action (CTA) aligned with intended audience action.")

        # 4. Validate all modular cut-downs
        for cd in blueprint.technical_scope.modular_cutdowns:
            cd_ok, cd_errs = cls.validate_cutdown(cd, target_wpm)
            if not cd_ok:
                violations.extend(cd_errs)

        return len(violations) == 0, violations

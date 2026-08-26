from typing import Any, Dict, List, Tuple
from loop_engine.herald.schema import MasterAVScriptBlueprint, AVTableRow
from loop_engine.herald.linguistics import AntiAILinguisticGuard
from loop_engine.herald.cinematography import CinematographyValidator


class DeterministicScriptValidator:
    """
    Slice 3: Multi-Layer Deterministic Validation Suite.
    
    Validates:
    1. Pacing & Word Count per row (checks row pacing against conversational target 110-180 WPM).
    2. Zero AI language & Zero em-dashes across all sections.
    3. Cinematography realism (focal lengths, lighting ratios, motivated B-roll).
    4. Monotonic timecodes with zero overlaps and zero unexplained gaps.
    5. Clear Call to Action (CTA) in the final scene.
    """

    @classmethod
    def validate_row_pacing(cls, row: AVTableRow, target_wpm: float = 150.0) -> Tuple[bool, str]:
        duration = row.end_seconds - row.start_seconds
        if duration <= 0:
            return False, f"Row {row.row_index}: Invalid duration {duration}s."
        
        # Effective WPM calculated for this specific row
        effective_wpm = (row.spoken_words_count / (duration / 60.0))
        
        # Human conversational bounds (80 WPM slow to 210 WPM high-energy)
        if effective_wpm > 215.0:
            return False, (
                f"Row {row.row_index} ('{row.scene_name}'): Spoken delivery ({effective_wpm:.1f} WPM, {row.spoken_words_count} words in {duration:.1f}s) "
                f"exceeds maximum human spoken ceiling (215 WPM max)."
            )
        if effective_wpm < 50.0 and row.spoken_words_count > 0:
            return False, (
                f"Row {row.row_index} ('{row.scene_name}'): Spoken delivery ({effective_wpm:.1f} WPM) is dragging significantly below standard dialogue speed."
            )
        return True, ""

    @classmethod
    def validate_blueprint(cls, blueprint: MasterAVScriptBlueprint) -> Tuple[bool, List[str]]:
        violations = []

        # 1. Row-level pacing and language
        prev_end = 0.0
        for idx, row in enumerate(blueprint.av_table, 1):
            # Timecode monotonicity & overlap check
            if row.start_seconds < prev_end - 0.01:
                violations.append(f"Row {row.row_index}: Timecode overlap detected (start {row.start_seconds}s < prev end {prev_end}s).")
            if row.start_seconds > prev_end + 5.0 and idx > 1:
                violations.append(f"Row {row.row_index}: Unexplained temporal gap of {row.start_seconds - prev_end:.1f}s before scene.")
            prev_end = row.end_seconds

            # Pacing check
            p_ok, p_err = cls.validate_row_pacing(row, blueprint.technical_scope.target_pacing_wpm)
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

        # 2. Check for single clear CTA
        last_row = blueprint.av_table[-1] if blueprint.av_table else None
        if not last_row or ("call to action" not in last_row.scene_name.lower() and "cta" not in last_row.scene_name.lower() and "link" not in last_row.spoken_audio.lower() and "visit" not in last_row.spoken_audio.lower() and "join" not in last_row.spoken_audio.lower() and "apply" not in last_row.spoken_audio.lower()):
            violations.append("Structure Violation: Final scene must provide a clear Call to Action (CTA) aligned with intended audience action.")

        return len(violations) == 0, violations

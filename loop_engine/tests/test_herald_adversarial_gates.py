import pytest
from pydantic import ValidationError
from loop_engine.herald.input_contract import CanonicalMediaBrief, EvidenceItem, UnknownItem, ProductionConstraints
from loop_engine.herald.generator import IntelligentAVScriptGenerator
from loop_engine.herald.validators import DeterministicScriptValidator
from loop_engine.herald.schema import MasterAVScriptBlueprint, AVTableRow
from loop_engine.herald.linguistics import AntiAILinguisticGuard
from loop_engine.herald.cinematography import CinematographyValidator


def test_adversarial_pacing_ceiling_rejection():
    """Validates that a scene with too many words for its duration is rejected."""
    # Split into 2 short sentences to satisfy breath unit while exceeding word ceiling for 10s
    row = AVTableRow(
        row_index=1,
        scene_name="Scene 1: Rapid Dialogue",
        time_window="0:00 - 0:10",
        start_seconds=0.0,
        end_seconds=10.0,
        spoken_audio="We have so much to talk about today. This voiceover contains too many words to be spoken cleanly in ten seconds.",
        spoken_words_count=21,
        pacing_wpm=126.0,
        video_direction="Wide Shot (24mm, f/4) tracking past workstations.",
    )
    # Target is 80 WPM: for 10s allowed is 13 words (+15% = 15 words). 21 words must fail.
    ok, err = DeterministicScriptValidator.validate_row_pacing(row, target_wpm=80.0)
    assert ok is False
    assert "exceeds binding target pacing ceiling" in err


def test_adversarial_banned_em_dash_rejection():
    """Validates that em-dashes and buzzwords in spoken audio fail Pydantic validation."""
    with pytest.raises(ValidationError) as exc:
        AVTableRow(
            row_index=1,
            scene_name="Scene 1: Stiff Dialogue",
            time_window="0:00 - 0:15",
            start_seconds=0.0,
            end_seconds=15.0,
            spoken_audio="We delve into this tapestry—to revolutionize our operations.",
            spoken_words_count=8,
            pacing_wpm=32.0,
            video_direction="Wide Shot (24mm, f/4) of workstations.",
        )
    assert "Linguistic Violation in Audio" in str(exc.value)


def test_adversarial_unrealistic_cinematography_rejection():
    """Validates that Hollywood tropes or missing shot cues fail Pydantic validation."""
    with pytest.raises(ValidationError) as exc:
        AVTableRow(
            row_index=1,
            scene_name="Scene 1: Impossible Shot",
            time_window="0:00 - 0:15",
            start_seconds=0.0,
            end_seconds=15.0,
            spoken_audio="Welcome to our facility where we build scalable software.",
            spoken_words_count=8,
            pacing_wpm=32.0,
            video_direction="Helicopter drone flying through window with matrix bullet time effect.",
        )
    assert "Cinematography Violation in Video" in str(exc.value)


def test_adversarial_timecode_overlap_rejection():
    """Validates that overlapping timecodes fail global blueprint validation."""
    brief = CanonicalMediaBrief(
        project_id="test_overlap",
        project_title="Timecode Test",
        organizational_goal="Verify timecode validation physics.",
        target_audience="Engineers testing boundaries.",
        intended_audience_action="Review test logs.",
        core_message="Timecodes must be strictly monotonic.",
        narrative_arc_type="Start -> Middle -> End",
        production_constraints=ProductionConstraints(target_duration_seconds=75),
    )
    script = IntelligentAVScriptGenerator.synthesize_from_brief(brief)
    
    # Introduce deliberate overlap
    script.av_table[1].start_seconds = 2.0  # Collides with Scene 1 which ends at 15.0s
    
    ok, violations = DeterministicScriptValidator.validate_blueprint(script)
    assert ok is False
    assert any("Timecode overlap detected" in v for v in violations)


def test_adversarial_missing_cta_rejection():
    """Validates that an AV script missing a Call to Action in the finale fails."""
    brief = CanonicalMediaBrief(
        project_id="test_no_cta",
        project_title="No CTA Test",
        organizational_goal="Verify CTA validation physics.",
        target_audience="Engineers testing boundaries.",
        intended_audience_action="Visit portal.",
        core_message="Scripts require clear call to action.",
        narrative_arc_type="Start -> Middle -> End",
        production_constraints=ProductionConstraints(target_duration_seconds=75),
    )
    script = IntelligentAVScriptGenerator.synthesize_from_brief(brief)
    
    # Remove CTA from scene 3
    script.av_table[2].scene_name = "Scene 3: Random Conclusion"
    script.av_table[2].spoken_audio = "And that was everything about our daily routine. The end."
    
    ok, violations = DeterministicScriptValidator.validate_blueprint(script)
    assert ok is False
    assert any("Final scene must provide a clear Call to Action" in v for v in violations)

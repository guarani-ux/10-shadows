import pytest
from pydantic import ValidationError
from loop_engine.herald.linguistics import AntiAILinguisticGuard
from loop_engine.herald.cinematography import CinematographyValidator
from loop_engine.herald.input_contract import ProductionConstraints
from loop_engine.herald.schema import (
    MasterAVScriptBlueprint,
    StrategicIntent,
    TechnicalScope,
    ValidatedCutDownScript,
    AVTableRow,
)


def test_anti_ai_guard_rejects_em_dashes():
    valid, violations = AntiAILinguisticGuard.validate_text("We are building this—together—for everyone.")
    assert valid is False
    assert any("Em-dash" in v for v in violations)


def test_anti_ai_guard_rejects_banned_buzzwords():
    valid, violations = AntiAILinguisticGuard.validate_text("Let us delve into this tapestry to revolutionize our work.")
    assert valid is False
    assert any("delve" in v for v in violations)
    assert any("tapestry" in v for v in violations)
    assert any("revolutionize" in v for v in violations)


def test_anti_ai_guard_passes_natural_speech():
    valid, violations = AntiAILinguisticGuard.validate_text(
        "If you thought public libraries were just quiet rooms with books, you haven't seen our morning rush. "
        "We help patrons, manage 3D printers, and keep the spaces organized."
    )
    assert valid is True
    assert len(violations) == 0


def test_cinematography_validator_rejects_vague_direction():
    valid, violations = CinematographyValidator.validate_visual_direction("Show something interesting on screen.")
    assert valid is False
    assert any("explicit camera shot size" in v for v in violations)


def test_cinematography_validator_passes_realistic_direction():
    valid, violations = CinematographyValidator.validate_visual_direction(
        "Medium Shot (50mm, f/2.8) of assistant smiling at the counter. Soft 2:1 lighting ratio."
    )
    assert valid is True
    assert len(violations) == 0


def test_master_av_script_blueprint_validation():
    row = AVTableRow(
        row_index=1,
        scene_name="Scene 1: The Hook",
        time_window="0:00 - 0:15",
        start_seconds=0.0,
        end_seconds=15.0,
        spoken_audio="Most people think library work is quiet and slow. That couldn't be further from the truth.",
        spoken_words_count=17,
        pacing_wpm=68.0,
        video_direction="Wide Shot tracking past active study pods into the main lobby. Dynamic movement on gimbal.",
    )

    blueprint = MasterAVScriptBlueprint(
        script_id="script_lib_01",
        strategic_intent=StrategicIntent(
            project_title="Day in the Life of a Library Facilitator",
            organizational_goal="Attract 25 qualified candidates for customer service positions.",
            target_audience_persona="University students and graduates looking for active community careers.",
            intended_audience_action="Visit the career portal and apply for open assistant roles.",
            core_brand_alignment="Public service accessibility and welcoming community spaces.",
            narrative_arc_type="Workplace Spotlight & Lifestyle Balance",
        ),
        technical_scope=TechnicalScope(
            target_runtime_seconds=90,
            target_runtime_formatted="1m 30s",
            target_pacing_wpm=150.0,
            total_spoken_words=225,
            actual_overall_wpm=150.0,
            production_constraints=ProductionConstraints(target_duration_seconds=90),
            modular_cutdowns=[
                ValidatedCutDownScript(
                    cutdown_id="short_01",
                    short_title="Myth Busters: Library Work",
                    target_platform="YouTube Shorts",
                    derived_from_row_indices=[1],
                    target_duration_seconds=20,
                    actual_duration_seconds=20.0,
                    standalone_hook="3 things you didn't know library assistants do before noon.",
                    spoken_audio="Most people think library work is quiet. We manage 3D printers and community workshops. Apply online today.",
                    spoken_words_count=18,
                    pacing_wpm=54.0,
                    vertical_video_direction="9:16 Vertical Framing. Wide Shot of makerspace lab.",
                    platform_cta="Click the link in bio to apply.",
                    strategic_purpose="Drive top-of-funnel recruiting awareness on mobile feeds.",
                )
            ],
        ),
        av_table=[row],
    )

    assert blueprint.script_id == "script_lib_01"
    assert len(blueprint.av_table) == 1
    assert len(blueprint.technical_scope.modular_cutdowns) == 1

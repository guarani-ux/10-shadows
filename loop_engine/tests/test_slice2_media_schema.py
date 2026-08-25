import pytest
from pydantic import ValidationError
from loop_engine.media.schema import (
    VideoDeconstructionBlueprint,
    GroundedScene,
    EpistemicBlindspot,
)


def test_schema_valid_construction():
    scene = GroundedScene(
        scene_index=1,
        time_window="0:00 - 0:30",
        start_seconds=0.0,
        end_seconds=30.0,
        duration_seconds=30.0,
        words_count=75,
        pacing_wpm=150.0,
        summary="Opening hook introducing library staff duties.",
        verbatim_anchor_quote="The role of an LEA starts off by shelving books.",
    )

    blueprint = VideoDeconstructionBlueprint(
        video_id="C31vB3Mi0i0",
        title="Day in the Life",
        channel="Calgary Public Library",
        duration_formatted="2m 31s",
        total_words=324,
        overall_wpm=128.7,
        core_subject="Workplace duties and routine of library experience assistant.",
        scenes=[scene],
        known_blindspots=[
            EpistemicBlindspot(
                time_window="0:00 - 3.8s",
                anomaly_type="VISUAL_ONLY_GAP",
                description="Intro title card with background music.",
                gap_duration_seconds=3.8,
            )
        ],
    )

    assert blueprint.video_id == "C31vB3Mi0i0"
    assert len(blueprint.scenes) == 1
    assert len(blueprint.known_blindspots) == 1


def test_schema_rejects_invalid_time_order():
    with pytest.raises(ValidationError):
        GroundedScene(
            scene_index=1,
            time_window="0:30 - 0:10",
            start_seconds=30.0,
            end_seconds=10.0,  # Invalid: end before start
            duration_seconds=-20.0,
            words_count=50,
            pacing_wpm=100.0,
            summary="Invalid scene",
            verbatim_anchor_quote="Quote text",
        )


def test_schema_rejects_empty_scenes():
    with pytest.raises(ValidationError):
        VideoDeconstructionBlueprint(
            video_id="C31vB3Mi0i0",
            title="Title",
            channel="Channel",
            duration_formatted="1m",
            total_words=10,
            overall_wpm=10.0,
            core_subject="Subject",
            scenes=[],  # Invalid: min_length=1
        )

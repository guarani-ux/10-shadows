import pytest
from loop_engine.media.semantic_chunker import SemanticChunker


def test_semantic_chunker_empty():
    chunker = SemanticChunker()
    assert chunker.chunk_transcript([]) == []


def test_semantic_chunker_multi_scene_segmentation():
    chunker = SemanticChunker(target_scene_duration=20.0, max_scene_duration=40.0)

    # Simulated 2-minute dialogue
    mock_segments = [
        {"start": 0.0, "end": 10.0, "words": 25, "text": "First we start by shelving all the books on the main floor."},
        {"start": 10.0, "end": 22.0, "words": 30, "text": "And then we move on to checking the pull lists for patrons."},
        {"start": 22.0, "end": 35.0, "words": 28, "text": "When there is an event we do the full setup in the conference room."},
        {"start": 35.0, "end": 50.0, "words": 32, "text": "Also the team environment here is super friendly and supportive."},
        {"start": 50.0, "end": 75.0, "words": 45, "text": "One of my favourite parts is the regular scheduled shifts every week."},
    ]

    scenes = chunker.chunk_transcript(mock_segments)

    # Must split into multiple coherent scenes (fixes 1-scene collapse)
    assert len(scenes) >= 3
    assert scenes[0]["scene_index"] == 1
    assert "shelving" in scenes[0]["full_dialogue"]
    assert scenes[0]["pacing_wpm"] > 0
    assert scenes[0]["duration_seconds"] > 0


def test_semantic_chunker_respects_max_duration():
    chunker = SemanticChunker(target_scene_duration=10.0, max_scene_duration=25.0)

    long_segments = [
        {"start": 0.0, "end": 15.0, "words": 40, "text": "Continuous speaking without transition words."},
        {"start": 15.0, "end": 30.0, "words": 40, "text": "Still continuous speaking continuing the thought."},
        {"start": 30.0, "end": 45.0, "words": 40, "text": "Finally wrapping up the long speech."},
    ]

    scenes = chunker.chunk_transcript(long_segments)
    assert len(scenes) >= 2
    for s in scenes:
        assert s["duration_seconds"] <= 35.0

import pytest
from pathlib import Path
from loop_engine.media.visual_extractor import EphemeralKeyframeExtractor


def test_visual_extractor_cleanup(tmp_path):
    extractor = EphemeralKeyframeExtractor(keyframes_dir=tmp_path)

    mock_scenes = [
        {"scene_index": 1, "start_seconds": 5.0, "time_window": "0:00 - 0:30"}
    ]

    # Test with real short library video
    res = extractor.extract_scene_keyframes(
        url="https://www.youtube.com/watch?v=C31vB3Mi0i0",
        video_id="C31vB3Mi0i0",
        scenes=mock_scenes,
        timeout_seconds=25.0,
    )

    # 1. Assert raw video is completely cleaned up (zero disk leak)
    temp_vids = list(tmp_path.glob("*.mp4"))
    assert len(temp_vids) == 0

    # 2. Assert keyframe was generated
    assert len(res) == 1
    if res[0].get("keyframe_path"):
        assert Path(res[0]["keyframe_path"]).exists()
        assert Path(res[0]["keyframe_path"]).suffix == ".jpg"

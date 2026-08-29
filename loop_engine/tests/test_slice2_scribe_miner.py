import pytest

from loop_engine.scribe.memory_store import ScribeMemoryStore
from loop_engine.scribe.pattern_miner import ScribePatternMiner


def test_scribe_pattern_miner(tmp_path):
    db_file = tmp_path / "test_miner.db"
    store = ScribeMemoryStore(db_path=db_file)

    vid1 = {
        "video_id": "vid_fast",
        "title": "High Velocity Video",
        "channel": "Fast Channel",
        "duration_formatted": "1m",
        "total_words": 180,
        "overall_wpm": 180.0,
        "core_subject": "Fast paced demo",
        "scenes": [
            {
                "scene_index": 1,
                "time_window": "0:00 - 0:20",
                "start_seconds": 0.0,
                "end_seconds": 20.0,
                "duration_seconds": 20.0,
                "words_count": 65,
                "pacing_wpm": 195.0,
                "summary": "Rapid intro hook",
                "verbatim_anchor_quote": "Stop wasting time.",
            }
        ],
        "known_blindspots": [
            {
                "time_window": "0:00 - 2.0s",
                "anomaly_type": "VISUAL_ONLY_GAP",
                "description": "Fast logo splash",
                "gap_duration_seconds": 2.0,
            }
        ],
    }

    vid2 = {
        "video_id": "vid_slow",
        "title": "Slow Thoughtful Video",
        "channel": "Slow Channel",
        "duration_formatted": "2m",
        "total_words": 200,
        "overall_wpm": 100.0,
        "core_subject": "Thoughtful lecture",
        "scenes": [
            {
                "scene_index": 1,
                "time_window": "0:00 - 0:40",
                "start_seconds": 0.0,
                "end_seconds": 40.0,
                "duration_seconds": 40.0,
                "words_count": 80,
                "pacing_wpm": 120.0,
                "summary": "Slow intro hook",
                "verbatim_anchor_quote": "Let us consider the nature of reality.",
            }
        ],
        "known_blindspots": [],
    }

    store.index_blueprint(vid1)
    store.index_blueprint(vid2)

    miner = ScribePatternMiner(store)

    # 1. Test Hook Velocity Rankings
    hooks = miner.extract_hook_velocity_report()
    assert len(hooks) == 2
    assert hooks[0]["video_id"] == "vid_fast"
    assert hooks[0]["hook_wpm"] == 195.0
    assert hooks[1]["video_id"] == "vid_slow"
    assert hooks[1]["hook_wpm"] == 120.0

    # 2. Test Anomaly Inventory
    anomalies = miner.extract_blindspot_inventory()
    assert anomalies["total_flagged_anomalies"] == 1
    assert anomalies["anomaly_breakdown"][0]["anomaly_type"] == "VISUAL_ONLY_GAP"

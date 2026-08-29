from pathlib import Path

import pytest

from loop_engine.scribe.memory_store import ScribeMemoryStore


def test_scribe_store_indexing_and_retrieval(tmp_path):
    db_file = tmp_path / "test_scribe.db"
    store = ScribeMemoryStore(db_path=db_file)

    blueprint = {
        "video_id": "test_vid_123",
        "title": "A Day in the Life of a Librarian",
        "channel": "Calgary Public Library",
        "duration_formatted": "2m 31s",
        "total_words": 324,
        "overall_wpm": 128.7,
        "core_subject": "Library duties overview",
        "scenes": [
            {
                "scene_index": 1,
                "time_window": "0:00 - 0:30",
                "start_seconds": 0.0,
                "end_seconds": 30.0,
                "duration_seconds": 30.0,
                "words_count": 75,
                "pacing_wpm": 150.0,
                "summary": "Morning shelving routine",
                "verbatim_anchor_quote": "The role starts by shelving books.",
            }
        ],
        "known_blindspots": [
            {
                "time_window": "0:00 - 3.8s",
                "anomaly_type": "VISUAL_ONLY_GAP",
                "description": "Silent opening title graphic.",
                "gap_duration_seconds": 3.8,
            }
        ],
    }

    # 1. Index
    vid_id = store.index_blueprint(blueprint)
    assert vid_id == "test_vid_123"

    # 2. Retrieve
    retrieved = store.get_video("test_vid_123")
    assert retrieved is not None
    assert retrieved["title"] == "A Day in the Life of a Librarian"
    assert len(retrieved["scenes"]) == 1
    assert retrieved["scenes"][0]["verbatim_anchor_quote"] == "The role starts by shelving books."
    assert len(retrieved["known_blindspots"]) == 1

    # 3. Query by channel
    channel_vids = store.query_by_channel("Calgary Public Library")
    assert len(channel_vids) == 1

    # 4. Global Stats
    stats = store.get_pacing_statistics()
    assert stats["total_indexed_videos"] == 1
    assert stats["corpus_avg_wpm"] == 128.7

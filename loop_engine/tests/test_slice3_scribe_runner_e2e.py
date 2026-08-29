from pathlib import Path

import pytest

from loop_engine.governor import Governor
from loop_engine.receipts import ReceiptStore
from loop_engine.runners.scribe_runner import ScribeDomainRunner
from loop_engine.scribe.memory_store import ScribeMemoryStore


def test_scribe_domain_runner_e2e(tmp_path):
    db_file = tmp_path / "test_scribe.db"
    store = ScribeMemoryStore(db_path=db_file)
    receipt_store = ReceiptStore(db_path=tmp_path / "test_receipts.db")

    runner = ScribeDomainRunner(memory_store=store, receipt_store=receipt_store)
    gov = Governor()

    mock_blueprint = {
        "video_id": "test_e2e_scribe",
        "title": "E2E Scribe Test Video",
        "channel": "Test Channel",
        "duration_formatted": "1m 30s",
        "total_words": 150,
        "overall_wpm": 100.0,
        "core_subject": "Scribe E2E Verification",
        "scenes": [
            {
                "scene_index": 1,
                "time_window": "0:00 - 0:30",
                "start_seconds": 0.0,
                "end_seconds": 30.0,
                "duration_seconds": 30.0,
                "words_count": 50,
                "pacing_wpm": 100.0,
                "summary": "Intro",
                "verbatim_anchor_quote": "Let us begin.",
            }
        ],
        "known_blindspots": [],
    }

    result = gov.run_loop(runner, mock_blueprint)

    assert result["status"] == "SUCCESS"
    assert result["strikes_used"] == 1
    assert result["receipt"]["status"] == "COMMITTED"
    assert Path(result["receipt"]["destination"]).exists()

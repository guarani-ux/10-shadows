import pytest
from pathlib import Path
from loop_engine.runners.media_runner import HeraldMediaRunner
from loop_engine.governor import Governor
from loop_engine.receipts import ReceiptStore


def test_herald_media_runner_e2e(tmp_path):
    db_file = tmp_path / "test_receipts.db"
    store = ReceiptStore(db_path=db_file)
    runner = HeraldMediaRunner(receipt_store=store)

    gov = Governor()

    result = gov.run_loop(runner, "https://www.youtube.com/watch?v=C31vB3Mi0i0")

    assert result["status"] == "SUCCESS"
    assert result["strikes_used"] <= 3
    assert result["receipt"]["status"] == "COMMITTED"
    assert Path(result["receipt"]["destination"]).exists()

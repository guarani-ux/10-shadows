import pytest
from pathlib import Path
from loop_engine.runners.slicer_runner import SlicerDomainRunner
from loop_engine.receipts import ReceiptStore
from loop_engine.governor import Governor


def test_slicer_domain_runner_e2e(tmp_path):
    receipt_store = ReceiptStore(db_path=tmp_path / "test_receipts.db")
    runner = SlicerDomainRunner(receipt_store=receipt_store)
    gov = Governor(max_strikes=3)

    payload = {
        "goal_id": "goal_distributed_lock",
        "goal_description": "Implement Redis-backed distributed mutex",
        "base_package_name": "dist_lock",
    }

    result = gov.run_loop(runner, payload)

    assert result["status"] == "SUCCESS"
    assert result["strikes_used"] == 1
    assert result["receipt"]["status"] == "COMMITTED"
    assert Path(result["receipt"]["destination"]).exists()

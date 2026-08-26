import pytest
from pathlib import Path
from loop_engine.runners.alchemist_runner import AlchemistDomainRunner
from loop_engine.receipts import ReceiptStore
from loop_engine.governor import Governor


def test_alchemist_domain_runner_e2e(tmp_path):
    receipt_store = ReceiptStore(db_path=tmp_path / "test_receipts.db")
    runner = AlchemistDomainRunner(receipt_store=receipt_store)
    gov = Governor(max_strikes=3)

    sample_crash = """
Traceback (most recent call last):
  File "math_server.py", line 22, in calculate_average
    avg = total / count
ZeroDivisionError: division by zero
"""

    result = gov.run_loop(runner, sample_crash)

    assert result["status"] == "SUCCESS"
    assert result["strikes_used"] == 1
    assert result["receipt"]["status"] == "COMMITTED"
    assert Path(result["receipt"]["destination"]).exists()

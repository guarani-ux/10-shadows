import pytest
from pathlib import Path
from loop_engine.runners.forge_runner import ForgeDomainRunner
from loop_engine.runners.svris_runner import SvrisDomainRunner
from loop_engine.governor import Governor
from loop_engine.receipts import ReceiptStore


def test_forge_domain_runner_success(tmp_path):
    db_file = tmp_path / "test_receipts.db"
    store = ReceiptStore(db_path=db_file)
    runner = ForgeDomainRunner(receipt_store=store)

    payload = {
        "request_id": "forge_unit_01",
        "target_filename": "calculator.py",
        "code": "def add(a, b):\n    return a + b\n",
    }

    gov = Governor()
    result = gov.run_loop(runner, payload)

    assert result["status"] == "SUCCESS"
    assert result["strikes_used"] == 1
    assert result["receipt"]["receipt_id"] == 1


def test_svris_domain_runner_verification(tmp_path):
    db_file = tmp_path / "test_receipts.db"
    store = ReceiptStore(db_path=db_file)
    runner = SvrisDomainRunner(receipt_store=store)

    safe_payload = {
        "task_id": "svris_audit_01",
        "content": "def clean_calc():\n    return 100\n",
    }

    gov = Governor()
    result = gov.run_loop(runner, safe_payload)

    assert result["status"] == "SUCCESS"
    assert result["receipt"]["status"] == "VERIFIED"
    assert len(result["receipt"]["sha256"]) == 64


def test_svris_domain_runner_catches_unsafe_code(tmp_path):
    db_file = tmp_path / "test_receipts.db"
    store = ReceiptStore(db_path=db_file)
    runner = SvrisDomainRunner(receipt_store=store)

    unsafe_payload = {
        "task_id": "svris_audit_unsafe",
        "content": "import os\nos.system('calc')\n",
    }

    gov = Governor()
    result = gov.run_loop(runner, unsafe_payload)

    assert result["status"] == "ABORTED"
    assert result["strikes_exhausted"] == 3
    assert any("Banned execution call 'os.system()'" in entry["error"] for entry in result["negative_constraints_ledger"])

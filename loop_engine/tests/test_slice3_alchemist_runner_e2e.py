import pytest
import tempfile
from pathlib import Path
from loop_engine.runners.alchemist_runner import RealAlchemistSelfHealingEngine
from loop_engine.governor import Governor
from loop_engine.receipts import ReceiptStore


def test_alchemist_self_healing_successful_repair(tmp_path):
    """Proves that Alchemist patches broken file, runs test, and promotes on success."""
    db_file = tmp_path / "test_receipts.db"
    store = ReceiptStore(db_path=db_file)
    runner = RealAlchemistSelfHealingEngine(receipt_store=store)

    # 1. Create a broken target source file with a zero division bug
    source_file = tmp_path / "math_module.py"
    source_file.write_text(
        "def compute_average(total, count):\n"
        "    return total / count\n",
        encoding="utf-8",
    )

    # 2. Create a test file verifying safe handling of count=0
    test_file = tmp_path / "test_math.py"
    test_file.write_text(
        f"import sys\n"
        f"sys.path.insert(0, r'{tmp_path}')\n"
        f"from math_module import compute_average\n\n"
        f"def test_compute_average_safe():\n"
        f"    res = compute_average(100, 0)\n"
        f"    assert res == 0.0\n",
        encoding="utf-8",
    )

    # 3. Simulated crash trace
    crash_trace = (
        f'Traceback (most recent call last):\n'
        f'  File "{source_file}", line 2, in compute_average\n'
        f'    return total / count\n'
        f'ZeroDivisionError: division by zero\n'
    )

    input_payload = {
        "task_id": "heal_zero_div_01",
        "raw_trace": crash_trace,
        "source_file": str(source_file.as_posix()),
        "target_test_file": str(test_file.as_posix()),
    }

    gov = Governor()
    result = gov.run_loop(runner, input_payload)

    assert result["status"] == "SUCCESS"
    assert result["receipt"]["status"] == "COMMITTED"
    
    # Verify file on disk was physically modified and fixed
    repaired_code = source_file.read_text(encoding="utf-8")
    assert "return total / count if count != 0 else 0.0" in repaired_code


def test_alchemist_self_healing_failed_repair_rollback(tmp_path):
    """Proves that Alchemist rolls back original source file if test fails after patching."""
    db_file = tmp_path / "test_receipts.db"
    store = ReceiptStore(db_path=db_file)
    runner = RealAlchemistSelfHealingEngine(receipt_store=store)

    original_code = (
        "def compute_data(payload):\n"
        "    return payload['missing_key']\n"
    )
    source_file = tmp_path / "data_module.py"
    source_file.write_text(original_code, encoding="utf-8")

    # Create an intentionally impossible test that demands a non-existent behavior
    test_file = tmp_path / "test_data.py"
    test_file.write_text(
        f"import sys\n"
        f"sys.path.insert(0, r'{tmp_path}')\n"
        f"from data_module import compute_data\n\n"
        f"def test_impossible_assertion():\n"
        f"    assert compute_data({{}}) == 'IMPOSSIBLE_VALUE'\n",
        encoding="utf-8",
    )

    crash_trace = (
        f'Traceback (most recent call last):\n'
        f'  File "{source_file}", line 2, in compute_data\n'
        f'    return payload[\'missing_key\']\n'
        f'KeyError: \'missing_key\'\n'
    )

    input_payload = {
        "task_id": "heal_failed_rollback",
        "raw_trace": crash_trace,
        "source_file": str(source_file.as_posix()),
        "target_test_file": str(test_file.as_posix()),
    }

    # Use strike_ceiling=1 via GovernanceConfig for fast deterministic failure test
    from loop_engine.governance import load_canonical_governance
    custom_gov = load_canonical_governance().model_copy(deep=True)
    custom_gov.governor.strike_ceiling = 1
    gov = Governor(governance_config=custom_gov)
    result = gov.run_loop(runner, input_payload)


    # Governor should abort
    assert result["status"] == "ABORTED"
    assert result["strikes_exhausted"] == 1

    # CRITICAL: Verify source code was rolled back to original pristine state
    current_code = source_file.read_text(encoding="utf-8")
    assert current_code == original_code

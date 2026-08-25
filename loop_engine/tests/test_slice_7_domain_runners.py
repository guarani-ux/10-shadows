import pytest
from pathlib import Path
from loop_engine.runners.code_runner import CodeRunnerLoop
from loop_engine.governor import Governor
from loop_engine.receipts import ReceiptStore


def test_code_runner_end_to_end_success(tmp_path):
    db_file = tmp_path / "receipts.db"
    store = ReceiptStore(db_path=db_file)
    runner = CodeRunnerLoop(receipt_store=store)

    dest_file = tmp_path / "output_tool.py"

    payload = {
        "task_id": "forge_task_01",
        "target_filename": "output_tool.py",
        "destination_path": str(dest_file),
        "code": "```python\ndef compute_answer():\n    return 42\n```",
    }

    gov = Governor(max_strikes=3)
    result = gov.run_loop(runner, payload)

    assert result["status"] == "SUCCESS"
    assert result["strikes_used"] == 1
    assert dest_file.exists()
    assert "def compute_answer():" in dest_file.read_text(encoding="utf-8")
    assert result["receipt"]["receipt_id"] == 1


def test_code_runner_rejects_ast_violation(tmp_path):
    db_file = tmp_path / "receipts.db"
    store = ReceiptStore(db_path=db_file)
    runner = CodeRunnerLoop(receipt_store=store)

    dest_file = tmp_path / "unsafe_tool.py"

    payload = {
        "task_id": "forge_task_unsafe",
        "target_filename": "unsafe_tool.py",
        "destination_path": str(dest_file),
        "code": "```python\nimport os\nos.system('whoami')\n```",
    }

    gov = Governor(max_strikes=3)
    result = gov.run_loop(runner, payload)

    # Must fail 3 strikes due to hard AST ban and abort
    assert result["status"] == "ABORTED"
    assert result["strikes_exhausted"] == 3
    assert not dest_file.exists()
    assert any("Banned execution call 'os.system()'" in item["error"] for item in result["negative_constraints_ledger"])


def test_code_runner_with_subprocess_test_gate(tmp_path):
    db_file = tmp_path / "receipts.db"
    store = ReceiptStore(db_path=db_file)
    runner = CodeRunnerLoop(receipt_store=store)

    # Create a pytest file that verifies the tool
    test_file = tmp_path / "test_tool.py"
    test_file.write_text("""
def test_tool():
    assert 2 * 2 == 4
""", encoding="utf-8")

    dest_file = tmp_path / "validated_tool.py"

    payload = {
        "task_id": "forge_task_with_tests",
        "target_filename": "validated_tool.py",
        "destination_path": str(dest_file),
        "test_file": str(test_file),
        "code": "def run():\n    return True\n",
    }

    gov = Governor(max_strikes=3)
    result = gov.run_loop(runner, payload)

    assert result["status"] == "SUCCESS"
    assert dest_file.exists()

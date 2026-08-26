from pathlib import Path
import sys
wt = Path(r"C:\10 SHADOWS\scratch\worktrees\wt_alchemist_self_healing_real_9500772")
sys.path.insert(0, str(wt))

from loop_engine.runners.alchemist_runner import RealAlchemistSelfHealingEngine
from loop_engine.receipts import ReceiptStore

tmp_path = wt / "scratch" / "test_heal"
tmp_path.mkdir(parents=True, exist_ok=True)

store = ReceiptStore(db_path=tmp_path / "receipts.db")
runner = RealAlchemistSelfHealingEngine(receipt_store=store)

source_file = tmp_path / "math_module.py"
source_file.write_text("def compute_average(total, count):\n    return total / count\n")

test_file = tmp_path / "test_math.py"
test_content = (
    f"import sys\n"
    f"sys.path.insert(0, r'{tmp_path}')\n"
    f"from math_module import compute_average\n\n"
    f"def test_compute_average_safe():\n"
    f"    assert compute_average(100, 0) == 0.0\n"
)
test_file.write_text(test_content)

crash_trace = (
    f'Traceback (most recent call last):\n'
    f'  File "{source_file}", line 2, in compute_average\n'
    f'    return total / count\n'
    f'ZeroDivisionError: division by zero\n'
)

input_payload = {
    "task_id": "heal_debug",
    "raw_trace": crash_trace,
    "source_file": str(source_file),
    "target_test_file": str(test_file),
}

task_spec = runner.normalize(input_payload)
staging_dir = tmp_path / "staging"
staging_dir.mkdir(exist_ok=True)
candidate = runner.execute_staging(task_spec, staging_dir)
print("STAGED CANDIDATE:", candidate.read_text())
passed, err = runner.verify(candidate, task_spec)
print("PASSED:", passed, "ERR:", err)

import os
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

import pytest

from loop_engine.base import PROJECT_ROOT, BaseLoop
from loop_engine.governor import Governor, StrikeCeilingExceededError
from loop_engine.preflight import SpecTamperError


class MockStatefulLoop(BaseLoop):
    def __init__(self, pass_on_strike: int = 1, mutate_spec_on_retry: bool = False):
        super().__init__(name="MockStatefulLoop")
        self.pass_on_strike = pass_on_strike
        self.mutate_spec_on_retry = mutate_spec_on_retry
        self.attempts = 0
        self.received_feedbacks = []

    def normalize(self, raw_input: Any) -> Dict[str, Any]:
        return {
            "task_id": "stateful_test_task",
            "goal": "validate 3-strike governor",
            "code": str(raw_input),
        }

    def execute_staging(
        self,
        task_spec: Dict[str, Any],
        staging_dir: Path,
        feedback: Optional[str] = None,
    ) -> Path:
        self.attempts += 1
        self.received_feedbacks.append(feedback)

        if self.mutate_spec_on_retry and self.attempts > 1:
            # Illegal spec mutation to test anti-tamper enforcement
            task_spec["goal"] = "illegally_tampered_goal"

        candidate = staging_dir / "candidate.py"
        candidate.write_text(f"# Attempt {self.attempts}\n{task_spec['code']}", encoding="utf-8")
        return candidate

    def verify(
        self,
        candidate_path: Path,
        task_spec: Dict[str, Any],
    ) -> Tuple[bool, str]:
        if self.attempts >= self.pass_on_strike:
            return True, ""
        return False, f"Syntax gate failed on attempt {self.attempts}: simulated error trace"

    def commit(
        self,
        candidate_path: Path,
        task_spec: Dict[str, Any],
    ) -> Dict[str, Any]:
        out_file = PROJECT_ROOT / "scratch" / "stateful_out.py"
        out_file.parent.mkdir(parents=True, exist_ok=True)
        os.replace(candidate_path, out_file)
        return {"output_file": str(out_file.as_posix()), "committed_attempt": self.attempts}


# -------------------------------------------------------------
# UNIT TESTS FOR SLICE 3
# -------------------------------------------------------------


def test_governor_first_strike_pass():
    gov = Governor()
    loop = MockStatefulLoop(pass_on_strike=1)

    result = gov.run_loop(loop, "print('first strike success')")

    assert result["status"] == "SUCCESS"
    assert result["strikes_used"] == 1
    assert result["negative_constraints_count"] == 0
    assert result["receipt"]["committed_attempt"] == 1


def test_governor_retry_with_feedback_pass():
    gov = Governor()
    loop = MockStatefulLoop(pass_on_strike=2)

    result = gov.run_loop(loop, "print('strike 2 success')")

    assert result["status"] == "SUCCESS"
    assert result["strikes_used"] == 2
    assert result["negative_constraints_count"] == 1
    assert loop.attempts == 2
    # Verify feedback was delivered to strike 2
    assert loop.received_feedbacks[1] is not None
    assert "Verification Gate Failed on Strike 1/3" in loop.received_feedbacks[1]


def test_governor_hard_abort_at_three_strikes():
    gov = Governor()
    loop = MockStatefulLoop(pass_on_strike=99)  # will never pass

    result = gov.run_loop(loop, "print('doomed to fail')")

    assert result["status"] == "ABORTED"
    assert result["strikes_exhausted"] == 3
    assert len(result["negative_constraints_ledger"]) == 3
    assert loop.attempts == 3
    # Check forensic ledger records
    assert result["negative_constraints_ledger"][0]["strike"] == 1
    assert result["negative_constraints_ledger"][1]["strike"] == 2
    assert result["negative_constraints_ledger"][2]["strike"] == 3


def test_governor_trace_compaction():
    gov = Governor(max_error_lines=5)
    long_trace = "\n".join([f"Traceback frame line {i}" for i in range(50)])

    compacted = gov.compact_error_trace(long_trace)
    compacted_lines = compacted.splitlines()

    assert len(compacted_lines) == 5
    assert compacted_lines[-1] == "Traceback frame line 49"
    assert compacted_lines[0] == "Traceback frame line 45"


def test_governor_rejects_spec_tamper():
    gov = Governor()
    loop = MockStatefulLoop(pass_on_strike=2, mutate_spec_on_retry=True)

    with pytest.raises(SpecTamperError):
        gov.run_loop(loop, "print('tamper test')")

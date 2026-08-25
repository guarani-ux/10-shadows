# Current Mission: Slice 3 — 3-Strike Governor & Anti-Oscillation Memory

## Objective
Implement `loop_engine/governor.py` and `loop_engine/tests/test_slice_3_retry_and_abort.py`.

## Invariants & Requirements
1. **Bounded Loop:** `max_strikes = 3` ceiling.
2. **Anti-Oscillation Ledger:** Accumulate structured negative constraints (`negative_constraints_ledger`) containing previous strike error signatures and root causes.
3. **Trace Compaction:** Compact stdout/stderr feedback to <= 30 lines.
4. **Hard Abort:** Emit forensic crash receipt on 3rd failure.
5. **Atomic Commit:** Preserve staging isolation and atomic replacements.
